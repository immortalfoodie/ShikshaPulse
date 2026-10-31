"""HTTP API. Every data endpoint is authenticated and scoped; state-changing calls are audit-logged."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from .. import db, runtime
from ..actions import service as actions
from ..ai import assistant, brief, drafter
from ..ai.llm import llm
from ..analytics import common, context, diagnose, expected, peers, quality, radar, trends
from ..auth import (
    PERSONAS,
    audit,
    can_list_schools,
    clamp_school_scope,
    current_user,
    issue_token,
    persona,
    require_view,
)
from ..config import SCENARIO_OUT, public_demo, settings, today
from ..ingest import pipeline
from ..sources import describe_all, get_adapter
from ..sources.readers import read_table

MAX_UPLOAD_MB = 15
router = APIRouter(prefix="/api")


def _ready():
    if common.panel().empty:
        raise HTTPException(409, "Warehouse is empty — ingest data in Data Studio first.")


def _unit(unit_type: str, unit: str | None) -> tuple[str, str | None]:
    return unit_type, (None if unit_type == "state" else unit)


# ---------------------------------------------------------------- auth / meta
@router.get("/personas")
def personas():
    return [persona(p["id"]) for p in PERSONAS]


@router.post("/login")
def login(persona_id: str = Body(..., embed=True)):
    p = persona(persona_id)
    audit(p, "login")
    return {"token": issue_token(persona_id), "user": p}


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.get("/meta")
def meta(user=Depends(current_user)):
    p = common.panel()
    tree = {}
    if not p.empty:
        for (d, b), _ in p.groupby(["district", "block"]):
            tree.setdefault(d, []).append(b)
    tiers = sorted(p.provenance.dropna().unique().tolist()) if not p.empty and "provenance" in p else []
    return {
        "user": user,
        "ready": not p.empty,
        "years": common.years(),
        "tree": tree,
        "mode": settings()["mode"],
        "provenance_tiers": tiers,
        "synthetic": "synthetic_demo" in tiers,
        "scenario": runtime.active_scenario(),
        "public_demo": public_demo(),
        "llm": llm().status(),
        "schools": int(p.udise_code.nunique()) if not p.empty else 0,
        "today": today().isoformat(),
    }


# ---------------------------------------------------------------- analytics
@router.get("/overview")
def overview(unit_type: str = "state", unit: str | None = None, user=Depends(current_user)):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    o = trends.overview(ut, u)
    o["quality"] = quality.unit_quality(ut, u)
    return o


@router.get("/trend")
def trend(metric: str = "numeracy", unit_type: str = "state", unit: str | None = None, user=Depends(current_user)):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    return trends.trend(metric, ut, u)


@router.get("/breakdown")
def breakdown(metric: str = "numeracy", unit_type: str = "state", unit: str | None = None, user=Depends(current_user)):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    b = trends.breakdown(metric, ut, u)
    if b["child_type"] == "school" and not can_list_schools(user, ut, u):
        raise HTTPException(403, "School-level detail is outside your scope")
    return b


@router.get("/children-reasons")
def children_reasons(
    unit_type: str = "state", unit: str | None = None, metric: str = "numeracy", user=Depends(current_user)
):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    return diagnose.children_reasons(ut, u, metric, limit=0)


@router.get("/diagnose")
def diagnose_ep(
    unit_type: str = "state", unit: str | None = None, metric: str = "numeracy", user=Depends(current_user)
):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    d = diagnose.diagnose(ut, u, metric)
    if not can_list_schools(user, ut, u):
        d = json.loads(json.dumps(d, default=str))
        for s in d["signals"]:
            s.pop("affected_schools", None)
    return d


@router.get("/expected")
def expected_ep(unit_type: str = "block", unit: str | None = None, user=Depends(current_user)):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    return expected.expected_vs_actual(ut, u)


@router.get("/expected/model")
def expected_model(user=Depends(current_user)):
    _ready()
    return expected.model_card()


@router.get("/expected/ranking")
def expected_ranking(district: str | None = None, user=Depends(current_user)):
    _ready()
    rows = expected.residual_ranking("block")
    if district:
        blocks = set(common.subset("district", district).block)
        rows = [r for r in rows if r["unit"] in blocks]
    return rows


@router.get("/peers")
def peers_ep(
    block: str, election_only: bool = False, k: int = 5, other_districts: bool = True, user=Depends(current_user)
):
    _ready()
    return peers.peers(block, k=k, election_only=election_only, other_districts=other_districts)


@router.get("/radar")
def radar_ep(unit_type: str = "district", unit: str | None = None, min_flags: int = 2, user=Depends(current_user)):
    _ready()
    ut, u = clamp_school_scope(user, *_unit(unit_type, unit))
    return radar.radar(ut, u, min_flags=min_flags, limit=200)


@router.get("/radar/matrix")
def radar_matrix(unit_type: str = "district", unit: str | None = None, user=Depends(current_user)):
    _ready()
    ut, u = clamp_school_scope(user, *_unit(unit_type, unit))
    return radar.overlap_matrix(ut, u)


@router.get("/school/{udise}")
def school(udise: str, user=Depends(current_user)):
    _ready()
    require_view(user, "school", udise)
    return trends.school_profile(udise)


@router.get("/my-school")
def my_school(udise: str | None = None, user=Depends(current_user)):
    """Simple school view for headmasters/teachers: 3-year profile, support flags, block reference, actions."""
    _ready()
    code = udise or (user["scope"] if user["scope_type"] == "school" else None)
    if not code:
        raise HTTPException(400, "No school selected")
    require_view(user, "school", code)
    prof = trends.school_profile(code)
    r = radar.radar("block", prof["block"], min_flags=1, limit=100000)
    me = next((x for x in r["schools"] if x["udise_code"] == code), None)
    blk = trends.overview("block", prof["block"])
    acts = [
        a
        for a in actions.for_user(user, actions.list_actions(user, "block", prof["block"]))
        if (a["owner_id"] == user["id"] and code == user.get("scope"))
        or code in [s if isinstance(s, str) else s.get("udise_code") for s in a["schools"]]
        or a["unit"] == code
    ]
    return {
        "school": prof,
        "flags": me["flags"] if me else [],
        "missing": me["missing"] if me else [],
        "block_kpis": {k["metric"]: k["latest"] for k in blk["kpis"]},
        "actions": acts,
        "latest_year": blk["latest_year"],
        "baseline_year": blk["baseline_year"],
    }


@router.get("/early-warning")
def early_warning_ep(unit_type: str = "state", unit: str | None = None, user=Depends(current_user)):
    _ready()
    from ..analytics.early_warning import early_warning

    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    w = early_warning(ut, u)
    if not can_list_schools(user, ut, u):
        w["schools"] = []
    return w


@router.get("/redistribution")
def redistribution_ep(unit_type: str = "block", unit: str | None = None, user=Depends(current_user)):
    _ready()
    from ..analytics.redistribution import suggestions

    ut, u = clamp_school_scope(user, *_unit(unit_type, unit))
    return suggestions(ut, u)


@router.get("/track-record")
def track_record_ep(intervention_key: str | None = None, trigger: str | None = None, user=Depends(current_user)):
    return actions.track_record(intervention_key, trigger)


@router.get("/schools")
def schools_list(unit_type: str = "block", unit: str | None = None, user=Depends(current_user)):
    """Schools a user may open individually (for the visit form and report cards)."""
    ut, u = clamp_school_scope(user, *_unit(unit_type, unit))
    df = common.subset(ut, u)[["udise_code", "school_name", "block", "cluster"]].drop_duplicates("udise_code")
    return df.sort_values(["cluster", "school_name"]).to_dict("records")


@router.get("/visits/checklist")
def visit_checklist(user=Depends(current_user)):
    from .. import visits

    return {"items": visits.CHECKLIST, "values": list(visits.VALUES)}


@router.get("/visits")
def visits_list(unit_type: str = "block", unit: str | None = None, user=Depends(current_user)):
    from .. import visits

    ut, u = clamp_school_scope(user, *_unit(unit_type, unit))
    rows = visits.list_visits(
        block=u if ut == "block" else None,
        district=u if ut == "district" else None,
        udise=u if ut == "school" else None,
        limit=200,
    )
    return {"visits": rows, "summary": visits.summary(ut, u)}


@router.post("/visits")
def visits_create(payload: dict = Body(...), user=Depends(current_user)):
    """Accepts one visit or {"visits": [...]} (offline batch sync). Idempotent on client_id."""
    from .. import visits

    items = payload.get("visits") if "visits" in payload else [payload]
    out = []
    for v in items:
        if not v.get("udise_code"):
            raise HTTPException(400, "udise_code required")
        require_view(user, "school", v["udise_code"])
        try:
            out.append(visits.record(v, user))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    audit(user, "visits_sync", {"n": len(out)})
    return {"saved": out}


@router.get("/tiles")
def tiles(user=Depends(current_user)):
    _ready()
    return trends.tiles()


@router.get("/context")
def context_ep(unit_type: str = "district", unit: str | None = None, user=Depends(current_user)):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    return context.timeline(ut, u)


@router.get("/review-order")
def review_order(district: str, user=Depends(current_user)):
    _ready()
    return context.review_order(district)


@router.get("/quality")
def quality_ep(unit_type: str | None = None, unit: str | None = None, user=Depends(current_user)):
    if unit_type:
        _ready()
        return quality.unit_quality(*_unit(unit_type, unit))
    return quality.overall()


# ---------------------------------------------------------------- ingestion / Data Studio
@router.get("/ingest/sources")
def sources(user=Depends(current_user)):
    out = {"adapters": describe_all(), "scenario": runtime.active_scenario(), "files": {}}
    runtime.ensure_scenario()
    for key in ("synthetic_files", "upload"):
        ad = get_adapter(key, scenario=runtime.active_scenario()) if key == "synthetic_files" else get_adapter(key)
        out["files"][key] = [{"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1)} for p in ad.files()]
    return out


@router.get("/ingest/raw")
def raw_preview(adapter: str, file: str, rows: int = 12, user=Depends(current_user)):
    ad = (
        get_adapter(adapter, scenario=runtime.active_scenario())
        if adapter == "synthetic_files"
        else get_adapter(adapter)
    )
    match = [p for p in ad.files() if p.name == file]
    if not match:
        raise HTTPException(404, "file not found")
    df = read_table(match[0]).drop(columns=["_row"]).head(rows)
    return {"file": file, "columns": list(df.columns), "rows": df.fillna("").astype(str).values.tolist()}


@router.post("/ingest/upload")
async def upload(files: list[UploadFile] = File(...), user=Depends(current_user)):
    ad = get_adapter("upload")
    saved = []
    for f in files:
        content = await f.read()
        if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"{f.filename} is larger than {MAX_UPLOAD_MB} MB")
        saved.append(ad.save(f.filename, content).name)
    audit(user, "upload", {"files": saved})
    return {"saved": saved}


@router.delete("/ingest/upload")
def clear_upload(user=Depends(current_user)):
    get_adapter("upload").clear()
    return {"ok": True}


@router.post("/ingest/preview")
def ingest_preview(
    adapter: str = Body("synthetic_files", embed=True),
    use_ai: bool = Body(True, embed=True),
    user=Depends(current_user),
):
    ds = runtime.datasets_for(adapter)
    if not ds:
        raise HTTPException(400, "No files found for this source")
    files = pipeline.preview(ds, use_ai=use_ai)
    pid = uuid.uuid4().hex[:8]
    runtime.PREVIEWS[pid] = {"adapter": adapter, "files": files}
    return {"preview_id": pid, "adapter": adapter, "files": files, "llm": llm().status()}


@router.post("/ingest/run")
def ingest_run(
    adapter: str = Body("synthetic_files", embed=True),
    preview_id: str | None = Body(None, embed=True),
    overrides: dict | None = Body(None, embed=True),
    use_ai: bool = Body(True, embed=True),
    user=Depends(current_user),
):
    if user["role"] not in ("district", "state"):
        raise HTTPException(403, "Only district/state officers can rebuild the warehouse")
    if public_demo() and adapter != "synthetic_files":
        raise HTTPException(
            403,
            "On the public demo the record is rebuilt only from the demo files. "
            "Uploaded files can be read and previewed; run locally to build from them.",
        )
    jid = runtime.start_job(adapter, overrides, preview_id, use_ai, user)
    return {"job_id": jid}


@router.get("/ingest/jobs/{jid}")
def job(jid: str, user=Depends(current_user)):
    if jid not in runtime.JOBS:
        raise HTTPException(404, "job not found")
    return runtime.JOBS[jid]


@router.get("/ingest/summary")
def ingest_summary(user=Depends(current_user)):
    return pipeline.summary() if db.table_exists("ingest_files") else {"files": 0}


@router.get("/ingest/review")
def review_list(status: str = "pending", user=Depends(current_user)):
    rows = db.query(
        "SELECT id, source_file, kind, academic_year, district, block, name_variant, candidates, n_rows,"
        " status, resolved_udise, resolved_by FROM match_review WHERE status=:s ORDER BY block, name_variant",
        {"s": status},
    )
    rows = [r for r in rows if _review_in_scope(user, r)]
    for r in rows:
        r["candidates"] = json.loads(r["candidates"] or "[]")
    return rows


def _review_in_scope(user: dict, r: dict) -> bool:
    """Officers check unmatched school records only for their own area (they know those schools)."""
    if user["role"] == "state":
        return True
    if user["role"] == "district":
        return str(r.get("district") or "").casefold() == str(user["scope"]).casefold()
    if user["role"] == "block" and not user.get("crc"):
        return str(r.get("block") or "").casefold() == str(user["scope"]).casefold()
    return False


@router.post("/ingest/review/{rid}")
def review_resolve(rid: int, udise_code: str | None = Body(None, embed=True), user=Depends(current_user)):
    row = db.query("SELECT district, block FROM match_review WHERE id=:i", {"i": rid})
    if row and not _review_in_scope(user, row[0]):
        raise HTTPException(403, "This record belongs to another area")
    try:
        res = pipeline.resolve_review(rid, udise_code, user["name"])
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    audit(user, "match_review", {"id": rid, "udise_code": udise_code})
    return res


@router.post("/ingest/review-bulk")
def review_bulk(min_score: float = Body(90, embed=True), user=Depends(current_user)):
    """Officer-confirmed bulk accept of top candidates scoring ≥ min_score (each logged)."""
    rows = review_list("pending", user)
    done = 0
    for r in rows:
        c = r["candidates"]
        if c and c[0]["score"] >= min_score and (len(c) == 1 or c[0]["score"] - c[1]["score"] >= 5):
            pipeline.resolve_review(r["id"], c[0]["udise_code"], user["name"])
            done += 1
    audit(user, "match_review_bulk", {"min_score": min_score, "accepted": done})
    return {"accepted": done, "remaining": len(rows) - done}


@router.get("/lineage")
def lineage(udise: str, user=Depends(current_user)):
    require_view(user, "school", udise)
    out = {}
    tables = {
        "assessments": "academic_year, subject, score_raw, scoring_scale, score_pct, assessment_type",
        "attendance_monthly": "academic_year, year, month, student_att_pct, teacher_att_pct",
        "teacher_snapshot": "academic_year, snapshot_date, subject, sanctioned, working, vacant",
        "udise_year": "academic_year, enrolment, infra_index",
    }
    for t, cols in tables.items():
        if db.table_exists(t):
            out[t] = db.query(
                f"SELECT {cols}, _source_file, _source_row, _match_method, _match_conf, _provenance "
                f"FROM {t} WHERE udise_code=:c ORDER BY academic_year LIMIT 60",
                {"c": udise},
            )
    files = {
        f["file"]: {
            "transforms": f["transforms"],
            "mapping_version": f["mapping_version"],
            "schema_version": f["schema_version"],
        }
        for f in quality.file_report()
    }
    return {"udise_code": udise, "records": out, "files": files}


# ---------------------------------------------------------------- actions
@router.get("/interventions")
def interventions(user=Depends(current_user)):
    return actions.library()


@router.get("/owners")
def owners(unit_type: str = "district", unit: str | None = None, user=Depends(current_user)):
    return actions.owners(*_unit(unit_type, unit))


@router.get("/actions")
def list_actions(unit_type: str | None = None, unit: str | None = None, mine: bool = False, user=Depends(current_user)):
    if unit_type is None and user["role"] != "state":
        unit_type, unit = (
            (user["scope_type"], user["scope"]) if user["scope_type"] != "school" else ("block", user.get("block"))
        )
    acts = actions.for_user(user, actions.list_actions(user, unit_type if unit_type != "state" else None, unit, mine))
    return {"actions": acts, "summary": actions.summary(acts)}


@router.get("/actions/{aid}")
def get_action(aid: int, user=Depends(current_user)):
    return {**_task_for(user, aid), "can_update": actions.can_update(user, _task_for(user, aid))}


def _task_for(user: dict, aid: int, update: bool = False) -> dict:
    """The task, if this user may see it (and update it, when asked)."""
    try:
        a = actions.get_action(aid)
    except KeyError as e:
        raise HTTPException(404, "not found") from e
    if not actions.in_scope(user, a):
        raise HTTPException(403, "This task is outside your area")
    if update and not actions.can_update(user, a):
        raise HTTPException(403, "Only the task owner or the responsible officer can update this task")
    return a


@router.post("/actions")
def create_action(payload: dict = Body(...), user=Depends(current_user)):
    if user["role"] == "headmaster":
        raise HTTPException(403, "Headmasters update actions assigned to them; officers create actions")
    for k in ("title", "unit_type", "unit"):
        if not payload.get(k):
            raise HTTPException(400, f"missing {k}")
    a = actions.create_action(payload, user)
    audit(user, "action_create", {"id": a["id"], "title": a["title"], "owner": a["owner_name"]})
    return a


@router.post("/actions/draft")
def draft(
    unit_type: str = Body(..., embed=True),
    unit: str = Body(..., embed=True),
    schools: list[str] | None = Body(None, embed=True),
    user=Depends(current_user),
):
    _ready()
    return drafter.draft_actions(unit_type, unit, schools)


@router.post("/actions/{aid}/status")
def set_status(
    aid: int,
    status: str = Body(..., embed=True),
    note: str = Body("", embed=True),
    evidence_note: str | None = Body(None, embed=True),
    user=Depends(current_user),
):
    _task_for(user, aid, update=True)
    try:
        a = actions.set_status(aid, status, user, note, evidence_note)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    audit(user, "action_status", {"id": aid, "status": status})
    return a


@router.post("/actions/{aid}/measurement")
def measurement(
    aid: int,
    kind: str = Body(..., embed=True),
    value: float = Body(..., embed=True),
    evidence: str = Body("", embed=True),
    user=Depends(current_user),
):
    _task_for(user, aid, update=True)
    try:
        a = actions.record_measurement(aid, kind, value, user, evidence)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    audit(user, "action_measurement", {"id": aid, "kind": kind, "value": value})
    return a


@router.post("/actions/{aid}/evidence")
async def evidence(aid: int, file: UploadFile = File(...), note: str = Form(""), user=Depends(current_user)):
    _task_for(user, aid, update=True)
    a = actions.attach_evidence(aid, file.filename, await file.read(), user, note)
    audit(user, "action_evidence", {"id": aid, "file": file.filename})
    return a


@router.get("/audit")
def audit_log(limit: int = 100, user=Depends(current_user)):
    if user["role"] not in ("district", "state"):
        raise HTTPException(403, "Audit log is available to district/state officers")
    return db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT :l", {"l": limit})


# ---------------------------------------------------------------- AI
@router.post("/ask")
def ask(
    question: str = Body(..., embed=True),
    lang: str = Body("en", embed=True),
    force_fallback: bool = Body(False, embed=True),
    user=Depends(current_user),
):
    _ready()
    res = assistant.ask(question, user, lang, force_fallback)
    audit(user, "ask", {"question": question[:200], "engine": res["engine"], "passed": res["guard"]["passed"]})
    return res


@router.get("/brief")
def brief_ep(unit_type: str = "district", unit: str | None = None, lang: str = "en", user=Depends(current_user)):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    return brief.build_brief(ut, u, user, lang)


@router.get("/brief.pdf")
def brief_pdf(unit_type: str = "district", unit: str | None = None, lang: str = "en", user=Depends(current_user)):
    _ready()
    ut, u = _unit(unit_type, unit)
    require_view(user, ut, u)
    b = brief.build_brief(ut, u, user, lang)
    audit(user, "brief_pdf", {"unit": u})
    return Response(
        brief.brief_pdf(b),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ShikshaPulse_brief_{u or "state"}.pdf"'},
    )


@router.get("/llm/status")
def llm_status(user=Depends(current_user)):
    return llm().status()


# ---------------------------------------------------------------- Scenario Lab & evaluation
@router.get("/lab/scenarios")
def lab_scenarios(user=Depends(current_user)):
    from scenario_lab.generator import list_scenarios

    out = list_scenarios()
    for s in out:
        exp = SCENARIO_OUT / s["name"] / "expected.json"
        s["generated"] = exp.exists()
        if exp.exists():
            e = json.loads(exp.read_text(encoding="utf-8"))
            s["blocks"] = e["blocks"]
            s["n_schools"] = e["n_schools"]
    return {"scenarios": out, "active": runtime.active_scenario()}


@router.post("/lab/generate")
def lab_generate(
    scenario: str = Body(..., embed=True),
    seed: int | None = Body(None, embed=True),
    mess: dict | None = Body(None, embed=True),
    ingest: bool = Body(True, embed=True),
    user=Depends(current_user),
):
    if user["role"] not in ("district", "state"):
        raise HTTPException(403, "Scenario Lab is an internal tool for district/state roles")
    if public_demo():
        raise HTTPException(
            403,
            "Scenario Lab is switched off on the public demo so every visitor sees the same "
            "data. Run the project locally to generate other scenarios.",
        )
    from scenario_lab.generator import generate

    res = generate(scenario, SCENARIO_OUT, {"seed": seed, "mess": mess or {}})
    runtime.STATE["active_scenario"] = res["scenario"]
    audit(user, "lab_generate", {"scenario": scenario, "seed": seed, "mess": mess})
    out = {"generated": res}
    if ingest:
        out["job_id"] = runtime.start_job("synthetic_files", None, None, False, user)
    return out


@router.get("/lab/expected")
def lab_expected(scenario: str | None = None, user=Depends(current_user)):
    p = SCENARIO_OUT / (scenario or runtime.active_scenario()) / "expected.json"
    if not p.exists():
        raise HTTPException(404, "not generated")
    e = json.loads(p.read_text(encoding="utf-8"))
    e.pop("matches", None)
    return e


@router.get("/eval/report")
def eval_report(user=Depends(current_user)):
    p = Path(__file__).resolve().parents[2] / "eval" / "report.json"
    if not p.exists():
        raise HTTPException(404, "Evaluation has not been run yet: python -m eval")
    return json.loads(p.read_text(encoding="utf-8"))
