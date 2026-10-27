"""Early warning, CRC school visits, teacher-sharing suggestions and track records."""
from app.auth import persona


def test_early_warning_flags_planted_attendance_drop(warehouse):
    from app.analytics.early_warning import early_warning
    exp = warehouse["expected"]["blocks"]
    w = early_warning("state", None)
    flagged = {a["block"] for a in w["alerts"] if a["kind"] == "attendance_drop"}
    planted = {b for b, e in exp.items() if "attendance_decline" in e["effects"]}
    assert planted, "scenario should contain an attendance decline"
    assert planted & flagged, (planted, flagged)
    assert all(m.count("-") == 1 for m in w["months"])


def test_visit_record_offline_batch_is_idempotent_and_feeds_diagnosis(warehouse):
    from app import db, visits
    from app.analytics.diagnose import diagnose
    code, block = db.query("SELECT udise_code, block FROM schools LIMIT 1")[0].values()
    user = persona("state-spd")
    answers = {k: "no" for k in visits.CHECKLIST}
    for i in range(3):
        visits.record({"udise_code": code, "answers": answers, "client_id": f"t-{i}", "recorded_offline": True}, user)
    again = visits.record({"udise_code": code, "answers": answers, "client_id": "t-0"}, user)
    assert again.get("duplicate")
    s = visits.summary("block", block)
    assert s and s["n_visits"] >= 3 and s["avg_score"] == 0.0
    d = diagnose("block", block)
    assert d["field_observations"]["n_visits"] >= 3
    assert "gap_observation" not in d["data_gap_keys"]


def test_sharing_pairs_are_valid(warehouse):
    from app.analytics.redistribution import suggestions
    exp = warehouse["expected"]["blocks"]
    block = next((b for b, e in exp.items() if "vacancy_rise" in e["effects"]), next(iter(exp)))
    s = suggestions("block", block)
    for p in s["pairs"]:
        assert p["receiver"]["vacant"] >= 1
        assert p["donor"]["working"] >= 2
        assert p["receiver"]["udise_code"] != p["donor"]["udise_code"]


def test_track_record_shape(warehouse):
    from app.actions.service import track_record
    r = track_record("fln_remedial")
    assert "uses" in r
    assert track_record(None, None) == {"uses": 0}


def test_early_warning_answer_grounded_in_all_languages(warehouse):
    from app.ai.assistant import ask
    from app.ai.phrases import LANGS
    for lang in LANGS:
        r = ask("Any early warnings this month?", persona("state-spd"), lang, force_fallback=True)
        assert r["tool_calls"][0]["tool"] == "early_warning"
        assert r["guard"]["passed"], (lang, r["guard"]["unverified_numbers"])


def test_field_observation_answers_grounded_in_all_languages(warehouse):
    from app import db, visits
    from app.ai.assistant import ask
    from app.ai.phrases import LANGS
    rows = db.query("SELECT udise_code, block FROM schools ORDER BY udise_code DESC LIMIT 3")
    user = persona("state-spd")
    for i, r in enumerate(rows):
        answers = {k: "yes" for k in visits.CHECKLIST} | {"time_on_maths": "no", "level_groups": "no"}
        visits.record({"udise_code": r["udise_code"], "answers": answers, "client_id": f"lang-{i}"}, user)
    block = rows[0]["block"]
    for lang in LANGS:
        res = ask(f"Why did numeracy change in {block}?", user, lang, force_fallback=True)
        assert any("evidence" in f and f["text"] for f in res["answer"]["findings"])
        assert res["guard"]["passed"], (lang, res["guard"]["unverified_numbers"], [f["text"] for f in res["answer"]["findings"]])
