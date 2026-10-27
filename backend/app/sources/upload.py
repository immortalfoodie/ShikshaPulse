"""Department adapter: files uploaded through Data Studio (provenance: department_uploaded)."""
from __future__ import annotations

from pathlib import Path

from ..config import provenance_for, settings
from .base import RawDataset, SourceAdapter
from .readers import kind_hint_from_name, read_table, year_hint_from_name


class UploadAdapter(SourceAdapter):
    key = "upload"
    label = "Department file upload"
    requirements = {"access": "authenticated district/state officer", "fields": "any subset of canonical fields",
                    "coverage": "whatever the department holds", "refresh": "manual upload"}

    def __init__(self, batch: str = "current"):
        self.dir = Path(settings()["uploads_path"]) / batch

    def save(self, filename: str, content: bytes) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.dir / Path(filename).name
        p.write_bytes(content)
        return p

    def clear(self) -> None:
        if self.dir.exists():
            for p in self.dir.iterdir():
                p.unlink()

    def files(self) -> list[Path]:
        if not self.dir.exists():
            return []
        return sorted(p for p in self.dir.iterdir() if p.suffix.lower() in (".csv", ".xlsx", ".xls"))

    def fetch(self) -> list[RawDataset]:
        return [RawDataset(name=p.name, frame=read_table(p), source_ref=str(p), adapter=self.key,
                           provenance=provenance_for(self.key), year_hint=year_hint_from_name(p.name),
                           kind_hint=kind_hint_from_name(p.name)) for p in self.files()]
