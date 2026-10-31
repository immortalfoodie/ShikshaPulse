"""Peer benchmarking: how did *similar* blocks change over the same period (optionally election-affected)?"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import agg, baseline_latest, canonical_unit, panel, r1

PEER_FEATURES = {
    "n_schools": "Number of schools",
    "enrolment": "Total enrolment",
    "rural_share": "Rural share",
    "baseline_numeracy": "Baseline numeracy",
    "baseline_vacancy": "Baseline maths vacancy",
    "baseline_attendance": "Baseline attendance",
    "baseline_infra": "Baseline infrastructure",
}
ELECTION_DAYS = 10.0


def block_table(metric: str = "numeracy") -> pd.DataFrame:
    p = panel()
    y0, y1 = baseline_latest()
    rows = []
    for (d, b), g in p.groupby(["district", "block"]):
        a, z = g[g.academic_year == y0], g[g.academic_year == y1]
        base_v, late_v = agg(a, metric, True), agg(z, metric, True)
        rows.append(
            {
                "district": d,
                "block": b,
                "n_schools": g.udise_code.nunique(),
                "enrolment": float(a.enrolment.sum()),
                "rural_share": float(a.rural.mean()),
                "baseline_numeracy": base_v,
                "baseline_vacancy": float(a.maths_vacancy.mean() * 100) if a.maths_vacancy.notna().any() else np.nan,
                "baseline_attendance": float(a.student_att.mean()) if a.student_att.notna().any() else np.nan,
                "baseline_infra": float(a.infra_index.mean() * 100) if a.infra_index.notna().any() else np.nan,
                "latest": late_v,
                "change_pp": r1(late_v - base_v) if base_v is not None and late_v is not None else None,
                "teacher_days_lost": float(z.teacher_days_lost.mean()),
            }
        )
    return pd.DataFrame(rows)


def peers(
    block: str, k: int = 5, election_only: bool = False, metric: str = "numeracy", other_districts: bool = True
) -> dict:
    block = canonical_unit("block", block)
    t = block_table(metric)
    feats = list(PEER_FEATURES)
    X = t[feats].astype(float)
    X = X.fillna(X.mean())
    Z = (X - X.mean()) / X.std(ddof=0).replace(0, 1)
    me = t.index[t.block == block][0]
    dist = np.sqrt(((Z - Z.loc[me]) ** 2).sum(axis=1))
    t = t.assign(distance=dist.round(2))
    cand = t[(t.block != block) & t.change_pp.notna()]
    if other_districts:
        cand = cand[cand.district != t.loc[me, "district"]]
    if election_only:
        cand = cand[cand.teacher_days_lost >= ELECTION_DAYS]
    top = cand.sort_values("distance").head(k)
    mine = t.loc[me]
    ch = top.change_pp.dropna()
    y0, y1 = baseline_latest()
    summary = None
    if len(ch) and mine.change_pp is not None and not pd.isna(mine.change_pp):
        lo, hi, med = r1(ch.min()), r1(ch.max()), r1(ch.median())
        gap = r1(mine.change_pp - med)
        scope = ("similar election-affected blocks" if election_only else "similar blocks") + (
            " in other districts" if other_districts else ""
        )
        summary = {
            "low": lo,
            "high": hi,
            "median": med,
            "unit_change": r1(mine.change_pp),
            "gap_vs_median": gap,
            "text": f"Over {y0} → {y1}, {len(ch)} {scope} changed by {lo} to {hi} pp (median {med} pp); "
            f"{block} changed by {r1(mine.change_pp)} pp, {abs(gap)} pp "
            f"{'below' if gap < 0 else 'above'} the peer median.",
        }
        if election_only:
            summary["interpretation"] = (
                "Peers with comparable election duty did not show a change of this size, so election disruption "
                "alone is not consistent with the full change. Investigate the other signals."
                if gap <= -4
                else "The change is within the range seen in similar election-affected blocks; election disruption is "
                "a plausible shared context."
            )

    def row(r):
        return {
            "block": r.block,
            "district": r.district,
            "distance": float(r.distance),
            "baseline": r1(r.baseline_numeracy),
            "latest": r1(r.latest),
            "change_pp": r1(r.change_pp),
            "teacher_days_lost": r1(r.teacher_days_lost),
            "rural_share": round(float(r.rural_share), 2),
            "baseline_vacancy": r1(r.baseline_vacancy),
            "baseline_attendance": r1(r.baseline_attendance),
            "n_schools": int(r.n_schools),
        }

    return {
        "block": block,
        "metric": metric,
        "election_only": election_only,
        "other_districts": other_districts,
        "k": k,
        "baseline_year": y0,
        "latest_year": y1,
        "election_threshold_days": ELECTION_DAYS,
        "unit": row(mine),
        "peers": [row(r) for _, r in top.iterrows()],
        "summary": summary,
        "matched_on": [PEER_FEATURES[f] for f in feats],
        "method": "k-nearest neighbours on standardised baseline-year characteristics",
    }
