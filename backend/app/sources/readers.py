"""Robust tabular readers: CSV/XLSX, title/banner rows, header detection, year hints."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

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


def _detect_header(raw: pd.DataFrame) -> int:
    """Header = first row that is mostly filled with text, ignoring banner/title rows."""
    width = raw.notna().sum(axis=1).max()
    for i in range(min(15, len(raw))):
        row = raw.iloc[i]
        filled = row.notna().sum()
        first = str(row.dropna().iloc[0]) if filled else ""
        if filled >= max(2, 0.6 * width) and "SYNTHETIC" not in first.upper():
            return i
    return 0


def read_table(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        xl = pd.ExcelFile(path)
        sheet = (
            "Data"
            if "Data" in xl.sheet_names
            else next((s for s in xl.sheet_names if s.lower() not in ("about", "readme")), xl.sheet_names[0])
        )
        raw = pd.read_excel(xl, sheet_name=sheet, header=None, dtype=str)
    else:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
        # Skip banner/title lines that precede the real header (no delimiter or very few fields).
        start = 0
        widths = [ln.count(",") for ln in lines[:15]]
        maxw = max(widths) if widths else 0
        while start < len(lines) - 1 and (lines[start].count(",") < 0.6 * maxw or not lines[start].strip()):
            start += 1
        from io import StringIO

        raw = pd.read_csv(StringIO("\n".join(lines[start:])), header=None, dtype=str, keep_default_na=True)
    raw = raw.dropna(how="all").reset_index(drop=True)
    h = _detect_header(raw)
    cols = [str(c).strip() if pd.notna(c) else f"col_{j}" for j, c in enumerate(raw.iloc[h])]
    df = raw.iloc[h + 1 :].copy()
    df.columns = cols
    df = df.dropna(how="all")
    df = df.loc[:, [c for c in df.columns if not (c.startswith("col_") and df[c].isna().all())]]
    # Original row number for lineage (1-based data row index within the file).
    df.insert(0, "_row", range(1, len(df) + 1))
    return df.reset_index(drop=True)


def year_hint_from_name(name: str) -> str | None:
    s = name.lower()
    m = re.search(r"(20\d{2})\s*[-_/]\s*(20)?(\d{2})(?!\d)", s)
    if m:
        y = int(m.group(1))
        return f"{y}-{(y + 1) % 100:02d}"
    m = re.search(r"(?:ay|fy|sy)\s*[-_]?\s*(20\d{2})", s)
    if m:
        y = int(m.group(1))
        return f"{y}-{(y + 1) % 100:02d}"
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*[-_]?\s*(20\d{2})", s)
    if m:
        mo, y = MONTHS[m.group(1)], int(m.group(2))
        start = y if mo >= 6 else y - 1
        return f"{start}-{(start + 1) % 100:02d}"
    return None


def kind_hint_from_name(name: str) -> str | None:
    s = name.lower()
    for kind, keys in [
        ("context", ["context", "calendar", "event"]),
        ("attendance", ["attend"]),
        ("teachers", ["teacher", "vacanc", "position", "staff"]),
        ("udise", ["udise"]),
        ("assessment", ["assess", "fln", "nas", "result", "slas"]),
    ]:
        if any(k in s for k in keys):
            return kind
    return None
