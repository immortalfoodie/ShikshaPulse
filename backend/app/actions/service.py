"""Action Room: issues → actions with owners and deadlines → implementation and learning follow-up.

Implementation (was it done?) and learning (did outcomes move?) are tracked separately, so the
system can tell "not implemented" apart from "implemented, no improvement yet".
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from .. import db
from ..analytics.common import METRICS, agg, subset, years
from ..config import today

LIB_PATH = Path(__file__).with_name("interventions.yaml")
WORKFLOW = ["open", "in_progress", "awaiting_verification", "verified", "closed_not_implemented"]
LOWER_IS_BETTER = {"maths_vacancy"}
IMPROVE_PP = 2.0


def library() -> dict:
    return yaml.safe_load(LIB_PATH.read_text(encoding="utf-8"))


def find_intervention(key: str) -> tuple[str, dict] | tuple[None, None]:
    for trig, block in library().items():
        for a in block["actions"]:
            if a["key"] == key:
                return trig, a
    return None, None


def _now() -> str:
    # Uses the configured reference date (pinned in demo mode) so timelines and deadlines stay consistent.
    return datetime.combine(today(), datetime.now().time()).isoformat(timespec="seconds")


def unit_value(indicator: str, unit_type: str, unit: str, year: str | None = None) -> float | None:
    if indicator not in METRICS:
        return None
    df = subset(unit_type, unit)
    y = year or years()[-1]
    return agg(df[df.academic_year == y], indicator, comparable_only=True)


def create_action(data: dict, user: dict, simulated: bool = False) -> dict:
    trig, iv = find_intervention(data.get("intervention_key", "")) if data.get("intervention_key") else (None, None)
    due = data.get("due_date") or (today() + timedelta(days=(iv or {}).get("days", 21))).isoformat()
    impl = (iv or {}).get("implementation", {})
    learn = (iv or {}).get("learning", {})
    issue_id = data.get("issue_id")
    if not issue_id and data.get("issue_title"):
        issue_id = db.execute(
            "INSERT INTO issues (unit_type, unit, title, indicator, evidence, created_by, created_at) "
            "VALUES (:ut,:u,:t,:i,:e,:c,:at)",
            {
                "ut": data["unit_type"],
                "u": data["unit"],
                "t": data["issue_title"],
                "i": trig or data.get("indicator"),
                "e": json.dumps(data.get("evidence", []), default=str),
                "c": user["name"],
                "at": data.get("created_at") or _now(),
            },
        )
    aid = db.execute(
        "INSERT INTO actions (issue_id, title, description, intervention_key, unit_type, unit, schools, owner_name,"
        " owner_role, owner_id, due_date, priority, status, created_by, created_at, learning_indicator,"
        " implementation_indicator, is_simulated, evidence_note) VALUES (:iss,:t,:d,:k,:ut,:u,:s,:on,:orl,:oid,:due,"
        ":p,:st,:cb,:ca,:li,:ii,:sim,:en)",
        {
            "iss": issue_id,
            "t": data["title"],
            "d": data.get("description", ""),
            "k": data.get("intervention_key"),
            "ut": data["unit_type"],
            "u": data["unit"],
            "s": json.dumps(data.get("schools", [])),
            "on": data.get("owner_name") or (iv or {}).get("owner_role", "Block Education Officer"),
            "orl": data.get("owner_role") or (iv or {}).get("owner_role"),
            "oid": data.get("owner_id"),
            "due": due,
            "p": data.get("priority", "Medium"),
            "st": data.get("status", "open"),
            "cb": user["name"],
            "ca": data.get("created_at") or _now(),
            "li": learn.get("indicator") or data.get("learning_indicator"),
            "ii": impl.get("indicator") or data.get("implementation_indicator"),
            "sim": int(simulated),
            "en": data.get("evidence_note"),
        },
    )
    # Baselines are recorded at creation, so follow-up can be measured against them.
    n_schools = max(1, len(data.get("schools", [])) or len(subset(data["unit_type"], data["unit"]).udise_code.unique()))
    if impl:
        target = impl.get("target")
        if impl.get("target_from") == "schools":
            target = n_schools
        elif impl.get("target_from") == "vacancies":
            target = _vacancies(data["unit_type"], data["unit"], data.get("schools", []))
        add_measurement(
            aid,
            {
                "kind": "implementation",
                "indicator": impl["indicator"],
                "baseline": 0,
                "target": target,
                "value": None,
                "baseline_date": today().isoformat(),
                "unit": impl.get("label"),
            },
            user,
            simulated,
        )
    if learn and learn.get("indicator") in METRICS:
        base = unit_value(learn["indicator"], data["unit_type"], data["unit"])
        add_measurement(
            aid,
            {
                "kind": "learning",
                "indicator": learn["indicator"],
                "baseline": base,
                "target": None,
                "value": None,
                "baseline_date": today().isoformat(),
                "unit": learn.get("label"),
            },
            user,
            simulated,
        )
    _update(aid, user, "Action created", None, data.get("status", "open"), data.get("created_at"))
    return get_action(aid)


def _vacancies(unit_type: str, unit: str, schools: list) -> int:
    df = subset(unit_type, unit)
    df = df[df.academic_year == years()[-1]]
    if schools:
        df = df[df.udise_code.isin([s if isinstance(s, str) else s.get("udise_code") for s in schools])]
    return int(df.maths_vacant.fillna(0).sum()) or 1


def add_measurement(action_id: int, m: dict, user: dict, simulated: bool = False) -> None:
    db.execute(
        "INSERT INTO indicator_measurements (action_id, kind, indicator, unit, baseline, target, value, baseline_date,"
        " measured_at, evidence, recorded_by, is_simulated) VALUES (:a,:k,:i,:u,:b,:t,:v,:bd,:ma,:e,:r,:s)",
        {
            "a": action_id,
            "k": m["kind"],
            "i": m["indicator"],
            "u": m.get("unit"),
            "b": m.get("baseline"),
            "t": m.get("target"),
            "v": m.get("value"),
            "bd": m.get("baseline_date"),
            "ma": m.get("measured_at"),
            "e": m.get("evidence"),
            "r": user["name"],
            "s": int(simulated),
        },
    )


def record_measurement(
    action_id: int, kind: str, value: float, user: dict, evidence: str = "", measured_at: str | None = None
) -> dict:
    base = db.query(
        "SELECT * FROM indicator_measurements WHERE action_id=:a AND kind=:k ORDER BY id LIMIT 1",
        {"a": action_id, "k": kind},
    )
    if not base:
        raise ValueError(f"No {kind} indicator on this action")
    b = base[0]
    add_measurement(
        action_id,
        {
            "kind": kind,
            "indicator": b["indicator"],
            "unit": b["unit"],
            "baseline": b["baseline"],
            "target": b["target"],
            "value": value,
            "baseline_date": b["baseline_date"],
            "measured_at": measured_at or today().isoformat(),
            "evidence": evidence,
        },
        user,
    )
    _update(action_id, user, f"{kind.title()} measurement recorded: {value}", None, None)
    return get_action(action_id)


def _update(aid: int, user: dict, note: str, s_from, s_to, at: str | None = None) -> None:
    db.execute(
        "INSERT INTO action_updates (action_id, user_name, note, status_from, status_to, at) "
        "VALUES (:a,:u,:n,:f,:t,:at)",
        {"a": aid, "u": user["name"], "n": note, "f": s_from, "t": s_to, "at": at or _now()},
    )


def set_status(aid: int, status: str, user: dict, note: str = "", evidence_note: str | None = None) -> dict:
    if status not in WORKFLOW:
        raise ValueError(f"Unknown status {status}")
    a = get_action(aid)
    if status == "verified" and user["role"] not in ("district", "state") and user["name"] != a["created_by"]:
        raise PermissionError("Only the assigning officer or a higher level can verify an action")
    params = {"s": status, "i": aid}
    extra = ""
    if status == "verified":
        extra = ", verified_by=:vb, verified_at=:va"
        params.update(vb=user["name"], va=_now())
    if evidence_note:
        extra += ", evidence_note=:en"
        params["en"] = evidence_note
    db.execute(f"UPDATE actions SET status=:s{extra} WHERE id=:i", params)
    _update(aid, user, note or f"Status changed to {status}", a["status"], status)
    return get_action(aid)


def attach_evidence(aid: int, filename: str, content: bytes, user: dict, note: str = "") -> dict:
    from ..config import settings

    d = Path(settings()["uploads_path"]) / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    safe = f"action{aid}_{Path(filename).name}"
    (d / safe).write_bytes(content)
    db.execute(
        "UPDATE actions SET evidence_file=:f, evidence_note=COALESCE(:n, evidence_note) WHERE id=:i",
        {"f": safe, "n": note or None, "i": aid},
    )
    _update(aid, user, f"Evidence uploaded: {Path(filename).name}", None, None)
    return get_action(aid)


def outcome_status(a: dict, measures: list[dict]) -> dict:
    impl = [m for m in measures if m["kind"] == "implementation"]
    learn = [m for m in measures if m["kind"] == "learning"]
    impl_latest = next((m for m in reversed(impl) if m["value"] is not None), None)
    learn_latest = next((m for m in reversed(learn) if m["value"] is not None), None)
    due = date.fromisoformat(a["due_date"]) if a.get("due_date") else None
    overdue = bool(due and due < today() and a["status"] in ("open", "in_progress"))
    impl_ratio = None
    if impl_latest and impl_latest["target"]:
        impl_ratio = round(impl_latest["value"] / impl_latest["target"], 2)
    learn_change = None
    if learn_latest and learn_latest["baseline"] is not None:
        learn_change = round(learn_latest["value"] - learn_latest["baseline"], 1)
        if learn_latest["indicator"] in LOWER_IS_BETTER:
            learn_change = -learn_change
    if a["status"] == "closed_not_implemented" or (
        a["status"] == "verified" and impl_ratio is not None and impl_ratio < 0.5
    ):
        st = "not_implemented"
    elif a["status"] == "verified":
        if learn_change is None:
            st = "implemented_awaiting_outcome"
        elif learn_change >= IMPROVE_PP:
            st = "implemented_improved"
        else:
            st = "implemented_no_change"
    elif overdue:
        st = "overdue"
    elif a["status"] == "open":
        st = "not_started"
    else:
        st = "in_progress"
    return {
        "outcome_status": st,
        "overdue": overdue,
        "implementation_ratio": impl_ratio,
        "learning_change": learn_change,
        "days_to_due": (due - today()).days if due else None,
    }


def get_action(aid: int) -> dict:
    rows = db.query("SELECT * FROM actions WHERE id=:i", {"i": aid})
    if not rows:
        raise KeyError(aid)
    return _enrich(rows[0])


def _enrich(a: dict) -> dict:
    measures = db.query("SELECT * FROM indicator_measurements WHERE action_id=:i ORDER BY id", {"i": a["id"]})
    updates = db.query("SELECT * FROM action_updates WHERE action_id=:i ORDER BY id", {"i": a["id"]})
    a["schools"] = json.loads(a.get("schools") or "[]")
    a["is_simulated"] = bool(a.get("is_simulated"))
    a["unit_name"] = a["unit"]
    if a.get("unit_type") == "school":
        s = db.query("SELECT school_name FROM schools WHERE udise_code=:u", {"u": a["unit"]})
        if s:
            a["unit_name"] = s[0]["school_name"]
    a["measurements"] = measures
    a["updates"] = updates
    if a.get("issue_id"):
        iss = db.query("SELECT * FROM issues WHERE id=:i", {"i": a["issue_id"]})
        if iss:
            iss[0]["evidence"] = json.loads(iss[0].get("evidence") or "[]")
            a["issue"] = iss[0]
    a.update(outcome_status(a, measures))
    return a


def list_actions(
    user: dict | None = None, unit_type: str | None = None, unit: str | None = None, mine: bool = False
) -> list[dict]:
    rows = db.query("SELECT * FROM actions ORDER BY id DESC")
    out = []
    blocks_in = None
    if unit_type == "district" and unit:
        blocks_in = {b.casefold() for b in subset("district", unit).block.unique()}
    for r in rows:
        if mine and user and not (r["owner_id"] == user["id"] or r["owner_name"] == user["name"]):
            continue
        if (
            unit_type == "block"
            and unit
            and r["unit"].casefold() != unit.casefold()
            and (r["unit_type"] != "school" or subset("school", r["unit"]).block.iloc[0].casefold() != unit.casefold())
        ):
            continue
        if blocks_in is not None and not (
            r["unit"].casefold() == unit.casefold()
            or r["unit"].casefold() in blocks_in
            or (r["unit_type"] == "school" and subset("school", r["unit"]).block.iloc[0].casefold() in blocks_in)
        ):
            continue
        out.append(_enrich(r))
    return out


def action_area(a: dict) -> tuple[str | None, str | None]:
    """(district, block) a task belongs to."""
    if a["unit_type"] == "school":
        r = db.query("SELECT district, block FROM schools WHERE udise_code=:u", {"u": a["unit"]})
        return (r[0]["district"], r[0]["block"]) if r else (None, None)
    if a["unit_type"] == "block":
        r = db.query("SELECT district FROM schools WHERE block=:b LIMIT 1", {"b": a["unit"]})
        return (r[0]["district"] if r else None, a["unit"])
    if a["unit_type"] == "district":
        return a["unit"], None
    return None, None


def _school_codes(a: dict) -> list[str]:
    return [s if isinstance(s, str) else s.get("udise_code") for s in a.get("schools") or []]


def in_scope(user: dict, a: dict) -> bool:
    """Who may see a task: the state sees all; officers see tasks in their own district/block;
    school staff see tasks at their school or that list their school; owners always see theirs."""
    if user["role"] == "state" or (a.get("owner_id") and a["owner_id"] == user["id"]):
        return True
    d, b = action_area(a)
    if user["role"] == "district":
        return d == user["scope"]
    if user["role"] == "block":
        return b == user["scope"]
    return a["unit"] == user["scope"] or user["scope"] in _school_codes(a)


def can_update(user: dict, a: dict) -> bool:
    """Who may move a task or record progress: its owner; the officer who set it; officers in
    whose area it falls (not CRCs, who update only their own); a headmaster for tasks set for
    their own school. Teachers update only their own tasks."""
    if (a.get("owner_id") and a["owner_id"] == user["id"]) or a.get("owner_name") == user["name"]:
        return True
    if not in_scope(user, a):
        return False
    if a.get("created_by") == user["name"]:
        return True
    if user["role"] in ("state", "district", "block"):
        return not user.get("crc")
    return (
        user["role"] == "headmaster"
        and not user.get("teacher")
        and a["unit_type"] == "school"
        and a["unit"] == user["scope"]
    )


def for_user(user: dict, acts: list[dict]) -> list[dict]:
    """Tasks the user may see, each marked with whether they may update it."""
    return [{**a, "can_update": can_update(user, a)} for a in acts if in_scope(user, a)]


def summary(actions: list[dict]) -> dict:
    s = {
        "total": len(actions),
        "open": 0,
        "in_progress": 0,
        "awaiting_verification": 0,
        "verified": 0,
        "overdue": 0,
        "not_implemented": 0,
        "implemented_improved": 0,
        "implemented_no_change": 0,
        "implemented_awaiting_outcome": 0,
    }
    for a in actions:
        if a["status"] in s:
            s[a["status"]] += 1
        if a["overdue"]:
            s["overdue"] += 1
        if a["outcome_status"] in s:
            s[a["outcome_status"]] += 1
    return s


def owners(unit_type: str, unit: str | None) -> list[dict]:
    from ..auth import PERSONAS

    out = [{"id": p["id"], "name": p["name"], "role": p["title"]} for p in PERSONAS if p["role"] != "state"]
    try:
        from ..auth import persona

        out = [{"id": o["id"], "name": o["name"], "role": persona(o["id"])["title"]} for o in out]
    except Exception:
        pass
    blocks = sorted(subset(unit_type, unit).block.unique()) if unit_type in ("district", "block") else []
    for b in blocks:
        if not any(p.get("scope") == b for p in PERSONAS):
            out.append({"id": f"beo-{b.lower()}", "name": f"BEO {b}", "role": f"Block Education Officer, {b}"})
        out.append({"id": f"brp-{b.lower()}", "name": f"BRP {b}", "role": f"Block Resource Person, {b}"})
    return out


def seed_demo_actions() -> int:
    """Seed clearly-labelled simulated history so the closed loop can be demonstrated."""
    if db.query("SELECT COUNT(*) AS n FROM actions")[0]["n"] > 0:
        return 0
    ys = years()
    if len(ys) < 2:
        return 0
    blocks = set(subset("state", None).block.unique())
    sys_user = {"id": "seed", "name": "Mr. Chan", "role": "district"}
    n = 0

    def hist(block, key, title, created, due, status, impl_value, learn_years, owner, owner_id=None):
        nonlocal n
        if block not in blocks:
            return
        a = create_action(
            {
                "unit_type": "block",
                "unit": block,
                "intervention_key": key,
                "title": title,
                "description": "Simulated historical action (demonstration data).",
                "issue_title": f"{block}: historical review ({ys[0]})",
                "owner_name": owner,
                "owner_id": owner_id,
                "due_date": due,
                "priority": "Medium",
                "created_at": created,
                "status": "open",
            },
            sys_user,
            simulated=True,
        )
        aid = a["id"]
        # Rewrite baselines to the historical year and record follow-ups from the actual panel.
        li = a["learning_indicator"]
        b0 = unit_value(li, "block", block, learn_years[0]) if li else None
        db.execute(
            "UPDATE indicator_measurements SET baseline=:b, baseline_date=:d WHERE action_id=:a AND kind='learning'",
            {"b": b0, "d": created[:10], "a": aid},
        )
        db.execute(
            "UPDATE indicator_measurements SET baseline_date=:d WHERE action_id=:a AND kind='implementation'",
            {"d": created[:10], "a": aid},
        )
        imp = next(m for m in a["measurements"] if m["kind"] == "implementation")
        add_measurement(
            aid,
            {
                "kind": "implementation",
                "indicator": imp["indicator"],
                "unit": imp["unit"],
                "baseline": 0,
                "target": imp["target"],
                "value": round(impl_value * (imp["target"] or 1)),
                "baseline_date": created[:10],
                "measured_at": due,
                "evidence": "Block monthly report (simulated)",
            },
            sys_user,
            True,
        )
        if li and status == "verified":
            v1 = unit_value(li, "block", block, learn_years[1])
            add_measurement(
                aid,
                {
                    "kind": "learning",
                    "indicator": li,
                    "unit": None,
                    "baseline": b0,
                    "target": None,
                    "value": v1,
                    "baseline_date": created[:10],
                    "measured_at": f"{learn_years[1][:4]}-12-15",
                    "evidence": "Annual assessment (warehouse)",
                },
                sys_user,
                True,
            )
        db.execute(
            "UPDATE actions SET status=:s, verified_by=:vb, verified_at=:va WHERE id=:i",
            {
                "s": status,
                "vb": "Mr. Chan" if status == "verified" else None,
                "va": due if status == "verified" else None,
                "i": aid,
            },
        )
        db.execute("UPDATE action_updates SET at=:t WHERE action_id=:a", {"t": created, "a": aid})
        _update(aid, sys_user, "Closed (simulated history)", "open", status, due)
        n += 1

    hist(
        "Ranjhi",
        "fln_remedial",
        "FLN remedial programme in low-scoring schools",
        f"{ys[0][:4]}-08-01T10:00:00",
        f"{ys[0][:4]}-10-15",
        "verified",
        1.05,
        (ys[0], ys[1]),
        "BEO Ranjhi",
    )
    hist(
        "Bhanpur",
        "parent_engagement",
        "SMC / parent engagement drive",
        f"{ys[0][:4]}-07-15T10:00:00",
        f"{ys[0][:4]}-09-30",
        "verified",
        0.9,
        (ys[0], ys[1]),
        "BEO Bhanpur",
    )
    hist(
        "Ujjaini",
        "teacher_redistribution",
        "Temporary maths teacher redistribution",
        f"{ys[0][:4]}-07-20T10:00:00",
        f"{ys[0][:4]}-08-31",
        "verified",
        1.0,
        (ys[0], ys[1]),
        "BEO Ujjaini",
    )
    hist(
        "Khilchipur",
        "attendance_review",
        "School-level attendance review",
        f"{ys[0][:4]}-07-10T10:00:00",
        f"{ys[0][:4]}-08-20",
        "verified",
        1.0,
        (ys[0], ys[1]),
        "BEO Khilchipur",
    )
    hist(
        "Badnagar",
        "remedial_catchup",
        "Catch-up classes for lost teaching days",
        f"{ys[1][:4]}-07-15T10:00:00",
        f"{ys[1][:4]}-09-30",
        "verified",
        0.95,
        (ys[1], ys[2]),
        "BEO Badnagar",
    )
    hist(
        "Sironj",
        "guest_teacher_request",
        "Guest maths teacher request",
        f"{ys[1][:4]}-07-01T10:00:00",
        f"{ys[1][:4]}-08-15",
        "closed_not_implemented",
        0.0,
        (ys[1], ys[2]),
        "BEO Sironj",
    )
    hist(
        "Kerwa",
        "classroom_observation",
        "Structured classroom observation visits (maths)",
        f"{ys[1][:4]}-08-10T10:00:00",
        f"{ys[1][:4]}-10-31",
        "closed_not_implemented",
        0.08,
        (ys[1], ys[2]),
        "Kavita Rao",
        "beo-kerwa",
    )

    # Current open actions: one overdue, one in progress.
    if "Poti" in blocks:
        create_action(
            {
                "unit_type": "block",
                "unit": "Poti",
                "intervention_key": "guest_teacher_request",
                "title": "Guest maths teacher request for Poti schools with vacancies",
                "description": "Simulated demonstration action.",
                "issue_title": "Poti: maths vacancy",
                "owner_name": "Mr. Chan",
                "owner_id": "deo-devgarh",
                "priority": "High",
                "due_date": (today() - timedelta(days=10)).isoformat(),
                "created_at": (datetime.combine(today(), datetime.min.time()) - timedelta(days=40)).isoformat(),
            },
            sys_user,
            simulated=True,
        )
        n += 1
    if "Sinda" in blocks:
        a = create_action(
            {
                "unit_type": "block",
                "unit": "Sinda",
                "intervention_key": "attendance_review",
                "title": "School-level attendance review in Sinda",
                "issue_title": "Sinda: attendance",
                "description": "Simulated demonstration action.",
                "owner_name": "Arjun Patel",
                "owner_id": "beo-sinda",
                "priority": "High",
                "due_date": (today() + timedelta(days=16)).isoformat(),
                "created_at": (datetime.combine(today(), datetime.min.time()) - timedelta(days=5)).isoformat(),
            },
            sys_user,
            simulated=True,
        )
        set_status(
            a["id"],
            "in_progress",
            {"id": "beo-sinda", "name": "Arjun Patel", "role": "block"},
            "Review visits started in 12 schools",
        )
        n += 1
    n += _seed_field_actions(blocks, sys_user)
    return n


def _seed_field_actions(blocks: set, sys_user: dict) -> int:
    """Current tasks that reach schools: so the board has every column filled, and headmasters,
    teachers, CRCs and school report cards all have something real to show (all simulated)."""
    from ..analytics import radar
    from ..analytics.redistribution import suggestions

    n = 0
    now = datetime.combine(today(), datetime.min.time())

    def make(data, status=None, by=None, note="", impl_value=None, evidence_note=None):
        nonlocal n
        a = create_action(
            {
                "description": "Simulated demonstration action.",
                "priority": "Medium",
                "created_at": (now - timedelta(days=data.pop("age", 10))).isoformat(),
                **data,
            },
            sys_user,
            simulated=True,
        )
        if impl_value is not None:
            imp = next(m for m in a["measurements"] if m["kind"] == "implementation")
            add_measurement(
                a["id"],
                {
                    "kind": "implementation",
                    "indicator": imp["indicator"],
                    "unit": imp["unit"],
                    "baseline": 0,
                    "target": imp["target"],
                    "value": round(impl_value * (imp["target"] or 1)),
                    "baseline_date": a["created_at"][:10],
                    "measured_at": (today() - timedelta(days=2)).isoformat(),
                    "evidence": "Weekly school report (simulated)",
                },
                by or sys_user,
                True,
            )
        if status:
            set_status(a["id"], status, by or sys_user, note, evidence_note)
        n += 1
        return a

    if "Poti" in blocks:
        romi = {"id": "beo-poti", "name": "Romi", "role": "block"}
        pairs = suggestions("block", "Poti").get("pairs", [])[:3]
        if pairs:
            sch = [
                {"udise_code": s["udise_code"], "school_name": s["school_name"]}
                for p in pairs
                for s in (p["receiver"], p["donor"])
            ]
            make(
                {
                    "unit_type": "block",
                    "unit": "Poti",
                    "intervention_key": "teacher_redistribution",
                    "title": "Maths teacher sharing between Poti schools",
                    "issue_title": "Poti: maths vacancy",
                    "owner_name": "Romi",
                    "owner_id": "beo-poti",
                    "priority": "High",
                    "schools": sch,
                    "age": 21,
                    "due_date": (today() + timedelta(days=3)).isoformat(),
                },
                "awaiting_verification",
                romi,
                "Sharing timetable running in all paired schools",
                impl_value=0.6,
                evidence_note="Signed sharing timetables from the paired schools (simulated)",
            )
        flagged = radar.radar("block", "Poti", min_flags=2, limit=12)["schools"]
        hm = db.query("SELECT udise_code, school_name FROM schools WHERE block='Poti' ORDER BY udise_code LIMIT 1")
        if flagged:
            make(
                {
                    "unit_type": "block",
                    "unit": "Poti",
                    "intervention_key": "fln_remedial",
                    "title": "FLN remedial classes in flagged Poti schools",
                    "issue_title": "Poti: low numeracy",
                    "owner_name": "Romi",
                    "owner_id": "beo-poti",
                    "priority": "High",
                    "age": 18,
                    "schools": [{"udise_code": s["udise_code"], "school_name": s["school_name"]} for s in flagged],
                    "due_date": (today() + timedelta(days=40)).isoformat(),
                },
                "in_progress",
                romi,
                "Remedial timetable shared with headmasters",
                impl_value=0.3,
            )
        if hm:
            code = hm[0]["udise_code"]
            sunita = {"id": "hm-poti-1", "name": "Sunita Verma", "role": "headmaster"}
            make(
                {
                    "unit_type": "school",
                    "unit": code,
                    "intervention_key": "remedial_catchup",
                    "title": "Daily 30-minute maths catch-up in level groups",
                    "issue_title": "School: maths fell",
                    "owner_name": "Sunita Verma",
                    "owner_id": "hm-poti-1",
                    "priority": "High",
                    "age": 12,
                    "due_date": (today() + timedelta(days=25)).isoformat(),
                },
                "in_progress",
                sunita,
                "Started with Grades 3 and 4",
                impl_value=0.35,
            )
            make(
                {
                    "unit_type": "school",
                    "unit": code,
                    "intervention_key": "parent_engagement",
                    "title": "SMC meeting on maths results with parents",
                    "issue_title": "School: parents",
                    "owner_name": "Shanti Devi",
                    "owner_id": "teacher-poti-1",
                    "age": 4,
                    "due_date": (today() + timedelta(days=12)).isoformat(),
                }
            )
    if "Kerwa" in blocks:
        from .. import visits

        visited = sorted(
            {v["udise_code"]: v["school_name"] for v in visits.list_visits(block="Kerwa", limit=50)}.items()
        )
        make(
            {
                "unit_type": "block",
                "unit": "Kerwa",
                "intervention_key": "classroom_observation",
                "title": "Maths classroom observation with the CRC checklist",
                "issue_title": "Kerwa: unexplained fall",
                "owner_name": "Meena Kumari",
                "owner_id": "crc-kerwa-1",
                "priority": "High",
                "age": 30,
                "schools": [{"udise_code": c, "school_name": s} for c, s in visited],
                "due_date": (today() + timedelta(days=20)).isoformat(),
            },
            "in_progress",
            {"id": "crc-kerwa-1", "name": "Meena Kumari", "role": "block"},
            "Checklist visits under way",
            impl_value=0.25,
        )

    # Every remaining block gets one current task that follows its own diagnosis, so no block's
    # Action room or meeting brief is empty. Missing or non-comparable data → finish the data first.
    from ..analytics.diagnose import diagnose

    has = {r["unit"] for r in db.query("SELECT DISTINCT unit FROM actions WHERE unit_type='block'")}
    trig_of = {
        "maths_vacancy": "maths_vacancy",
        "student_attendance": "student_attendance",
        "teacher_attendance": "teacher_attendance",
        "infrastructure": "infrastructure",
    }
    plan = [("open", None), ("in_progress", 0.4), ("in_progress", 0.7), ("awaiting_verification", 1.0)]
    for i, block in enumerate(sorted(blocks - has)):
        d = diagnose("block", block)
        strong = [
            s
            for s in d.get("signals", [])
            if s["classification"] in ("HIGH", "MEDIUM") and d.get("direction") == "decline" and s["factor"] in trig_of
        ]
        if d["verdict"] in ("INSUFFICIENT_EVIDENCE", "NON_COMPARABLE"):
            key = "data_completion"
        elif strong:
            key = library()[trig_of[strong[0]["factor"]]]["actions"][0]["key"]
        elif any("remainder_pp" in u for u in d.get("unresolved", [])):
            key = "classroom_observation"
        else:
            key = "fln_remedial"
        flagged = radar.radar("block", block, min_flags=1, limit=6)["schools"]
        status, impl = plan[i % len(plan)]
        beo = {"id": None, "name": f"BEO {block}", "role": "block"}
        make(
            {
                "unit_type": "block",
                "unit": block,
                "intervention_key": key,
                "title": f"{find_intervention(key)[1]['title']} — {block}",
                "issue_title": f"{block}: monthly review",
                "owner_name": f"BEO {block}",
                "age": 6 + 3 * (i % 5),
                "schools": [{"udise_code": s["udise_code"], "school_name": s["school_name"]} for s in flagged],
                "due_date": (today() + timedelta(days=(-4 if i % 6 == 5 else 9 + 4 * (i % 5)))).isoformat(),
            },
            None if status == "open" else status,
            beo,
            "Started (simulated)",
            impl_value=impl,
            evidence_note="Block report uploaded (simulated)" if status == "awaiting_verification" else None,
        )
    return n


def track_record(intervention_key: str | None = None, trigger: str | None = None) -> dict:
    """What happened when this kind of action was used before: done or not, and did learning move?"""
    keys = []
    if intervention_key:
        keys = [intervention_key]
    elif trigger and trigger in library():
        keys = [a["key"] for a in library()[trigger]["actions"]]
    if not keys:
        return {"uses": 0}
    rows = db.query(
        "SELECT * FROM actions WHERE intervention_key IN (" + ",".join(f"'{k}'" for k in keys) + ")"
        " AND status IN ('verified','closed_not_implemented')"
    )
    acts = [_enrich(r) for r in rows]
    changes = [
        a["learning_change"]
        for a in acts
        if a["learning_change"] is not None and a["outcome_status"] != "not_implemented"
    ]
    return {
        "uses": len(acts),
        "implemented": sum(a["outcome_status"] != "not_implemented" for a in acts),
        "not_implemented": sum(a["outcome_status"] == "not_implemented" for a in acts),
        "improved": sum(a["outcome_status"] == "implemented_improved" for a in acts),
        "no_change": sum(a["outcome_status"] == "implemented_no_change" for a in acts),
        "avg_change": round(sum(changes) / len(changes), 1) if changes else None,
        "simulated": all(a["is_simulated"] for a in acts) if acts else False,
        "examples": [
            {"unit": a["unit"], "outcome_status": a["outcome_status"], "learning_change": a["learning_change"]}
            for a in acts[:4]
        ],
    }
