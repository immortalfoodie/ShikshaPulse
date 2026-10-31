"""Data-source adapter contract.

Every source — synthetic demo files, department uploads, or (future) authorised government
APIs — yields `RawDataset`s. The ingestion pipeline, warehouse, analytics and frontend never
know which adapter produced the data; they only see the provenance tier recorded on each row.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

import pandas as pd


@dataclass
class RawDataset:
    name: str  # file or resource name
    frame: pd.DataFrame  # header-detected, all values as strings
    source_ref: str  # path / URI
    adapter: str  # adapter key
    provenance: str  # synthetic_demo | department_uploaded | verified_official
    year_hint: str | None = None  # academic year inferred from the name, if any
    kind_hint: str | None = None  # assessment | attendance | teachers | udise | context
    notes: list[str] = field(default_factory=list)


class SourceAdapter(ABC):
    """Base class for every data source. Subclasses override the class attributes and `fetch()`."""

    key: str = "base"
    label: str = "Base adapter"
    available: bool = True
    requirements: ClassVar[dict[str, str]] = {}

    @abstractmethod
    def fetch(self) -> list[RawDataset]:
        """Return the raw tables this source currently provides."""

    def describe(self) -> dict:
        """Public metadata shown in Data Studio (what the source is and what access it needs)."""
        return {"key": self.key, "label": self.label, "available": self.available, "requirements": self.requirements}
