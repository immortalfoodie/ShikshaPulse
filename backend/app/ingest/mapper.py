"""AI-assisted column mapping.

Layered so it is accurate offline and explainable:
  1. dictionary  — exact match against known synonyms            (confidence 1.0)
  2. fuzzy       — rapidfuzz similarity to synonyms              (0.80–0.95)
  3. profile     — value profiling (11-digit codes, registry overlap, roman grades ...)
  4. ai          — the LLM resolves whatever is still ambiguous, given headers + sample values
Every decision carries a method and confidence; the officer confirms before ingestion.
"""

from __future__ import annotations

import hashlib
import json
import re

import pandas as pd
from rapidfuzz import fuzz

from ..ai.llm import llm
from .schema import CANONICAL, FIELD_HELP, REQUIRED, WIDE_MONTH, norm_header

PROFILE_FIELDS = ["udise_code", "block", "district", "school_name", "grade", "academic_year"]


def detect_kind(columns: list[str], kind_hint: str | None) -> tuple[str, float]:
    """Identify which dataset kind (`assessment`, `attendance`, `teachers`, `udise`, `context`) fits `columns`."""
    normed = [norm_header(c) for c in columns]
    scores = {}
    for kind, fields in CANONICAL.items():
        syn = {s for v in fields.values() for s in v}
        scores[kind] = sum(1 for c in normed if c in syn) / max(1, len(normed))
    if any(WIDE_MONTH.match(c.strip()) for c in columns):
        scores["attendance"] += 0.5
    if kind_hint and kind_hint in scores:
        return kind_hint, round(min(1.0, 0.8 + scores[kind_hint]), 2)
    best = max(scores, key=scores.get)
    return best, round(min(1.0, scores[best] + 0.3), 2)


def _profile(series: pd.Series, field: str, registry: dict | None) -> float:
    vals = series.dropna().astype(str).str.strip()
    vals = vals[vals != ""].head(300)
    if vals.empty:
        return 0.0
    low = vals.str.casefold()
    score = 0.0
    if field == "udise_code":
        score = float(vals.str.replace(r"\.0$", "", regex=True).str.fullmatch(r"\d{11}").mean())
    elif field in ("block", "district") and registry:
        known = {x.casefold() for x in registry.get(field + "s", [])}
        score = float(low.isin(known).mean()) if known else 0.0
    elif field == "school_name":
        score = 0.9 if low.str.contains("school|vidyalaya|sch").mean() > 0.6 else 0.0
    elif field == "grade":
        ok = low.str.fullmatch(r"(class |grade |std )?(i{1,3}|iv|v|vi{0,3}|[1-9]|1[0-2])")
        score = 0.85 if ok.mean() > 0.9 and low.nunique() <= 3 else 0.0
    elif field == "academic_year":
        score = float(low.str.contains(r"20\d\d\s*[-_/]\s*\d{2}").mean()) * 0.9
    return score


def _sample_values(df: pd.DataFrame, col: str) -> list[str]:
    return [str(v) for v in df[col].dropna().astype(str).head(4).tolist()]


def _dictionary_and_fuzzy_pass(
    cols: list[str],
    kind: str,
    fields: dict[str, list[str]],
    result: dict[str, dict],
    taken: set[str],
) -> list[str]:
    wide: list[str] = []
    scored = []
    for c in cols:
        if kind == "attendance" and WIDE_MONTH.match(c.strip()):
            wide.append(c)
            continue
        h = norm_header(c)
        best_f, best_s = None, 0.0
        for f, syns in fields.items():
            for s in syns:
                sc = 100.0 if h == s else max(fuzz.ratio(h, s), fuzz.token_sort_ratio(h, s) - 3)
                if sc > best_s:
                    best_f, best_s = f, sc
        scored.append((best_s, c, best_f))
    for sc, c, f in sorted(scored, key=lambda x: -x[0]):
        if f in taken:
            continue
        if sc >= 100:
            result[c] = {"target": f, "confidence": 1.0, "method": "dictionary"}
            taken.add(f)
        elif sc >= 86:
            result[c] = {"target": f, "confidence": round(0.8 + (sc - 86) / 100, 2), "method": "fuzzy"}
            taken.add(f)
    return wide


def _profile_pass(
    df: pd.DataFrame,
    cols: list[str],
    wide: list[str],
    fields: dict[str, list[str]],
    registry: dict | None,
    result: dict[str, dict],
    taken: set[str],
) -> None:
    for c in cols:
        if c in result or c in wide:
            continue
        best_f, best_p = None, 0.0
        for f in PROFILE_FIELDS:
            if f in fields and f not in taken:
                p = _profile(df[c], f, registry)
                if p > best_p:
                    best_f, best_p = f, p
        if best_f and best_p >= 0.6:
            result[c] = {"target": best_f, "confidence": round(0.7 + 0.2 * best_p, 2), "method": "profile"}
            taken.add(best_f)


def _llm_pass(
    df: pd.DataFrame,
    kind: str,
    unresolved: list[str],
    fields: dict[str, list[str]],
    result: dict[str, dict],
    taken: set[str],
) -> str:
    try:
        free = [f for f in fields if f not in taken or any(result.get(c, {}).get("target") == f for c in unresolved)]
        prompt = {
            "dataset_kind": kind,
            "columns": [{"header": c, "samples": _sample_values(df, c)} for c in unresolved],
            "target_fields": {f: FIELD_HELP.get(f, f) for f in free},
            "instructions": "Map each column header to one target field or null if none fits. "
            'Each target may be used once. Reply JSON: {"mappings":[{"source":...,'
            '"target":...|null,"reason":...}]}',
        }
        out = llm().complete_json(
            "You map messy Indian school-education spreadsheet headers to a canonical "
            "schema. Be conservative: return null when unsure.",
            json.dumps(prompt),
            timeout=12,
        )
        n_ai = 0
        for m in out.get("mappings", []):
            src, tgt = m.get("source"), m.get("target")
            if src in unresolved and tgt in fields and (tgt not in taken or result.get(src, {}).get("target") == tgt):
                if src in result:
                    taken.discard(result[src]["target"])
                result[src] = {"target": tgt, "confidence": 0.9, "method": "ai", "reason": m.get("reason", "")}
                taken.add(tgt)
                n_ai += 1
        return f"AI resolved {n_ai} of {len(unresolved)} ambiguous column(s)"
    except Exception as e:
        return f"AI mapping unavailable ({type(e).__name__}); used deterministic profiling"


def map_columns(df: pd.DataFrame, kind: str, registry: dict | None = None, use_ai: bool = True) -> dict:
    """Map raw DataFrame columns to the canonical schema for `kind`."""
    fields = CANONICAL[kind]
    cols = [c for c in df.columns if c != "_row"]
    result: dict[str, dict] = {}
    taken: set[str] = set()

    wide = _dictionary_and_fuzzy_pass(cols, kind, fields, result, taken)
    _profile_pass(df, cols, wide, fields, registry, result, taken)

    unresolved = [c for c in cols if c not in wide and (c not in result or result[c]["confidence"] < 0.8)]
    ai_note = (
        _llm_pass(df, kind, unresolved, fields, result, taken) if (unresolved and use_ai and llm().available) else None
    )

    columns = [
        {
            "source": c,
            "target": r["target"] if (r := result.get(c)) else None,
            "confidence": r["confidence"] if r else 0.0,
            "method": r["method"] if r else "unmapped",
            "reason": (r or {}).get("reason", ""),
            "sample": _sample_values(df, c),
        }
        for c in cols
        if c not in wide
    ]
    mapped = {x["target"] for x in columns if x["target"]}
    if wide:
        mapped.add("__wide__")
    missing = [" or ".join(g) for g in REQUIRED[kind] if not any(f in mapped for f in g)]
    return {
        "kind": kind,
        "columns": columns,
        "wide_month_columns": wide,
        "required_missing": missing,
        "ai_note": ai_note,
    }


def mapping_dict(mapping: dict) -> dict[str, str]:
    """Return `{source_column: canonical_target}` for mapped columns."""
    return {c["source"]: c["target"] for c in mapping["columns"] if c["target"]}


def mapping_version(mapping: dict) -> str:
    """Short deterministic hash of the column mapping for lineage tracking."""
    payload = json.dumps(sorted(mapping_dict(mapping).items()) + sorted(mapping.get("wide_month_columns", [])))
    return hashlib.sha1(payload.encode()).hexdigest()[:10]


def apply_overrides(mapping: dict, overrides: dict[str, str | None]) -> dict:
    """Officer edits from Data Studio: {source_header: target_or_null}."""
    for c in mapping["columns"]:
        if c["source"] in overrides:
            t = overrides[c["source"]]
            c.update({"target": t or None, "confidence": 1.0 if t else 0.0, "method": "manual" if t else "unmapped"})
    return mapping


def clean_code(v) -> str | None:
    """Extract digits from a UDISE code string or float cell."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = re.sub(r"\.0$", "", str(v).strip())
    s = re.sub(r"\D", "", s)
    return s or None
