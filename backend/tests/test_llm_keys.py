"""Primary -> fallback API key rotation (no network: fake clients)."""
from types import SimpleNamespace

import pytest


class _RateLimited(Exception):
    status_code = 429


class _BadRequest(Exception):
    status_code = 400


def _client_with(behaviour, monkeypatch):
    from app.ai.llm import LLMClient
    c = LLMClient()
    c.api_key, c.fallback_key, c.disabled = "key-A", "key-B", False
    used = []

    def fake_get(key, timeout=None, retries=2):
        def create(**kw):
            used.append((key, retries))
            err = behaviour.get(key)
            if err:
                raise err()
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=key, tool_calls=None))])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(c, "_get", fake_get)
    return c, used


def test_rate_limited_primary_switches_to_fallback_and_rests(monkeypatch):
    c, used = _client_with({"key-A": _RateLimited}, monkeypatch)
    assert c.chat([{"role": "user", "content": "hi"}]).content == "key-B"
    assert used == [("key-A", 0), ("key-B", 2)]  # no SDK back-off on the rate-limited key
    assert c.status()["active_key"] == "fallback" and c.status()["key_switches"] == 1
    used.clear()
    c.chat([{"role": "user", "content": "again"}])
    assert used[0][0] == "key-B"  # primary is resting during its cooldown
    assert "key-A" not in str(c.status()) and "key-B" not in str(c.status())  # keys never exposed


def test_non_retryable_error_does_not_switch(monkeypatch):
    c, used = _client_with({"key-A": _BadRequest}, monkeypatch)
    with pytest.raises(_BadRequest):
        c.chat([{"role": "user", "content": "hi"}])
    assert [k for k, _ in used] == ["key-A"]


def test_both_keys_limited_raises_so_offline_engine_answers(monkeypatch):
    c, _ = _client_with({"key-A": _RateLimited, "key-B": _RateLimited}, monkeypatch)
    with pytest.raises(_RateLimited):
        c.chat([{"role": "user", "content": "hi"}])
    assert c.stats["errors"] == 1


def test_single_key_still_works(monkeypatch):
    c, used = _client_with({}, monkeypatch)
    c.fallback_key = ""
    assert c.chat([{"role": "user", "content": "hi"}]).content == "key-A" and c.status()["keys_configured"] == 1
