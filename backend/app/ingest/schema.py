"""Canonical schema: target fields per dataset kind, with known header synonyms."""

from __future__ import annotations

import re

FACILITIES = ["electricity", "drinking_water", "functional_toilet", "adequate_classrooms", "library", "ramp"]

# kind -> field -> synonyms (normalised header text)
CANONICAL: dict[str, dict[str, list[str]]] = {
    "assessment": {
        "udise_code": ["udise code", "udise sch code", "udise", "school code", "schoolcode", "school id", "sch code"],
        "school_name": ["school name", "name of school", "school", "sch name", "school nm"],
        "district": ["district", "district name", "dist"],
        "block": ["block", "block name"],
        "academic_year": ["academic year", "year", "session", "acad year", "ay"],
        "grade": ["grade", "class"],
        "subject": ["subject", "sub", "subject name"],
        "score": ["avg score", "avg score %", "score", "score %", "average score", "mean score"],
        "score_maths": ["maths %", "math %", "mathematics %", "maths score", "math score", "mathematics score"],
        "score_language": ["language %", "lang %", "language score", "lang score"],
        "max_marks": ["max marks", "maximum marks", "out of", "full marks"],
        "students_assessed": ["students assessed", "no of students assessed", "no assessed", "number assessed"],
        "assessment_type": ["assessment", "assessment type", "test", "test name", "survey"],
    },
    "attendance": {
        "udise_code": ["udise code", "udise", "school code", "school id", "sch code", "schoolcode"],
        "school_name": ["school name", "school", "name of school", "school nm", "sch name"],
        "block": ["block", "block name"],
        "month": ["month", "month name", "period"],
        "cal_year": ["yr", "calendar year", "year"],
        "student_att": [
            "student att %",
            "student attendance",
            "student attendance %",
            "avg attendance",
            "attendance %",
            "stu att",
        ],
        "teacher_att": ["teacher att %", "teacher attendance", "teacher attendance %", "tch att"],
        "days_open": ["working days", "days", "days open", "school days"],
    },
    "teachers": {
        "udise_code": ["udise code", "udise", "school code", "sch code", "school id", "schoolcode"],
        "school_name": ["school name", "school", "sch name", "name of school"],
        "block": ["block", "block name"],
        "subject": ["subject", "subject name", "subj", "sub"],
        "sanctioned": ["sanctioned", "sanctioned posts", "sanctioned strength", "sanc"],
        "working": ["working", "in position", "working teachers", "filled", "men in position"],
        "vacant": ["vacant", "vac", "vacancies", "vacant posts"],
        "snapshot_date": ["as on", "date", "snapshot", "as of", "reference date"],
    },
    "udise": {
        "udise_code": ["udise sch code", "udise code", "udise", "school code"],
        "school_name": ["school name", "school", "name of school"],
        "district": ["district name", "district"],
        "block": ["block name", "block"],
        "cluster": ["cluster name", "cluster", "crc"],
        "management": ["management", "mgmt"],
        "location": ["location", "rural urban", "rural/urban", "area"],
        "enrolment": ["total enrolment", "enrolment", "enrol total", "enrollment", "total enrollment"],
        "grade3_enrolment": ["class3 enrolment", "class 3 enrolment", "enrolment class iii", "enrol c3"],
        "electricity": ["electricity", "elec"],
        "drinking_water": ["drinking water", "water"],
        "functional_toilet": ["functional toilet", "toilet"],
        "adequate_classrooms": ["adequate classrooms", "classrooms ok", "classrooms"],
        "library": ["library"],
        "ramp": ["ramp"],
        "academic_year": ["academic year", "year", "session"],
    },
    "context": {
        "district": ["district"],
        "block": ["block"],
        "event": ["event", "event name", "description"],
        "start": ["from", "start", "start date", "from date"],
        "end": ["to", "end", "end date", "to date"],
        "teacher_days_lost": ["teacher days lost", "days lost", "teacher days"],
        "source": ["source", "reported by"],
    },
}

FIELD_HELP = {
    "udise_code": "11-digit UDISE+ school code",
    "school_name": "School name",
    "district": "District name",
    "block": "Block name",
    "academic_year": "Academic year e.g. 2024-25",
    "grade": "Grade/class",
    "subject": "Subject name",
    "score": "Average score (long format)",
    "score_maths": "Maths score (wide)",
    "score_language": "Language score (wide)",
    "max_marks": "Maximum marks / scale",
    "students_assessed": "Number of students assessed",
    "assessment_type": "Assessment instrument",
    "month": "Month (name, number or YYYY-MM)",
    "cal_year": "Calendar year",
    "student_att": "Student attendance",
    "teacher_att": "Teacher attendance",
    "days_open": "Working days",
    "sanctioned": "Sanctioned posts",
    "working": "Teachers in position",
    "vacant": "Vacant posts",
    "snapshot_date": "Snapshot date",
    "cluster": "Cluster",
    "management": "Management",
    "location": "Rural/Urban",
    "enrolment": "Total enrolment",
    "grade3_enrolment": "Grade 3 enrolment",
    "event": "Event",
    "start": "Start date",
    "end": "End date",
    "teacher_days_lost": "Teacher-days lost",
    "source": "Source",
    **{f: f"Facility: {f.replace('_', ' ')}" for f in FACILITIES},
}

REQUIRED = {
    "assessment": [["udise_code", "school_name"], ["score", "score_maths", "score_language"]],
    "attendance": [["udise_code", "school_name"], ["student_att", "__wide__"]],
    "teachers": [["udise_code", "school_name"], ["sanctioned"], ["working", "vacant"]],
    "udise": [["udise_code"], ["school_name"], ["block"]],
    "context": [["event"], ["start"]],
}

WIDE_MONTH = re.compile(
    r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_']*(\d{2,4})\s*[\(\-_ ]*\s*"
    r"(students?|stu|pupils?|teachers?|tch|staff)?\)?$",
    re.I,
)


def norm_header(h: str) -> str:
    s = str(h).lower().replace("%", " % ")
    s = re.sub(r"[^a-z0-9%/]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace(" %", " %").strip()
