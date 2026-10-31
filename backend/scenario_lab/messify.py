"""Write the true panel out as messy, inconsistent files — the way departments actually receive them.

Each year uses different column names, file formats (xlsx/csv, wide/long), year formats and value
encodings. Some rows lose their school code and carry a variant school name, some months go
missing, some rows are duplicated or incomplete. Every file carries a SYNTHETIC banner.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .generator import FACILITIES, MONTHS, Scenario

BANNER = "SYNTHETIC — NOT GOVERNMENT DATA (ShikshaPulse Scenario Lab)"
MON = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

ABBREV = {
    "Government Primary School": [
        "Govt. Primary School,",
        "GPS",
        "Govt Pri. Sch.",
        "Government Pry School",
        "Govt. P.S.",
    ],
    "Zilla Parishad Primary School": ["ZP Primary School", "Z.P. Pri. School", "ZPPS", "Zilla Parishad Pri Sch"],
    "Government Upper Primary School": ["Govt. Upper Primary School,", "GUPS", "Govt U.P. School"],
    "Municipal Primary School": ["Mun. Primary School", "MPS", "Municipal Pri. Sch."],
    "Kasturba Primary School": ["Kasturba Pri. School", "Kasturba P.S."],
}


def _typo(word: str, rng: np.random.Generator) -> str:
    if len(word) < 5:
        return word
    i = int(rng.integers(1, len(word) - 2))
    return word[:i] + word[i + 1] + word[i] + word[i + 2 :]


def _variant(school: dict, rng: np.random.Generator) -> str:
    stype, rest = school["school_type"], school["school_name"][len(school["school_type"]) :].strip()
    if rng.random() < 0.12:
        prefix = "Govt School"  # vague: type information lost
    else:
        opts = ABBREV[stype]
        prefix = opts[int(rng.integers(len(opts)))]
    if rng.random() < 0.3:
        parts = rest.split(" ")
        parts[0] = _typo(parts[0], rng)
        rest = " ".join(parts)
    return f"{prefix} {rest}"


class _Mess:
    """Per-file helper that blanks codes, records ground truth and injects defects."""

    def __init__(self, sc: Scenario, schools: pd.DataFrame, rng: np.random.Generator, matches: list):
        self.sc, self.rng, self.matches = sc, rng, matches
        self.schools = schools.set_index("udise_code")
        shared = schools.groupby(["block", "village"]).udise_code.transform("count") > 1
        self.ambiguous = set(schools.loc[shared, "udise_code"])

    def variant_map(self, source: str, year: str) -> dict:
        """Choose schools whose code is blanked in this file, and the name they appear under."""
        pct = self.sc.mess.get("name_variant_pct", 0.03)
        codes = self.schools.index.to_numpy()
        chosen = codes[self.rng.random(len(codes)) < pct]
        out = {}
        for c in chosen:
            s = self.schools.loc[c].to_dict()
            name = _variant(s, self.rng)
            out[c] = name
            self.matches.append(
                {
                    "source": source,
                    "academic_year": year,
                    "block": s["block"],
                    "district": s["district"],
                    "name_variant": name,
                    "true_udise": c,
                    "ambiguous": bool(c in self.ambiguous or name.startswith("Govt School")),
                }
            )
        return out

    def finish(self, df: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
        rng, m = self.rng, self.sc.mess
        # Incomplete rows: blank a value cell.
        inc = rng.random(len(df)) < m.get("incomplete_rows_pct", 0.01)
        if value_cols and inc.any():
            col = value_cols[0]
            df.loc[inc, col] = np.nan
        # Duplicates.
        dup = df[rng.random(len(df)) < m.get("duplicate_pct", 0.01)]
        df = pd.concat([df, dup]).sort_index(kind="stable").reset_index(drop=True)
        return df


def _write(df: pd.DataFrame, path: Path) -> None:
    if path.suffix == ".xlsx":
        with pd.ExcelWriter(path, engine="openpyxl") as xw:
            df.to_excel(xw, sheet_name="Data", index=False, startrow=2)
            ws = xw.sheets["Data"]
            ws["A1"] = BANNER
            pd.DataFrame(
                {
                    "About": [
                        BANNER,
                        "Generated for demonstration and testing only.",
                        "All schools, codes and values are fictional.",
                    ]
                }
            ).to_excel(xw, sheet_name="About", index=False)
    else:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(f"{BANNER}\n\n")
            df.to_csv(f, index=False)


def write_messy_files(sc: Scenario, truth: dict, raw_dir: Path, rng: np.random.Generator):
    schools: pd.DataFrame = truth["schools"]
    panel: pd.DataFrame = truth["panel"].merge(
        schools[["udise_code", "school_name", "cluster", "management", "village", "school_type"]], on="udise_code"
    )
    monthly: pd.DataFrame = truth["monthly"].merge(
        schools[["udise_code", "school_name", "block", "district"]], on="udise_code"
    )
    matches: list = []
    mess = _Mess(sc, schools, rng, matches)
    y0, y1, y2 = sc.years
    files: list[dict] = []

    # Blocks with an insufficient-evidence effect lose attendance months and teacher rows.
    insuff = {}
    for d in sc.districts:
        for b in d["blocks"]:
            for e in b.get("effects", []) or []:
                if e["type"] == "insufficient_evidence":
                    insuff[b["name"]] = e

    def add(path: Path, kind: str, year: str):
        files.append({"file": path.name, "kind": kind, "academic_year": year})

    def name_code(df: pd.DataFrame, vmap: dict, code_col: str, name_col: str):
        hit = df[code_col].isin(vmap.keys())
        df.loc[hit, name_col] = df.loc[hit, code_col].map(vmap)
        df[code_col] = df[code_col].astype(object)
        df.loc[hit, code_col] = ""
        return df

    # ---------------- Assessment ----------------
    p = panel[panel.academic_year == y0]
    long = pd.concat(
        [
            p.assign(Subject="Mathematics", score=p.numeracy),
            p.assign(Subject="Language", score=p.literacy),
        ]
    ).sort_values(["udise_code", "Subject"])
    a0 = pd.DataFrame(
        {
            "UDISE_SCH_CODE": long.udise_code,
            "School Name": long.school_name,
            "District": long.district,
            "Block": long.block,
            "Academic Year": y0,
            "Grade": "Class 3",
            "Subject": long.Subject,
            "Avg Score %": long.score.round(1),
            "Students Assessed": long.students_assessed,
            "Assessment": long.assessment_type,
        }
    ).reset_index(drop=True)
    a0 = name_code(a0, mess.variant_map("assessment", y0), "UDISE_SCH_CODE", "School Name")
    a0 = mess.finish(a0, ["Avg Score %"])
    f = raw_dir / f"Assessment_FLN_{y0}.xlsx"
    _write(a0, f)
    add(f, "assessment", y0)

    p = panel[panel.academic_year == y1].sort_values("udise_code")
    a1 = pd.DataFrame(
        {
            "School Code": p.udise_code,
            "Name of School": p.school_name,
            "Dist": p.district,
            "Block Name": p.block,
            "Year": f"AY {y1[:4]}",
            "Class": 3,
            "Maths %": p.numeracy.round(1),
            "Language %": p.literacy.round(1),
            "No. of Students Assessed": p.students_assessed,
            "Test": p.assessment_type,
        }
    ).reset_index(drop=True)
    a1 = name_code(a1, mess.variant_map("assessment", y1), "School Code", "Name of School")
    a1 = mess.finish(a1, ["Maths %"])
    f = raw_dir / f"assessment results AY{y1[:4]}.csv"
    _write(a1, f)
    add(f, "assessment", y1)

    p = panel[panel.academic_year == y2].sort_values("udise_code")
    scale = p.max_marks / 100.0
    a2 = pd.DataFrame(
        {
            "SchoolCode": p.udise_code,
            "SCHOOL_NAME": p.school_name.str.upper(),
            "DIST": p.district.str.upper(),
            "BLK": p.block.str.upper(),
            "Session": y2.replace("-", "_"),
            "Std": "III",
            "MAT_SCORE": (p.numeracy * scale).round(1),
            "LANG_SCORE": (p.literacy * scale).round(1),
            "Max_Marks": p.max_marks,
            "No_Assessed": p.students_assessed,
            "Assessment_Type": p.assessment_type,
        }
    ).reset_index(drop=True)
    vm = {k: v.upper() for k, v in mess.variant_map("assessment", y2).items()}
    for mt in matches[-len(vm) :] if vm else []:
        mt["name_variant"] = mt["name_variant"].upper()
    a2 = name_code(a2, vm, "SchoolCode", "SCHOOL_NAME")
    a2 = mess.finish(a2, ["MAT_SCORE"])
    f = raw_dir / f"FLN_Assessment_{y2.replace('-', '_')}.xlsx"
    _write(a2, f)
    add(f, "assessment", y2)

    # ---------------- Attendance ----------------
    def drop_months(m: pd.DataFrame, year: str) -> pd.DataFrame:
        keep = rng.random(len(m)) >= sc.mess.get("missing_months_pct", 0.04)
        for blk, e in insuff.items():
            if sc.years.index(year) >= e.get("start", 2):
                sel = (m.block == blk).to_numpy()
                keep &= ~(sel & (rng.random(len(m)) < e.get("missing_attendance", 0.8)))
        return m[keep]

    m0 = drop_months(monthly[monthly.academic_year == y0], y0)
    wide = m0.assign(col=m0.apply(lambda r: f"{MON[r.month]}-{str(r.year)[2:]}", axis=1))
    stu = wide.pivot_table(index="udise_code", columns="col", values="student_att_pct", aggfunc="first")
    tch = wide.pivot_table(index="udise_code", columns="col", values="teacher_att_pct", aggfunc="first")
    order = [f"{MON[m]}-{str(int(y0[:4]) + (1 if m < 6 else 0))[2:]}" for m in MONTHS]
    meta = schools.set_index("udise_code")[["school_name", "block"]]
    at0 = (
        meta.loc[stu.index]
        .reset_index()
        .rename(columns={"udise_code": "UDISE Code", "school_name": "School", "block": "Block"})
    )
    for c in order:
        at0[f"{c} Students"] = stu[c].to_numpy() if c in stu else np.nan
        at0[f"{c} Teachers"] = tch[c].to_numpy() if c in tch else np.nan
    at0 = name_code(at0, mess.variant_map("attendance", y0), "UDISE Code", "School")
    at0 = mess.finish(at0, [])
    f = raw_dir / f"Attendance_Register_{y0.replace('-', '_')}.xlsx"
    _write(at0, f)
    add(f, "attendance", y0)

    m1 = drop_months(monthly[monthly.academic_year == y1], y1).sort_values(["udise_code", "year", "month"])
    at1 = pd.DataFrame(
        {
            "School_ID": m1.udise_code,
            "School Name": m1.school_name,
            "Block": m1.block,
            "Month": m1.year.astype(str) + "-" + m1.month.map(lambda x: f"{x:02d}"),
            "Student Att %": m1.student_att_pct,
            "Teacher Att %": m1.teacher_att_pct,
            "Working Days": m1.days_open,
        }
    ).reset_index(drop=True)
    at1 = name_code(at1, mess.variant_map("attendance", y1), "School_ID", "School Name")
    at1 = mess.finish(at1, ["Student Att %"])
    f = raw_dir / f"attendance_monthly_{y1}.csv"
    _write(at1, f)
    add(f, "attendance", y1)

    m2 = drop_months(monthly[monthly.academic_year == y2], y2).sort_values(["udise_code", "year", "month"])
    at2 = pd.DataFrame(
        {
            "udise": m2.udise_code,
            "school_nm": m2.school_name,
            "blk_name": m2.block.str.lower(),
            "month_name": m2.month.map(MON),
            "yr": m2.year,
            "avg_attendance": (m2.student_att_pct / 100).round(3),
            "teacher_attendance": (m2.teacher_att_pct / 100).round(3),
            "days": m2.days_open,
        }
    ).reset_index(drop=True)
    at2 = name_code(at2, mess.variant_map("attendance", y2), "udise", "school_nm")
    at2 = mess.finish(at2, ["avg_attendance"])
    f = raw_dir / f"StudentAttendance_FY{y2}.csv"
    _write(at2, f)
    add(f, "attendance", y2)

    # ---------------- Teachers (vacancy snapshot) ----------------
    def teacher_long(year: str) -> pd.DataFrame:
        p = panel[panel.academic_year == year]
        if sc.years.index(year) >= 2:
            drop = [b for b, e in insuff.items() if e.get("drop_teacher_file")]
            p = p[~p.block.isin(drop)]
        t = (
            pd.concat(
                [
                    p.assign(subj="M", sanc=p.maths_sanctioned, vac=p.maths_vacant),
                    p.assign(subj="L", sanc=p.lang_sanctioned, vac=p.lang_vacant),
                ]
            )
            .sort_values(["udise_code", "subj"])
            .reset_index(drop=True)
        )
        t["work"] = t.sanc - t.vac
        return t

    t = teacher_long(y0)
    t0 = pd.DataFrame(
        {
            "UDISE Code": t.udise_code,
            "School Name": t.school_name,
            "Block": t.block,
            "Subject": t.subj.map({"M": "Mathematics", "L": "Language"}),
            "Sanctioned Posts": t.sanc,
            "Working": t.work,
            "Vacant": t.vac,
            "As On": f"30/09/{y0[:4]}",
        }
    )
    t0 = name_code(t0, mess.variant_map("teachers", y0), "UDISE Code", "School Name")
    t0 = mess.finish(t0, [])
    f = raw_dir / f"Teacher_Vacancy_Sep{y0[:4]}.csv"
    _write(t0, f)
    add(f, "teachers", y0)

    t = teacher_long(y1)
    t1 = pd.DataFrame(
        {
            "School Code": t.udise_code,
            "School": t.school_name,
            "Block Name": t.block,
            "Subject Name": t.subj.map({"M": "Maths", "L": "Lang"}),
            "Sanctioned": t.sanc,
            "In Position": t.work,
            "Date": f"{y1[:4]}-09-30",
        }
    )
    t1 = name_code(t1, mess.variant_map("teachers", y1), "School Code", "School")
    t1 = mess.finish(t1, [])
    f = raw_dir / f"TeacherPositions_{y1}.xlsx"
    _write(t1, f)
    add(f, "teachers", y1)

    t = teacher_long(y2)
    t2 = pd.DataFrame(
        {
            "SCH_CODE": t.udise_code,
            "SCH_NAME": t.school_name,
            "BLOCK_NM": t.block.str.upper(),
            "SUBJ": t.subj.map({"M": "MATH", "L": "LANG"}),
            "SANC": t.sanc,
            "WORKING": t.work,
            "VAC": t.vac,
            "SNAPSHOT": f"Sep {y2[:4]}",
        }
    )
    t2 = name_code(t2, mess.variant_map("teachers", y2), "SCH_CODE", "SCH_NAME")
    t2 = mess.finish(t2, [])
    f = raw_dir / f"teacher_vacancy_{y2}.csv"
    _write(t2, f)
    add(f, "teachers", y2)

    # ---------------- UDISE+ (school master + infrastructure) ----------------
    yn = lambda s: s.map({1: "Yes", 0: "No"})  # noqa: E731
    p = panel[panel.academic_year == y0].sort_values("udise_code")
    u0 = pd.DataFrame(
        {
            "udise_sch_code": p.udise_code,
            "school_name": p.school_name,
            "district_name": p.district,
            "block_name": p.block,
            "cluster_name": p.cluster,
            "management": p.management,
            "location": p.rural.map({1: "Rural", 0: "Urban"}),
            "total_enrolment": p.enrolment,
            "class3_enrolment": p.grade3_enrolment,
            **{f: yn(p[f]) for f in FACILITIES},
        }
    )
    f = raw_dir / f"UDISE_Plus_{y0}.xlsx"
    _write(u0, f)
    add(f, "udise", y0)

    p = panel[panel.academic_year == y1].sort_values("udise_code")
    u1 = pd.DataFrame(
        {
            "UDISE Code": p.udise_code,
            "School": p.school_name,
            "District": p.district,
            "Block": p.block,
            "Cluster": p.cluster,
            "Mgmt": p.management,
            "Rural/Urban": p.rural.map({1: "R", 0: "U"}),
            "Enrolment": p.enrolment,
            "Enrolment Class III": p.grade3_enrolment,
            "Elec": p.electricity,
            "Water": p.drinking_water,
            "Toilet": p.functional_toilet,
            "Classrooms OK": p.adequate_classrooms,
            "Library": p.library,
            "Ramp": p.ramp,
        }
    )
    f = raw_dir / f"udise_{y1.replace('-', '_')}.csv"
    _write(u1, f)
    add(f, "udise", y1)

    p = panel[panel.academic_year == y2].sort_values("udise_code")
    ynn = lambda s: s.map({1: "Y", 0: "N"})  # noqa: E731
    u2 = pd.DataFrame(
        {
            "UDISE_CODE": p.udise_code,
            "SCHOOL_NAME": p.school_name,
            "DISTRICT": p.district,
            "BLOCK": p.block,
            "CLUSTER": p.cluster,
            "MANAGEMENT": p.management,
            "AREA": p.rural.map({1: "RURAL", 0: "URBAN"}),
            "ENROL_TOTAL": p.enrolment,
            "ENROL_C3": p.grade3_enrolment,
            "ELECTRICITY": ynn(p.electricity),
            "WATER": ynn(p.drinking_water),
            "TOILET": ynn(p.functional_toilet),
            "CLASSROOMS": ynn(p.adequate_classrooms),
            "LIBRARY": ynn(p.library),
            "RAMP": ynn(p.ramp),
            "YEAR": y2.replace("-", "/"),
        }
    )
    f = raw_dir / f"UDISE+_{y2}.xlsx"
    _write(u2, f)
    add(f, "udise", y2)

    # ---------------- Context calendar ----------------
    ev = truth["events"]
    c = pd.DataFrame(
        {
            "District": ev.district,
            "Block": ev.block,
            "Event": ev.event,
            "From": ev.start,
            "To": ev.end,
            "Teacher days lost": ev.teacher_days_lost,
            "Source": ev.source,
        }
    )
    f = raw_dir / f"Context_Calendar_{y0[:4]}-{y2[:4]}.csv"
    _write(c, f)
    add(f, "context", "all")
    return files, matches
