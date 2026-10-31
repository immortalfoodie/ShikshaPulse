"""Demo adapter: reads the active Scenario Lab output folder (SYNTHETIC — NOT GOVERNMENT DATA)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from ..config import SCENARIO_OUT, provenance_for, settings
from .base import RawDataset, SourceAdapter
from .readers import kind_hint_from_name, read_table, year_hint_from_name


class SyntheticFileAdapter(SourceAdapter):
    key = "synthetic_files"
    label = "Synthetic scenario files (Scenario Lab)"
    requirements: ClassVar[dict[str, str]] = {
        "access": "none — generated locally",
        "fields": "all canonical fields",
        "coverage": "3 academic years",
        "refresh": "on demand via Scenario Lab",
    }

    def __init__(self, scenario: str | None = None, raw_dir: Path | None = None):
        self.scenario = scenario or settings()["active_scenario"]
        self.raw_dir = Path(raw_dir) if raw_dir else SCENARIO_OUT / self.scenario / "raw"

    def files(self) -> list[Path]:
        if not self.raw_dir.exists():
            return []
        return sorted(p for p in self.raw_dir.iterdir() if p.suffix.lower() in (".csv", ".xlsx", ".xls"))

    def fetch(self) -> list[RawDataset]:
        return [
            RawDataset(
                name=p.name,
                frame=read_table(p),
                source_ref=str(p),
                adapter=self.key,
                provenance=provenance_for(self.key),
                year_hint=year_hint_from_name(p.name),
                kind_hint=kind_hint_from_name(p.name),
            )
            for p in self.files()
        ]
