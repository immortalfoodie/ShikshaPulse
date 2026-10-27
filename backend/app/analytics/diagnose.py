"""The "Why?" engine — evidence-graded contributing signals, never causal claims.

For a unit (state/district/block/school) and an outcome, between the baseline and latest year:

  * outcome change (comparable instruments only);
  * for each tracked factor: change, data coverage, within-unit association across schools
    (does a school's factor change line up with its outcome change?), and an estimated
    contribution = pooled first-difference coefficient × factor change;
  * classification: HIGH / MEDIUM signal, CONFLICTING, INSUFFICIENT_EVIDENCE or none;
  * context (election duty, calendar events), an unresolved remainder, and known data gaps.

Every number is returned inside an evidence payload so the UI and the AI guard can cite it.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .. import db
from ..config import settings
from .common import (CHILD, METRICS, agg, baseline_latest, canonical_unit, comparability_flags, panel, r1,
                     source_files, subset, unit_label)
from .quality import unit_quality

FACTORS = {
    "maths_vacancy": {"col": "maths_vacancy", "label": "Maths teacher vacancy", "scale": 100, "source": "teachers",
                      "adverse_when": "up"},
    "student_attendance": {"col": "student_att", "label": "Student attendance", "scale": 1, "source": "attendance",
                           "adverse_when": "down"},
    "teacher_attendance": {"col": "teacher_att", "label": "Teacher attendance", "scale": 1, "source": "attendance",
                           "adverse_when": "down"},
    "infrastructure": {"col": "infra_index", "label": "Infrastructure (facilities available)", "scale": 100,
                       "source": "udise", "adverse_when": "down"},
}
DATA_GAPS = [
    "No classroom-observation or teaching-practice data is available.",
    "Learning data is school-level aggregate only (no student-level progression).",
    "Teacher subject knowledge and training participation are not captured.",
]


def _paired(df: pd.DataFrame, y0: str, y1: str, metric: str) -> pd.DataFrame:
    a = df[df.academic_year == y0].set_index("udise_code")
    b = df[df.academic_year == y1].set_index("udise_code")
    idx = a.index.intersection(b.index)
    a, b = a.loc[idx], b.loc[idx]
    w = pd.DataFrame(index=idx)
    ok = a.comparable & b.comparable & a[metric].notna() & b[metric].notna()
    w["d_y"] = (b[metric] - a[metric]).where(ok)
    w["weight"] = b.students_assessed.fillna(1)
    for k, f in FACTORS.items():
        w[f"d_{k}"] = (b[f["col"]] - a[f["col"]]) * f["scale"]
        w[f"a_{k}"] = a[f["col"]] * f["scale"]
        w[f"b_{k}"] = b[f["col"]] * f["scale"]
    w["school_name"] = b.school_name
    w["block"] = b.block
    w["district"] = b.district
    w["tdl"] = b.teacher_days_lost
    return w


@lru_cache(maxsize=8)
def _coefficients(version: int, metric: str) -> dict:
    """Pooled first-difference regression across all schools in the state (association estimates)."""
    y0, y1 = baseline_latest()
    w = _paired(panel(), y0, y1, metric)
    cols = [f"d_{k}" for k in FACTORS]
    d = w.dropna(subset=["d_y", *cols])
    if len(d) < 30:
        return {k: 0.0 for k in FACTORS} | {"_n": len(d), "_r2": None}
    X = np.column_stack([np.ones(len(d)), d[cols].to_numpy()])
    y = d.d_y.to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    out = {k: float(b) for k, b in zip(FACTORS, beta[1:])}
    out.update({"_n": int(len(d)), "_r2": round(float(r2), 3), "_intercept": float(beta[0])})
    return out


def coefficients(metric: str = "numeracy") -> dict:
    return _coefficients(db.version(), metric)


def diagnose(unit_type: str, unit: str | None, metric: str = "numeracy") -> dict:
    return _diagnose(db.version(), unit_type, canonical_unit(unit_type, unit), metric)


@lru_cache(maxsize=256)
def _diagnose(version: int, unit_type: str, unit: str, metric: str) -> dict:
    cfg = settings().get("diagnosis", {})
    min_cov = cfg.get("min_coverage", 0.6)
    hi_pp, med_pp = cfg.get("high_contribution_pp", 2.5), cfg.get("medium_contribution_pp", 1.2)
    min_assoc, unexpl_pp = cfg.get("min_assoc", 0.25), cfg.get("unexplained_pp", 4.0)

    y0, y1 = baseline_latest()
    period = f"{y0} → {y1}"
    df = subset(unit_type, unit)
    w = _paired(df, y0, y1, metric)
    beta = coefficients(metric)
    flags = comparability_flags(unit_type, unit)
    quality = unit_quality(unit_type, unit)
    from .. import visits as _visits
    field = _visits.summary(unit_type, unit)
    n_schools = int(len(w))
    pairs = w[w.d_y.notna()]
    n_pairs = int(len(pairs))
    ev_id = 0

    def nid(prefix: str) -> str:
        nonlocal ev_id
        ev_id += 1
        return f"{prefix}{ev_id}"

    base = {"unit_type": unit_type, "unit": unit, "unit_label": unit_label(unit_type, unit), "metric": metric,
            "metric_label": METRICS[metric]["label"], "baseline_year": y0, "latest_year": y1, "period": period,
            "n_schools": n_schools, "data_confidence": quality["confidence"],
            "data_confidence_label": quality["label"], "quality_warnings": quality["warnings"],
            "comparability_flags": flags, "data_gaps": list(DATA_GAPS),
            "data_gap_keys": (["gap_student", "gap_training"] if field else ["gap_observation", "gap_student", "gap_training"]),
            "field_observations": field,
            "quality_warning_items": quality.get("warning_items", []),
            "model": {"type": "pooled first-difference OLS (association)", "n": beta.get("_n"), "r2": beta.get("_r2"),
                      "coefficients": {k: round(beta.get(k, 0), 3) for k in FACTORS}}}

    def wavg(s: pd.Series, wt: pd.Series) -> float | None:
        m = s.notna()
        if not m.any():
            return None
        return float(np.average(s[m], weights=wt[m]))

    outcome = {"id": nid("O"), "type": "observed_fact", "metric": metric, "period": period,
               "n_schools_compared": n_pairs, "sources": source_files("assessment")}
    if n_pairs >= 5:
        # Same computation as the trend shown everywhere else, so numbers agree across screens.
        a_v = agg(df[df.academic_year == y0], metric, comparable_only=True)
        b_v = agg(df[df.academic_year == y1], metric, comparable_only=True)
        outcome["baseline"], outcome["latest"] = a_v, b_v
        outcome["change_pp"] = r1(b_v - a_v) if a_v is not None and b_v is not None else None
        outcome["paired_change_pp"] = r1(wavg(pairs.d_y, pairs.weight))
    else:
        outcome["change_pp"] = None
    dy = outcome["change_pp"]

    if dy is None:
        verdict = "NON_COMPARABLE" if any(f["reason"] == "methodology_change" for f in flags) else "INSUFFICIENT_EVIDENCE"
        reason = ("Assessment instrument or scale changed between the comparison years, so the scores cannot be "
                  "compared directly." if verdict == "NON_COMPARABLE" else
                  "Too few schools have comparable outcome data in both years.")
        return {**base, "verdict": verdict, "verdict_reason": reason, "outcome": outcome, "signals": [],
                "context": _context(unit_type, unit, df, y1, nid), "unresolved": [
                    {"id": nid("Q"), "type": "unresolved_question", "text": reason, "period": period,
                     "kind": "noncomparable" if verdict == "NON_COMPARABLE" else "too_few"}],
                "explained_pp": None, "remainder_pp": None}

    direction = "decline" if dy < 0 else "improvement"
    signals, explained, insufficient = [], 0.0, []
    for k, f in FACTORS.items():
        col = f"d_{k}"
        have = pairs[col].notna()
        coverage = float(have.mean()) if n_pairs else 0.0
        sig = {"id": nid("S"), "factor": k, "label": f["label"], "type": "associated_signal", "period": period,
               "coverage": round(coverage, 2), "sources": source_files(f["source"]), "unit_of_change": "pp"}
        if coverage < min_cov:
            sig.update({"classification": "INSUFFICIENT_EVIDENCE", "type": "unresolved_question",
                        "note": f"Only {coverage:.0%} of compared schools have {f['label'].lower()} data in both "
                                f"years (needs ≥{min_cov:.0%})."})
            insufficient.append(k)
            signals.append(sig)
            continue
        d = pairs[have]
        a_v, b_v = d[f"a_{k}"].mean(), d[f"b_{k}"].mean()
        dfac = float(b_v - a_v)
        contrib = beta.get(k, 0.0) * dfac
        r = float(np.corrcoef(d[col], d.d_y)[0, 1]) if len(d) >= 12 and d[col].std() > 1e-9 and d.d_y.std() > 1e-9 else 0.0
        r_signed = r * (1 if beta.get(k, 0) >= 0 else -1)
        same_dir = (contrib < 0) == (dy < 0)
        if abs(contrib) >= hi_pp and same_dir and r_signed >= min_assoc:
            cls = "HIGH"
        elif abs(contrib) >= hi_pp and same_dir and r_signed <= -min_assoc:
            cls = "CONFLICTING"
        elif abs(contrib) >= med_pp and same_dir and r_signed >= 0.1:
            cls = "MEDIUM"
        elif abs(contrib) >= 0.8 and same_dir and r_signed >= 0.3:
            cls = "MEDIUM"  # moderate size but clearly concentrated in the schools where the factor changed
        elif abs(contrib) >= hi_pp and same_dir:
            cls = "MEDIUM"
        else:
            cls = "NONE"
        if cls in ("HIGH", "MEDIUM"):
            explained += contrib
        adverse_up = f["adverse_when"] == "up"
        worst = d.sort_values(col, ascending=not adverse_up).head(8)
        sig.update({
            "classification": cls, "baseline": r1(a_v), "latest": r1(b_v), "change": r1(dfac),
            "assoc_r": round(r, 2), "contribution_pp": r1(contrib), "n_schools": int(len(d)),
            "direction": "adverse" if (dfac > 0) == adverse_up and abs(dfac) > 0.05 else "favourable",
            "affected_schools": [{"udise_code": i, "school_name": row.school_name, "block": row.block,
                                  "baseline": r1(row[f"a_{k}"]), "latest": r1(row[f"b_{k}"]), "change": r1(row[col])}
                                 for i, row in worst.iterrows()],
        })
        if cls == "CONFLICTING":
            sig["type"] = "unresolved_question"
            sig["note"] = ("The unit-level change points one way but schools with larger changes did not see larger "
                           "outcome changes — evidence conflicts.")
        if CHILD.get(unit_type) in ("district", "block"):
            child = CHILD[unit_type]
            ch = d.groupby(child)[col].mean().sort_values(ascending=not adverse_up)
            ch = ch[(ch > 0.5) if adverse_up else (ch < -0.5)] if sig["direction"] == "adverse" else ch
            sig["affected_units"] = [{"unit_type": child, "unit": u, "change": r1(v)} for u, v in ch.head(5).items()]
        signals.append(sig)

    order = {"HIGH": 0, "MEDIUM": 1, "CONFLICTING": 2, "INSUFFICIENT_EVIDENCE": 3, "NONE": 4}
    signals.sort(key=lambda s: (order[s["classification"]], -abs(s.get("contribution_pp") or 0)))
    remainder = dy - explained
    unresolved = []
    if len(insufficient) < 2 and abs(dy) >= unexpl_pp and (remainder * dy > 0) and abs(remainder) >= unexpl_pp and abs(remainder) >= 0.5 * abs(dy):
        unresolved.append({"id": nid("Q"), "type": "unresolved_question", "period": period,
                           "remainder_pp": r1(remainder), "kind": "remainder", "pp": abs(r1(remainder)),
                           "direction": direction,
                           "text": f"{abs(r1(remainder))} pp of the {direction} is not associated with any tracked "
                                   f"indicator. Classroom-level investigation is needed before attributing it."})
    # At district/state level, child blocks whose own change is unexplained or unmeasurable stay visible.
    if CHILD.get(unit_type) in ("district", "block"):
        child = CHILD[unit_type]
        for c in sorted(df[child].dropna().unique()):
            cd = _diagnose(version, child, c, metric)
            ch = cd["outcome"].get("change_pp")
            if cd["verdict"] in ("UNEXPLAINED", "INSUFFICIENT_EVIDENCE", "NON_COMPARABLE") and (
                    ch is None or ch <= -unexpl_pp):
                what = {"UNEXPLAINED": f"a {abs(ch) if ch is not None else '?'} pp decline that tracked indicators do "
                                       "not account for",
                        "INSUFFICIENT_EVIDENCE": f"a {abs(ch) if ch is not None else '?'} pp decline that cannot be "
                                                 "explained because supporting data is missing",
                        "NON_COMPARABLE": "scores that are not comparable across years (instrument changed)"}
                unresolved.append({"id": nid("Q"), "type": "unresolved_question", "period": period, "child": c,
                                   "child_verdict": cd["verdict"], "change_pp": ch, "kind": "child",
                                   "pp": abs(ch) if ch is not None else None,
                                   "text": f"{c}: {what[cd['verdict']]}."})
    for s in signals:
        if s["classification"] in ("INSUFFICIENT_EVIDENCE", "CONFLICTING"):
            unresolved.append({"id": nid("Q"), "type": "unresolved_question", "period": period,
                               "text": f"{s['label']}: {s['note']}", "signal": s["id"], "factor": s["factor"],
                               "kind": "insufficient" if s["classification"] == "INSUFFICIENT_EVIDENCE" else "conflicting",
                               "coverage_pct": round(s["coverage"] * 100)})
    strong = [s for s in signals if s["classification"] in ("HIGH", "MEDIUM")]
    if len(insufficient) >= 2:
        verdict = "INSUFFICIENT_EVIDENCE"
        reason = (f"Key supporting data is missing ({', '.join(FACTORS[k]['label'] for k in insufficient)}), so "
                  f"the {direction} cannot be explained from the available evidence.")
    elif abs(dy) < unexpl_pp:
        verdict = "STABLE"
        reason = f"A change of {dy} pp is small (under {unexpl_pp:g} pp) and within typical year-to-year variation."
    elif not strong or abs(explained) < 0.25 * abs(dy):
        verdict = "UNEXPLAINED"
        reason = (f"No tracked indicator moved in a way that accounts for the {direction}"
                  + (" (minor signals only)." if strong else "."))
    elif unresolved and any("remainder_pp" in u for u in unresolved):
        verdict = "PARTIALLY_EXPLAINED"
        reason = f"Tracked indicators are associated with part of the {direction}; the rest is unresolved."
    else:
        verdict = "EXPLAINED_BY_ASSOCIATED_SIGNALS"
        reason = f"The {direction} coincides with changes in tracked indicators (association, not proof of cause)."
    return {**base, "verdict": verdict, "verdict_reason": reason, "direction": direction, "outcome": outcome,
            "signals": signals, "context": _context(unit_type, unit, df, y1, nid),
            "unresolved": unresolved, "explained_pp": r1(explained), "remainder_pp": r1(remainder)}


def _context(unit_type: str, unit: str, df: pd.DataFrame, y1: str, nid) -> list[dict]:
    out = []
    if not db.table_exists("context_events"):
        return out
    ev = db.read_df("SELECT * FROM context_events WHERE academic_year=:y", {"y": y1})
    if ev.empty:
        return out
    blocks = {b.casefold() for b in df.block.dropna().unique()}
    ev = ev[ev.block.fillna("").str.casefold().isin(blocks) | (ev.block.fillna("").str.upper() == "ALL")]
    for name, g in ev.groupby("event"):
        local = g[g.block.str.upper() != "ALL"]
        tdl = float(local.teacher_days_lost.mean()) if len(local) else 0.0
        out.append({"id": nid("C"), "type": "context", "event": name, "period": y1,
                    "blocks_affected": int(local.block.nunique()), "avg_teacher_days_lost": r1(tdl),
                    "start": g.start.min(), "end": g.end.max(), "source": g.source.iloc[0],
                    "classification": "CONTEXT" if tdl >= 5 else "BACKGROUND"})
    return sorted(out, key=lambda c: -(c["avg_teacher_days_lost"] or 0))


def children_reasons(unit_type: str, unit: str | None, metric: str = "numeracy", limit: int = 8) -> list[dict]:
    """Per-child diagnosis summary, used for 'blocks requiring review' (with reasons, not a ranking)."""
    from .trends import breakdown
    b = breakdown(metric, unit_type, unit)
    out = []
    for c in b["children"]:
        if c["unit_type"] == "school":
            continue
        dg = diagnose(c["unit_type"], c["unit"], metric)
        top = [s for s in dg["signals"] if s["classification"] in ("HIGH", "MEDIUM")]
        reasons = [f"{s['label']} {('+' if (s.get('change') or 0) > 0 else '')}{s.get('change')} pp "
                   f"({s['classification'].lower()} signal)" for s in top[:2]]
        if dg["verdict"] == "INSUFFICIENT_EVIDENCE":
            reasons.append("Insufficient supporting data")
        if dg["verdict"] == "NON_COMPARABLE":
            reasons.append("Assessment instrument changed — not comparable")
        if any("remainder_pp" in u for u in dg["unresolved"]):
            reasons.append(f"{abs(dg['remainder_pp'])} pp unexplained by tracked indicators")
        items = [{"kind": "signal", "factor": s["factor"], "change": s.get("change"), "cls": s["classification"]}
                 for s in top[:2]]
        if dg["verdict"] in ("INSUFFICIENT_EVIDENCE", "NON_COMPARABLE"):
            items.append({"kind": dg["verdict"].lower()})
        if any("remainder_pp" in u for u in dg["unresolved"]):
            items.append({"kind": "unexplained", "pp": abs(dg["remainder_pp"])})
        out.append({**c, "verdict": dg["verdict"], "reasons": reasons, "reason_items": items,
                    "data_confidence": dg["data_confidence"],
                    "needs_review": dg["verdict"] in ("INSUFFICIENT_EVIDENCE", "NON_COMPARABLE", "UNEXPLAINED")
                    or (c["change_pp"] is not None and c["change_pp"] <= -5)
                    or (bool(top) and dg.get("direction") == "decline")})
    out.sort(key=lambda r: (not r["needs_review"], r["change_pp"] if r["change_pp"] is not None else 0))
    return out[:limit] if limit else out
