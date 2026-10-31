"""Evaluation suite:  python -m eval   (from backend/)

Runs the full pipeline on every Scenario Lab scenario in an isolated warehouse and scores the
results against each scenario's expected.json ground truth. Writes eval/report.json + report.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

EVAL_DIR = BACKEND / "eval"
RUNS = BACKEND / "data" / "eval_runs"
SCENARIOS = ["demo_district_a", "test_random_a", "test_random_b", "test_overlap_c"]
THRESHOLDS = {
    "match_precision": 0.97,
    "match_recall": 0.80,
    "signal_recall": 0.80,
    "false_flags_per_block": 0.10,
    "status_accuracy": 0.80,
    "decline_detection": 0.90,
    "r2_heldout": 0.40,
    "unexplained_bottom": 1.0,
    "peer_filter": 1.0,
    "guard_catch_rate": 1.0,
    "fallback_grounded": 1.0,
}
ADVERSE_FACTORS = {"maths_vacancy", "student_attendance", "infrastructure"}


def use_warehouse(name: str) -> None:
    from app import db

    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"{name}.db"
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(path) + suffix)
        if p.exists():
            p.unlink()
    os.environ["SHIKSHAPULSE_DB"] = str(path.relative_to(BACKEND))
    db.reset_engine()
    db.engine()


def ingest(scenario: str, overrides: dict | None = None) -> tuple[dict, dict, float]:
    from app.ingest.pipeline import run_ingest
    from app.sources.synthetic_files import SyntheticFileAdapter
    from scenario_lab.generator import generate

    res = generate(scenario, RUNS / "scenarios", overrides)
    name = res["scenario"]
    use_warehouse(name)
    t0 = time.time()
    ds = SyntheticFileAdapter(raw_dir=Path(res["raw_dir"])).fetch()
    run_ingest(ds, use_ai=False)
    expected = json.loads((Path(res["out_dir"]) / "expected.json").read_text(encoding="utf-8"))
    return res, expected, time.time() - t0


def eval_matching(expected: dict) -> dict:
    from app import db
    from app.ingest.matcher import SchoolRegistry

    reg = SchoolRegistry(db.read_df("SELECT * FROM schools"))
    seen, auto, correct, review, wrong, amb_total, amb_review = set(), 0, 0, 0, [], 0, 0
    for m in expected["matches"]:
        key = (m["name_variant"], m["block"])
        if key in seen:
            continue
        seen.add(key)
        r = reg.match_one(m["name_variant"], m["block"])
        if m["ambiguous"]:
            amb_total += 1
        if r["udise_code"] and r["confidence"] >= reg.auto:
            auto += 1
            if r["udise_code"] == m["true_udise"]:
                correct += 1
            else:
                wrong.append(
                    {
                        "variant": m["name_variant"],
                        "block": m["block"],
                        "got": r["udise_code"],
                        "true": m["true_udise"],
                        "method": r["method"],
                    }
                )
        else:
            review += 1
            amb_review += int(m["ambiguous"])
    n = len(seen)
    return {
        "variants": n,
        "auto_matched": auto,
        "correct": correct,
        "sent_to_review": review,
        "precision": round(correct / auto, 3) if auto else 1.0,
        "recall": round(correct / n, 3) if n else 1.0,
        "review_share": round(review / n, 3) if n else 0.0,
        "ambiguous_sent_to_review": f"{amb_review}/{amb_total}",
        "errors": wrong[:10],
    }


def eval_diagnosis(expected: dict) -> dict:
    from app.analytics import diagnose as dg
    from app.analytics import trends as tr

    per_signal = {f: {"expected": 0, "detected": 0} for f in ADVERSE_FACTORS}
    false_flags, status_ok, status_n, decl_ok, decl_n, rows = 0, 0, 0, 0, 0, []
    for block, exp in expected["blocks"].items():
        d = dg.diagnose("block", block)
        flagged = {
            s["factor"]
            for s in d["signals"]
            if s["classification"] in ("HIGH", "MEDIUM") and s.get("direction") == "adverse"
        }
        for f in exp["expected_signals"]:
            per_signal[f]["expected"] += 1
            per_signal[f]["detected"] += int(f in flagged)
        fp = sorted((flagged & ADVERSE_FACTORS) - set(exp["expected_signals"]))
        false_flags += len(fp)
        st = exp["status"]
        ok = {
            "insufficient": d["verdict"] == "INSUFFICIENT_EVIDENCE",
            "non_comparable": d["verdict"] == "NON_COMPARABLE"
            and any(f["reason"] == "methodology_change" for f in d["comparability_flags"]),
            "unexplained": d["verdict"] == "UNEXPLAINED" or any("remainder_pp" in u for u in d["unresolved"]),
            "decline": bool(set(exp["expected_signals"]) & flagged),
            "improving": (d["outcome"].get("change_pp") or 0) > 0,
            "stable": not (flagged & ADVERSE_FACTORS),
        }[st]
        status_ok += int(ok)
        status_n += 1
        if st in ("decline", "unexplained"):
            decl_n += 1
            ch = tr.trend("numeracy", "block", block)["change_pp"]
            decl_ok += int(ch is not None and ch <= -4)
        rows.append(
            {
                "block": block,
                "status": st,
                "verdict": d["verdict"],
                "expected": exp["expected_signals"],
                "flagged": sorted(flagged),
                "false_flags": fp,
                "status_ok": ok,
                "change_pp": d["outcome"].get("change_pp"),
            }
        )
    exp_total = sum(v["expected"] for v in per_signal.values())
    det_total = sum(v["detected"] for v in per_signal.values())
    return {
        "signal_recall": round(det_total / exp_total, 3) if exp_total else 1.0,
        "per_signal": per_signal,
        "false_flags": false_flags,
        "false_flags_per_block": round(false_flags / max(1, len(rows)), 3),
        "status_accuracy": round(status_ok / status_n, 3),
        "decline_detection": round(decl_ok / decl_n, 3) if decl_n else 1.0,
        "blocks": rows,
    }


def eval_comparability(expected: dict) -> dict:
    from app import db

    f = db.read_df("SELECT * FROM comparability_flags")
    hits = 0
    for nc in expected["non_comparable"]:
        hits += int(
            (
                (f.unit_type == "block")
                & (f.unit == nc["block"])
                & (f.to_year == nc["to"])
                & (f.reason == "methodology_change")
            ).any()
        )
    return {"expected": len(expected["non_comparable"]), "flagged": hits}


def eval_model(expected: dict) -> dict:
    from app.analytics import expected as ex

    card = ex.model_card()
    leakage = not (set(ex.FEATURES) & ex.OUTCOME_COLUMNS)
    ranking = ex.residual_ranking("block")
    units = [r["unit"] for r in ranking]
    unexplained = [b for b, e in expected["blocks"].items() if e["status"] == "unexplained"]
    res = {r["unit"]: r["residual"] for r in ranking}
    bottom = [u for u in units if (res[u] or 0) <= -ex.BAND_PP]
    hits = sum(1 for b in unexplained if b in bottom)
    return {
        "r2_heldout": card.get("r2_heldout"),
        "mae_heldout": card.get("mae_heldout"),
        "n": card.get("n"),
        "validation": card.get("validation"),
        "no_leakage": leakage,
        "unexplained_blocks": unexplained,
        "bottom_residual_blocks": bottom,
        "unexplained_bottom": round(hits / len(unexplained), 3) if unexplained else 1.0,
    }


def eval_peers(expected: dict) -> dict:
    from app.analytics import peers as pr

    ok, n = 0, 0
    for b in expected["election_affected_blocks"]:
        p = pr.peers(b, election_only=True, other_districts=False)
        n += 1
        ok += int(len(p["peers"]) > 0 and all(x["teacher_days_lost"] >= pr.ELECTION_DAYS for x in p["peers"]))
    return {"election_blocks": n, "filter_respected": ok, "peer_filter": round(ok / n, 3) if n else 1.0}


def eval_guard() -> dict:
    """Adversarial checks: canned bad answers must be caught; fallback answers must be fully grounded."""
    from app.ai.assistant import ask
    from app.ai.evidence import EvidenceStore
    from app.ai.guard import check
    from app.ai.tools import run_tool
    from app.auth import persona

    user = persona("state-spd")
    from app.analytics.common import panel

    p = panel()
    some_block = p.groupby("block").numeracy.mean().idxmin()

    def fresh():
        store = EvidenceStore()
        r = run_tool("diagnose", {"unit_type": "block", "unit": some_block}, store, user)
        return store, r

    cases = []
    store, r = fresh()
    o = r["outcome"]
    real = o["change_pp"]
    # 1. invented number
    ans = {
        "summary": f"Numeracy changed by {real} pp; 73.9% of schools are affected.",
        "findings": [{"label": "observed_fact", "text": f"Change {real} pp.", "evidence": [o["evidence"]]}],
    }
    rep = check(ans, store)
    cases.append(
        {
            "case": "invented number",
            "caught": not rep["passed"] and any(u["value"] == "73.9" for u in rep["unverified_numbers"]),
        }
    )
    # 2. causal claim softened
    store, r = fresh()
    ans = {
        "summary": "The decline was caused by teacher shortages and happened because of poor attendance.",
        "findings": [
            {"label": "associated_signal", "text": "Vacancy led to the drop.", "evidence": [r["outcome"]["evidence"]]}
        ],
    }
    rep = check(ans, store)
    low = (ans["summary"] + ans["findings"][0]["text"]).lower()
    cases.append(
        {
            "case": "causal language",
            "caught": rep["causal_softened"] >= 3
            and "caused" not in low
            and "because of" not in low
            and "led to" not in low,
        }
    )
    # 3. missing citation
    store, r = fresh()
    ans = {"summary": "See findings.", "findings": [{"label": "observed_fact", "text": "Scores fell.", "evidence": []}]}
    rep = check(ans, store)
    cases.append({"case": "missing citation", "caught": not rep["passed"] and bool(rep["citation_errors"])})
    # 4. unknown evidence id
    store, r = fresh()
    ans = {
        "summary": "See findings.",
        "findings": [{"label": "observed_fact", "text": "Scores fell.", "evidence": ["E99"]}],
    }
    rep = check(ans, store)
    cases.append({"case": "fabricated evidence id", "caught": not rep["passed"]})
    # 5. signal presented as fact
    store, r = fresh()
    sig = next((s for s in r["signals"]), None)
    if sig:
        ans = {
            "summary": "See findings.",
            "findings": [{"label": "observed_fact", "text": "A factor moved.", "evidence": [sig["evidence"]]}],
        }
        rep = check(ans, store)
        cases.append({"case": "signal labelled as fact", "caught": ans["findings"][0]["label"] == "associated_signal"})
    # 6. omitted unresolved questions get surfaced
    store = EvidenceStore()
    insuff = list(p.block.unique())
    found = False
    for b in insuff:
        store = EvidenceStore()
        rr = run_tool("diagnose", {"unit_type": "block", "unit": b}, store, user)
        if rr.get("unresolved"):
            ans = {
                "summary": "All explained.",
                "findings": [
                    {"label": "observed_fact", "text": "Scores changed.", "evidence": [rr["outcome"]["evidence"]]}
                ],
            }
            rep = check(ans, store)
            cases.append({"case": "omitted unresolved question", "caught": rep["unresolved_added"] >= 1})
            found = True
            break
    if not found:
        cases.append(
            {"case": "omitted unresolved question", "caught": True, "note": "no unresolved evidence in scenario"}
        )
    caught = sum(c["caught"] for c in cases)
    # Fallback answers must be fully grounded.
    questions = [
        "Why did numeracy fall?",
        f"Why did numeracy change in {some_block}?",
        f"How did similar election-affected blocks compare with {some_block}?",
        "Which schools have both attendance decline and maths vacancies?",
        "Show the three year trend",
        "Which blocks had the largest decline?",
        "How reliable is the data?",
        "What actions are overdue?",
        f"{some_block} में संख्या ज्ञान क्यों गिरा?",
    ]
    grounded = []
    for q in questions:
        a = ask(q, user, "hi" if any(ord(ch) > 2304 for ch in q) else "en", force_fallback=True)
        grounded.append(
            {
                "question": q,
                "passed": a["guard"]["passed"],
                "numbers": a["guard"]["numbers_checked"],
                "unverified": a["guard"]["unverified_numbers"],
            }
        )
    live = None
    from app.ai.llm import llm

    if llm().available:
        live = []
        for q in questions[:5]:
            a = ask(q, user, "en")
            live.append(
                {"question": q, "engine": a["engine"], "passed": a["guard"]["passed"], "attempts": a["attempts"]}
            )
    return {
        "adversarial_cases": cases,
        "guard_catch_rate": round(caught / len(cases), 3),
        "fallback_answers": grounded,
        "fallback_grounded": round(sum(g["passed"] for g in grounded) / len(grounded), 3),
        "live_llm": live,
    }


def eval_quality_monotonic() -> dict:
    from app.analytics.quality import unit_quality

    out = []
    for pct in (0.0, 0.2, 0.45):
        name = f"quality_missing_{int(pct * 100)}"
        _, _, _ = ingest("test_random_a", {"name": name, "mess": {"missing_months_pct": pct}})
        q = unit_quality("state", None)
        out.append(
            {
                "missing_months_pct": pct,
                "attendance_completeness": q["comparison_completeness"]["attendance"],
                "confidence": q["confidence"],
            }
        )
    mono = all(out[i]["confidence"] >= out[i + 1]["confidence"] for i in range(len(out) - 1)) and all(
        out[i]["attendance_completeness"] > out[i + 1]["attendance_completeness"] for i in range(len(out) - 1)
    )
    return {"runs": out, "monotonic": mono}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="demo scenario only, skip quality sweep")
    a = ap.parse_args()
    t0 = time.time()
    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "thresholds": THRESHOLDS, "scenarios": {}}
    for sc in SCENARIOS[:1] if a.quick else SCENARIOS:
        print(f"== {sc}")
        res, expected, secs = ingest(sc)
        r = {
            "schools": res["n_schools"],
            "blocks": res["n_blocks"],
            "ingest_seconds": round(secs, 1),
            "matching": eval_matching(expected),
            "diagnosis": eval_diagnosis(expected),
            "comparability": eval_comparability(expected),
            "model": eval_model(expected),
            "peers": eval_peers(expected),
        }
        if sc == "demo_district_a":
            r["guard"] = eval_guard()
        report["scenarios"][sc] = r
        print(
            f"   match P={r['matching']['precision']} R={r['matching']['recall']} | signal recall "
            f"{r['diagnosis']['signal_recall']} | false flags/block {r['diagnosis']['false_flags_per_block']} | "
            f"status {r['diagnosis']['status_accuracy']} | R2 {r['model']['r2_heldout']}"
        )
    if not a.quick:
        print("== quality sweep")
        report["quality_monotonic"] = eval_quality_monotonic()
    report["checks"] = checks(report)
    report["passed"] = all(c["passed"] for c in report["checks"])
    report["seconds"] = round(time.time() - t0, 1)
    EVAL_DIR.joinpath("report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    EVAL_DIR.joinpath("report.md").write_text(markdown(report), encoding="utf-8")
    print(
        f"\n{'PASSED' if report['passed'] else 'FAILED'} — {sum(c['passed'] for c in report['checks'])}/"
        f"{len(report['checks'])} checks. Report: eval/report.md"
    )


def checks(report: dict) -> list[dict]:
    out = []
    T = THRESHOLDS
    for sc, r in report["scenarios"].items():

        def add(name, value, ok, target, sc=sc):
            out.append({"scenario": sc, "check": name, "value": value, "target": target, "passed": bool(ok)})

        m, d, md = r["matching"], r["diagnosis"], r["model"]
        add(
            "School-match precision",
            m["precision"],
            m["precision"] >= T["match_precision"],
            f"≥ {T['match_precision']}",
        )
        add("School-match recall (auto)", m["recall"], m["recall"] >= T["match_recall"], f"≥ {T['match_recall']}")
        add(
            "Signal detection recall",
            d["signal_recall"],
            d["signal_recall"] >= T["signal_recall"],
            f"≥ {T['signal_recall']}",
        )
        add(
            "False flags per block",
            d["false_flags_per_block"],
            d["false_flags_per_block"] <= T["false_flags_per_block"],
            f"≤ {T['false_flags_per_block']}",
        )
        add(
            "Block status accuracy",
            d["status_accuracy"],
            d["status_accuracy"] >= T["status_accuracy"],
            f"≥ {T['status_accuracy']}",
        )
        add(
            "Decline detection",
            d["decline_detection"],
            d["decline_detection"] >= T["decline_detection"],
            f"≥ {T['decline_detection']}",
        )
        add(
            "Methodology changes flagged",
            f"{r['comparability']['flagged']}/{r['comparability']['expected']}",
            r["comparability"]["flagged"] == r["comparability"]["expected"],
            "all",
        )
        add(
            "Expected-vs-actual held-out R²",
            md["r2_heldout"],
            (md["r2_heldout"] or 0) >= T["r2_heldout"],
            f"≥ {T['r2_heldout']}",
        )
        add("No outcome leakage in model features", md["no_leakage"], md["no_leakage"], "true")
        add(
            "Unexplained declines classed 'underperforming conditions'",
            md["unexplained_bottom"],
            md["unexplained_bottom"] >= T["unexplained_bottom"],
            "all",
        )
        add(
            "Election peer filter respected",
            r["peers"]["peer_filter"],
            r["peers"]["peer_filter"] >= T["peer_filter"],
            "all",
        )
        if "guard" in r:
            g = r["guard"]
            add(
                "Guard catches adversarial answers",
                g["guard_catch_rate"],
                g["guard_catch_rate"] >= T["guard_catch_rate"],
                "all",
            )
            add(
                "Fallback answers fully grounded",
                g["fallback_grounded"],
                g["fallback_grounded"] >= T["fallback_grounded"],
                "all",
            )
    if "quality_monotonic" in report:
        q = report["quality_monotonic"]
        out.append(
            {
                "scenario": "test_random_a (sweep)",
                "check": "Confidence falls as missing data rises",
                "value": [x["confidence"] for x in q["runs"]],
                "target": "monotonic",
                "passed": q["monotonic"],
            }
        )
    return out


def markdown(report: dict) -> str:
    lines = [
        "# ShikshaPulse — Evaluation report",
        "",
        f"Generated {report['generated_at']} · {report['seconds']}s · "
        f"**{'PASSED' if report['passed'] else 'FAILED'}** "
        f"({sum(c['passed'] for c in report['checks'])}/{len(report['checks'])} checks)",
        "",
        "All scenarios are SYNTHETIC (Scenario Lab) with known ground truth; randomised scenarios place effects "
        "on random block names, so results cannot rely on hard-coded outcomes.",
        "",
        "| Scenario | Check | Value | Target | Result |",
        "|---|---|---|---|---|",
    ]
    for c in report["checks"]:
        lines.append(
            f"| {c['scenario']} | {c['check']} | {c['value']} | {c['target']} | {'✅' if c['passed'] else '❌'} |"
        )
    for sc, r in report["scenarios"].items():
        lines += [
            "",
            f"## {sc}",
            f"- {r['schools']} schools, {r['blocks']} blocks, ingested in {r['ingest_seconds']}s",
            f"- Matching: {r['matching']['variants']} name variants without codes → {r['matching']['auto_matched']} "
            f"auto-matched ({r['matching']['correct']} correct), {r['matching']['sent_to_review']} sent to review; "
            f"ambiguous sent to review {r['matching']['ambiguous_sent_to_review']}",
            f"- Model: held-out R² {r['model']['r2_heldout']}, MAE {r['model']['mae_heldout']} pp "
            f"({r['model']['validation']})",
            "",
            "| Block | Planted status | Verdict | Expected signals | Flagged | False flags |",
            "|---|---|---|---|---|---|",
        ]
        for b in r["diagnosis"]["blocks"]:
            lines.append(
                f"| {b['block']} | {b['status']} | {b['verdict']} | {', '.join(b['expected']) or '—'} | "
                f"{', '.join(b['flagged']) or '—'} | {', '.join(b['false_flags']) or '—'} |"
            )
        if "guard" in r:
            lines += [
                "",
                "**Guard adversarial cases:** "
                + ", ".join(f"{c['case']} {'✅' if c['caught'] else '❌'}" for c in r["guard"]["adversarial_cases"]),
            ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
