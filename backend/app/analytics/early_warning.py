"""Early warning from monthly attendance — months before the annual assessment shows the damage.

Compares the last reported months with the same months a year earlier (so seasonal patterns
cancel out), flags months where teacher presence dipped (e.g. election duty), and schools that
stopped reporting. Output uses structured codes so the UI can phrase alerts in any language.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .. import db
from .common import canonical_unit, r1, subset

DROP_PP = 8.0          # school-level student attendance fall that counts as a warning
TEACHER_LOW = 80.0     # block-month teacher attendance below this is a dip
MIN_SHARE = 0.10       # at least 10% of a block's schools (and >= 3) to raise a block alert


@lru_cache(maxsize=4)
def _monthly(version: int) -> pd.DataFrame:
    if not db.table_exists("attendance_monthly"):
        return pd.DataFrame()
    m = db.read_df("SELECT udise_code, academic_year, year, month, student_att_pct, teacher_att_pct FROM attendance_monthly")
    m = m[m.udise_code.notna()].copy()
    m["period"] = m.year.astype(int) * 100 + m.month.astype(int)
    return m


def _label(p: int) -> str:
    return f"{p // 100}-{p % 100:02d}"


def early_warning(unit_type: str, unit: str | None, window: int = 3) -> dict:
    unit = canonical_unit(unit_type, unit)
    m = _monthly(db.version())
    sch = subset(unit_type, unit)[["udise_code", "school_name", "block", "district"]].drop_duplicates("udise_code")
    if m.empty or sch.empty:
        return {"unit_type": unit_type, "unit": unit, "alerts": [], "schools": []}
    m = m[m.udise_code.isin(set(sch.udise_code))].merge(sch, on="udise_code")
    latest_ay = sorted(m.academic_year.unique())[-1]
    cur = m[m.academic_year == latest_ay]
    periods = sorted(cur.period.unique())[-window:]
    prev_periods = [p - 100 for p in periods]  # same months, one year earlier
    now = cur[cur.period.isin(periods)].groupby("udise_code").student_att_pct.mean()
    before = m[m.period.isin(prev_periods)].groupby("udise_code").student_att_pct.mean()
    drop = (now - before).dropna()
    reported = cur[cur.period.isin(periods[-2:])].groupby("udise_code").period.nunique()
    missing = set(sch.udise_code) - set(reported[reported > 0].index)

    alerts, schools = [], []
    for block, g in sch.groupby("block"):
        codes = set(g.udise_code)
        n = len(codes)
        need = max(3, int(np.ceil(MIN_SHARE * n)))
        d = drop[drop.index.isin(codes)]
        bad = d[d <= -DROP_PP]
        if len(bad) >= need:
            alerts.append({"kind": "attendance_drop", "block": block, "district": g.district.iloc[0],
                           "n": int(len(bad)), "of": n, "avg_drop": r1(float(-bad.mean())),
                           "months": [_label(p) for p in periods],
                           "severity": "high" if len(bad) >= 0.25 * n else "medium"})
        bm = cur[cur.udise_code.isin(codes)].groupby("period").teacher_att_pct.mean()
        dips = bm[bm < TEACHER_LOW]
        if len(dips):
            alerts.append({"kind": "teacher_dip", "block": block, "district": g.district.iloc[0],
                           "months": [_label(int(p)) for p in dips.index], "min_value": r1(float(dips.min())),
                           "severity": "high" if dips.min() < 70 else "medium"})
        miss = codes & missing
        if len(miss) >= need:
            alerts.append({"kind": "missing_reports", "block": block, "district": g.district.iloc[0],
                           "n": len(miss), "of": n, "months": [_label(p) for p in periods[-2:]], "severity": "medium"})
    names = sch.set_index("udise_code")
    for code, v in drop.sort_values().head(12).items():
        if v <= -DROP_PP:
            schools.append({"udise_code": code, "school_name": names.loc[code, "school_name"],
                            "block": names.loc[code, "block"], "drop": r1(float(-v)),
                            "now": r1(float(now[code])), "before": r1(float(before[code]))})
    # Teacher dips shared by several blocks (e.g. election duty) become one alert, not a wall of repeats.
    dips = [a for a in alerts if a["kind"] == "teacher_dip"]
    if len(dips) >= 3:
        alerts = [a for a in alerts if a["kind"] != "teacher_dip"]
        low = min(dips, key=lambda a: a["min_value"])
        months = sorted({m for a in dips for m in a["months"]})
        alerts.append({"kind": "teacher_dip_multi", "block": low["block"], "district": low["district"],
                       "n_blocks": len(dips), "months": months, "min_value": low["min_value"],
                       "blocks": [{"block": a["block"], "min_value": a["min_value"]} for a in sorted(dips, key=lambda a: a["min_value"])],
                       "severity": "high" if low["min_value"] < 70 else "medium"})
    order = {"high": 0, "medium": 1}
    alerts.sort(key=lambda a: (order[a["severity"]], a["kind"] != "attendance_drop", a["block"]))
    return {"unit_type": unit_type, "unit": unit, "academic_year": latest_ay, "months": [_label(p) for p in periods],
            "compared_with": [_label(p) for p in prev_periods], "alerts": alerts, "schools": schools,
            "thresholds": {"drop_pp": DROP_PP, "teacher_low": TEACHER_LOW}}
