"""State attendance / teacher-HR portal connector — STUB for authorised deployment."""
from __future__ import annotations

from .base import RawDataset, SourceAdapter


class StatePortalAdapter(SourceAdapter):
    key = "state_portal"
    label = "State attendance & teacher-HR portal (authorised integration — not enabled)"
    available = False
    requirements = {
        "access": "MoU or data-sharing order from the State Education Department; read-only service credentials",
        "fields": "monthly student & teacher attendance by school; sanctioned/working posts by subject",
        "not_assumed": "formats differ by state; election-duty deployment may sit with the District Election Office",
        "coverage": "monthly; history depends on the portal's retention",
        "refresh": "monthly batch (or API where available)",
        "controls": "aggregated pulls by default, encryption in transit, audit logging, DPDP Rules 2025 review",
    }

    def fetch(self) -> list[RawDataset]:
        raise NotImplementedError("State portal integration requires authorised access; see requirements.")
