"""Shared fixture: a small randomised scenario ingested into an isolated test warehouse."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ["LLM_DISABLED"] = "1"


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory):
    from app import db
    from app.ingest.pipeline import run_ingest
    from app.sources.synthetic_files import SyntheticFileAdapter
    from scenario_lab.generator import generate

    root = tmp_path_factory.mktemp("sp")
    res = generate("test_random_a", root, {"name": "pytest_scenario"})
    rel = os.path.relpath(root / "test.db", BACKEND)
    os.environ["SHIKSHAPULSE_DB"] = rel
    db.reset_engine()
    db.engine()
    run_ingest(SyntheticFileAdapter(raw_dir=Path(res["raw_dir"])).fetch(), use_ai=False)
    import json
    expected = json.loads((Path(res["out_dir"]) / "expected.json").read_text(encoding="utf-8"))
    return {"expected": expected, "raw_dir": Path(res["raw_dir"])}
