"""Safe analytics tools exposed to the LLM. No raw SQL — only vetted, scoped analytics functions.

Each tool registers its results in the EvidenceStore and returns a compact, citable payload.
"""

from __future__ import annotations

from ..actions import service as actions
from ..analytics import diagnose as dg
from ..analytics import expected as ex
from ..analytics import peers as pr
from ..analytics import quality as q
from ..analytics import radar as rd
from ..analytics import trends as tr
from ..auth import can_view, clamp_school_scope
from .evidence import EvidenceStore

UNIT_PARAMS = {
    "unit_type": {"type": "string", "enum": ["state", "district", "block", "school"]},
    "unit": {"type": "string", "description": "District/block name or UDISE code; omit for state"},
}
METRIC_PARAM = {
    "type": "string",
    "enum": ["numeracy", "literacy", "student_att", "teacher_att", "maths_vacancy", "infra_index"],
    "default": "numeracy",
}


def _fn(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOL_SPECS = [
    _fn(
        "get_overview",
        "KPI overview of a unit (latest value, 3-year change, state reference, rank).",
        UNIT_PARAMS,
        ["unit_type"],
    ),
    _fn(
        "get_trend",
        "Three-year trend of a metric for a unit, with comparability caveats.",
        {**UNIT_PARAMS, "metric": METRIC_PARAM},
        ["unit_type", "metric"],
    ),
    _fn(
        "where_did_it_change",
        "Break a unit's change down by its child units (state→districts→blocks→schools).",
        {**UNIT_PARAMS, "metric": METRIC_PARAM},
        ["unit_type", "metric"],
    ),
    _fn(
        "diagnose",
        "Evidence-graded contributing signals for a unit's outcome change (association, not cause), "
        "including context events, unresolved remainder and data gaps.",
        {**UNIT_PARAMS, "metric": METRIC_PARAM},
        ["unit_type"],
    ),
    _fn(
        "expected_vs_actual",
        "Compare a unit's actual score with what its structural conditions predict.",
        UNIT_PARAMS,
        ["unit_type"],
    ),
    _fn(
        "find_peers",
        "Find blocks with similar baseline characteristics and compare their change; "
        "set election_only to restrict to blocks with comparable election duty.",
        {"block": {"type": "string"}, "election_only": {"type": "boolean", "default": False}},
        ["block"],
    ),
    _fn(
        "intervention_radar",
        "Schools where several indicators deteriorate together, with reasons.",
        {**UNIT_PARAMS, "min_flags": {"type": "integer", "default": 2}},
        ["unit_type"],
    ),
    _fn(
        "find_schools_with",
        "Schools in a unit meeting ALL given conditions.",
        {**UNIT_PARAMS, "conditions": {"type": "array", "items": {"type": "string", "enum": list(rd.RULES)}}},
        ["unit_type", "conditions"],
    ),
    _fn(
        "list_actions",
        "Actions in the Action Room for a unit with owners, deadlines and outcome status.",
        UNIT_PARAMS,
        ["unit_type"],
    ),
    _fn(
        "early_warning",
        "Recent monthly warnings: student attendance falls vs the same months last year, teacher "
        "attendance dips (e.g. election duty) and schools that stopped reporting.",
        UNIT_PARAMS,
        ["unit_type"],
    ),
    _fn(
        "get_school",
        "One school's 3-year profile (numeracy, attendance, maths posts, support flags).",
        {"udise": {"type": "string", "description": "11-digit UDISE code"}},
        ["udise"],
    ),
    _fn(
        "data_quality",
        "Data completeness/confidence and comparability warnings for a unit.",
        UNIT_PARAMS,
        ["unit_type"],
    ),
]


def _unit(args: dict) -> tuple[str, str | None]:
    ut = args.get("unit_type") or "state"
    u = args.get("unit") or None
    return ut, (None if ut == "state" else u)


def run_tool(name: str, args: dict, store: EvidenceStore, user: dict) -> dict:
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    ut, u = _unit(args)
    if name not in ("find_peers",) and not can_view(user, ut, u):
        return {"error": "outside your data scope"}
    try:
        return fn(args, store, user)
    except KeyError as e:
        return {"error": f"not found: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def t_overview(args, store, user):
    ut, u = _unit(args)
    o = tr.overview(ut, u)
    out = {"unit": o["unit_label"], "rank": o["rank"], "kpis": []}
    for k in o["kpis"]:
        eid = store.add(
            "kpi",
            f"{k['label']} — {o['unit_label']}",
            {
                "latest": k["latest"],
                "baseline": k["baseline"],
                "change_pp": k["change_pp"],
                "state_latest": k["state_latest"],
            },
            f"{o['baseline_year']} → {o['latest_year']}",
            link={"page": "overview", "unit_type": ut, "unit": o["unit"]},
        )
        out["kpis"].append(
            {
                "evidence": eid,
                "metric": k["label"],
                "latest": k["latest"],
                "baseline": k["baseline"],
                "change_pp": k["change_pp"],
                "state_latest": k["state_latest"],
            }
        )
    if o["rank"]:
        out["rank_evidence"] = store.add("rank", f"Numeracy rank — {o['unit_label']}", o["rank"], o["latest_year"])
    return out


def t_trend(args, store, user):
    ut, u = _unit(args)
    t = tr.trend(args.get("metric", "numeracy"), ut, u)
    eid = store.add(
        "trend",
        f"{t['label']} trend — {t['unit_label']}",
        {"points": [{"year": p["year"], "value": p["value"]} for p in t["points"]], "change_pp": t["change_pp"]},
        f"{t['baseline_year']} → {t['latest_year']}",
        source=t["sources"],
        link={"page": "overview", "unit_type": ut, "unit": t["unit"]},
    )
    out = {
        "evidence": eid,
        "points": [{"year": p["year"], "value": p["value"]} for p in t["points"]],
        "change_pp": t["change_pp"],
        "caveats": t["caveats"],
    }
    if t["caveats"]:
        out["caveat_evidence"] = store.add(
            "comparability",
            "Comparability caveat",
            {"caveats": t["caveats"]},
            t["latest_year"],
            ev_type="unresolved_question",
        )
    return out


def t_breakdown(args, store, user):
    ut, u = _unit(args)
    b = tr.breakdown(args.get("metric", "numeracy"), ut, u)
    kids = [c for c in b["children"] if c["change_pp"] is not None]
    out = {
        "parent_change_pp": b["parent_change_pp"],
        "period": f"{b['baseline_year']} → {b['latest_year']}",
        "children": [],
    }
    for c in kids[:6]:
        eid = store.add(
            "breakdown",
            f"{c['name']} ({c['unit_type']})",
            {
                "baseline": c["baseline"],
                "latest": c["latest"],
                "change_pp": c["change_pp"],
                "contribution_pp": c["contribution_pp"],
            },
            out["period"],
            link={
                "page": "block" if c["unit_type"] == "block" else "overview",
                "unit_type": c["unit_type"],
                "unit": c["unit"],
            },
        )
        out["children"].append(
            {
                "evidence": eid,
                "name": c["name"],
                "type": c["unit_type"],
                "baseline": c["baseline"],
                "latest": c["latest"],
                "change_pp": c["change_pp"],
                "contribution_pp": c["contribution_pp"],
            }
        )
    noncomp = [c["name"] for c in b["children"] if not c["comparable"]]
    if len(noncomp) > 5:
        noncomp = [f"{len(noncomp)} {b['child_type']}s"]
    if noncomp:
        out["not_comparable"] = noncomp
        out["not_comparable_evidence"] = store.add(
            "comparability",
            "Units with non-comparable latest scores",
            {"units": noncomp},
            b["latest_year"],
            ev_type="unresolved_question",
        )
    return out


def t_diagnose(args, store, user):
    ut, u = _unit(args)
    d = dg.diagnose(ut, u, args.get("metric", "numeracy"))
    link = {"page": "why", "unit_type": ut, "unit": d["unit"]}
    o = d["outcome"]
    out = {
        "unit": d["unit_label"],
        "period": d["period"],
        "verdict": d["verdict"],
        "verdict_reason": d["verdict_reason"],
        "data_confidence": d["data_confidence"],
    }
    out["outcome"] = {
        "evidence": store.add(
            "outcome",
            f"{d['metric_label']} change — {d['unit_label']}",
            {
                "baseline": o.get("baseline"),
                "latest": o.get("latest"),
                "change_pp": o.get("change_pp"),
                "n_schools": o["n_schools_compared"],
            },
            d["period"],
            source=o.get("sources"),
            link=link,
        ),
        "baseline": o.get("baseline"),
        "latest": o.get("latest"),
        "change_pp": o.get("change_pp"),
        "schools_compared": o["n_schools_compared"],
    }
    out["signals"] = []
    for s in d["signals"]:
        if s["classification"] not in ("HIGH", "MEDIUM"):
            continue  # insufficient/conflicting factors are carried as unresolved questions below
        data = {
            k: s.get(k) for k in ("baseline", "latest", "change", "contribution_pp", "assoc_r", "coverage", "n_schools")
        }
        if s.get("affected_units"):
            data["affected_units"] = [{"unit": a["unit"], "change": a["change"]} for a in s["affected_units"][:3]]
        ev_type = "associated_signal" if s["classification"] in ("HIGH", "MEDIUM") else "unresolved_question"
        eid = store.add(
            "signal",
            f"{s['label']} — {s['classification']}",
            data,
            s["period"],
            ev_type=ev_type,
            source=s.get("sources"),
            link={**link, "signal": s["factor"]},
        )
        out["signals"].append(
            {
                "evidence": eid,
                "factor": s["label"],
                "factor_key": s["factor"],
                "strength": s["classification"],
                **data,
                **({"note": s["note"]} if s.get("note") else {}),
            }
        )
    out["context"] = []
    for c in d["context"]:
        if c["classification"] != "CONTEXT":
            continue
        eid = store.add(
            "context",
            c["event"],
            {"avg_teacher_days_lost": c["avg_teacher_days_lost"], "blocks_affected": c["blocks_affected"]},
            c["period"],
            ev_type="observed_fact",
            source=c["source"],
        )
        out["context"].append(
            {
                "evidence": eid,
                "event": c["event"],
                "avg_teacher_days_lost": c["avg_teacher_days_lost"],
                "blocks_affected": c["blocks_affected"],
            }
        )
    out["unresolved"] = []
    for uq in d["unresolved"]:
        params = {
            k: uq.get(k)
            for k in ("kind", "pp", "child", "child_verdict", "factor", "coverage_pct", "direction")
            if uq.get(k) is not None
        }
        eid = store.add(
            "unresolved",
            "Unresolved question",
            {"text": uq["text"], "remainder_pp": uq.get("remainder_pp"), **params},
            uq["period"],
            ev_type="unresolved_question",
            link=link,
        )
        out["unresolved"].append({"evidence": eid, "text": uq["text"], **params})
    out["data_gaps"] = d["data_gaps"]
    f = d.get("field_observations")
    if f:
        eid = store.add(
            "field",
            f"Field observations — {d['unit_label']}",
            {
                "n_visits": f["n_visits"],
                "n_schools": f["n_schools"],
                "avg_score": f["avg_score"],
                "items": f["items"],
                "scale": 100,
                "minutes_threshold": 30,
            },
            f"{f['first']} → {f['last']}",
            ev_type="observed_fact",
            source="CRC school visits" + (" (simulated)" if f["simulated"] else ""),
        )
        out["field_observations"] = {
            "evidence": eid,
            "n_visits": f["n_visits"],
            "avg_score": f["avg_score"],
            "weakest": [{"item": i["item"], "pct_yes": i["pct_yes"]} for i in f["items"][:2]],
            "period": f"{f['first']} → {f['last']}",
        }
    return out


def t_expected(args, store, user):
    ut, u = _unit(args)
    e = ex.expected_vs_actual(ut, u)
    if not e.get("ok"):
        return {"error": e.get("reason")}
    lt = e["latest"]
    eid = store.add(
        "expected",
        f"Expected vs actual — {e['unit_label']}",
        {
            "actual": lt["actual"],
            "expected": lt["expected"],
            "residual": lt["residual"],
            "r2_heldout": e["model"]["r2_heldout"],
        },
        lt["year"],
        link={"page": "block", "unit_type": ut, "unit": e["unit"]},
    )
    return {
        "evidence": eid,
        "year": lt["year"],
        "actual": lt["actual"],
        "expected": lt["expected"],
        "gap_pp": lt["residual"],
        "category": e["category"],
        "interpretation": e["interpretation"],
        "model_r2_heldout": e["model"]["r2_heldout"],
    }


def t_peers(args, store, user):
    p = pr.peers(args["block"], election_only=bool(args.get("election_only")))
    out = {
        "block": p["block"],
        "election_only": p["election_only"],
        "period": f"{p['baseline_year']} → {p['latest_year']}",
        "unit_change_pp": p["unit"]["change_pp"],
        "unit_teacher_days_lost": p["unit"]["teacher_days_lost"],
        "peers": [],
    }
    for r in p["peers"]:
        eid = store.add(
            "peer",
            f"Peer block {r['block']} ({r['district']})",
            {
                "change_pp": r["change_pp"],
                "teacher_days_lost": r["teacher_days_lost"],
                "baseline": r["baseline"],
                "latest": r["latest"],
            },
            out["period"],
            link={"page": "peers", "block": p["block"]},
        )
        out["peers"].append(
            {
                "evidence": eid,
                "block": r["block"],
                "district": r["district"],
                "change_pp": r["change_pp"],
                "teacher_days_lost": r["teacher_days_lost"],
            }
        )
    if p["summary"]:
        out["summary_evidence"] = store.add(
            "peer_summary",
            f"Peer comparison — {p['block']}",
            p["summary"],
            out["period"],
            link={"page": "peers", "block": p["block"]},
        )
        out["summary"] = p["summary"]
    return out


def _scoped_radar(args, user, min_flags):
    ut, u = clamp_school_scope(user, *_unit(args))
    return rd.radar(ut, u, min_flags=min_flags)


def t_radar(args, store, user):
    r = _scoped_radar(args, user, int(args.get("min_flags", 2)))
    eid = store.add(
        "radar",
        f"Intervention radar — {r['unit']}",
        {
            "n_schools": r["n_schools"],
            "n_flagged": r["n_flagged"],
            "n_priority": r["n_priority"],
            "flag_counts": r["flag_counts_flagged"],
            "min_flags": 2,
            "priority_flags": 3,
            "schools": [s["school_name"] for s in r["schools"][:8]],
        },
        r["latest_year"],
        link={"page": "radar", "unit_type": r["unit_type"], "unit": r["unit"]},
    )
    return {
        "evidence": eid,
        "n_schools": r["n_schools"],
        "n_flagged": r["n_flagged"],
        "n_priority": r["n_priority"],
        "top_schools": [
            {
                "school": s["school_name"],
                "udise": s["udise_code"],
                "block": s["block"],
                "reasons": s["reasons"],
                "numeracy_change": s["numeracy_change"],
            }
            for s in r["schools"][:8]
        ],
        "note": r["note"],
    }


def t_find_schools(args, store, user):
    conds = [c for c in args.get("conditions", []) if c in rd.RULES]
    r = _scoped_radar(args, user, 1)
    full = rd.radar(r["unit_type"], r["unit"], min_flags=1, limit=100000)["schools"]
    hits = [s for s in full if all(c in s["flags"] for c in conds)]
    eid = store.add(
        "school_filter",
        f"Schools with {' + '.join(rd.RULES[c] for c in conds)} — {r['unit']}",
        {"n_matching": len(hits), "n_schools": r["n_schools"], "schools": [s["school_name"] for s in hits[:10]]},
        r["latest_year"],
        link={"page": "radar", "unit_type": r["unit_type"], "unit": r["unit"]},
    )
    return {
        "evidence": eid,
        "conditions": [rd.RULES[c] for c in conds],
        "condition_keys": conds,
        "n_matching": len(hits),
        "schools": [
            {
                "school": s["school_name"],
                "udise": s["udise_code"],
                "block": s["block"],
                "numeracy": s["numeracy"],
                "attendance_change": s["attendance_change"],
                "maths_vacancy": s["maths_vacancy"],
            }
            for s in hits[:10]
        ],
    }


def t_actions(args, store, user):
    ut, u = _unit(args)
    acts = actions.list_actions(user, ut if ut != "state" else None, u)
    acts = actions.for_user(user, acts) if user else acts
    s = actions.summary(acts)
    eid = store.add("actions", f"Action Room — {u or 'State'}", s, None, link={"page": "actions"})
    return {
        "evidence": eid,
        "summary": s,
        "actions": [
            {
                "id": a["id"],
                "title": a["title"],
                "unit": a["unit"],
                "owner": a["owner_name"],
                "due": a["due_date"],
                "status": a["status"],
                "outcome_status": a["outcome_status"],
                "simulated": a["is_simulated"],
            }
            for a in acts[:10]
        ],
    }


def t_quality(args, store, user):
    ut, u = _unit(args)
    qq = q.unit_quality(ut, u)
    eid = store.add(
        "quality",
        f"Data quality — {qq['unit']}",
        {
            "confidence": qq["confidence"],
            "scale": 100,
            "completeness": {k: round(v * 100) for k, v in qq["comparison_completeness"].items()},
        },
        None,
        ev_type="observed_fact",
        link={"page": "data"},
    )
    out = {
        "evidence": eid,
        "confidence": qq["confidence"],
        "label": qq["label"],
        "completeness_pct": {k: round(v * 100) for k, v in qq["comparison_completeness"].items()},
        "warnings": qq["warnings"],
        "warning_items": qq.get("warning_items", []),
    }
    if qq["warnings"]:
        out["warnings_evidence"] = store.add(
            "quality_warning",
            "Data limitations",
            {"warnings": qq["warnings"], "items": qq.get("warning_items", []), "months_needed": 6},
            None,
            ev_type="unresolved_question",
        )
    return out


def t_early_warning(args, store, user):
    from ..analytics.early_warning import early_warning

    ut, u = _unit(args)
    w = early_warning(ut, u)
    eid = store.add(
        "early_warning",
        f"Early warning — {w['unit']}",
        {"alerts": w["alerts"], "months": w.get("months"), "thresholds": w.get("thresholds")},
        " · ".join(w.get("months", [])),
        link={"page": "overview"},
    )
    return {
        "evidence": eid,
        "months": w.get("months"),
        "compared_with": w.get("compared_with"),
        "alerts": w["alerts"][:8],
    }


def t_school(args, store, user):
    """One school's 3-year picture in plain terms (used for headmaster/teacher questions)."""
    from ..analytics.trends import school_profile

    code = args.get("udise") or user.get("scope")
    if not can_view(user, "school", code):
        return {"error": "outside your data scope"}
    p = school_profile(code)
    ys = p["years"]
    first, last = ys[0], ys[-1]
    findings, data = [], {"school": p["school_name"]}
    if first.get("numeracy") is not None and last.get("numeracy") is not None:
        ch = round(last["numeracy"] - first["numeracy"], 1)
        params = {
            "name": p["school_name"],
            "b": last["numeracy"],
            "change": ch,
            "y0": first["academic_year"],
            "y1": last["academic_year"],
        }
        data.update(numeracy_latest=last["numeracy"], numeracy_baseline=first["numeracy"], numeracy_change=ch)
        findings.append({"label": "observed_fact", "code": "num", "params": params})
    if first.get("student_att") is not None and last.get("student_att") is not None:
        ch = round(last["student_att"] - first["student_att"], 1)
        data.update(att_latest=last["student_att"], att_baseline=first["student_att"], att_change=ch)
        findings.append(
            {
                "label": "observed_fact",
                "code": "att",
                "params": {"b": last["student_att"], "change": ch, "y0": first["academic_year"]},
            }
        )
    if last.get("maths_sanctioned"):
        data.update(maths_vacant=last["maths_vacant"], maths_sanctioned=last["maths_sanctioned"])
        findings.append(
            {
                "label": "observed_fact",
                "code": "vac",
                "params": {"vac": int(last["maths_vacant"] or 0), "san": int(last["maths_sanctioned"])},
            }
        )
    flags = []
    r = rd.radar("block", p["block"], min_flags=1, limit=100000)
    me = next((x for x in r["schools"] if x["udise_code"] == code), None)
    if me:
        flags = me["flags"]
        data["flags"] = flags
        data["n_flags"] = len(flags)
        findings.append({"label": "associated_signal", "code": "flags", "params": {"flags": flags}})
    eid = store.add(
        "school",
        f"School profile — {p['school_name']}",
        data,
        f"{first['academic_year']} → {last['academic_year']}",
        link={"page": "school", "udise": code},
    )
    for f in findings:
        f["evidence"] = [eid]
        f["period"] = f"{first['academic_year']} → {last['academic_year']}"
    steps = {
        "maths_vacancy": "step_vacancy",
        "attendance_decline": "step_attendance",
        "infra_gap": "step_infra",
        "teacher_attendance": "step_teacher",
    }
    return {
        "evidence": eid,
        "school": p["school_name"],
        "block": p["block"],
        "years": ys,
        "flags": flags,
        "findings": findings,
        "step_keys": [steps[f] for f in flags if f in steps],
    }


TOOLS = {
    "get_school": t_school,
    "early_warning": t_early_warning,
    "get_overview": t_overview,
    "get_trend": t_trend,
    "where_did_it_change": t_breakdown,
    "diagnose": t_diagnose,
    "expected_vs_actual": t_expected,
    "find_peers": t_peers,
    "intervention_radar": t_radar,
    "find_schools_with": t_find_schools,
    "list_actions": t_actions,
    "data_quality": t_quality,
}
