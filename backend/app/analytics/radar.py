"""Intervention Radar: schools where several independent indicators deteriorate together.

Deliberately not a "worst schools" ranking — each school is flagged with the reasons, and
missing data is shown as missing rather than counted against the school.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import baseline_latest, canonical_unit, panel, r1, subset

RULES = {
    "low_numeracy": "Numeracy in the state's bottom quarter",
    "numeracy_decline": "Numeracy fell ≥10 pp since baseline",
    "attendance_decline": "Student attendance fell ≥8 pp",
    "maths_vacancy": "At least a third of maths posts vacant",
    "infra_gap": "Half or more of tracked facilities missing",
    "teacher_attendance": "Teacher attendance below 80%",
}


def radar(unit_type: str, unit: str | None, min_flags: int = 2, limit: int = 60) -> dict:
    unit = canonical_unit(unit_type, unit)
    y0, y1 = baseline_latest()
    p = panel()
    p25 = float(p[(p.academic_year == y1) & p.comparable].numeracy.quantile(0.25))
    df = subset(unit_type, unit)
    a = df[df.academic_year == y0].set_index("udise_code")
    b = df[df.academic_year == y1].set_index("udise_code")
    b = b.join(a[["numeracy", "student_att", "comparable"]].add_suffix("_base"))
    out, counts = [], dict.fromkeys(RULES, 0)
    for code, r in b.iterrows():
        flags, missing = [], []
        comp = bool(r.comparable) and bool(r.comparable_base)
        if pd.isna(r.numeracy) or not r.comparable:
            missing.append("comparable numeracy")
        else:
            if r.numeracy < p25:
                flags.append("low_numeracy")
            if comp and not pd.isna(r.numeracy_base) and r.numeracy - r.numeracy_base <= -10:
                flags.append("numeracy_decline")
        if pd.isna(r.student_att) or pd.isna(r.student_att_base):
            missing.append("attendance")
        elif r.student_att - r.student_att_base <= -8:
            flags.append("attendance_decline")
        if pd.isna(r.maths_vacancy):
            missing.append("teacher posts")
        elif r.maths_vacancy >= 0.33 and (r.maths_vacant or 0) >= 1:
            flags.append("maths_vacancy")
        if pd.isna(r.infra_index):
            missing.append("infrastructure")
        elif r.infra_index <= 0.5:
            flags.append("infra_gap")
        if not pd.isna(r.teacher_att) and r.teacher_att < 80:
            flags.append("teacher_attendance")
        for f in flags:
            counts[f] += 1
        if len(flags) >= min_flags:
            out.append(
                {
                    "udise_code": code,
                    "school_name": r.school_name,
                    "block": r.block,
                    "district": r.district,
                    "flags": flags,
                    "n_flags": len(flags),
                    "reasons": [RULES[f] for f in flags],
                    "missing": missing,
                    "tier": "priority_support" if len(flags) >= 3 else "watch",
                    "numeracy": r1(r.numeracy),
                    "numeracy_change": r1(r.numeracy - r.numeracy_base)
                    if comp and not pd.isna(r.numeracy_base)
                    else None,
                    "attendance": r1(r.student_att),
                    "attendance_change": r1(r.student_att - r.student_att_base)
                    if not pd.isna(r.student_att) and not pd.isna(r.student_att_base)
                    else None,
                    "maths_vacancy": r1(r.maths_vacancy * 100) if not pd.isna(r.maths_vacancy) else None,
                    "infra": r1(r.infra_index * 100) if not pd.isna(r.infra_index) else None,
                    "teacher_att": r1(r.teacher_att),
                }
            )
    out.sort(key=lambda s: (-s["n_flags"], s["numeracy_change"] if s["numeracy_change"] is not None else 0))
    matrix = {f: int(sum(1 for s in out if f in s["flags"])) for f in RULES}
    return {
        "unit_type": unit_type,
        "unit": unit,
        "latest_year": y1,
        "baseline_year": y0,
        "min_flags": min_flags,
        "rules": RULES,
        "low_numeracy_threshold": r1(p25),
        "n_schools": len(b),
        "n_flagged": len(out),
        "n_priority": sum(1 for s in out if s["tier"] == "priority_support"),
        "flag_counts_all_schools": counts,
        "flag_counts_flagged": matrix,
        "schools": out[:limit],
        "note": "Schools are flagged for support based on multiple indicators, not ranked. Missing data is "
        "listed separately and never counted as a flag.",
    }


def overlap_matrix(unit_type: str, unit: str | None) -> dict:
    """Pairwise co-occurrence of flags among schools in the unit (for the radar heat-map)."""
    r = radar(unit_type, unit, min_flags=1, limit=0)
    keys = list(RULES)
    m = np.zeros((len(keys), len(keys)), dtype=int)
    schools = radar(unit_type, unit, min_flags=1, limit=100000)["schools"]
    for s in schools:
        for i, a in enumerate(keys):
            if a in s["flags"]:
                for j, b in enumerate(keys):
                    if b in s["flags"]:
                        m[i, j] += 1
    return {"keys": keys, "labels": [RULES[k] for k in keys], "matrix": m.tolist(), "n_schools": r["n_schools"]}
