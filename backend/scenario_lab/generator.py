"""Deterministic synthetic education-data generator.

A scenario YAML declares districts, blocks and *effects* (vacancy rise, attendance decline,
election disruption, ...). The generator builds a "true" school-year panel from a simple
structural model, then `messify.py` writes it out as deliberately inconsistent files, and
`expected.json` records the ground truth that the evaluation suite checks against.

Everything produced here is SYNTHETIC — NOT GOVERNMENT DATA.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

SCENARIO_DIR = Path(__file__).parent / "scenarios"

# Academic-year months reported by schools (June–March; April–May are vacation/exams).
MONTHS = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
SEASONAL = {6: -3, 7: -1, 8: 0, 9: 1, 10: 0, 11: -1, 12: -1, 1: 0, 2: 1, 3: -2}
FACILITIES = ["electricity", "drinking_water", "functional_toilet", "adequate_classrooms", "library", "ramp"]

# Structural model coefficients (the "truth" analytics should rediscover, never read directly).
COEF = {"intercept": 8.0, "att": 0.6, "mvac": -30.0, "infra": 10.0, "rural": -2.5, "tdl": -0.25}
LIT_COEF = {"intercept": 14.0, "att": 0.55, "lvac": -15.0, "infra": 8.0, "rural": -2.0, "tdl": -0.2}

ADVERSE = {"vacancy_rise", "attendance_decline", "infra_gap", "unexplained_decline", "insufficient_evidence"}
SIGNAL_OF_EFFECT = {
    "vacancy_rise": "maths_vacancy",
    "attendance_decline": "student_attendance",
    "infra_gap": "infrastructure",
}

BLOCK_NAME_POOL = [
    "Amla",
    "Barwah",
    "Chandla",
    "Deori",
    "Etawa",
    "Gohad",
    "Hatta",
    "Jatara",
    "Kasrawad",
    "Lahar",
    "Mehgaon",
    "Niwari",
    "Pawai",
    "Raghogarh",
    "Sanwer",
    "Tendukheda",
    "Udaipura",
    "Vijaypur",
    "Waraseoni",
    "Zirnia",
    "Bichhiya",
    "Chourai",
    "Dindori",
    "Garoth",
    "Harrai",
    "Jaithari",
    "Khaknar",
    "Lanji",
    "Mohgaon",
    "Nasrullaganj",
    "Pansemal",
    "Rampur",
    "Sihawal",
    "Timarni",
    "Umaria",
    "Vidisha Rural",
    "Badi",
    "Chachaura",
    "Dhimarkheda",
    "Gyaraspur",
    "Kurwai",
    "Majhauli",
    "Narsinghgarh",
    "Patharia",
    "Rehli",
    "Shahpura",
]
DISTRICT_NAME_POOL = ["Antarpur", "Belgarh", "Chandrapura", "Dhaulagiri", "Ekamra", "Gopalganj Rural"]
VILLAGE_SYLLABLES_A = [
    "Khar",
    "Bel",
    "Sir",
    "Dhan",
    "Mal",
    "Kes",
    "Pip",
    "Ram",
    "Sham",
    "Gor",
    "Hir",
    "Jam",
    "Kal",
    "Lak",
    "Man",
    "Nim",
    "Pal",
    "Sag",
    "Tal",
    "Ud",
    "Ven",
    "Bor",
    "Char",
    "Dev",
]
VILLAGE_SYLLABLES_B = [
    "pada",
    "gaon",
    "pur",
    "ora",
    "wadi",
    "kheda",
    "nagar",
    "tola",
    "khedi",
    "ganj",
    "garh",
    "pura",
    "bari",
    "dih",
    "sar",
    "ner",
]
SCHOOL_TYPES = [
    ("Government Primary School", 0.45),
    ("Zilla Parishad Primary School", 0.25),
    ("Government Upper Primary School", 0.15),
    ("Municipal Primary School", 0.08),
    ("Kasturba Primary School", 0.07),
]


@dataclass
class Scenario:
    name: str
    seed: int
    years: list[str]
    state: str
    schools_per_block: int
    election: dict
    mess: dict
    districts: list[dict]
    description: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def baseline_year(self) -> str:
        return self.years[0]

    @property
    def latest_year(self) -> str:
        return self.years[-1]


def load_scenario(name_or_path: str | Path, overrides: dict | None = None) -> Scenario:
    path = Path(name_or_path)
    if not path.exists():
        path = SCENARIO_DIR / f"{name_or_path}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    overrides = overrides or {}
    if "seed" in overrides and overrides["seed"] is not None:
        raw["seed"] = int(overrides["seed"])
    if overrides.get("mess"):
        raw["mess"] = {**raw.get("mess", {}), **overrides["mess"]}
    if overrides.get("name"):
        raw["name"] = overrides["name"]
    rng = np.random.default_rng(raw["seed"])
    districts = raw.get("districts") or _randomize(raw["randomize"], rng)
    return Scenario(
        name=raw["name"],
        seed=raw["seed"],
        years=raw["years"],
        state=raw.get("state", "Fictional State"),
        schools_per_block=raw.get("schools_per_block", 40),
        election=raw.get("election", {}),
        mess=raw.get("mess", {}),
        districts=districts,
        description=raw.get("description", ""),
        raw=raw,
    )


def list_scenarios() -> list[dict]:
    out = []
    for p in sorted(SCENARIO_DIR.glob("*.yaml")):
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        out.append(
            {
                "name": raw["name"],
                "description": raw.get("description", "").strip(),
                "seed": raw["seed"],
                "mess": raw.get("mess", {}),
                "randomized": "randomize" in raw,
            }
        )
    return out


def _random_effect(kind: str, rng: np.random.Generator) -> dict | None:
    u = lambda a, b: round(float(rng.uniform(a, b)), 2)  # noqa: E731
    if kind == "none":
        return None
    if kind == "vacancy_rise":
        return {"type": kind, "start": 1, "to": u(0.36, 0.5)}
    if kind == "attendance_decline":
        return {"type": kind, "start": 1, "drop": u(11, 16), "months": [11, 12, 1, 2]}
    if kind == "unexplained_decline":
        return {"type": kind, "start": 1, "drop": u(11, 14)}
    if kind == "insufficient_evidence":
        return {"type": kind, "start": 2, "drop": u(7, 10), "missing_attendance": 0.8, "drop_teacher_file": True}
    if kind == "infra_gap":
        return {"type": kind, "start": 1, "share_schools": u(0.6, 0.7), "facilities_lost": 4}
    if kind == "improvement":
        return {"type": kind, "start": 1, "attendance_gain": u(4, 6), "vacancy_to": 0.04, "extra": 1.0}
    if kind == "methodology_change":
        return {"type": kind, "start": 2, "assessment_type": "SLAS", "max_marks": 50, "coverage": 0.45}
    if kind == "election_disruption":
        return {"type": kind, "teacher_days_lost": u(15, 19)}
    raise ValueError(kind)


def _randomize(spec: dict, rng: np.random.Generator) -> list[dict]:
    n_d, n_b = spec["districts"], spec["blocks_per_district"]
    names = list(rng.permutation(BLOCK_NAME_POOL))[: n_d * n_b]
    dnames = list(rng.permutation(DISTRICT_NAME_POOL))[:n_d]
    pool = spec["effect_pool"]
    overlap_prob = float(spec.get("overlap_prob", 0.0))
    districts = []
    for di in range(n_d):
        blocks = []
        for bi in range(n_b):
            kind = pool[int(rng.integers(len(pool)))]
            effects = [e for e in [_random_effect(kind, rng)] if e]
            if effects and kind in SIGNAL_OF_EFFECT and rng.random() < overlap_prob:
                other = [k for k in SIGNAL_OF_EFFECT if k != kind]
                effects.append(_random_effect(other[int(rng.integers(len(other)))], rng))
            blocks.append(
                {
                    "name": str(names[di * n_b + bi]),
                    "rural_share": round(float(rng.uniform(0.4, 0.9)), 2),
                    "effects": effects,
                }
            )
        districts.append({"name": str(dnames[di]), "shift": round(float(rng.normal(0, 1.5)), 2), "blocks": blocks})
    return districts


def _progress(t: int, start: int, n_years: int) -> float:
    if t < start:
        return 0.0
    return (t - start + 1) / max(1, n_years - start)


def _village_names(rng: np.random.Generator, n: int) -> list[str]:
    names: set[str] = set()
    while len(names) < n:
        names.add(rng.choice(VILLAGE_SYLLABLES_A) + rng.choice(VILLAGE_SYLLABLES_B))
    return sorted(names)


def generate_truth(sc: Scenario) -> dict:
    """Build the true school registry, monthly attendance and school-year panel."""
    rng = np.random.default_rng(sc.seed)
    n_years = len(sc.years)
    el = sc.election or {}
    el_year = el.get("year_index", n_years - 1)
    el_months = el.get("months", [11, 12])
    tdl_lo, tdl_hi = el.get("teacher_days_lost", [5, 10])

    schools, panel, monthly, events, block_meta = [], [], [], [], []
    type_names = [t for t, _ in SCHOOL_TYPES]
    type_p = np.array([p for _, p in SCHOOL_TYPES])

    for di, d in enumerate(sc.districts):
        d_shift = float(d.get("shift", 0.0))
        for bi, b in enumerate(d["blocks"]):
            bname = b["name"]
            effects = b.get("effects", []) or []
            eff = {e["type"]: e for e in effects}
            rural_share = float(b.get("rural_share", 0.7))
            b_shift = float(rng.normal(0, 2.0))
            b_att = float(rng.normal(0, 1.5))
            base_mvac = float(rng.uniform(0.08, 0.14))
            base_lvac = float(rng.uniform(0.05, 0.10))
            n = int(sc.schools_per_block * rng.uniform(0.9, 1.1))
            # ~6% of villages host two schools, which creates genuinely ambiguous name matches.
            n_villages = max(1, int(n * 0.94))
            villages = _village_names(rng, n_villages)
            village_of = list(villages) + list(rng.choice(villages, n - n_villages, replace=True))
            tdl_block = [0.0] * n_years
            tdl_block[el_year] = float(
                eff.get("election_disruption", {}).get("teacher_days_lost", rng.uniform(tdl_lo, tdl_hi))
            )
            block_meta.append(
                {"district": d["name"], "block": bname, "effects": effects, "teacher_days_lost": tdl_block}
            )
            if tdl_block[el_year] > 0:
                start_m = el_months[0]
                yr0 = int(sc.years[el_year][:4])
                yr = yr0 if start_m >= 6 else yr0 + 1
                events.append(
                    {
                        "district": d["name"],
                        "block": bname,
                        "event": "Assembly election duty",
                        "start": f"{yr}-{start_m:02d}-01",
                        "end": f"{yr}-{el_months[-1]:02d}-28",
                        "teacher_days_lost": round(tdl_block[el_year], 1),
                        "year": sc.years[el_year],
                        "source": "District Election Office (synthetic)",
                    }
                )
            used_names: set[str] = set()
            infra_gap_sel = None
            if "infra_gap" in eff:
                infra_gap_sel = rng.random(n) < eff["infra_gap"]["share_schools"]
            for si in range(n):
                village = village_of[si]
                stype = str(rng.choice(type_names, p=type_p))
                sname = f"{stype} {village}"
                k = 2
                while sname in used_names:
                    sname = f"{stype} {village} {k}"
                    k += 1
                used_names.add(sname)
                code = f"99{di + 1:02d}{bi + 1:02d}{si + 1:03d}{int(rng.integers(10, 99)):02d}"
                rural = int(rng.random() < rural_share)
                enrol = int(rng.integers(40, 180) if rural else rng.integers(120, 420))
                mgmt = "Local Body" if "Zilla" in stype or "Municipal" in stype else "Department of Education"
                cluster = f"{bname} CRC-{(si // 12) + 1}"
                schools.append(
                    {
                        "udise_code": code,
                        "school_name": sname,
                        "district": d["name"],
                        "block": bname,
                        "cluster": cluster,
                        "management": mgmt,
                        "rural": rural,
                        "enrolment": enrol,
                        "village": village,
                        "school_type": stype,
                    }
                )
                # Latent, persistent school characteristics.
                u_s = float(rng.normal(0, 4.0))
                u_l = float(rng.normal(0, 4.0))
                att_base = float(np.clip(rng.normal(86 + b_att - 1.5 * rural, 3.5), 65, 97))
                tatt_base = float(np.clip(rng.normal(91, 3), 75, 99))
                m_posts = int(rng.choice([1, 2, 2, 3, 3, 4]))
                l_posts = int(rng.choice([1, 2, 2, 3]))
                m_u = rng.random(m_posts)
                l_u = rng.random(l_posts)
                fac_p = 0.88 - 0.08 * rural
                fac_latent = rng.random(len(FACILITIES))
                fac_base = fac_latent < fac_p
                lost_idx = rng.permutation(len(FACILITIES))
                tdl_scale = float(rng.uniform(0.5, 1.5))
                att_mult = float(rng.uniform(0.4, 1.6))  # migration/attendance effects vary by village
                for t, year in enumerate(sc.years):
                    # --- Factors ---
                    att_shift = 0.0
                    month_weights = dict.fromkeys(MONTHS, 1.0)
                    mvac_rate, lvac_rate = base_mvac, base_lvac
                    extra = 0.0
                    if "attendance_decline" in eff:
                        e = eff["attendance_decline"]
                        p = _progress(t, e.get("start", 1), n_years)
                        att_shift -= e["drop"] * p * att_mult
                        mig = set(e.get("months", []))
                        if mig:
                            hi_w = len(MONTHS) / (len(mig) * 1.6 + (len(MONTHS) - len(mig)) * 0.6)
                            month_weights = {m: (1.6 if m in mig else 0.6) * hi_w for m in MONTHS}
                    if "vacancy_rise" in eff:
                        e = eff["vacancy_rise"]
                        p = _progress(t, e.get("start", 1), n_years)
                        mvac_rate = base_mvac + (e["to"] - base_mvac) * p
                    if "improvement" in eff:
                        e = eff["improvement"]
                        p = _progress(t, e.get("start", 1), n_years)
                        att_shift += e.get("attendance_gain", 4) * p
                        mvac_rate = base_mvac + (e.get("vacancy_to", 0.04) - base_mvac) * p
                        lvac_rate = base_lvac + (e.get("vacancy_to", 0.04) - base_lvac) * p
                        extra += e.get("extra", 1.0) * p
                    if "unexplained_decline" in eff:
                        e = eff["unexplained_decline"]
                        extra -= e["drop"] * _progress(t, e.get("start", 1), n_years)
                    if "insufficient_evidence" in eff:
                        e = eff["insufficient_evidence"]
                        extra -= e["drop"] * _progress(t, e.get("start", 2), n_years)
                    m_vacant = int((m_u < mvac_rate).sum())
                    l_vacant = int((l_u < lvac_rate).sum())
                    fac = fac_base.copy()
                    if infra_gap_sel is not None and infra_gap_sel[si] and t >= eff["infra_gap"].get("start", 1):
                        fac[lost_idx[: eff["infra_gap"].get("facilities_lost", 3)]] = False
                    infra = float(fac.mean())
                    tdl = tdl_block[t] * tdl_scale
                    # --- Monthly attendance ---
                    att_vals, tatt_vals = [], []
                    for m in MONTHS:
                        a = att_base + SEASONAL[m] + att_shift * month_weights[m] + rng.normal(0, 1.8)
                        ta = tatt_base + rng.normal(0, 1.5)
                        if t == el_year and m in el_months and tdl > 0:
                            ta -= tdl / len(el_months) / 22 * 100
                        a, ta = float(np.clip(a, 30, 99.5)), float(np.clip(ta, 20, 100))
                        att_vals.append(a)
                        tatt_vals.append(ta)
                        cal_year = int(year[:4]) + (1 if m < 6 else 0)
                        monthly.append(
                            {
                                "udise_code": code,
                                "academic_year": year,
                                "year": cal_year,
                                "month": m,
                                "student_att_pct": round(a, 1),
                                "teacher_att_pct": round(ta, 1),
                                "days_open": int(rng.integers(20, 25)),
                            }
                        )
                    att = float(np.mean(att_vals))
                    mvac = m_vacant / m_posts
                    lvac = l_vacant / l_posts
                    # --- Outcomes ---
                    num = (
                        COEF["intercept"]
                        + d_shift
                        + b_shift
                        + COEF["att"] * att
                        + COEF["mvac"] * mvac
                        + COEF["infra"] * infra
                        + COEF["rural"] * rural
                        + COEF["tdl"] * tdl
                        + u_s
                        + extra
                        + rng.normal(0, 2.5)
                    )
                    lit = (
                        LIT_COEF["intercept"]
                        + d_shift
                        + b_shift
                        + LIT_COEF["att"] * att
                        + LIT_COEF["lvac"] * lvac
                        + LIT_COEF["infra"] * infra
                        + LIT_COEF["rural"] * rural
                        + LIT_COEF["tdl"] * tdl
                        + u_l
                        + 0.5 * extra
                        + rng.normal(0, 2.5)
                    )
                    num, lit = float(np.clip(num, 5, 98)), float(np.clip(lit, 5, 98))
                    enrol3 = max(8, int(enrol / 8 * rng.uniform(0.9, 1.1)))
                    coverage = float(rng.uniform(0.85, 0.97))
                    a_type, max_marks, method_v = "FLN-NAS", 100, "v1"
                    if "methodology_change" in eff and t >= eff["methodology_change"].get("start", 2):
                        e = eff["methodology_change"]
                        a_type, max_marks, method_v = e.get("assessment_type", "SLAS"), e.get("max_marks", 50), "v2"
                        coverage = float(e.get("coverage", 0.45)) * rng.uniform(0.9, 1.1)
                        num -= 6.0  # different instrument: scores are not comparable with earlier years
                        lit -= 4.0
                    panel.append(
                        {
                            "udise_code": code,
                            "academic_year": year,
                            "district": d["name"],
                            "block": bname,
                            "numeracy": round(num, 1),
                            "literacy": round(lit, 1),
                            "student_att": round(att, 2),
                            "teacher_att": round(float(np.mean(tatt_vals)), 2),
                            "maths_sanctioned": m_posts,
                            "maths_vacant": m_vacant,
                            "lang_sanctioned": l_posts,
                            "lang_vacant": l_vacant,
                            "infra_index": round(infra, 3),
                            **{f: int(v) for f, v in zip(FACILITIES, fac, strict=True)},
                            "teacher_days_lost": round(tdl, 1),
                            "rural": rural,
                            "enrolment": enrol,
                            "grade3_enrolment": enrol3,
                            "students_assessed": max(3, int(enrol3 * coverage)),
                            "coverage_pct": round(min(coverage, 1.0) * 100, 1),
                            "assessment_type": a_type,
                            "max_marks": max_marks,
                            "methodology_version": method_v,
                        }
                    )

    # State-wide calendar context (no teacher days lost, shown on the context timeline).
    for year in sc.years:
        y1 = int(year[:4]) + 1
        events.append(
            {
                "district": "ALL",
                "block": "ALL",
                "event": "Annual examinations",
                "start": f"{y1}-03-01",
                "end": f"{y1}-03-25",
                "teacher_days_lost": 0,
                "year": year,
                "source": "State calendar (synthetic)",
            }
        )
    return {
        "schools": pd.DataFrame(schools),
        "panel": pd.DataFrame(panel),
        "monthly": pd.DataFrame(monthly),
        "events": pd.DataFrame(events),
        "block_meta": block_meta,
    }


def build_expected(sc: Scenario, truth: dict) -> dict:
    """Ground truth used by the evaluation suite."""
    el_year = (sc.election or {}).get("year_index", len(sc.years) - 1)
    blocks = {}
    election_blocks, non_comparable = [], []
    for bm in truth["block_meta"]:
        types = [e["type"] for e in bm["effects"]]
        signals = sorted({SIGNAL_OF_EFFECT[t] for t in types if t in SIGNAL_OF_EFFECT})
        adverse = [t for t in types if t in ADVERSE]
        if "insufficient_evidence" in types:
            status = "insufficient"
        elif "methodology_change" in types:
            status = "non_comparable"
        elif "unexplained_decline" in types and not signals:
            status = "unexplained"
        elif signals:
            status = "decline"
        elif "improvement" in types:
            status = "improving"
        else:
            status = "stable"
        if bm["teacher_days_lost"][el_year] >= 14:
            election_blocks.append(bm["block"])
        if "methodology_change" in types:
            start = next(e for e in bm["effects"] if e["type"] == "methodology_change").get("start", 2)
            non_comparable.append({"block": bm["block"], "from": sc.years[start - 1], "to": sc.years[start]})
        blocks[bm["block"]] = {
            "district": bm["district"],
            "effects": types,
            "expected_signals": signals,
            "overlap": len(adverse) >= 2,
            "status": status,
            "teacher_days_lost": [round(x, 1) for x in bm["teacher_days_lost"]],
        }
    return {
        "scenario": sc.name,
        "seed": sc.seed,
        "years": sc.years,
        "baseline_year": sc.baseline_year,
        "latest_year": sc.latest_year,
        "n_schools": len(truth["schools"]),
        "blocks": blocks,
        "election_affected_blocks": election_blocks,
        "non_comparable": non_comparable,
        "always_allowed_signals": ["teacher_attendance"],
        "note": "SYNTHETIC — NOT GOVERNMENT DATA. Ground truth for evaluation only.",
    }


def generate(name_or_path: str | Path, out_root: Path, overrides: dict | None = None) -> dict:
    """Generate truth, messy raw files and expected.json. Returns a summary dict."""
    from .messify import write_messy_files

    sc = load_scenario(name_or_path, overrides)
    truth = generate_truth(sc)
    expected = build_expected(sc, truth)
    out_dir = Path(out_root) / sc.name
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for old in raw_dir.glob("*"):
        old.unlink()
    rng = np.random.default_rng(sc.seed + 1)
    files, matches = write_messy_files(sc, truth, raw_dir, rng)
    expected["matches"] = matches
    expected["files"] = files
    (out_dir / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    truth_dir = out_dir / "truth"
    truth_dir.mkdir(exist_ok=True)
    truth["panel"].to_csv(truth_dir / "panel_truth.csv", index=False)
    return {
        "scenario": sc.name,
        "seed": sc.seed,
        "out_dir": str(out_dir),
        "raw_dir": str(raw_dir),
        "files": files,
        "n_schools": expected["n_schools"],
        "n_blocks": len(expected["blocks"]),
        "name_variants": len(matches),
    }
