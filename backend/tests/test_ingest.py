"""Mapping, normalisation, matching and pipeline tests."""
import pandas as pd

from app.ingest.mapper import detect_kind, map_columns, mapping_dict
from app.ingest.matcher import SchoolRegistry, norm_name
from app.ingest.normalise import norm_year, parse_month, to_pct
from app.sources.readers import read_table, year_hint_from_name


def test_year_formats():
    for raw in ["2024-25", "2024/25", "2024_25", "AY 2024", "2024-2025", "FY2024-25", 2024]:
        assert norm_year(raw) == "2024-25"
    assert norm_year(None, "2023-24") == "2023-24"


def test_year_hint_from_file_names():
    assert year_hint_from_name("assessment results AY2023.csv") == "2023-24"
    assert year_hint_from_name("Teacher_Vacancy_Sep2022.csv") == "2022-23"
    assert year_hint_from_name("FLN_Assessment_2024_25.xlsx") == "2024-25"


def test_month_parsing():
    assert parse_month("2023-07") == (2023, 7)
    assert parse_month("Jul", 2024) == (2024, 7)
    assert parse_month("Jan-23") == (2023, 1)


def test_fraction_to_percent():
    s, frac = to_pct(pd.Series(["0.82", "0.9"]))
    assert frac and abs(s.iloc[0] - 82) < 1e-9


def test_name_normalisation():
    assert norm_name("Govt. P.S. Kharpada") == norm_name("Government Primary School Kharpada")
    assert norm_name("GUPS Belgaon") == "government upper primary school belgaon"
    assert norm_name("Z.P. Pri. School Sirpur") == "zilla parishad primary school sirpur"


def test_every_scenario_file_maps_without_missing_fields(warehouse):
    registry = {"blocks": list(warehouse["expected"]["blocks"]), "districts": []}
    for p in warehouse["raw_dir"].iterdir():
        df = read_table(p)
        kind, _ = detect_kind(list(df.columns), None)
        m = map_columns(df, kind, registry, use_ai=False)
        assert m["required_missing"] == [], (p.name, m["required_missing"])
        assert "_row" not in mapping_dict(m)


def test_messy_headers_resolved(warehouse):
    p = next(x for x in warehouse["raw_dir"].iterdir() if x.name.startswith("FLN_Assessment"))
    df = read_table(p)
    m = mapping_dict(map_columns(df, "assessment", {"blocks": list(warehouse["expected"]["blocks"])}, use_ai=False))
    assert m["MAT_SCORE"] == "score_maths"
    assert m["BLK"] == "block"
    assert m["Std"] == "grade"


def test_matcher_precision_on_planted_variants(warehouse):
    from app import db
    reg = SchoolRegistry(db.read_df("SELECT * FROM schools"))
    auto = wrong = 0
    for mt in warehouse["expected"]["matches"]:
        r = reg.match_one(mt["name_variant"], mt["block"])
        if r["udise_code"] and r["confidence"] >= reg.auto:
            auto += 1
            wrong += r["udise_code"] != mt["true_udise"]
    assert auto > 0
    assert wrong / auto <= 0.03


def test_panel_built_with_three_years(warehouse):
    from app.analytics.common import panel, years
    assert len(years()) == 3
    p = panel()
    assert p.udise_code.nunique() == warehouse["expected"]["n_schools"]
    assert p.numeracy.notna().mean() > 0.9


def test_review_queue_and_resolution(warehouse):
    from app import db
    from app.ingest.pipeline import resolve_review
    rows = db.query("SELECT * FROM match_review WHERE status='pending'")
    if not rows:
        return
    import json
    r = rows[0]
    cands = json.loads(r["candidates"])
    res = resolve_review(r["id"], cands[0]["udise_code"] if cands else None, "pytest")
    assert res["status"] in ("resolved", "rejected")
