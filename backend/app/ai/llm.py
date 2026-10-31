"""Provider-agnostic LLM client over the OpenAI-compatible API (Gemini / Groq / Ollama).

If no key is configured, or a call fails, callers fall back to deterministic logic, so the
platform never depends on the LLM being reachable.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time

_PROVIDER_DEFAULTS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
}


# Errors worth retrying on another key: rate limit / quota (429), bad or revoked key (401/403),
# and provider overload (5xx). Anything else (bad request, timeout) would fail the same way again.
_SWITCH_STATUS = {401, 403, 429, 500, 502, 503, 504}
_COOLDOWN_S = {429: 60, 401: 600, 403: 600}  # how long to skip a key after it failed (default 20 s)


def _status_of(e: Exception) -> int | None:
    code = getattr(e, "status_code", None)
    if code is None and getattr(e, "response", None) is not None:
        code = getattr(e.response, "status_code", None)
    if code is None and "RateLimit" in type(e).__name__:
        code = 429
    return code


class LLMClient:
    """Tries the primary key first. If it is rate-limited, over quota, rejected or the provider is
    overloaded, the same request is retried on the fallback key (LLM_API_KEY_FALLBACK). A key
    that failed is rested for a cooldown, so later calls go straight to the healthy key."""

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        base, model = _PROVIDER_DEFAULTS.get(self.provider, _PROVIDER_DEFAULTS["gemini"])
        self.base_url = os.getenv("LLM_BASE_URL") or base
        self.model = os.getenv("LLM_MODEL") or model
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.fallback_key = os.getenv("LLM_API_KEY_FALLBACK", "").strip()
        self.disabled = os.getenv("LLM_DISABLED", "").lower() in ("1", "true", "yes")
        self.stats = {
            "calls": 0,
            "errors": 0,
            "last_error": None,
            "last_latency_ms": None,
            "key_switches": 0,
            "active_key": "primary",
        }
        self._clients: dict[tuple[str, float | None, int], object] = {}
        self._rest_until: dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def keys(self) -> list[tuple[str, str]]:
        out = [("primary", self.api_key)] if self.api_key else []
        if self.fallback_key and self.fallback_key != self.api_key:
            out.append(("fallback", self.fallback_key))
        return out

    @property
    def available(self) -> bool:
        return bool(self.keys) and not self.disabled

    def status(self) -> dict:
        # never include the keys themselves
        return {
            "provider": self.provider,
            "model": self.model,
            "available": self.available,
            "mode": "live" if self.available else "deterministic-fallback",
            "keys_configured": len(self.keys),
            **self.stats,
        }

    def _order(self) -> list[tuple[str, str]]:
        """Healthy keys first (in configured order), then rested ones as a last resort."""
        now = time.time()
        ks = self.keys
        healthy = [k for k in ks if self._rest_until.get(k[0], 0) <= now]
        return healthy + [k for k in ks if k not in healthy]

    def _get(self, key: str, timeout: float | None = None, retries: int = 2):
        ck = (key, timeout, retries)
        if ck not in self._clients:
            from openai import OpenAI

            self._clients[ck] = OpenAI(base_url=self.base_url, api_key=key, timeout=timeout or 45, max_retries=retries)
        return self._clients[ck]

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        json_mode: bool = False,
        timeout: float | None = None,
    ):
        """Returns the assistant message object, or raises on failure (after trying every key)."""
        if not self.available:
            raise RuntimeError("LLM not configured")
        kw: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = "auto"
        if json_mode and not tools:
            kw["response_format"] = {"type": "json_object"}
        t0 = time.time()
        with self._lock:
            self.stats["calls"] += 1
        order = self._order()
        last_exc: Exception | None = None
        for i, (name, key) in enumerate(order):
            is_last = i == len(order) - 1
            # with another key waiting, fail fast instead of sitting in SDK back-off on a rate-limited key
            retries = (1 if timeout is not None else 2) if is_last else 0
            client = self._get(key, timeout, retries)
            try:
                resp = self._create(client, kw)
            except Exception as e:
                last_exc = e
                code = _status_of(e)
                if code in _SWITCH_STATUS and not is_last:
                    self._rest_until[name] = time.time() + _COOLDOWN_S.get(code, 20)
                    with self._lock:
                        self.stats["key_switches"] += 1
                        self.stats["last_error"] = f"{name} key: HTTP {code}; switched to next key"
                    continue
                self._fail(e)
                raise
            self._rest_until.pop(name, None)
            self.stats["active_key"] = name
            self.stats["last_latency_ms"] = int((time.time() - t0) * 1000)
            return resp.choices[0].message
        raise last_exc or RuntimeError("no LLM key available")

    @staticmethod
    def _create(client, kw: dict):
        try:
            return client.chat.completions.create(**kw)
        except Exception as e:
            # some OpenAI-compatible endpoints reject response_format: retry once without it
            if "response_format" in kw and _status_of(e) not in _SWITCH_STATUS:
                return client.chat.completions.create(**{k: v for k, v in kw.items() if k != "response_format"})
            raise

    def complete_json(self, system: str, user: str, timeout: float | None = None) -> dict:
        msg = self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}], json_mode=True, timeout=timeout
        )
        return parse_json(msg.content or "")

    def _fail(self, e: Exception) -> None:
        with self._lock:
            self.stats["errors"] += 1
            self.stats["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"


def parse_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


_llm: LLMClient | None = None


def llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def reset_llm() -> None:
    global _llm
    _llm = None
