"""Ingestion orchestration: adapters → map → normalise → dedupe → match → warehouse (+ lineage)."""

from __future__ import annotations

import io
import json
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime

import pandas as pd

from .. import db
from ..analytics.derive import rebuild_derived
from ..config import settings
from ..sources.base import RawDataset
from .dedupe import dedupe
from .mapper import apply_overrides, detect_kind, map_columns, mapping_dict, mapping_version
from .matcher import SchoolRegistry
from .normalise import (
    normalise_assessment,
    normalise_attendance,
    normalise_context,
    normalise_teachers,
    normalise_udise,
)

KIND_ORDER = {"udise": 0, "context": 1, "assessment": 2, "teachers": 3, "attendance": 4}
TABLE = {
    "assessment": "assessments",
    "attendance": "attendance_monthly",
    "teachers": "teacher_snapshot",
    "udise": "udise_year",
    "context": "context_events",
}

Progress = Callable[[str, str, float], None]


def _registry_hint(datasets: list[RawDataset]) -> dict | None:
    """Known block/district names for value profiling — from the warehouse or the batch's UDISE files."""
    names = {"blocks": set(), "districts": set()}
    if db.table_exists("schools"):
        s = db.read_df("SELECT DISTINCT block, district FROM schools")
        names["blocks"].update(s.block.dropna())
        names["districts"].update(s.district.dropna())
    for ds in datasets:
        kind, _ = detect_kind(list(ds.frame.columns), ds.kind_hint)
        if kind == "udise":
            m = mapping_dict(map_columns(ds.frame, "udise", None, use_ai=False))
            for src, tgt in m.items():
                if tgt == "block":
                    names["blocks"].update(ds.frame[src].dropna().astype(str))
                if tgt == "district":
                    names["districts"].update(ds.frame[src].dropna().astype(str))
    return {k: sorted(v) for k, v in names.items()} if names["blocks"] else None


def preview(datasets: list[RawDataset], use_ai: bool = True) -> list[dict]:
    """Generate column-mapping previews for Data Studio without mutating the warehouse."""
    hint = _registry_hint(datasets)
    out = []
    for ds in sorted(datasets, key=lambda d: KIND_ORDER.get(detect_kind(list(d.frame.columns), d.kind_hint)[0], 9)):
        kind, kconf = detect_kind(list(ds.frame.columns), ds.kind_hint)
        m = map_columns(ds.frame, kind, hint, use_ai=use_ai)
        out.append(
            {
                "file": ds.name,
                "adapter": ds.adapter,
                "provenance": ds.provenance,
                "kind": kind,
                "kind_confidence": kconf,
                "year_hint": ds.year_hint,
                "rows": len(ds.frame),
                "mapping_version": mapping_version(m),
                **m,
            }
        )
    return out


def _plan_datasets(
    datasets: list[RawDataset],
    overrides: dict,
    previews: list[dict] | None,
    hint: dict | None,
    use_ai: bool,
) -> list[tuple[RawDataset, dict, float]]:
    prev_by_file = {p["file"]: p for p in previews or []}
    plans = []
    for ds in datasets:
        if ds.name in prev_by_file:
            p = prev_by_file[ds.name]
            m = {k: p[k] for k in ("kind", "columns", "wide_month_columns", "required_missing", "ai_note")}
            m = json.loads(json.dumps(m))
            kconf = p.get("kind_confidence", 1.0)
        else:
            kind, kconf = detect_kind(list(ds.frame.columns), ds.kind_hint)
            m = map_columns(ds.frame, kind, hint, use_ai=use_ai)
        if ds.name in overrides:
            m = apply_overrides(m, overrides[ds.name])
        plans.append((ds, m, kconf))
    plans.sort(key=lambda x: KIND_ORDER.get(x[1]["kind"], 9))
    return plans


def _normalise_dataset(ds: RawDataset, kind: str, m: dict, mp: dict[str, str]) -> tuple[pd.DataFrame, list[str]]:
    if kind == "udise":
        return normalise_udise(ds.frame, mp, ds.year_hint, ds.name)
    if kind == "assessment":
        return normalise_assessment(ds.frame, mp, ds.year_hint, ds.name)
    if kind == "attendance":
        return normalise_attendance(ds.frame, mp, ds.year_hint, m.get("wide_month_columns", []), ds.name)
    if kind == "teachers":
        return normalise_teachers(ds.frame, mp, ds.year_hint, ds.name)
    return normalise_context(ds.frame, mp, ds.year_hint, ds.name)


def _persist_warehouse(
    registry: SchoolRegistry,
    frames: dict[str, list[pd.DataFrame]],
    files_meta: list[dict],
    reviews: list[dict],
) -> None:
    schools = registry.df.drop(columns=["norm", "dist", "block_key"])
    db.write_df(schools, "schools")
    for kind, table in TABLE.items():
        if frames[kind]:
            db.write_df(pd.concat(frames[kind], ignore_index=True), table)
        elif not db.table_exists(table):
            db.write_df(pd.DataFrame(), table)
    fm = pd.DataFrame(files_meta)
    fm["ingested_at"] = datetime.now().isoformat(timespec="seconds")
    db.write_df(fm, "ingest_files")
    db.execute("DELETE FROM match_review")
    for r in reviews:
        rows = r["rows"].copy()
        db.execute(
            "INSERT INTO match_review (source_file, kind, academic_year, district, block, name_variant, candidates,"
            " payload, n_rows, status) VALUES (:f,:k,:y,:d,:b,:n,:c,:p,:nr,'pending')",
            {
                "f": r["source_file"],
                "k": r["kind"],
                "y": r["academic_year"],
                "d": rows["district"].iloc[0] if "district" in rows and rows["district"].notna().any() else None,
                "b": r["block"],
                "n": r["name_variant"],
                "c": json.dumps(r["candidates"], default=str),
                "p": rows.to_json(orient="records"),
                "nr": len(rows),
            },
        )


def run_ingest(
    datasets: list[RawDataset],
    overrides: dict | None = None,
    progress: Progress | None = None,
    use_ai: bool = True,
    previews: list[dict] | None = None,
) -> dict:
    """Full rebuild of the warehouse from the given datasets."""
    t0 = time.time()
    cfg = settings()
    say = progress or (lambda *_a: None)
    say("read", f"{len(datasets)} files received", 0.05)
    hint = _registry_hint(datasets)
    plans = _plan_datasets(datasets, overrides or {}, previews, hint, use_ai)
    say("map", "Columns mapped to canonical schema", 0.2)

    files_meta: list[dict] = []
    frames: dict[str, list[pd.DataFrame]] = {k: [] for k in TABLE}
    reviews: list[dict] = []
    registry: SchoolRegistry | None = None

    for i, (ds, m, kconf) in enumerate(plans):
        kind = m["kind"]
        mp = mapping_dict(m)
        meta = {
            "file": ds.name,
            "kind": kind,
            "kind_confidence": kconf,
            "adapter": ds.adapter,
            "provenance": ds.provenance,
            "rows_in": len(ds.frame),
            "mapping": json.dumps(m["columns"]),
            "wide_month_columns": len(m.get("wide_month_columns", [])),
            "mapping_version": mapping_version(m),
            "schema_version": db.SCHEMA_VERSION,
            "ai_note": m.get("ai_note"),
            "required_missing": json.dumps(m["required_missing"]),
            "status": "ok",
        }
        if m["required_missing"]:
            meta.update(
                status="skipped",
                transforms=json.dumps([f"missing required: {m['required_missing']}"]),
                rows_out=0,
                academic_year=ds.year_hint,
            )
            files_meta.append(meta)
            continue

        df, tr = _normalise_dataset(ds, kind, m, mp)
        df["_provenance"], df["_adapter"], df["_source_file"] = ds.provenance, ds.adapter, ds.name
        if "_row" in df:
            df = df.rename(columns={"_row": "_source_row"})
        meta["academic_year"] = (
            df["academic_year"].mode().iloc[0]
            if "academic_year" in df and df["academic_year"].notna().any()
            else ds.year_hint
        )
        if kind != "context":
            df, dstats = dedupe(df, kind)
            meta.update(dstats)
        if kind in ("udise", "context"):
            df["_match_method"] = "udise_code" if kind == "udise" else None
            df["_match_conf"] = 1.0 if kind == "udise" else None
            frames[kind].append(df)
        else:
            if registry is None:
                registry = _build_registry(frames["udise"], cfg)
            matched, rev = registry.match_frame(df)
            counts = Counter(matched.match_method)
            matched = matched.rename(columns={"match_method": "_match_method", "match_confidence": "_match_conf"})
            matched, d2 = dedupe(matched, kind)
            meta.update(
                {
                    "matched_by_code": counts.get("udise_code", 0),
                    "matched_by_name": sum(v for k, v in counts.items() if k != "udise_code"),
                    "review_rows": int(sum(len(r["rows"]) for r in rev)),
                    "review_groups": len(rev),
                    "key_duplicates": meta.get("key_duplicates", 0) + d2["key_duplicates"],
                }
            )
            for r in rev:
                reviews.append({**r, "source_file": ds.name, "kind": kind, "academic_year": meta["academic_year"]})
            frames[kind].append(matched)
            tr = [
                *tr,
                f"{counts.get('udise_code', 0)} rows matched by UDISE code",
                f"{meta['matched_by_name']} rows matched by name rules",
                f"{meta['review_rows']} rows sent to review",
            ]
        meta["rows_out"] = int(sum(len(f) for f in frames[kind][-1:]))
        meta["transforms"] = json.dumps(tr)
        files_meta.append(meta)
        say("normalise", f"{ds.name}: {kind}, {meta['rows_out']} rows", 0.2 + 0.6 * (i + 1) / len(plans))

    if registry is None:
        registry = _build_registry(frames["udise"], cfg)
    say("write", "Writing warehouse tables", 0.85)
    _persist_warehouse(registry, frames, files_meta, reviews)
    say("derive", "Building 3-year school panel and comparability checks", 0.92)
    rebuild_derived()
    db.bump_version()
    secs = round(time.time() - t0, 1)
    db.write_df(
        pd.DataFrame([{"seconds": secs, "files": len(datasets), "at": datetime.now().isoformat(timespec="seconds")}]),
        "ingest_runs",
        if_exists="append",
    )
    say("done", f"Warehouse ready in {secs}s", 1.0)
    return summary(secs)


def _build_registry(udise_frames: list[pd.DataFrame], cfg: dict) -> SchoolRegistry:
    if udise_frames:
        u = pd.concat(udise_frames, ignore_index=True)
        u = u[u.udise_code.notna()].sort_values("academic_year")
        latest = u.groupby("udise_code").last().reset_index()
        schools = latest[
            ["udise_code", "school_name", "district", "block", "cluster", "management", "rural", "_provenance"]
        ].rename(columns={"_provenance": "provenance"})
    elif db.table_exists("schools"):
        schools = db.read_df("SELECT * FROM schools")
    else:
        raise ValueError("No UDISE+ school master available: upload at least one UDISE+ file first.")
    m = cfg.get("matching", {})
    return SchoolRegistry(schools, m.get("auto_threshold", 0.85), m.get("review_threshold", 0.7))


def summary(seconds: float | None = None) -> dict:
    """Return high-level warehouse and ingestion statistics."""
    files = db.read_df("SELECT * FROM ingest_files") if db.table_exists("ingest_files") else pd.DataFrame()
    pending = db.query("SELECT COUNT(*) AS n, COALESCE(SUM(n_rows),0) AS r FROM match_review WHERE status='pending'")[0]
    n_schools = db.query("SELECT COUNT(*) AS n FROM schools")[0]["n"] if db.table_exists("schools") else 0
    if seconds is None and db.table_exists("ingest_runs"):
        last = db.query("SELECT seconds FROM ingest_runs ORDER BY rowid DESC LIMIT 1")
        seconds = last[0]["seconds"] if last else None
    years = (
        db.read_df("SELECT DISTINCT academic_year FROM panel ORDER BY 1").academic_year.tolist()
        if db.table_exists("panel")
        else []
    )
    return {
        "seconds": seconds,
        "files": len(files),
        "schools": int(n_schools),
        "years": years,
        "rows_in": int(files.rows_in.sum()) if len(files) else 0,
        "rows_out": int(files.rows_out.fillna(0).sum()) if len(files) else 0,
        "duplicates_removed": int(
            files.get("exact_duplicates", pd.Series(dtype=float)).fillna(0).sum()
            + files.get("key_duplicates", pd.Series(dtype=float)).fillna(0).sum()
        )
        if len(files)
        else 0,
        "matched_by_name": int(files.get("matched_by_name", pd.Series(dtype=float)).fillna(0).sum())
        if len(files)
        else 0,
        "review_groups": int(pending["n"]),
        "review_rows": int(pending["r"]),
        "ai_columns": int(sum(1 for m in files.get("mapping", []) for c in json.loads(m) if c["method"] == "ai")),
        "mapped_columns": int(sum(1 for m in files.get("mapping", []) for c in json.loads(m) if c["target"])),
    }


def resolve_review(review_id: int, udise_code: str | None, user: str) -> dict:
    """Resolve or reject a pending school-name review group and rebuild derived tables."""
    rows = db.query("SELECT * FROM match_review WHERE id=:i", {"i": review_id})
    if not rows:
        raise KeyError(review_id)
    r = rows[0]
    now = datetime.now().isoformat(timespec="seconds")
    if not udise_code:
        db.execute(
            "UPDATE match_review SET status='rejected', resolved_by=:u, resolved_at=:t WHERE id=:i",
            {"u": user, "t": now, "i": review_id},
        )
        return {"id": review_id, "status": "rejected"}
    school = db.query("SELECT * FROM schools WHERE udise_code=:c", {"c": udise_code})
    if not school:
        raise ValueError("Unknown UDISE code")
    payload = pd.read_json(io.StringIO(r["payload"]), orient="records", dtype={"udise_code": str})
    payload["udise_code"] = udise_code
    payload["school_name"] = school[0]["school_name"]
    payload["block"] = school[0]["block"]
    payload["_match_method"] = "manual_review"
    payload["_match_conf"] = 1.0
    table = TABLE[r["kind"]]
    existing = db.read_df(f"SELECT * FROM {table} LIMIT 0")
    payload = payload.reindex(columns=existing.columns)
    db.write_df(payload, table, if_exists="append")
    db.execute(
        "UPDATE match_review SET status='resolved', resolved_udise=:c, resolved_by=:u, resolved_at=:t WHERE id=:i",
        {"c": udise_code, "u": user, "t": now, "i": review_id},
    )
    rebuild_derived()
    db.bump_version()
    return {"id": review_id, "status": "resolved", "udise_code": udise_code, "rows": len(payload)}
