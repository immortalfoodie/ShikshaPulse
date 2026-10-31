"""Normalise mapped datasets into canonical long tables.

Handles year formats, wide→long reshaping, percent vs fraction, raw marks vs percent (scale
tagging), Yes/No/Y/N/1/0 facility encodings, date formats and subject/grade spellings. Each
function returns (frame, transforms) so lineage can record exactly what was done.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .mapper import clean_code
from .schema import FACILITIES, WIDE_MONTH

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}


def norm_year(v, hint: str | None = None) -> str | None:
    """'2024-25' | '2024/25' | '2024_25' | 'AY 2024' | '2024-2025' | 'FY2024-25' | 2024 -> '2024-25'."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() == "":
        return hint
    s = str(v).strip().lower()
    m = re.search(r"(20\d{2})\s*[-_/]\s*(20)?(\d{2})(?!\d)", s)
    if m:
        y = int(m.group(1))
        return f"{y}-{(y + 1) % 100:02d}"
    m = re.search(r"(20\d{2})", s)
    if m:
        y = int(m.group(1))
        return f"{y}-{(y + 1) % 100:02d}"
    return hint


def academic_year_of(year: int, month: int) -> str:
    start = year if month >= 6 else year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(r"[%,\s]", "", regex=True).replace({"": np.nan, "nan": np.nan, "None": np.nan}),
        errors="coerce",
    )


def to_pct(s: pd.Series) -> tuple[pd.Series, bool]:
    x = to_num(s)
    if x.dropna().size and x.dropna().max() <= 1.0:
        return x * 100, True
    return x, False


def to_bool(s: pd.Series) -> pd.Series:
    m = {
        "yes": 1,
        "y": 1,
        "1": 1,
        "true": 1,
        "available": 1,
        "functional": 1,
        "no": 0,
        "n": 0,
        "0": 0,
        "false": 0,
        "not available": 0,
        "non-functional": 0,
    }
    return s.astype(str).str.strip().str.lower().str.replace(r"\.0$", "", regex=True).map(m)


def norm_subject(v) -> str | None:
    s = str(v).strip().lower()
    if s.startswith(("mat", "num")):
        return "maths"
    if s.startswith(("lan", "lit", "hin", "eng", "read")):
        return "language"
    return s or None


def norm_grade(v) -> int | None:
    s = re.sub(r"(class|grade|std|standard)", "", str(v).strip().lower()).strip(" .")
    if s in ROMAN:
        return ROMAN[s]
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def parse_month(v, cal_year=None) -> tuple[int | None, int | None]:
    s = str(v).strip().lower()
    m = re.match(r"(20\d{2})[-/](\d{1,2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"(\d{1,2})[-/](20\d{2})", s)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.match(r"([a-z]{3})[a-z]*[\s\-_']*(\d{2,4})?", s)
    if m and m.group(1) in MONTHS:
        y = m.group(2)
        y = int(y) + 2000 if y and len(y) == 2 else (int(y) if y else None)
        if y is None and cal_year is not None and str(cal_year) not in ("", "nan"):
            y = int(float(cal_year))
        return y, MONTHS[m.group(1)]
    if s.isdigit() and cal_year is not None:
        return int(float(cal_year)), int(s)
    return None, None


def parse_date(v) -> pd.Timestamp | None:
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    for dayfirst in (False, True):
        try:
            if re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", s):
                return pd.to_datetime(s, dayfirst=True)
            return pd.to_datetime(s, dayfirst=dayfirst)
        except (ValueError, TypeError):
            continue
    return None


def _base(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    keep = {src: tgt for src, tgt in mapping.items() if src in df.columns}
    out = df[["_row", *keep.keys()]].rename(columns=keep).copy()
    if "udise_code" in out:
        out["udise_code"] = out["udise_code"].map(clean_code)
    else:
        out["udise_code"] = None
    for c in ("school_name", "block", "district"):
        if c in out:
            out[c] = out[c].astype(str).str.strip().replace({"nan": None, "": None})
    return out


def normalise_assessment(df, mapping, year_hint, file_name):
    t = []
    out = _base(df, mapping)
    if "academic_year" in out:
        out["academic_year"] = out["academic_year"].map(lambda v: norm_year(v, year_hint))
        t.append("academic_year normalised to YYYY-YY")
    else:
        out["academic_year"] = year_hint
        t.append(f"academic_year taken from file name ({year_hint})")
    if "score_maths" in out or "score_language" in out:
        parts = []
        for col, subj in (("score_maths", "maths"), ("score_language", "language")):
            if col in out:
                parts.append(
                    out.drop(columns=[c for c in ("score_maths", "score_language") if c in out]).assign(
                        subject=subj, score=out[col]
                    )
                )
        out = pd.concat(parts, ignore_index=True)
        t.append("wide subject columns reshaped to long")
    else:
        out["subject"] = out["subject"].map(norm_subject)
        t.append("subject names standardised")
    out["score_raw"] = to_num(out["score"])
    if "max_marks" in out:
        mm = to_num(out["max_marks"]).fillna(100)
        out["max_marks"] = mm
        out["score_pct"] = out["score_raw"] / mm * 100
        if (mm != 100).any():
            t.append("raw marks converted to percent using Max Marks; scale tagged")
    else:
        pct, frac = to_pct(out["score"])
        out["score_pct"] = pct
        out["max_marks"] = 100.0
        if frac:
            t.append("fractions converted to percent")
    out["scoring_scale"] = "0-" + out["max_marks"].astype(int).astype(str)
    out["grade"] = out["grade"].map(norm_grade) if "grade" in out else 3
    out["students_assessed"] = to_num(out["students_assessed"]) if "students_assessed" in out else np.nan
    out["assessment_type"] = out["assessment_type"].fillna("unspecified") if "assessment_type" in out else "unspecified"
    out["source"] = file_name
    cols = [
        "_row",
        "udise_code",
        "school_name",
        "block",
        "district",
        "academic_year",
        "grade",
        "subject",
        "assessment_type",
        "scoring_scale",
        "max_marks",
        "score_raw",
        "score_pct",
        "students_assessed",
        "source",
    ]
    return out.reindex(columns=cols), t


def normalise_attendance(df, mapping, year_hint, wide_cols, file_name):
    t = []
    base = _base(df, mapping)
    if wide_cols:
        recs = []
        for c in wide_cols:
            m = WIDE_MONTH.match(c.strip())
            mon = MONTHS[m.group(1).lower()[:3]]
            yy = int(m.group(2))
            yy = yy + 2000 if yy < 100 else yy
            who = (m.group(3) or "students").lower()
            field = "teacher_att" if who.startswith(("t", "staff")) else "student_att"
            recs.append(
                base[["_row", "udise_code", *[x for x in ("school_name", "block") if x in base]]].assign(
                    year=yy, month=mon, field=field, value=to_num(df[c]).values
                )
            )
        long = pd.concat(recs, ignore_index=True)
        idx = [c for c in ["_row", "udise_code", "school_name", "block", "year", "month"] if c in long]
        long["udise_code"] = long["udise_code"].fillna("")
        out = long.pivot_table(index=idx, columns="field", values="value", aggfunc="first").reset_index()
        out["udise_code"] = out["udise_code"].replace({"": None})
        out.columns.name = None
        t.append(f"wide month columns ({len(wide_cols)}) reshaped to long")
        out["days_open"] = np.nan
    else:
        out = base
        ym = [parse_month(m, cy) for m, cy in zip(out["month"], out.get("cal_year", [None] * len(out)), strict=True)]
        out["year"] = [y for y, _ in ym]
        out["month"] = [mo for _, mo in ym]
        t.append("month values parsed to (year, month)")
    for c in ("student_att", "teacher_att"):
        if c in out:
            out[c], frac = to_pct(out[c])
            if frac:
                t.append(f"{c} fractions converted to percent")
        else:
            out[c] = np.nan
    out["days_open"] = to_num(out["days_open"]) if "days_open" in out else np.nan
    out = out.dropna(subset=["year", "month"])
    out["year"] = out["year"].astype(int)
    out["month"] = out["month"].astype(int)
    out["academic_year"] = [academic_year_of(y, m) for y, m in zip(out.year, out.month, strict=True)]
    out = out.rename(columns={"student_att": "student_att_pct", "teacher_att": "teacher_att_pct"})
    out["source"] = file_name
    cols = [
        "_row",
        "udise_code",
        "school_name",
        "block",
        "academic_year",
        "year",
        "month",
        "student_att_pct",
        "teacher_att_pct",
        "days_open",
        "source",
    ]
    return out.reindex(columns=cols), t


def normalise_teachers(df, mapping, year_hint, file_name):
    t = []
    out = _base(df, mapping)
    out["subject"] = out["subject"].map(norm_subject)
    out["sanctioned"] = to_num(out["sanctioned"])
    w = to_num(out["working"]) if "working" in out else None
    v = to_num(out["vacant"]) if "vacant" in out else None
    if w is None and v is not None:
        w = out["sanctioned"] - v
        t.append("working derived as sanctioned − vacant")
    if v is None and w is not None:
        v = out["sanctioned"] - w
        t.append("vacant derived as sanctioned − working")
    out["working"], out["vacant"] = w, v
    if "snapshot_date" in out:
        d = out["snapshot_date"].map(parse_date)
        out["snapshot_date"] = d.map(lambda x: x.date().isoformat() if x is not None and not pd.isna(x) else None)
        out["academic_year"] = d.map(
            lambda x: academic_year_of(x.year, x.month) if x is not None and not pd.isna(x) else year_hint
        )
        t.append("snapshot dates parsed (mixed formats)")
    else:
        out["snapshot_date"], out["academic_year"] = None, year_hint
    out["source"] = file_name
    cols = [
        "_row",
        "udise_code",
        "school_name",
        "block",
        "academic_year",
        "snapshot_date",
        "subject",
        "sanctioned",
        "working",
        "vacant",
        "source",
    ]
    return out.reindex(columns=cols), t


def normalise_udise(df, mapping, year_hint, file_name):
    t = []
    out = _base(df, mapping)
    out["academic_year"] = (
        out["academic_year"].map(lambda v: norm_year(v, year_hint)) if "academic_year" in out else year_hint
    )
    for f in FACILITIES:
        out[f] = to_bool(out[f]) if f in out else np.nan
    t.append("facility flags standardised to 1/0")
    if "location" in out:
        out["rural"] = out["location"].astype(str).str.strip().str.lower().str[0].map({"r": 1, "u": 0})
    else:
        out["rural"] = np.nan
    for c in ("enrolment", "grade3_enrolment"):
        out[c] = to_num(out[c]) if c in out else np.nan
    present = [f for f in FACILITIES if out[f].notna().any()]
    out["infra_index"] = out[present].mean(axis=1) if present else np.nan
    out["source"] = file_name
    cols = [
        "_row",
        "udise_code",
        "school_name",
        "district",
        "block",
        "cluster",
        "management",
        "rural",
        "academic_year",
        "enrolment",
        "grade3_enrolment",
        *FACILITIES,
        "infra_index",
        "source",
    ]
    return out.reindex(columns=cols), t


def normalise_context(df, mapping, year_hint, file_name):
    out = _base(df, mapping)
    s = out["start"].map(parse_date)
    e = out["end"].map(parse_date) if "end" in out else s
    out["start"] = s.map(lambda x: x.date().isoformat() if x is not None else None)
    out["end"] = e.map(lambda x: x.date().isoformat() if x is not None else None)
    out["academic_year"] = s.map(lambda x: academic_year_of(x.year, x.month) if x is not None else year_hint)
    out["teacher_days_lost"] = to_num(out["teacher_days_lost"]).fillna(0) if "teacher_days_lost" in out else 0
    if "source" not in out:
        out["source"] = file_name
    cols = ["district", "block", "event", "start", "end", "academic_year", "teacher_days_lost", "source"]
    return out.reindex(columns=cols), ["dates parsed; academic year derived"]
