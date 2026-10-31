"""Deterministic answer engine (6 languages) — used when no LLM is configured or the LLM fails the guard.

Routes the question to tools by intent (keywords in English and Indian languages), then writes
findings from the tool outputs only, so every number is grounded by construction.
"""

from __future__ import annotations

import re

from .. import db
from .phrases import EW, FIELD, ITEM, event, factor, rule, t

FACTOR_KEY_BY_LABEL = {
    "Maths teacher vacancy": "maths_vacancy",
    "Student attendance": "student_attendance",
    "Teacher attendance": "teacher_attendance",
    "Infrastructure (facilities available)": "infrastructure",
}

KW = {
    "peers": [
        "similar",
        "peer",
        "compare",
        "comparable",
        "election",
        "चुनाव",
        "समान",
        "तुलना",
        "निवडणूक",
        "সমান",
        "তুলনা",
        "নির্বাচন",
        "ஒப்பி",
        "தேர்தல்",
        "ஒத்த",
        "పోల్చ",
        "ఎన్నిక",
        "ఒకే రకమైన",
    ],
    "election": ["election", "चुनाव", "निवडणूक", "নির্বাচন", "தேர்தல்", "ఎన్నిక"],
    "schools": [
        "which schools",
        "schools with",
        "schools where",
        "both",
        "overlap",
        "radar",
        "कौन से स्कूल",
        "कोणत्या शाळा",
        "কোন স্কুল",
        "எந்தப் பள்ளி",
        "ఏ పాఠశాల",
    ],
    "attendance": ["attendance", "उपस्थिति", "उपस्थिती", "উপস্থিতি", "வருகை", "హాజరు"],
    "vacancy": ["vacan", "teacher short", "shortage", "रिक्ति", "खाली", "रिक्त", "শূন্য", "காலி", "ఖాళీ"],
    "low": ["low numeracy", "low score", "कम अंक", "कमी गुण", "কম নম্বর", "குறைந்த", "తక్కువ మార్కు"],
    "infra": ["infra", "facilit", "सुविधा", "সুবিধা", "வசதி", "సౌకర్య"],
    "actions": [
        "action",
        "overdue",
        "assigned",
        "owner",
        "responsib",
        "task",
        "कार्रवाई",
        "कार्य",
        "काम",
        "কাজ",
        "பணி",
        "పని",
    ],
    "quality": ["quality", "complete", "missing", "reliab", "trust", "गुणवत्ता", "डेटा", "माहिती", "তথ্য", "தரவு", "సమాచార"],
    "expected": ["expected", "fair", "conditions", "underperform", "अपेक्षित", "परिस्थिती", "প্রত্যাশিত", "எதிர்பார்", "అంచనా"],
    "largest": [
        "largest",
        "biggest",
        "most",
        "worst",
        "which block",
        "where",
        "कहाँ",
        "सबसे",
        "सर्वात",
        "কোথায়",
        "সবচেয়ে",
        "மிகப்பெரிய",
        "எங்கே",
        "అతిపెద్ద",
        "ఎక్కడ",
    ],
    "trend": [
        "trend",
        "always",
        "fallen",
        "years",
        "history",
        "were we",
        "रुझान",
        "वर्ष",
        "कल",
        "वर्षे",
        "প্রবণতা",
        "বছর",
        "போக்கு",
        "ஆண்டு",
        "ధోరణి",
        "సంవత్సర",
    ],
    "school": [
        "my school",
        "मेरा स्कूल",
        "मेरे स्कूल",
        "माझी शाळा",
        "আমার স্কুল",
        "என் பள்ளி",
        "నా పాఠశాల",
        "school",
        "स्कूल",
        "शाळा",
        "স্কুল",
        "பள்ளி",
        "పాఠశాల",
    ],
    "literacy": ["literacy", "language", "reading", "साक्षरता", "भाषा", "সাক্ষরতা", "எழுத்தறிவு", "అక్షరాస్యత"],
    "state": ["state", "राज्य", "রাজ্য", "மாநில", "రాష్ట్ర"],
    "warning": [
        "warning",
        "alert",
        "early",
        "recent",
        "this month",
        "last month",
        "चेतावनी",
        "इशारा",
        "সতর্ক",
        "எச்சரிக்கை",
        "హెచ్చరిక",
    ],
}


def _sign(x) -> str:
    return f"+{x}" if isinstance(x, (int, float)) and x > 0 else f"{x}"


def known_units() -> dict:
    if not db.table_exists("schools"):
        return {"blocks": [], "districts": []}
    s = db.read_df("SELECT DISTINCT block, district FROM schools")
    return {
        "blocks": sorted(s.block.unique(), key=len, reverse=True),
        "districts": sorted(s.district.unique(), key=len, reverse=True),
    }


def _has(q: str, key: str) -> bool:
    return any(w in q for w in KW[key])


def extract_unit(question: str, user: dict) -> tuple[str, str | None]:
    q = question.casefold()
    m = re.search(r"\b\d{11}\b", question)
    if m:
        return "school", m.group(0)
    u = known_units()
    for b in u["blocks"]:
        if re.search(rf"\b{re.escape(b.casefold())}\b", q):
            return "block", b
    for d in u["districts"]:
        if re.search(rf"\b{re.escape(d.casefold())}\b", q):
            return "district", d
    if _has(q, "state"):
        return "state", None
    if user["role"] == "headmaster":
        return "school", user["scope"]
    return (user["scope_type"], user["scope"]) if user["scope_type"] != "state" else ("state", None)


def all_blocks_in(question: str) -> list[str]:
    q = question.casefold()
    return [b for b in known_units()["blocks"] if re.search(rf"\b{re.escape(b.casefold())}\b", q)]


def extract_metric(question: str) -> str:
    q = question.casefold()
    if _has(q, "literacy"):
        return "literacy"
    return "numeracy"


def route(question: str, user: dict) -> list[tuple[str, dict]]:
    """Intent → ordered tool calls."""
    q = question.casefold()
    ut, u = extract_unit(question, user)
    metric = extract_metric(question)
    unit = {"unit_type": ut, "unit": u}
    if ut == "school":
        calls: list[tuple[str, dict]] = [("get_school", {"udise": u})]
        if _has(q, "actions"):
            calls.append(("list_actions", {"unit_type": "block", "unit": user.get("block")}))
        return calls
    if _has(q, "warning"):
        return [("early_warning", unit)]
    if _has(q, "peers"):
        blocks = all_blocks_in(question) or ([u] if ut == "block" else [])
        calls = [("find_peers", {"block": b, "election_only": _has(q, "election")}) for b in blocks[:2]]
        return calls or [("where_did_it_change", {**unit, "metric": metric})]
    if _has(q, "schools"):
        conds = []
        if _has(q, "attendance"):
            conds.append("attendance_decline")
        if _has(q, "vacancy"):
            conds.append("maths_vacancy")
        if _has(q, "low"):
            conds.append("low_numeracy")
        if _has(q, "infra"):
            conds.append("infra_gap")
        return [
            ("find_schools_with", {**unit, "conditions": conds})
            if conds
            else ("intervention_radar", {**unit, "min_flags": 2})
        ]
    if _has(q, "actions"):
        return [("list_actions", unit)]
    if _has(q, "quality"):
        return [("data_quality", unit)]
    if _has(q, "expected"):
        return [("expected_vs_actual", unit), ("diagnose", {**unit, "metric": metric})]
    if _has(q, "largest"):
        return [("where_did_it_change", {**unit, "metric": metric}), ("get_trend", {**unit, "metric": metric})]
    if _has(q, "trend"):
        return [("get_trend", {**unit, "metric": metric}), ("where_did_it_change", {**unit, "metric": metric})]
    calls = [("diagnose", {**unit, "metric": metric})]
    if ut in ("state", "district"):
        calls.append(("where_did_it_change", {**unit, "metric": metric}))
    return calls


def unresolved_text(u: dict, lang: str) -> str:
    kind = u.get("kind")
    if kind == "remainder":
        return t(lang, "q_remainder", pp=u.get("pp"))
    if kind == "insufficient":
        return t(lang, "q_insufficient", factor=factor(lang, u.get("factor", "")), cov=u.get("coverage_pct"))
    if kind == "conflicting":
        return t(lang, "q_conflicting", factor=factor(lang, u.get("factor", "")))
    if kind == "child":
        return t(lang, f"q_child_{u.get('child_verdict')}", child=u.get("child"), pp=u.get("pp"))
    if kind == "noncomparable":
        return t(lang, "q_noncomparable")
    if kind == "too_few":
        return t(lang, "q_too_few")
    return u.get("text", "")


def warning_text(w: dict, lang: str) -> str:
    if w["kind"] == "low":
        return t(lang, "w_low", source=t(lang, f"src_{w['source']}"), pct=w["pct"])
    if w["kind"] == "thin":
        return t(lang, "w_thin", n=w["n"])
    return t(lang, "w_comparability")


def compose(results: list[tuple[str, dict, dict]], lang: str = "en") -> dict:
    """Build {summary, findings, next_steps} from tool outputs, in the requested language."""
    summary, findings, steps = [], [], []
    pp = t(lang, "pp")
    for name, _args, r in results:
        if "error" in r:
            findings.append(
                {"label": "unresolved_question", "text": t(lang, "no_data", err=r["error"]), "evidence": []}
            )
            continue
        if name == "diagnose":
            o = r["outcome"]
            vt = t(lang, f"v_{r['verdict']}")
            if o.get("change_pp") is not None:
                summary.append(
                    t(
                        lang,
                        "diag_summary",
                        unit=r["unit"],
                        period=r["period"],
                        change=o["change_pp"],
                        a=o["baseline"],
                        b=o["latest"],
                        n=o["schools_compared"],
                        verdict=vt,
                    )
                )
                findings.append(
                    {
                        "label": "observed_fact",
                        "evidence": [o["evidence"]],
                        "period": r["period"],
                        "text": t(
                            lang,
                            "outcome",
                            n=o["schools_compared"],
                            a=o["baseline"],
                            b=o["latest"],
                            change=_sign(o["change_pp"]),
                        ),
                    }
                )
            else:
                summary.append(t(lang, "diag_summary_nc", unit=r["unit"], verdict=vt))
            strong = []
            for s in r["signals"]:
                if s["strength"] not in ("HIGH", "MEDIUM"):
                    continue
                strong.append(s)
                fk = s.get("factor_key") or FACTOR_KEY_BY_LABEL.get(s["factor"], s["factor"])
                where = ""
                if s.get("affected_units"):
                    where = t(
                        lang,
                        "most_affected",
                        list=", ".join(f"{a['unit']} ({_sign(a['change'])})" for a in s["affected_units"][:3]),
                    )
                findings.append(
                    {
                        "label": "associated_signal",
                        "evidence": [s["evidence"]],
                        "text": t(
                            lang,
                            "signal",
                            factor=factor(lang, fk),
                            a=s["baseline"],
                            b=s["latest"],
                            change=_sign(s["change"]),
                            strength=t(lang, "strong" if s["strength"] == "HIGH" else "moderate"),
                            contrib=s["contribution_pp"],
                            r=s["assoc_r"],
                        )
                        + where,
                    }
                )
            for c in r["context"]:
                findings.append(
                    {
                        "label": "observed_fact",
                        "evidence": [c["evidence"]],
                        "text": t(
                            lang,
                            "context",
                            event=event(lang, c["event"]),
                            tdl=c["avg_teacher_days_lost"],
                            n=c["blocks_affected"],
                        ),
                    }
                )
            for u in r["unresolved"]:
                findings.append(
                    {"label": "unresolved_question", "evidence": [u["evidence"]], "text": unresolved_text(u, lang)}
                )
            fo = r.get("field_observations")
            if fo:
                items = ITEM.get(lang, ITEM["en"])
                findings.append(
                    {
                        "label": "observed_fact",
                        "evidence": [fo["evidence"]],
                        "period": fo["period"],
                        "text": FIELD.get(lang, FIELD["en"]).format(
                            n=fo["n_visits"],
                            s=fo["avg_score"],
                            w="; ".join(f"{items[w['item']]} ({w['pct_yes']}%)" for w in fo["weakest"]),
                        ),
                    }
                )
            steps += _steps_for(strong, r, lang)
        elif name == "get_trend":
            pts = ", ".join(f"{p['year']}: {p['value']}%" for p in r["points"] if p["value"] is not None)
            findings.append(
                {
                    "label": "observed_fact",
                    "evidence": [r["evidence"]],
                    "text": t(lang, "trend", pts=pts, change=_sign(r["change_pp"])),
                }
            )
            if r["change_pp"] is not None:
                summary.append(
                    t(lang, "trend_decline" if r["change_pp"] <= -3 else "trend_stable", change=_sign(r["change_pp"]))
                )
            if r.get("caveats"):
                findings.append(
                    {
                        "label": "unresolved_question",
                        "evidence": [r.get("caveat_evidence", r["evidence"])],
                        "text": t(lang, "caveat"),
                    }
                )
        elif name == "where_did_it_change":
            kids = r["children"][:3]
            if kids:
                lst = ", ".join(f"{c['name']} ({_sign(c['change_pp'])} {pp})" for c in kids)
                findings.append(
                    {
                        "label": "observed_fact",
                        "evidence": [c["evidence"] for c in kids],
                        "period": r["period"],
                        "text": t(lang, "largest", list=lst),
                    }
                )
                if not summary:
                    summary.append(t(lang, "largest_summary", name=kids[0]["name"], change=_sign(kids[0]["change_pp"])))
            if r.get("not_comparable"):
                findings.append(
                    {
                        "label": "unresolved_question",
                        "evidence": [r["not_comparable_evidence"]],
                        "text": t(lang, "noncomp_units", list=", ".join(r["not_comparable"])),
                    }
                )
        elif name == "find_peers":
            s = r.get("summary")
            if s:
                txt = t(
                    lang,
                    "peers",
                    period=r["period"],
                    n=len(r["peers"]),
                    scope=t(lang, "scope_election" if r["election_only"] else "scope_plain"),
                    lo=s["low"],
                    hi=s["high"],
                    med=s["median"],
                    block=r["block"],
                    u=s["unit_change"],
                    gap=abs(s["gap_vs_median"]),
                    dir=t(lang, "dir_below" if s["gap_vs_median"] < 0 else "dir_above"),
                )
                findings.append(
                    {"label": "observed_fact", "evidence": [r["summary_evidence"]], "period": r["period"], "text": txt}
                )
                summary.append(txt)
                if r["election_only"]:
                    big = s["gap_vs_median"] <= -4
                    findings.append(
                        {
                            "label": "associated_signal" if big else "observed_fact",
                            "evidence": [r["summary_evidence"]],
                            "period": r["period"],
                            "text": t(lang, "peers_big" if big else "peers_small"),
                        }
                    )
        elif name in ("intervention_radar", "find_schools_with"):
            if name == "intervention_radar":
                txt = t(lang, "radar", flagged=r["n_flagged"], n=r["n_schools"], priority=r["n_priority"])
                top = r["top_schools"][:4]
            else:
                conds = "; ".join(rule(lang, c) for c in r.get("condition_keys", []))
                txt = t(lang, "schools_match", n=r["n_matching"], conds=conds)
                top = r["schools"][:4]
            findings.append({"label": "observed_fact", "evidence": [r["evidence"]], "text": txt})
            if top:
                findings.append(
                    {
                        "label": "observed_fact",
                        "evidence": [r["evidence"]],
                        "text": t(lang, "examples", list="; ".join(f"{s['school']} ({s['block']})" for s in top)),
                    }
                )
            summary.append(txt)
            steps.append(t(lang, "step_radar"))
        elif name == "list_actions":
            s = r["summary"]
            txt = t(
                lang,
                "actions",
                total=s["total"],
                overdue=s["overdue"],
                awaiting=s["awaiting_verification"],
                improved=s["implemented_improved"],
                notimpl=s["not_implemented"],
            )
            findings.append({"label": "observed_fact", "evidence": [r["evidence"]], "text": txt})
            summary.append(txt)
        elif name == "data_quality":
            txt = t(lang, "quality", c=r["confidence"], label=t(lang, f"q_{r['label']}"))
            findings.append({"label": "observed_fact", "evidence": [r["evidence"]], "text": txt})
            for w in r.get("warning_items", [])[:4]:
                findings.append(
                    {
                        "label": "unresolved_question",
                        "evidence": [r.get("warnings_evidence", r["evidence"])],
                        "text": warning_text(w, lang),
                    }
                )
            summary.append(txt)
        elif name == "expected_vs_actual":
            txt = (
                t(lang, "expected", a=r["actual"], e=r["expected"], g=_sign(r["gap_pp"]))
                + " "
                + t(lang, f"e_{r['category']}")
            )
            findings.append(
                {"label": "associated_signal", "evidence": [r["evidence"]], "period": r["year"], "text": txt}
            )
            summary.append(txt)
        elif name == "early_warning":
            tbl = EW.get(lang, EW["en"])
            if not r["alerts"]:
                findings.append({"label": "observed_fact", "evidence": [r["evidence"]], "text": tbl["none"]})
            for a in r["alerts"][:5]:
                txt = tbl[a["kind"]].format(
                    block=a["block"],
                    d=a.get("avg_drop"),
                    n=a.get("n"),
                    of=a.get("of"),
                    v=a.get("min_value"),
                    nb=a.get("n_blocks"),
                    months=", ".join(a.get("months", [])),
                )
                findings.append({"label": "observed_fact", "evidence": [r["evidence"]], "text": txt})
                if len(summary) == 0:
                    summary.append(txt)
        elif name == "get_school":
            for f in r.get("findings", []):
                findings.append({**f, "text": school_text(f, lang)})
            if r.get("findings"):
                summary.append(findings[-len(r["findings"])]["text"])
            steps += [t(lang, k) for k in r.get("step_keys", [])]
    summary = [s for s in summary if s]
    if not summary:
        summary = [t(lang, "default")]
    return {"summary": " ".join(summary[:2]), "findings": findings, "next_steps": list(dict.fromkeys(steps))[:4]}


SCHOOL_TXT = {
    "en": {
        "num": "{name}: numeracy {b}% in {y1} ({change} points since {y0}).",
        "att": "Student attendance {b}% ({change} points since {y0}).",
        "vac": "Maths teacher posts: {vac} of {san} empty.",
        "flags": "Needs support because: {list}.",
    },
    "hi": {
        "num": "{name}: {y1} में संख्या ज्ञान {b}% ({y0} से {change} अंक)।",
        "att": "छात्र उपस्थिति {b}% ({y0} से {change} अंक)।",
        "vac": "गणित शिक्षक पद: {san} में से {vac} खाली।",
        "flags": "सहायता की ज़रूरत क्योंकि: {list}।",
    },
    "mr": {
        "num": "{name}: {y1} मध्ये संख्याज्ञान {b}% ({y0} पासून {change} गुण).",
        "att": "विद्यार्थी उपस्थिती {b}% ({y0} पासून {change} गुण).",
        "vac": "गणित शिक्षक पदे: {san} पैकी {vac} रिक्त.",
        "flags": "मदतीची गरज कारण: {list}.",
    },
    "bn": {
        "num": "{name}: {y1}-এ সংখ্যাজ্ঞান {b}% ({y0} থেকে {change} পয়েন্ট)।",
        "att": "ছাত্রছাত্রীর উপস্থিতি {b}% ({y0} থেকে {change} পয়েন্ট)।",
        "vac": "গণিত শিক্ষক পদ: {san}টির মধ্যে {vac}টি শূন্য।",
        "flags": "সহায়তা দরকার কারণ: {list}।",
    },
    "ta": {
        "num": "{name}: {y1} இல் எண்ணறிவு {b}% ({y0} முதல் {change} புள்ளிகள்).",
        "att": "மாணவர் வருகை {b}% ({y0} முதல் {change} புள்ளிகள்).",
        "vac": "கணித ஆசிரியர் பணியிடங்கள்: {san} இல் {vac} காலி.",
        "flags": "உதவி தேவை, ஏனெனில்: {list}.",
    },
    "te": {
        "num": "{name}: {y1} లో సంఖ్యా జ్ఞానం {b}% ({y0} నుండి {change} పాయింట్లు).",
        "att": "విద్యార్థుల హాజరు {b}% ({y0} నుండి {change} పాయింట్లు).",
        "vac": "గణిత ఉపాధ్యాయ పోస్టులు: {san} లో {vac} ఖాళీ.",
        "flags": "సహాయం అవసరం ఎందుకంటే: {list}.",
    },
}


def school_text(f: dict, lang: str) -> str:
    p = f["params"]
    tbl = SCHOOL_TXT.get(lang, SCHOOL_TXT["en"])
    if f["code"] == "flags":
        return tbl["flags"].format(list="; ".join(rule(lang, k) for k in p["flags"]))
    return tbl[f["code"]].format(**{k: (_sign(v) if k == "change" else v) for k, v in p.items()})


def _steps_for(strong: list[dict], r: dict, lang: str) -> list[str]:
    out = []
    for s in strong:
        fk = s.get("factor_key") or FACTOR_KEY_BY_LABEL.get(s["factor"], "")
        out.append(
            t(
                lang,
                {
                    "maths_vacancy": "step_vacancy",
                    "student_attendance": "step_attendance",
                    "teacher_attendance": "step_teacher",
                    "infrastructure": "step_infra",
                }.get(fk, "step_radar"),
            )
        )
    if any(u.get("kind") == "remainder" for u in r["unresolved"]):
        out.append(t(lang, "step_observe"))
    if r["verdict"] == "INSUFFICIENT_EVIDENCE":
        out.append(t(lang, "step_data"))
    if r["verdict"] == "NON_COMPARABLE":
        out.append(t(lang, "step_compare"))
    if not out:
        out.append(t(lang, "step_monitor"))
    return out
