"""Expected vs Actual — a fair comparison that separates conditions from performance.

A Ridge model predicts each school-year's numeracy from *structural conditions only*
(attendance, teacher attendance, maths vacancy, infrastructure, rurality, size). The outcome —
current or lagged — is never an input. Predictions are cross-fitted with block-grouped folds,
so every residual is out-of-sample and no block is ever in both train and test.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .. import db
from .common import canonical_unit, panel, r1, subset, unit_label

FEATURES = {
    "student_att": "Student attendance",
    "teacher_att": "Teacher attendance",
    "maths_vacancy": "Maths teacher vacancy",
    "infra_index": "Infrastructure",
    "rural": "Rural location",
    "log_enrolment": "School size",
}
OUTCOME_COLUMNS = {"numeracy", "literacy", "score_pct", "score_raw"}
BAND_PP = 4.0


def _frame(metric: str) -> pd.DataFrame:
    p = panel().copy()
    p["log_enrolment"] = np.log1p(p.enrolment)
    d = p[p.comparable & p[metric].notna()].dropna(subset=list(FEATURES))
    return d


@lru_cache(maxsize=4)
def _fit(version: int, metric: str) -> dict:
    d = _frame(metric)
    feats = list(FEATURES)
    assert not (set(feats) & OUTCOME_COLUMNS), "leakage: outcome column used as a feature"
    if len(d) < 100 or d.block.nunique() < 5:
        return {"ok": False}
    X, y, groups = d[feats].to_numpy(), d[metric].to_numpy(), d.block.to_numpy()
    oof = np.zeros(len(d))
    folds = min(5, d.block.nunique())
    for tr, te in GroupKFold(n_splits=folds).split(X, y, groups):
        m = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X[tr], y[tr])
        oof[te] = m.predict(X[te])
    final = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X, y)
    scaler, ridge = final.named_steps["standardscaler"], final.named_steps["ridge"]
    d = d.assign(expected=oof, residual=y - oof)
    return {
        "ok": True, "frame": d[["udise_code", "academic_year", "district", "block", "school_name", metric,
                                "expected", "residual", "students_assessed", *feats]],
        "metrics": {"r2_heldout": round(float(r2_score(y, oof)), 3),
                    "mae_heldout": round(float(mean_absolute_error(y, oof)), 2),
                    "n": int(len(d)), "folds": folds, "grouping": "block"},
        "features": feats, "coef": dict(zip(feats, ridge.coef_ / scaler.scale_)),
        "means": dict(zip(feats, scaler.mean_)),
    }


def model_card(metric: str = "numeracy") -> dict:
    f = _fit(db.version(), metric)
    if not f["ok"]:
        return {"ok": False}
    return {"ok": True, "metric": metric, "features": [{"key": k, "label": FEATURES[k],
                                                         "coef_per_unit": round(float(f["coef"][k]), 3)}
                                                        for k in f["features"]],
            "outcome_columns_excluded": sorted(OUTCOME_COLUMNS), **f["metrics"],
            "validation": "Out-of-fold predictions with GroupKFold by block (no block in both train and test)"}


def expected_vs_actual(unit_type: str, unit: str | None, metric: str = "numeracy") -> dict:
    unit = canonical_unit(unit_type, unit)
    f = _fit(db.version(), metric)
    if not f["ok"]:
        return {"ok": False, "reason": "Not enough comparable data to fit the model."}
    fr = f["frame"]
    codes = set(subset(unit_type, unit).udise_code)
    d = fr[fr.udise_code.isin(codes)]
    years = []
    for y, g in d.groupby("academic_year"):
        wts = g.students_assessed.fillna(1)
        actual = float(np.average(g[metric], weights=wts))
        exp = float(np.average(g.expected, weights=wts))
        years.append({"year": y, "actual": r1(actual), "expected": r1(exp), "residual": r1(actual - exp),
                      "n_schools": int(len(g))})
    latest = years[-1] if years else None
    contributions = []
    if latest:
        g = d[d.academic_year == latest["year"]]
        for k in f["features"]:
            delta = float(g[k].mean() - f["means"][k])
            contributions.append({"feature": k, "label": FEATURES[k], "unit_mean": r1(g[k].mean() * (100 if k in (
                "maths_vacancy", "infra_index", "rural") else 1)), "effect_pp": r1(f["coef"][k] * delta)})
        contributions.sort(key=lambda c: c["effect_pp"] or 0)
    state_mean = float(np.average(fr[fr.academic_year == latest["year"]][metric])) if latest else None
    category, text = "in_line", "Performing in line with what its conditions predict."
    residual_change = r1(years[-1]["residual"] - years[0]["residual"]) if len(years) >= 2 else None
    pattern = None
    if latest:
        res, exp = latest["residual"], latest["expected"]
        if res <= -BAND_PP:
            category = "underperforming_conditions"
            if residual_change is not None and residual_change <= -BAND_PP:
                pattern = "emerging"
                text = (f"Scoring {abs(res)} pp below what its conditions predict, and the gap widened by "
                        f"{abs(residual_change)} pp since {years[0]['year']} — an emerging problem that conditions do "
                        "not account for; investigate teaching and school-level factors.")
            else:
                pattern = "persistent"
                text = (f"Scoring {abs(res)} pp below what its conditions predict — a persistent gap seen in every "
                        "year, not a new problem; look at long-standing school-level factors.")
        elif res >= BAND_PP:
            category = "outperforming_conditions"
            text = f"Scoring {res} pp above what its conditions predict — a possible source of practices to learn from."
        elif state_mean is not None and exp <= state_mean - BAND_PP:
            category = "conditions_constrained"
            text = ("Low scores are in line with difficult conditions — the priority is resources (staff, attendance, "
                    "facilities) rather than blame.")
    return {"ok": True, "unit_type": unit_type, "unit": unit, "unit_label": unit_label(unit_type, unit),
            "metric": metric, "years": years, "latest": latest, "state_mean_latest": r1(state_mean),
            "category": category, "pattern": pattern, "residual_change": residual_change,
            "interpretation": text, "contributions": contributions,
            "model": f["metrics"]}


def residual_ranking(unit_type: str = "block", metric: str = "numeracy") -> list[dict]:
    """All units' latest-year residuals (used by eval and by the Instinct-vs-Evidence view)."""
    f = _fit(db.version(), metric)
    if not f["ok"]:
        return []
    fr = f["frame"]
    y = sorted(fr.academic_year.unique())[-1]
    g = fr[fr.academic_year == y].groupby(unit_type).agg(actual=(metric, "mean"), expected=("expected", "mean"),
                                                          residual=("residual", "mean"), n=("udise_code", "count"))
    g = g.reset_index().sort_values("residual")
    return [{"unit": r[unit_type], "actual": r1(r.actual), "expected": r1(r.expected), "residual": r1(r.residual),
             "n_schools": int(r.n)} for _, r in g.iterrows()]
