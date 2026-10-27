"""Derived warehouse tables: annual attendance, the school-year analytic panel, comparability flags."""
from __future__ import annotations

import pandas as pd

from .. import db
from ..ingest.schema import FACILITIES


def _safe(table: str) -> pd.DataFrame:
    return db.read_df(f"SELECT * FROM {table}") if db.table_exists(table) else pd.DataFrame()


def rebuild_derived() -> None:
    schools = _safe("schools")
    if schools.empty:
        return
    att = _safe("attendance_monthly")
    asmt = _safe("assessments")
    tch = _safe("teacher_snapshot")
    udy = _safe("udise_year")
    ctx = _safe("context_events")

    # Annual attendance is derived from monthly records and records which months it used.
    if not att.empty:
        att = att[att.udise_code.notna()]
        g = att.groupby(["udise_code", "academic_year"])
        annual = g.agg(student_att=("student_att_pct", "mean"), teacher_att=("teacher_att_pct", "mean"),
                       months_reported=("student_att_pct", "count")).reset_index()
        months = g.month.apply(lambda s: ",".join(str(int(m)) for m in sorted(set(s)))).rename("months_used")
        annual = annual.merge(months.reset_index(), on=["udise_code", "academic_year"])
    else:
        annual = pd.DataFrame(columns=["udise_code", "academic_year", "student_att", "teacher_att",
                                       "months_reported", "months_used"])
    db.write_df(annual, "attendance_annual")

    years = sorted(set(asmt.academic_year.dropna()) | set(udy.academic_year.dropna()) if not asmt.empty
                   else set(udy.academic_year.dropna()))
    base = schools[["udise_code", "school_name", "district", "block", "cluster", "rural", "provenance"]]
    panel = base.merge(pd.DataFrame({"academic_year": years}), how="cross")

    if not asmt.empty:
        a = asmt[(asmt.grade.fillna(3) == 3)]
        num = a[a.subject == "maths"].groupby(["udise_code", "academic_year"]).agg(
            numeracy=("score_pct", "mean"), students_assessed=("students_assessed", "max"),
            assessment_type=("assessment_type", "first"), scoring_scale=("scoring_scale", "first")).reset_index()
        lit = a[a.subject == "language"].groupby(["udise_code", "academic_year"]).agg(
            literacy=("score_pct", "mean")).reset_index()
        panel = panel.merge(num, how="left", on=["udise_code", "academic_year"]).merge(
            lit, how="left", on=["udise_code", "academic_year"])
    panel = panel.merge(annual[["udise_code", "academic_year", "student_att", "teacher_att", "months_reported"]],
                        how="left", on=["udise_code", "academic_year"])
    if not tch.empty:
        t = tch[tch.udise_code.notna()]
        piv = t.groupby(["udise_code", "academic_year", "subject"]).agg(
            sanctioned=("sanctioned", "sum"), vacant=("vacant", "sum")).reset_index()
        m = piv[piv.subject == "maths"].rename(columns={"sanctioned": "maths_sanctioned", "vacant": "maths_vacant"})
        lg = piv[piv.subject == "language"].rename(columns={"sanctioned": "lang_sanctioned", "vacant": "lang_vacant"})
        panel = panel.merge(m.drop(columns="subject"), how="left", on=["udise_code", "academic_year"])
        panel = panel.merge(lg.drop(columns="subject"), how="left", on=["udise_code", "academic_year"])
        panel["maths_vacancy"] = panel.maths_vacant / panel.maths_sanctioned.where(panel.maths_sanctioned > 0)
        panel["lang_vacancy"] = panel.lang_vacant / panel.lang_sanctioned.where(panel.lang_sanctioned > 0)
    if not udy.empty:
        u = udy[udy.udise_code.notna()].drop_duplicates(["udise_code", "academic_year"])
        panel = panel.merge(u[["udise_code", "academic_year", "enrolment", "grade3_enrolment", "infra_index",
                               *FACILITIES]], how="left", on=["udise_code", "academic_year"])
        panel["coverage_pct"] = (panel.students_assessed / panel.grade3_enrolment.where(panel.grade3_enrolment > 0)
                                 * 100).clip(upper=100)
    if not ctx.empty:
        c = ctx[(ctx.block.notna()) & (ctx.block.str.upper() != "ALL")]
        tdl = c.groupby(["block", "academic_year"]).teacher_days_lost.sum().reset_index()
        tdl["block_key"] = tdl.block.str.casefold()
        panel["block_key"] = panel.block.str.casefold()
        panel = panel.merge(tdl.drop(columns="block"), how="left", on=["block_key", "academic_year"]).drop(
            columns="block_key")
    for col in ["numeracy", "literacy", "students_assessed", "student_att", "teacher_att", "months_reported",
                "maths_vacancy", "lang_vacancy", "maths_sanctioned", "maths_vacant", "infra_index",
                "enrolment", "grade3_enrolment", "coverage_pct", "teacher_days_lost"]:
        if col not in panel:
            panel[col] = pd.NA
    panel["teacher_days_lost"] = panel.teacher_days_lost.fillna(0)
    for col in ("assessment_type", "scoring_scale"):
        if col not in panel:
            panel[col] = None
    db.write_df(panel, "panel")
    db.write_df(comparability(panel), "comparability_flags")


def comparability(panel: pd.DataFrame) -> pd.DataFrame:
    """Flag unit/year pairs where scores should not be compared directly."""
    rows = []
    years = sorted(panel.academic_year.dropna().unique())
    levels = [("state", None), ("district", "district"), ("block", "block")]
    for unit_type, col in levels:
        groups = [("State", panel)] if col is None else list(panel.groupby(col))
        for unit, g in groups:
            for y0, y1 in zip(years, years[1:]):
                a, b = g[g.academic_year == y0], g[g.academic_year == y1]
                if a.numeracy.notna().sum() == 0 or b.numeracy.notna().sum() == 0:
                    continue
                share_changed = _share_changed(a, b)
                if share_changed >= 0.5:
                    ta = a.assessment_type.dropna().mode()
                    tb = b.assessment_type.dropna().mode()
                    rows.append({"unit_type": unit_type, "unit": unit, "from_year": y0, "to_year": y1,
                                 "reason": "methodology_change",
                                 "detail": f"Assessment instrument/scale changed for {share_changed:.0%} of schools "
                                           f"({ta.iloc[0] if len(ta) else '?'} → {tb.iloc[0] if len(tb) else '?'})"})
                elif unit_type != "block" and share_changed >= 0.03:
                    rows.append({"unit_type": unit_type, "unit": unit, "from_year": y0, "to_year": y1,
                                 "reason": "partial_methodology_change",
                                 "detail": f"{share_changed:.0%} of schools changed instrument or scale; "
                                           "aggregate trend excludes them"})
                ca, cb = a.coverage_pct.mean(), b.coverage_pct.mean()
                if pd.notna(ca) and pd.notna(cb) and ca - cb >= 25:
                    rows.append({"unit_type": unit_type, "unit": unit, "from_year": y0, "to_year": y1,
                                 "reason": "coverage_drop",
                                 "detail": f"Assessment coverage fell from {ca:.0f}% to {cb:.0f}% of Grade 3 enrolment"})
    return pd.DataFrame(rows, columns=["unit_type", "unit", "from_year", "to_year", "reason", "detail"])


def _share_changed(a: pd.DataFrame, b: pd.DataFrame) -> float:
    m = a[["udise_code", "assessment_type", "scoring_scale"]].merge(
        b[["udise_code", "assessment_type", "scoring_scale"]], on="udise_code", suffixes=("_a", "_b")).dropna()
    if m.empty:
        return 0.0
    changed = (m.assessment_type_a != m.assessment_type_b) | (m.scoring_scale_a != m.scoring_scale_b)
    return float(changed.mean())
