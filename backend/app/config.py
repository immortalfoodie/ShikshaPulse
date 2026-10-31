"""Runtime configuration: config.yaml + environment (.env)."""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
SCENARIO_OUT = DATA_DIR / "scenarios"

load_dotenv(BACKEND_DIR / ".env")


@lru_cache
def settings() -> dict:
    cfg = yaml.safe_load((BACKEND_DIR / "config.yaml").read_text(encoding="utf-8"))
    cfg["mode"] = os.getenv("SHIKSHAPULSE_MODE", cfg.get("mode", "demo"))
    cfg["warehouse_path"] = str(BACKEND_DIR / os.getenv("SHIKSHAPULSE_DB", cfg["warehouse"]))
    cfg["uploads_path"] = str(BACKEND_DIR / cfg.get("uploads_dir", "data/uploads"))
    return cfg


def active_adapters() -> list[str]:
    cfg = settings()
    return cfg["adapters"][cfg["mode"]]


def provenance_for(adapter: str) -> str:
    return settings()["provenance"].get(adapter, "department_uploaded")


def today() -> date:
    """Reference date. Demo mode pins it so deadlines/overdue states are reproducible."""
    cfg = settings()
    if cfg["mode"] == "demo" and cfg.get("demo_today"):
        return date.fromisoformat(cfg["demo_today"])
    return date.today()


def public_demo() -> bool:
    """On a shared public URL, visitors must not replace the dataset everyone else is viewing."""
    return os.getenv("PUBLIC_DEMO", "").lower() in ("1", "true", "yes")


def app_secret() -> str:
    return os.getenv("APP_SECRET", "shikshapulse-demo-secret")
