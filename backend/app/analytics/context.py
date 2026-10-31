"""Context calendar (disruption timeline) and the Instinct-vs-Evidence review order."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import db
from .common import canonical_unit, r1, subset


def timeline(unit_type: str, unit: str | None) -> dict:
    """Monthly student/teacher attendance for the unit, overlaid with context events."""
    unit = canonical_unit(unit_type, unit)
    codes = set(subset(unit_type, unit).udise_code)
    att = (
        db.read_df("SELECT udise_code, year, month, student_att_pct, teacher_att_pct FROM attendance_monthly")
        if db.table_exists("attendance_monthly")
        else pd.DataFrame()
    )
    series = []
    if not att.empty:
        att = att[att.udise_code.isin(codes)]
        g = (
            att.groupby(["year", "month"])
            .agg(
                student=("student_att_pct", "mean"),
                teacher=("teacher_att_pct", "mean"),
                schools=("udise_code", "nunique"),
            )
            .reset_index()
        )
        g = g.sort_values(["year", "month"])
        series = [
            {
                "period": f"{int(r.year)}-{int(r.month):02d}",
                "student": r1(r.student),
                "teacher": r1(r.teacher),
                "schools_reporting": int(r.schools),
            }
            for r in g.itertuples()
        ]
    events = []
    if db.table_exists("context_events"):
        ev = db.read_df("SELECT * FROM context_events")
        blocks = {b.casefold() for b in subset(unit_type, unit).block.unique()}
        ev = ev[ev.block.fillna("").str.casefold().isin(blocks) | (ev.block.fillna("").str.upper() == "ALL")]
        for (name, ay), g in ev.groupby(["event", "academic_year"]):
            local = g[g.block.str.upper() != "ALL"]
            events.append(
                {
                    "event": name,
                    "academic_year": ay,
                    "start": g.start.min(),
                    "end": g.end.max(),
                    "blocks": int(local.block.nunique()),
                    "avg_teacher_days_lost": r1(local.teacher_days_lost.mean()) if len(local) else 0,
                    "source": g.source.iloc[0],
                }
            )
    return {
        "unit_type": unit_type,
        "unit": unit,
        "series": series,
        "events": events,
        "label": "Context overlay — associations, not causes",
    }


def review_order(district: str) -> dict:
    """Evidence-based review order of a district's blocks, with the reason for each position."""
    from .diagnose import diagnose
    from .expected import residual_ranking
    from .radar import radar

    district = canonical_unit("district", district)
    res = {r["unit"]: r for r in residual_ranking("block")}
    rows = []
    for b in sorted(subset("district", district).block.unique()):
        d = diagnose("block", b)
        r = radar("block", b, min_flags=2, limit=0)
        strong = [s for s in d["signals"] if s["classification"] in ("HIGH", "MEDIUM")]
        rows.append(
            {
                "block": b,
                "change_pp": d["outcome"].get("change_pp"),
                "verdict": d["verdict"],
                "residual_pp": res.get(b, {}).get("residual"),
                "expected": res.get(b, {}).get("expected"),
                "actual": res.get(b, {}).get("actual"),
                "priority_schools": r["n_priority"],
                "flagged_schools": r["n_flagged"],
                "n_schools": r["n_schools"],
                "signals": [
                    {
                        "label": s["label"],
                        "factor": s["factor"],
                        "classification": s["classification"],
                        "change": s.get("change"),
                    }
                    for s in strong
                ],
                "unexplained_pp": next((u.get("remainder_pp") for u in d["unresolved"] if "remainder_pp" in u), None),
                "data_confidence": d["data_confidence"],
            }
        )
    df = pd.DataFrame(rows)

    def z(s: pd.Series) -> pd.Series:
        s = pd.to_numeric(s, errors="coerce").fillna(0)
        return (s - s.mean()) / (s.std(ddof=0) or 1)

    df["attention"] = z(-df.change_pp) + z(-df.residual_pp) + z(df.priority_schools / df.n_schools.clip(lower=1))
    df = df.sort_values("attention", ascending=False)
    out = []
    for i, r in enumerate(df.to_dict("records")):
        reasons = []
        if r["change_pp"] is not None and r["change_pp"] <= -5:
            reasons.append(f"Numeracy {r['change_pp']} pp")
        if r["residual_pp"] is not None and r["residual_pp"] <= -4:
            reasons.append(f"{abs(r['residual_pp'])} pp below what its conditions predict")
        for s in r["signals"][:2]:
            reasons.append(f"{s['label']} ({s['classification'].lower()} signal)")
        if r["unexplained_pp"] is not None and not pd.isna(r["unexplained_pp"]):
            reasons.append(f"{abs(r['unexplained_pp'])} pp unexplained")
        if r["verdict"] in ("INSUFFICIENT_EVIDENCE", "NON_COMPARABLE"):
            reasons.append(r["verdict"].replace("_", " ").lower())
        items = []
        if r["change_pp"] is not None and r["change_pp"] <= -5:
            items.append({"kind": "decline", "pp": r["change_pp"]})
        if r["residual_pp"] is not None and r["residual_pp"] <= -4:
            items.append({"kind": "below_expected", "pp": abs(r["residual_pp"])})
        for sg in r["signals"][:2]:
            items.append(
                {"kind": "signal", "factor": sg["factor"], "cls": sg["classification"], "change": sg["change"]}
            )
        if r["unexplained_pp"] is not None and not pd.isna(r["unexplained_pp"]):
            items.append({"kind": "unexplained", "pp": abs(r["unexplained_pp"])})
        if r["verdict"] in ("INSUFFICIENT_EVIDENCE", "NON_COMPARABLE"):
            items.append({"kind": r["verdict"].lower()})
        r.update(position=i + 1, reasons=reasons, reason_items=items, attention=round(float(r["attention"]), 2))
        out.append({k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()})
    return {
        "district": district,
        "blocks": out,
        "method": "Ordered by combined evidence: size of decline, gap vs conditions-based expectation, and share "
        "of schools with 3+ deteriorating indicators. Each position comes with its reasons.",
    }
