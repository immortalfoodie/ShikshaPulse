"""Three-year trends, decline decomposition ("where did it fall?") and unit overview KPIs."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (CHILD, METRICS, agg, baseline_latest, canonical_unit, comparability_flags, panel, r1,
                     source_files, subset, unit_label, years)


def trend(metric: str, unit_type: str, unit: str | None) -> dict:
    unit = canonical_unit(unit_type, unit)
    df = subset(unit_type, unit)
    ys = years()
    is_assess = METRICS[metric]["source"] == "assessment"
    points = []
    for y in ys:
        d = df[df.academic_year == y]
        all_v = agg(d, metric)
        comp_v = agg(d, metric, comparable_only=True) if is_assess else all_v
        n_comp = int((d.comparable & d[metric].notna()).sum()) if is_assess else int(d[metric].notna().sum())
        points.append({"year": y, "value": comp_v, "value_all_instruments": all_v, "n_schools": n_comp,
                       "n_total": int(len(d)), "comparable": (comp_v is not None) if is_assess else True})
    first = next((p for p in points if p["value"] is not None), None)
    last = next((p for p in reversed(points) if p["value"] is not None), None)
    change = r1(last["value"] - first["value"]) if first and last and first is not last else None
    flags = comparability_flags(unit_type, unit) if is_assess else []
    caveats = []
    for f in flags:
        caveats.append(f"{f['from_year']}→{f['to_year']}: {f['detail']}")
    if is_assess and points and points[-1]["value"] is None and points[-1]["value_all_instruments"] is not None:
        caveats.append(f"{points[-1]['year']} scores come from a different instrument and are not comparable; "
                       f"the trend stops at {last['year'] if last else 'n/a'}.")
    return {"metric": metric, "label": METRICS[metric]["label"], "unit_type": unit_type, "unit": unit,
            "unit_label": unit_label(unit_type, unit), "points": points,
            "baseline_year": first["year"] if first else None, "latest_year": last["year"] if last else None,
            "change_pp": change, "caveats": caveats, "comparability_flags": flags,
            "sources": source_files(METRICS[metric]["source"])}


def breakdown(metric: str, unit_type: str, unit: str | None) -> dict:
    """Children of a unit with baseline/latest/change, and each child's share of the parent's change."""
    unit = canonical_unit(unit_type, unit)
    child = CHILD[unit_type]
    if child is None:
        raise ValueError("Schools have no children")
    df = subset(unit_type, unit)
    y0, y1 = baseline_latest()
    col = "udise_code" if child == "school" else child
    meta = METRICS[metric]
    is_assess = meta["source"] == "assessment"
    rows = []
    total_w = df[df.academic_year == y0][meta.get("weight", metric)].sum() if meta.get("weight") else len(
        df[df.academic_year == y0])
    parent_change = trend(metric, unit_type, unit)["change_pp"]
    for key, g in df.groupby(col):
        a = agg(g[g.academic_year == y0], metric, comparable_only=is_assess)
        b = agg(g[g.academic_year == y1], metric, comparable_only=is_assess)
        change = r1(b - a) if a is not None and b is not None else None
        w = (g[g.academic_year == y0][meta["weight"]].sum() if meta.get("weight") else len(g[g.academic_year == y0]))
        share = (w / total_w) if total_w else 0
        contrib = r1(change * share) if change is not None else None
        name = g.school_name.iloc[0] if child == "school" else key
        rows.append({"unit_type": child, "unit": key, "name": name, "baseline": a, "latest": b, "change_pp": change,
                     "weight_share": round(float(share), 3), "contribution_pp": contrib,
                     "comparable": not (is_assess and b is None and agg(g[g.academic_year == y1], metric) is not None),
                     "district": g.district.iloc[0], "block": g.block.iloc[0]})
    better = meta["higher_is_better"]
    rows.sort(key=lambda r: (r["change_pp"] is None, (r["change_pp"] or 0) * (1 if better else -1)))
    return {"metric": metric, "unit_type": unit_type, "unit": unit, "child_type": child, "baseline_year": y0,
            "latest_year": y1, "parent_change_pp": parent_change, "children": rows}


def overview(unit_type: str, unit: str | None) -> dict:
    """KPI tiles for a unit, with state reference and rank among siblings."""
    unit = canonical_unit(unit_type, unit)
    df = subset(unit_type, unit)
    y0, y1 = baseline_latest()
    state = panel()
    kpis = []
    for m in ["numeracy", "literacy", "student_att", "teacher_att", "maths_vacancy", "infra_index"]:
        is_assess = METRICS[m]["source"] == "assessment"
        t = trend(m, unit_type, unit)
        latest = t["points"][-1]["value"] if t["points"] else None
        st = agg(state[state.academic_year == y1], m, comparable_only=is_assess)
        kpis.append({"metric": m, "label": METRICS[m]["label"], "latest": latest,
                     "latest_year": y1, "baseline": t["points"][0]["value"] if t["points"] else None,
                     "change_pp": t["change_pp"], "state_latest": st,
                     "higher_is_better": METRICS[m]["higher_is_better"],
                     "spark": [p["value"] for p in t["points"]], "caveats": t["caveats"]})
    rank = None
    if unit_type in ("district", "block"):
        sibs = state if unit_type == "district" else state[state.district == df.district.iloc[0]]
        vals = []
        for key, g in sibs.groupby(unit_type):
            v = agg(g[g.academic_year == y1], "numeracy", comparable_only=True)
            if v is not None:
                vals.append((key, v))
        vals.sort(key=lambda x: -x[1])
        pos = next((i for i, (k, _) in enumerate(vals) if k == unit), None)
        all_units = state if unit_type == "district" else state
        vals_state = []
        for key, g in all_units.groupby(unit_type):
            v = agg(g[g.academic_year == y1], "numeracy", comparable_only=True)
            if v is not None:
                vals_state.append((key, v))
        vals_state.sort(key=lambda x: -x[1])
        pos_state = next((i for i, (k, _) in enumerate(vals_state) if k == unit), None)
        rank = {"metric": "numeracy", "within": "district" if unit_type == "block" else "state",
                "position": (pos + 1) if pos is not None else None, "of": len(vals),
                "state_position": (pos_state + 1) if pos_state is not None else None, "state_of": len(vals_state)}
    return {"unit_type": unit_type, "unit": unit, "unit_label": unit_label(unit_type, unit), "baseline_year": y0,
            "latest_year": y1, "kpis": kpis, "rank": rank, "n_schools": int(df.udise_code.nunique()),
            "n_blocks": int(df.block.nunique()), "n_districts": int(df.district.nunique())}


def tiles() -> list[dict]:
    """Block tiles for the hex map: latest numeracy and change."""
    p = panel()
    y0, y1 = baseline_latest()
    out = []
    for (d, b), g in p.groupby(["district", "block"]):
        a = agg(g[g.academic_year == y0], "numeracy", True)
        c = agg(g[g.academic_year == y1], "numeracy", True)
        out.append({"district": d, "block": b, "latest": c, "change_pp": r1(c - a) if a is not None and c is not None
                    else None, "comparable": c is not None})
    return out


def school_profile(udise: str) -> dict:
    s = subset("school", udise)
    if s.empty:
        raise KeyError(udise)
    s = s.sort_values("academic_year")
    cols = ["academic_year", "numeracy", "literacy", "student_att", "teacher_att", "maths_vacancy",
            "maths_sanctioned", "maths_vacant", "infra_index", "coverage_pct", "teacher_days_lost",
            "assessment_type", "scoring_scale", "months_reported"]
    rows = s[cols].replace({np.nan: None}).to_dict("records")
    for r in rows:
        for k in ("maths_vacancy", "infra_index"):
            if r[k] is not None:
                r[k] = round(r[k] * 100, 1)
        for k in ("numeracy", "literacy", "student_att", "teacher_att", "coverage_pct"):
            if r[k] is not None:
                r[k] = round(r[k], 1)
    first = s.iloc[0]
    return {"udise_code": udise, "school_name": first.school_name, "district": first.district, "block": first.block,
            "cluster": first.cluster, "rural": bool(first.rural) if pd.notna(first.rural) else None, "years": rows}
