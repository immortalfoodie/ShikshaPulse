"""Duplicate removal: exact duplicates, then key duplicates (same school/period/measure)."""
from __future__ import annotations

import pandas as pd

KEYS = {
    "assessment": ["udise_code", "academic_year", "grade", "subject"],
    "attendance": ["udise_code", "year", "month"],
    "teachers": ["udise_code", "academic_year", "subject"],
    "udise": ["udise_code", "academic_year"],
}


def dedupe(df: pd.DataFrame, kind: str) -> tuple[pd.DataFrame, dict]:
    n0 = len(df)
    cols = [c for c in df.columns if c not in ("_row",)]
    df = df.drop_duplicates(subset=cols)
    n1 = len(df)
    keys = [k for k in KEYS.get(kind, []) if k in df.columns]
    if keys:
        with_code = df[df.udise_code.notna()]
        without = df[df.udise_code.isna()]
        with_code = with_code.drop_duplicates(subset=keys, keep="first")
        df = pd.concat([with_code, without])
    return df, {"exact_duplicates": n0 - n1, "key_duplicates": n1 - len(df)}
