"""Data Quality Center: completeness, recency, duplicates, review backlog and a confidence score."""
from __future__ import annotations

import json

import pandas as pd

from .. import db
from .common import MIN_MONTHS, baseline_latest, canonical_unit, comparability_flags, panel, subset, years

WEIGHTS = {"assessment": 0.35, "attendance": 0.25, "teachers": 0.25, "udise": 0.15}


def completeness(df: pd.DataFrame) -> dict[str, float]:
    n = df.udise_code.nunique() or 1
    return {
        "assessment": round(float(df.numeracy.notna().sum() / n), 3),
        "attendance": round(float(df.months_reported.fillna(0).clip(upper=10).sum() / (n * 10)), 3),
        "teachers": round(float(df.maths_sanctioned.notna().sum() / n), 3),
        "udise": round(float(df.infra_index.notna().sum() / n), 3),
    }


def unit_quality(unit_type: str, unit: str | None) -> dict:
    unit = canonical_unit(unit_type, unit)
    df = subset(unit_type, unit)
    by_year = {}
    for y in years():
        by_year[y] = completeness(df[df.academic_year == y])
    y0, y1 = baseline_latest()
    pair = {k: min(by_year[y0][k], by_year[y1][k]) for k in WEIGHTS}
    review_share = _review_share(unit_type, unit, df)
    score = sum(WEIGHTS[k] * pair[k] for k in WEIGHTS) * (1 - review_share)
    thin = int((df.att_thin & (df.academic_year == y1)).sum())
    warnings, items = [], []
    for k, v in pair.items():
        if v < 0.6:
            items.append({"kind": "low", "source": k, "pct": round(v * 100)})
            warnings.append(f"{k.title()} data is only {v:.0%} complete in at least one comparison year — "
                            f"conclusions using it should be treated with caution.")
    if thin:
        items.append({"kind": "thin", "n": thin})
        warnings.append(f"{thin} school(s) reported fewer than {MIN_MONTHS} months of attendance in {y1}; "
                        "their attendance is treated as missing.")
    for f in comparability_flags(unit_type, unit):
        items.append({"kind": "comparability", "from_year": f["from_year"], "to_year": f["to_year"],
                      "reason": f["reason"]})
        warnings.append(f"Comparability: {f['detail']} ({f['from_year']}→{f['to_year']}).")
    return {"unit_type": unit_type, "unit": unit, "confidence": round(score * 100), "completeness_by_year": by_year,
            "comparison_completeness": pair, "review_share": round(review_share, 3), "warnings": warnings, "warning_items": items,
            "label": "High" if score >= 0.85 else "Moderate" if score >= 0.65 else "Low"}


def _review_share(unit_type: str, unit: str, df: pd.DataFrame) -> float:
    rows = db.query("SELECT block, district, n_rows FROM match_review WHERE status='pending'")
    if not rows:
        return 0.0
    r = pd.DataFrame(rows)
    if unit_type == "block":
        r = r[r.block.fillna("").str.casefold() == unit.casefold()]
    elif unit_type == "district":
        blocks = {b.casefold() for b in df.block.unique()}
        r = r[r.block.fillna("").str.casefold().isin(blocks)]
    elif unit_type == "school":
        return 0.0
    total = max(1, len(df) * 14)  # rough rows per school-year across sources
    return min(0.3, float(r.n_rows.sum()) / total)


def file_report() -> list[dict]:
    if not db.table_exists("ingest_files"):
        return []
    f = db.read_df("SELECT * FROM ingest_files")
    out = []
    for r in f.to_dict("records"):
        cols = json.loads(r.get("mapping") or "[]")
        out.append({
            "file": r["file"], "kind": r["kind"], "academic_year": r.get("academic_year"), "status": r.get("status"),
            "provenance": r.get("provenance"), "adapter": r.get("adapter"),
            "rows_in": r.get("rows_in"), "rows_out": r.get("rows_out"),
            "exact_duplicates": _i(r.get("exact_duplicates")), "key_duplicates": _i(r.get("key_duplicates")),
            "matched_by_code": _i(r.get("matched_by_code")), "matched_by_name": _i(r.get("matched_by_name")),
            "review_rows": _i(r.get("review_rows")), "review_groups": _i(r.get("review_groups")),
            "mapping_version": r.get("mapping_version"), "schema_version": r.get("schema_version"),
            "transforms": json.loads(r.get("transforms") or "[]"), "ai_note": r.get("ai_note"),
            "columns": cols, "wide_month_columns": _i(r.get("wide_month_columns")),
            "ingested_at": r.get("ingested_at"),
        })
    return out


def overall() -> dict:
    p = panel()
    if p.empty:
        return {"ready": False}
    by_year = {y: completeness(p[p.academic_year == y]) for y in years()}
    flags = db.read_df("SELECT * FROM comparability_flags").to_dict("records") if db.table_exists(
        "comparability_flags") else []
    state = unit_quality("state", None)
    return {"ready": True, "completeness_by_year": by_year, "comparability_flags": flags, "files": file_report(),
            "confidence": state["confidence"], "warnings": state["warnings"]}


def _i(v) -> int:
    try:
        return int(v) if v is not None and not pd.isna(v) else 0
    except (TypeError, ValueError):
        return 0
