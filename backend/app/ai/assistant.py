"""Ask ShikshaPulse — tool-calling assistant with the Evidence Guard and deterministic fallback.

Flow: question → LLM picks safe analytics tools (bounded steps) → tool results registered as
evidence → LLM writes a structured, cited answer → guard checks numbers, citations, labels and
causal wording → one regeneration with the guard's feedback if needed → deterministic fallback.
"""
from __future__ import annotations

import json
import time

from .evidence import EvidenceStore
from .guard import check
from .llm import llm, parse_json
from .phrases import LANG_NAMES, LANGS
from .templates import compose, extract_unit, route
from .tools import TOOL_SPECS, run_tool

MAX_STEPS = 4
TIME_BUDGET_S = 35.0   # total wait for the live model before the offline engine answers
CALL_TIMEOUT_S = 20.0

SYSTEM = """You are ShikshaPulse, a decision-support assistant for Indian district and block education officers.
You answer ONLY from the analytics tools provided. Never invent numbers, schools or events.

Rules:
- Call tools to get evidence first. Each tool result contains evidence ids like "E3".
- Present findings as one of: observed_fact (a measured value), associated_signal (an indicator that changed
  alongside the outcome — association, NOT cause), unresolved_question (insufficient, conflicting or unexplained).
- Never say an indicator "caused", "led to", or that something happened "due to"/"because of" it. Say
  "coincided with" or "is associated with".
- If the evidence is insufficient or conflicting, say so plainly instead of explaining it away.
- Copy numbers exactly as they appear in tool results (you may round to one decimal).
- Be concise and practical: an officer must be able to act on it.
- The officer's scope is: {scope}. Default to this unit when the question does not name one.

Final answer: reply with ONLY a JSON object:
{{"summary": "2-3 sentences", "findings": [{{"label": "observed_fact|associated_signal|unresolved_question",
"text": "...", "evidence": ["E1"], "period": "2022-23 → 2024-25"}}], "next_steps": ["..."]}}
{lang_rule}"""

def lang_rule(lang: str) -> str:
    if lang == "en":
        return "Write in clear, simple English that a village teacher can follow."
    return (f"Write the summary, findings and next_steps in simple {LANG_NAMES[lang]} (native script), in words a "
            "village teacher understands. Keep numbers (Western digits), evidence ids, school codes and block/district "
            "names unchanged.")


def ask(question: str, user: dict, lang: str = "en", force_fallback: bool = False) -> dict:
    t0 = time.time()
    lang = lang if lang in LANGS else "en"
    client = llm()
    if client.available and not force_fallback:
        try:
            res = _ask_llm(question, user, lang)
            if res is not None:
                res["latency_ms"] = int((time.time() - t0) * 1000)
                return res
        except Exception as e:  # noqa: BLE001
            client._fail(e)
    res = _ask_fallback(question, user, lang)
    res["latency_ms"] = int((time.time() - t0) * 1000)
    if client.available and not force_fallback:
        res["engine_note"] = "The LLM was unavailable or failed verification; answered by the deterministic engine."
    return res


def _scope_text(user: dict) -> str:
    if user["scope_type"] == "state":
        return "the whole state"
    return f"{user['scope_type']} {user['scope']} ({user['title']})"


def _ask_llm(question: str, user: dict, lang: str) -> dict | None:
    client = llm()
    started = time.time()

    def budget() -> float:
        left = TIME_BUDGET_S - (time.time() - started)
        if left < 4:
            raise TimeoutError("LLM time budget used up")
        return min(CALL_TIMEOUT_S, left)

    store = EvidenceStore()
    calls_log = []
    messages = [{"role": "system", "content": SYSTEM.format(scope=_scope_text(user), lang_rule=lang_rule(lang))},
                {"role": "user", "content": question}]
    final_text = None
    for _ in range(MAX_STEPS):
        msg = client.chat(messages, tools=TOOL_SPECS, timeout=budget())
        tool_calls = getattr(msg, "tool_calls", None) or []
        if not tool_calls:
            final_text = msg.content or ""
            break
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name,
                                                      "arguments": tc.function.arguments or "{}"}}
                                        for tc in tool_calls]})
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = run_tool(tc.function.name, args, store, user)
            calls_log.append({"tool": tc.function.name, "args": args, "ok": "error" not in result})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)[:12000]})
    if not store.items:
        # The model answered without evidence — not acceptable; let the fallback answer.
        return None
    if final_text is None:
        messages.append({"role": "user", "content": "Now write the final JSON answer."})
        final_text = client.chat(messages, timeout=budget()).content or ""
    attempts = []
    for attempt in range(2):
        try:
            answer = parse_json(final_text)
        except Exception:  # noqa: BLE001
            answer = {"summary": "", "findings": [], "next_steps": []}
        report = check(answer, store, question)
        attempts.append(report)
        if report["passed"] and answer.get("findings"):
            return _package(question, answer, report, store, calls_log, "llm", lang, attempts)
        if attempt == 0:
            feedback = {"unverified_numbers": report["unverified_numbers"],
                        "citation_errors": report["citation_errors"],
                        "instruction": "Fix these problems. Use only numbers present in tool results and cite valid "
                                       "evidence ids for every finding. Reply with the JSON object only."}
            messages.append({"role": "assistant", "content": final_text})
            messages.append({"role": "user", "content": json.dumps(feedback)})
            final_text = client.chat(messages, timeout=budget()).content or ""
    return None


def _ask_fallback(question: str, user: dict, lang: str) -> dict:
    store = EvidenceStore()
    results, calls_log = [], []
    for name, args in route(question, user):
        r = run_tool(name, args, store, user)
        results.append((name, args, r))
        calls_log.append({"tool": name, "args": args, "ok": "error" not in r})
    answer = compose(results, lang)
    report = check(answer, store, question)
    return _package(question, answer, report, store, calls_log, "deterministic", lang, [report])


def _package(question, answer, report, store, calls, engine, lang, attempts) -> dict:
    return {"question": question, "lang": lang, "engine": engine, "answer": answer, "guard": report,
            "attempts": len(attempts), "tool_calls": calls, "evidence": store.public(),
            "llm": llm().status()}


def detect_unit(question: str, user: dict) -> dict:
    ut, u = extract_unit(question, user)
    return {"unit_type": ut, "unit": u}
