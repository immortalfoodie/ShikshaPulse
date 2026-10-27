"""Analytics against ground truth, the Evidence Guard, the fallback engine and the LLM tool loop."""
import json
from types import SimpleNamespace

from app.ai.evidence import EvidenceStore
from app.ai.guard import check, soften
from app.auth import persona


def test_diagnosis_finds_planted_signals(warehouse):
    from app.analytics.diagnose import diagnose
    exp = warehouse["expected"]["blocks"]
    hits = total = 0
    for block, e in exp.items():
        d = diagnose("block", block)
        flagged = {s["factor"] for s in d["signals"] if s["classification"] in ("HIGH", "MEDIUM")}
        for f in e["expected_signals"]:
            total += 1
            hits += f in flagged
        if e["status"] == "insufficient":
            assert d["verdict"] == "INSUFFICIENT_EVIDENCE"
        if e["status"] == "non_comparable":
            assert d["verdict"] == "NON_COMPARABLE"
    assert total == 0 or hits / total >= 0.8


def test_model_has_no_outcome_leakage(warehouse):
    from app.analytics import expected as ex
    assert not set(ex.FEATURES) & ex.OUTCOME_COLUMNS
    assert ex.model_card()["r2_heldout"] > 0.3


def test_peer_election_filter(warehouse):
    from app.analytics.peers import ELECTION_DAYS, peers
    for b in warehouse["expected"]["election_affected_blocks"]:
        p = peers(b, election_only=True, other_districts=False)
        assert all(x["teacher_days_lost"] >= ELECTION_DAYS for x in p["peers"])


def test_guard_rejects_invented_number_and_softens_causal_language():
    s = EvidenceStore()
    e = s.add("outcome", "Numeracy change", {"change_pp": -6.7, "baseline": 61.3}, "2022-23 → 2024-25")
    ans = {"summary": "Numeracy fell 6.7 pp, caused by vacancies; 42.4% of schools hit.",
           "findings": [{"label": "observed_fact", "text": "Fell from 61.3%.", "evidence": [e]}]}
    rep = check(ans, s)
    assert not rep["passed"]
    assert any(u["value"] == "42.4" for u in rep["unverified_numbers"])
    assert "caused" not in ans["summary"]
    assert ans["findings"][0]["period"] == "2022-23 → 2024-25"


def test_guard_requires_citations_and_adds_unresolved():
    s = EvidenceStore()
    s.add("unresolved", "Open", {"text": "Kerwa: 15.2 pp unexplained"}, "p", ev_type="unresolved_question")
    ans = {"summary": "ok", "findings": [{"label": "observed_fact", "text": "x", "evidence": []}]}
    rep = check(ans, s)
    assert rep["citation_errors"]
    assert rep["unresolved_added"] == 1


def test_hindi_causal_softening():
    text, n = soften("गिरावट शिक्षक रिक्ति के कारण हुई")
    assert n == 1 and "के कारण" not in text


def test_fallback_answers_are_grounded(warehouse):
    from app.ai.assistant import ask
    user = persona("state-spd")
    for q in ["Why did numeracy fall?", "Which blocks had the largest decline?", "How reliable is the data?"]:
        r = ask(q, user, "en", force_fallback=True)
        assert r["guard"]["passed"], (q, r["guard"])
        assert r["answer"]["findings"]
    r = ask("संख्या ज्ञान क्यों गिरा?", user, "hi", force_fallback=True)
    assert r["guard"]["passed"]


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def test_llm_tool_loop_with_scripted_model(warehouse, monkeypatch):
    """A scripted model: calls diagnose, then first answers with an invented number (guard must
    reject it), then answers correctly on the retry."""
    from app.ai import assistant
    from app.ai.llm import LLMClient
    client = LLMClient()
    client.api_key, client.disabled = "test", False
    calls = {"n": 0}

    def fake_chat(messages, tools=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            tc = SimpleNamespace(id="c1", function=SimpleNamespace(name="diagnose",
                                                                  arguments=json.dumps({"unit_type": "state"})))
            return _msg(tool_calls=[tc])
        tool_msg = next(m for m in messages if m.get("role") == "tool")
        out = json.loads(tool_msg["content"])
        ev, ch = out["outcome"]["evidence"], out["outcome"]["change_pp"]
        if calls["n"] == 2:
            return _msg(json.dumps({"summary": f"Changed {ch} pp; 99.9% affected.",
                                    "findings": [{"label": "observed_fact", "text": f"{ch} pp", "evidence": [ev]}]}))
        return _msg(json.dumps({"summary": f"Numeracy changed by {ch} pp.",
                                "findings": [{"label": "observed_fact", "text": f"Change of {ch} pp.",
                                              "evidence": [ev]}], "next_steps": []}))

    monkeypatch.setattr(client, "chat", fake_chat)
    monkeypatch.setattr(assistant, "llm", lambda: client)
    r = assistant.ask("Why did numeracy change?", persona("state-spd"), "en")
    assert r["engine"] == "llm"
    assert r["attempts"] == 2
    assert r["guard"]["passed"]


def test_fallback_grounded_in_all_languages(warehouse):
    from app.ai.assistant import ask
    from app.ai.phrases import LANGS
    user = persona("state-spd")
    for lang in LANGS:
        for q in ["Why did numeracy fall?", "How reliable is the data?", "Which schools have both attendance decline "
                  "and maths vacancies?"]:
            r = ask(q, user, lang, force_fallback=True)
            assert r["guard"]["passed"], (lang, q, r["guard"]["unverified_numbers"], r["guard"]["citation_errors"])
            assert r["lang"] == lang


def test_school_level_answer(warehouse):
    from app import db
    from app.ai.assistant import ask
    code = db.query("SELECT udise_code FROM schools LIMIT 1")[0]["udise_code"]
    user = {**persona("state-spd"), "role": "headmaster", "scope_type": "school", "scope": code}
    for lang in ("en", "hi", "ta"):
        r = ask("How is my school doing?", user, lang, force_fallback=True)
        assert r["guard"]["passed"], (lang, r["guard"])
        assert r["tool_calls"][0]["tool"] == "get_school"
