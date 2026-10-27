"""Data-source adapter contract.

Every source — synthetic demo files, department uploads, or (future) authorised government
APIs — yields `RawDataset`s. The ingestion pipeline, warehouse, analytics and frontend never
know which adapter produced the data; they only see the provenance tier recorded on each row.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class RawDataset:
    name: str                      # file or resource name
    frame: pd.DataFrame            # header-detected, all values as strings
    source_ref: str                # path / URI
    adapter: str                   # adapter key
    provenance: str                # synthetic_demo | department_uploaded | verified_official
    year_hint: str | None = None   # academic year inferred from the name, if any
    kind_hint: str | None = None   # assessment | attendance | teachers | udise | context
    notes: list[str] = field(default_factory=list)


class SourceAdapter(ABC):
    key: str = "base"
    label: str = "Base adapter"
    available: bool = True
    requirements: dict = {}

    @abstractmethod
    def fetch(self) -> list[RawDataset]:
        ...

    def describe(self) -> dict:
        return {"key": self.key, "label": self.label, "available": self.available,
                "requirements": self.requirements}
