"""Source adapter registry."""
from __future__ import annotations

from ..config import active_adapters
from .base import RawDataset, SourceAdapter
from .state_portal import StatePortalAdapter
from .synthetic_files import SyntheticFileAdapter
from .udise_api import UdiseApiAdapter
from .upload import UploadAdapter

REGISTRY = {
    "synthetic_files": SyntheticFileAdapter,
    "upload": UploadAdapter,
    "udise_api": UdiseApiAdapter,
    "state_portal": StatePortalAdapter,
}


def get_adapter(key: str, **kw) -> SourceAdapter:
    return REGISTRY[key](**kw)


def active() -> list[SourceAdapter]:
    return [get_adapter(k) for k in active_adapters()]


def describe_all() -> list[dict]:
    act = set(active_adapters())
    return [{**cls().describe(), "active": k in act} for k, cls in REGISTRY.items()]


__all__ = ["RawDataset", "SourceAdapter", "get_adapter", "active", "describe_all"]
