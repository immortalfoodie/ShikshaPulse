"""School matching against the UDISE-code registry.

Order: valid UDISE code → exact normalised name within block → distinctive-token (village)
match → fuzzy name within block. Anything below the auto threshold, or ambiguous between
candidates, is sent to the human review queue instead of being silently guessed.
"""
from __future__ import annotations

import re

import pandas as pd
from rapidfuzz import fuzz, process

ACRONYMS = {"gps": "government primary school", "gups": "government upper primary school",
            "zpps": "zilla parishad primary school", "mps": "municipal primary school"}
REPLACEMENTS = [
    (r"\b(govt|gov|government)\b", "government"),
    (r"\b(pri|pry|prim)\b", "primary"),
    (r"\b(sch|schl)\b", "school"),
    (r"\bz p\b|\bzp\b", "zilla parishad"),
    (r"\bmun\b", "municipal"),
    (r"\bu p\b", "upper primary"),
    (r"\bp s\b", "primary school"),
]
GENERIC = {"government", "primary", "school", "upper", "zilla", "parishad", "municipal", "kasturba",
           "middle", "high", "secondary"}


def norm_name(name: str) -> str:
    s = str(name).lower().replace(".", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = " ".join(ACRONYMS.get(tok, tok) for tok in s.split())
    for pat, rep in REPLACEMENTS:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s+", " ", s).strip()


def distinctive(norm: str) -> str:
    return " ".join(t for t in norm.split() if t not in GENERIC)


def type_tokens(norm: str) -> set[str]:
    return {t for t in norm.split() if t in GENERIC} - {"school", "government"}


class SchoolRegistry:
    def __init__(self, schools: pd.DataFrame, auto_threshold: float = 0.85, review_threshold: float = 0.70):
        self.df = schools.copy()
        self.codes = set(self.df.udise_code)
        self.auto, self.review = auto_threshold, review_threshold
        self.df["norm"] = self.df.school_name.map(norm_name)
        self.df["dist"] = self.df.norm.map(distinctive)
        self.df["block_key"] = self.df.block.str.casefold()
        self.by_block = {b: g for b, g in self.df.groupby("block_key")}
        self.name_of = dict(zip(self.df.udise_code, self.df.school_name))
        self.block_of = dict(zip(self.df.udise_code, self.df.block))
        self.district_of = dict(zip(self.df.udise_code, self.df.district))

    def summary(self) -> dict:
        return {"schools": len(self.df), "blocks": sorted(self.df.block.unique().tolist()),
                "districts": sorted(self.df.district.unique().tolist())}

    def match_one(self, name: str | None, block: str | None) -> dict:
        """Returns {udise_code, method, confidence, candidates}."""
        if not name:
            return {"udise_code": None, "method": "no_name", "confidence": 0.0, "candidates": []}
        pool = self.by_block.get(str(block).casefold()) if block else None
        if pool is None:
            pool = self.df
        n = norm_name(name)
        exact = pool[pool.norm == n]
        if len(exact) == 1:
            return {"udise_code": exact.udise_code.iloc[0], "method": "normalised_name", "confidence": 0.97,
                    "candidates": []}
        # Distinctive-token (village) match: unique village and compatible school type.
        d = distinctive(n)
        cands = []
        if d:
            scores = process.extract(d, pool.dist.tolist(), scorer=fuzz.ratio, limit=5)
            for _, sc, idx in scores:
                row = pool.iloc[idx]
                cands.append((sc, row))
            strong = [(sc, r) for sc, r in cands if sc >= 85]
            if len(strong) == 1 or (len(strong) > 1 and strong[0][0] - strong[1][0] >= 8):
                sc, r = strong[0]
                tt_rec, tt_reg = type_tokens(n), type_tokens(r.norm)
                compatible = not tt_rec or tt_rec <= tt_reg or tt_reg <= tt_rec
                conf = (0.93 if sc == 100 else 0.88) if compatible else 0.75
                if conf >= self.auto:
                    return {"udise_code": r.udise_code, "method": "village_token" if sc == 100 else "fuzzy_village",
                            "confidence": conf, "candidates": []}
        # Full-name fuzzy as a last resort; ambiguous or weak results go to review.
        full = process.extract(n, pool.norm.tolist(), scorer=fuzz.token_sort_ratio, limit=3)
        top = [{"udise_code": pool.iloc[i].udise_code, "school_name": pool.iloc[i].school_name,
                "block": pool.iloc[i].block, "score": round(s, 1)} for _, s, i in full]
        if top and top[0]["score"] >= 93 and (len(top) == 1 or top[0]["score"] - top[1]["score"] >= 6):
            return {"udise_code": top[0]["udise_code"], "method": "fuzzy_name",
                    "confidence": round(top[0]["score"] / 100, 2), "candidates": top}
        seen = {c["udise_code"] for c in top}
        for sc, r in cands[:3]:
            if r.udise_code not in seen:
                top.append({"udise_code": r.udise_code, "school_name": r.school_name, "block": r.block,
                            "score": round(sc, 1)})
        top = sorted(top, key=lambda c: -c["score"])[:4]
        return {"udise_code": None, "method": "review", "confidence": round((top[0]["score"] if top else 0) / 100, 2),
                "candidates": top}

    def match_frame(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
        """Resolve udise_code for every row. Returns (matched_rows, review_groups)."""
        df = df.copy()
        has = df.udise_code.isin(self.codes)
        df["match_method"] = None
        df["match_confidence"] = None
        df.loc[has, "match_method"] = "udise_code"
        df.loc[has, "match_confidence"] = 1.0
        todo = df[~has]
        reviews = []
        if len(todo):
            keys = todo[["school_name", "block"]].fillna("").drop_duplicates()
            results = {}
            for name, block in keys.itertuples(index=False):
                results[(name, block)] = self.match_one(name or None, block or None)
            for idx, row in todo.iterrows():
                r = results[(row.school_name or "" if pd.notna(row.school_name) else "",
                             row.block or "" if pd.notna(row.block) else "")]
                if r["udise_code"] and r["confidence"] >= self.auto:
                    df.at[idx, "udise_code"] = r["udise_code"]
                    df.at[idx, "match_method"] = r["method"]
                    df.at[idx, "match_confidence"] = r["confidence"]
            unresolved = df.loc[todo.index][df.loc[todo.index, "match_method"].isna()]
            for (name, block), g in unresolved.groupby([unresolved.school_name.fillna(""),
                                                         unresolved.block.fillna("")]):
                r = results[(name, block)]
                reviews.append({"name_variant": name, "block": block, "candidates": r["candidates"],
                                "rows": g.drop(columns=["match_method", "match_confidence"])})
        matched = df[df.match_method.notna()].copy()
        matched["block"] = matched.udise_code.map(self.block_of)
        matched["school_name"] = matched.udise_code.map(self.name_of)
        return matched, reviews
