"""Teacher-sharing suggestions: pair schools with empty maths posts with nearby schools (same cluster,
else same block) that have comfortable maths staffing. A proposal for the officer — never an order."""

from __future__ import annotations

import numpy as np

from .common import baseline_latest, canonical_unit, subset


def suggestions(unit_type: str, unit: str | None, schools: list[str] | None = None, limit: int = 12) -> dict:
    unit = canonical_unit(unit_type, unit)
    _, y1 = baseline_latest()
    df = subset(unit_type, unit)
    df = df[(df.academic_year == y1) & df.maths_sanctioned.notna()].copy()
    if df.empty:
        return {"unit": unit, "pairs": [], "receivers": 0}
    df["working"] = df.maths_sanctioned - df.maths_vacant.fillna(0)
    df["load"] = df.enrolment / df.working.where(df.working > 0)
    receivers = df[df.maths_vacant.fillna(0) >= 1]
    if schools:
        receivers = receivers[receivers.udise_code.isin(schools)]
    pairs, used = [], {}
    for blk, g in df.groupby("block"):
        med = float(np.nanmedian(g.load)) if g.load.notna().any() else np.nan
        donors = g[(g.working >= 2) & (g.load <= 0.6 * med)].sort_values("load")
        for _, r in receivers[receivers.block == blk].sort_values("maths_vacant", ascending=False).iterrows():
            same = donors[(donors.cluster == r.cluster) & (donors.udise_code != r.udise_code)]
            pool, scope = (same, "cluster") if len(same) else (donors[donors.udise_code != r.udise_code], "block")
            pool = pool[pool.udise_code.map(lambda c: used.get(c, 0) < 2)]
            if pool.empty:
                continue
            d = pool.iloc[0]
            used[d.udise_code] = used.get(d.udise_code, 0) + 1
            pairs.append(
                {
                    "receiver": {
                        "udise_code": r.udise_code,
                        "school_name": r.school_name,
                        "vacant": int(r.maths_vacant),
                        "sanctioned": int(r.maths_sanctioned),
                        "enrolment": int(r.enrolment or 0),
                    },
                    "donor": {
                        "udise_code": d.udise_code,
                        "school_name": d.school_name,
                        "working": int(d.working),
                        "enrolment": int(d.enrolment or 0),
                        "load": round(float(d.load), 0),
                    },
                    "scope": scope,
                    "cluster": r.cluster,
                    "block": blk,
                    "days_per_week": 2,
                }
            )
    pairs = pairs[:limit]
    return {
        "unit": unit,
        "year": y1,
        "receivers": len(receivers),
        "pairs": pairs,
        "method": "Donor = 2+ working maths teachers and pupils per maths teacher at most 60% of the block median. "
        "Same cluster preferred. Suggested as part-time sharing (2 days/week) for officer review.",
    }
