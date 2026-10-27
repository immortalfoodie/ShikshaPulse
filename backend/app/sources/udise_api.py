"""UDISE+ API connector — STUB for authorised deployment.

Not callable in the hackathon build. Documents what a real integration needs so the
department can plan access. We do not assume the public API exposes every field below.
"""
from __future__ import annotations

from .base import RawDataset, SourceAdapter


class UdiseApiAdapter(SourceAdapter):
    key = "udise_api"
    label = "UDISE+ API (authorised integration — not enabled)"
    available = False
    requirements = {
        "access": "Registration on the UDISE+ API / Data Sharing portal; MoE or state approval; per-deployment key",
        "fields": "school profile, enrolment by grade, facilities, teacher counts (keyed by UDISE code)",
        "not_assumed": "subject-wise teacher vacancy and monthly attendance are typically NOT available in UDISE+",
        "coverage": "annual snapshots (reference date 30 Sept); historical years subject to portal availability",
        "refresh": "annual, after the state data freeze",
        "controls": "service account, IP allow-listing, audit logging, no student-level PII ingestion",
    }

    def fetch(self) -> list[RawDataset]:
        raise NotImplementedError("UDISE+ integration requires authorised API access; see requirements.")
