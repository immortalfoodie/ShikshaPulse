"""Shared analytics helpers: panel loading (cached per warehouse version), unit filters, metrics."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .. import db

METRICS = {
    "numeracy": {
        "label": "Foundational numeracy",
        "unit": "%",
        "higher_is_better": True,
        "weight": "students_assessed",
        "source": "assessment",
    },
    "literacy": {
        "label": "Foundational literacy",
        "unit": "%",
        "higher_is_better": True,
        "weight": "students_assessed",
        "source": "assessment",
    },
    "student_att": {"label": "Student attendance", "unit": "%", "higher_is_better": True, "source": "attendance"},
    "teacher_att": {"label": "Teacher attendance", "unit": "%", "higher_is_better": True, "source": "attendance"},
    "maths_vacancy": {
        "label": "Maths teacher vacancy",
        "unit": "%",
        "higher_is_better": False,
        "scale": 100,
        "source": "teachers",
    },
    "infra_index": {
        "label": "Infrastructure index",
        "unit": "%",
        "higher_is_better": True,
        "scale": 100,
        "source": "udise",
    },
    "coverage_pct": {"label": "Assessment coverage", "unit": "%", "higher_is_better": True, "source": "assessment"},
}
CHILD = {"state": "district", "district": "block", "block": "school", "school": None}
MIN_MONTHS = 6  # a school-year counts as having attendance evidence with >= 6 of 10 months reported


@lru_cache(maxsize=4)
def _panel(version: int) -> pd.DataFrame:
    if not db.table_exists("panel"):
        return pd.DataFrame()
    p = db.read_df("SELECT * FROM panel")
    for c in p.columns:
        if c not in (
            "udise_code",
            "school_name",
            "district",
            "block",
            "cluster",
            "academic_year",
            "provenance",
            "assessment_type",
            "scoring_scale",
        ):
            p[c] = pd.to_numeric(p[c], errors="coerce")
    # Attendance from too few months is treated as missing evidence, not as a value.
    thin = p.months_reported.fillna(0) < MIN_MONTHS
    p["att_thin"] = thin & p.months_reported.fillna(0).gt(0)
    p.loc[thin, ["student_att", "teacher_att"]] = np.nan
    std = _standard_instrument(p)
    p["comparable"] = (p.assessment_type == std[0]) & (p.scoring_scale == std[1])
    return p


def _standard_instrument(p: pd.DataFrame) -> tuple[str, str]:
    years = sorted(p.academic_year.dropna().unique())
    base = p[p.academic_year == years[0]] if years else p
    m = base.dropna(subset=["assessment_type", "scoring_scale"])
    if m.empty:
        return ("unspecified", "0-100")
    top = m.groupby(["assessment_type", "scoring_scale"]).size().idxmax()
    return top[0], top[1]


def panel() -> pd.DataFrame:
    return _panel(db.version())


def years() -> list[str]:
    p = panel()
    return sorted(p.academic_year.dropna().unique().tolist()) if len(p) else []


def baseline_latest() -> tuple[str, str]:
    y = years()
    return y[0], y[-1]


def subset(unit_type: str, unit: str | None) -> pd.DataFrame:
    p = panel()
    if unit_type == "state" or not unit:
        return p
    col = "udise_code" if unit_type == "school" else unit_type
    return p[p[col].str.casefold() == str(unit).casefold()]


def canonical_unit(unit_type: str, unit: str | None) -> str:
    if unit_type == "state" or not unit:
        return "State"
    s = subset(unit_type, unit)
    if s.empty:
        raise KeyError(f"Unknown {unit_type}: {unit}")
    col = "udise_code" if unit_type == "school" else unit_type
    return str(s[col].iloc[0])


def agg(df: pd.DataFrame, metric: str, comparable_only: bool = False) -> float | None:
    meta = METRICS[metric]
    d = df[df.comparable] if comparable_only and meta["source"] == "assessment" else df
    d = d[d[metric].notna()]
    if d.empty:
        return None
    w = meta.get("weight")
    if w and d[w].notna().all() and d[w].sum() > 0:
        v = float(np.average(d[metric], weights=d[w]))
    else:
        v = float(d[metric].mean())
    return round(v * meta.get("scale", 1), 1)


def r1(x) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 1)


def comparability_flags(unit_type: str, unit: str) -> list[dict]:
    if not db.table_exists("comparability_flags"):
        return []
    f = db.read_df("SELECT * FROM comparability_flags")
    if f.empty:
        return []
    if unit_type == "school":
        s = subset("school", unit)
        unit_type, unit = "block", s.block.iloc[0] if len(s) else unit
    f = f[(f.unit_type == unit_type) & (f.unit.str.casefold() == str(unit).casefold())]
    return f.to_dict("records")


def source_files(kind: str) -> list[str]:
    if not db.table_exists("ingest_files"):
        return []
    f = db.read_df("SELECT file FROM ingest_files WHERE kind=:k AND status='ok'", {"k": kind})
    return f.file.tolist()


def unit_label(unit_type: str, unit: str) -> str:
    if unit_type == "state":
        return "State"
    if unit_type == "school":
        s = subset("school", unit)
        return f"{s.school_name.iloc[0]} ({unit})" if len(s) else unit
    return f"{unit} {unit_type}"
