"""ShikshaPulse API server.  Run from backend/:  uvicorn app.main:app --port 8000"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from . import db, runtime  # noqa: E402
from .api.routes import router  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.engine()
    runtime.bootstrap()
    yield


app = FastAPI(
    title="ShikshaPulse",
    version="1.0",
    lifespan=lifespan,
    description="District education diagnostic & accountable-action platform",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/api/health")
def health():
    return {"ok": True}


DIST = BACKEND.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
