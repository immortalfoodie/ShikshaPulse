"""Mutable runtime state (active scenario, ingest jobs) and bootstrap helpers."""

from __future__ import annotations

import threading
import time
import uuid

from . import db
from .config import SCENARIO_OUT, settings

STATE = {"active_scenario": None}
JOBS: dict[str, dict] = {}
PREVIEWS: dict[str, dict] = {}
_ingest_lock = threading.Lock()


def active_scenario() -> str:
    return STATE["active_scenario"] or settings()["active_scenario"]


def ensure_scenario(name: str | None = None) -> None:
    from scenario_lab.generator import generate

    name = name or active_scenario()
    if not (SCENARIO_OUT / name / "raw").exists() or not any((SCENARIO_OUT / name / "raw").iterdir()):
        generate(name, SCENARIO_OUT)


def datasets_for(adapter: str):
    from .sources import get_adapter

    if adapter == "synthetic_files":
        ensure_scenario()
        return get_adapter("synthetic_files", scenario=active_scenario()).fetch()
    return get_adapter(adapter).fetch()


def start_job(
    adapter: str,
    overrides: dict | None = None,
    preview_id: str | None = None,
    use_ai: bool = True,
    user: dict | None = None,
) -> str:
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {
        "id": jid,
        "status": "running",
        "progress": 0.0,
        "steps": [],
        "result": None,
        "error": None,
        "adapter": adapter,
        "started": time.time(),
    }

    def say(step: str, detail: str, pct: float) -> None:
        JOBS[jid]["progress"] = pct
        JOBS[jid]["steps"].append({"step": step, "detail": detail, "t": round(time.time() - JOBS[jid]["started"], 1)})

    def work() -> None:
        from .ingest.pipeline import run_ingest

        with _ingest_lock:
            try:
                ds = datasets_for(adapter)
                previews = PREVIEWS.get(preview_id, {}).get("files") if preview_id else None
                res = run_ingest(ds, overrides, say, use_ai=use_ai, previews=previews)
                from .actions.service import seed_demo_actions

                if settings()["mode"] == "demo":
                    from .visits import seed_demo_visits

                    seed_demo_visits()
                    seed_demo_actions()
                JOBS[jid].update(status="done", result=res, progress=1.0)
                if user:
                    from .auth import audit

                    audit(
                        user, "ingest", {"adapter": adapter, "files": res.get("files"), "seconds": res.get("seconds")}
                    )
            except Exception as e:
                import traceback

                traceback.print_exc()
                JOBS[jid].update(status="error", error=f"{type(e).__name__}: {e}")

    threading.Thread(target=work, daemon=True).start()
    return jid


def bootstrap(force: bool = False) -> dict | None:
    """First run: generate the demo scenario, ingest it and seed simulated actions."""
    from .actions.service import seed_demo_actions
    from .ingest.pipeline import run_ingest
    from .visits import seed_demo_visits

    if db.table_exists("panel") and not force:
        seed_demo_visits()
        seed_demo_actions()
        return None
    ensure_scenario()
    with _ingest_lock:
        res = run_ingest(
            datasets_for("synthetic_files"), use_ai=False, progress=lambda s, d, p: print(f"[bootstrap] {d}")
        )
    seed_demo_visits()
    seed_demo_actions()
    return res
