"""Demo personas, signed session tokens, row-level scoping and audit logging."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime

from fastapi import Header, HTTPException

from . import db
from .config import app_secret

ROLE_LEVEL = {"headmaster": 0, "block": 1, "district": 2, "state": 3}

PERSONAS = [
    {
        "id": "state-spd",
        "name": "Dr. Meera Iyer",
        "role": "state",
        "title": "State Project Director",
        "scope_type": "state",
        "scope": None,
    },
    {
        "id": "deo-devgarh",
        "name": "Mr. Chan",
        "role": "district",
        "title": "District Education Officer, Devgarh",
        "scope_type": "district",
        "scope": "Devgarh",
    },
    {
        "id": "beo-poti",
        "name": "Romi",
        "role": "block",
        "title": "Block Education Officer, Poti",
        "scope_type": "block",
        "scope": "Poti",
    },
    {
        "id": "beo-sinda",
        "name": "Arjun Patel",
        "role": "block",
        "title": "Block Education Officer, Sinda",
        "scope_type": "block",
        "scope": "Sinda",
    },
    {
        "id": "beo-kerwa",
        "name": "Kavita Rao",
        "role": "block",
        "title": "Block Education Officer, Kerwa",
        "scope_type": "block",
        "scope": "Kerwa",
    },
    {
        "id": "crc-kerwa-1",
        "name": "Meena Kumari",
        "role": "block",
        "title": "Cluster Resource Coordinator, Kerwa",
        "scope_type": "block",
        "scope": "Kerwa",
        "crc": True,
    },
    {
        "id": "hm-poti-1",
        "name": "Sunita Verma",
        "role": "headmaster",
        "title": "Headmaster, Poti block",
        "scope_type": "school",
        "scope": None,
    },
    {
        "id": "teacher-poti-1",
        "name": "Shanti Devi",
        "role": "headmaster",
        "title": "Teacher, Poti block",
        "scope_type": "school",
        "scope": None,
        "teacher": True,
    },
]


def persona(pid: str) -> dict:
    p = next((x for x in PERSONAS if x["id"] == pid), None)
    if p is None:
        raise HTTPException(404, "Unknown persona")
    p = dict(p)
    if p["role"] == "headmaster" and db.table_exists("schools"):
        s = db.query(
            "SELECT udise_code, school_name, block, district FROM schools WHERE block='Poti' "
            "ORDER BY udise_code LIMIT 1"
        )
        if s:
            p["scope"] = s[0]["udise_code"]
            p["title"] = f"{'Teacher' if p.get('teacher') else 'Headmaster'}, {s[0]['school_name']}"
            p["school_name"] = s[0]["school_name"]
    p.update(_scope_parents(p))
    return p


def _scope_parents(p: dict) -> dict:
    out = {"district": None, "block": None}
    if not db.table_exists("schools"):
        return out
    if p["scope_type"] == "district":
        out["district"] = p["scope"]
    elif p["scope_type"] == "block":
        r = db.query("SELECT district FROM schools WHERE block=:b LIMIT 1", {"b": p["scope"]})
        out.update(block=p["scope"], district=r[0]["district"] if r else None)
    elif p["scope_type"] == "school" and p["scope"]:
        r = db.query("SELECT district, block FROM schools WHERE udise_code=:c", {"c": p["scope"]})
        if r:
            out.update(district=r[0]["district"], block=r[0]["block"])
    return out


def _sign(payload: str) -> str:
    return hmac.new(app_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def issue_token(pid: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"pid": pid}).encode()).decode()
    return f"{payload}.{_sign(payload)}"


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(401, "Login required")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload, sig = token.split(".")
    except ValueError as e:
        raise HTTPException(401, "Bad token") from e
    if not hmac.compare_digest(sig, _sign(payload)):
        raise HTTPException(401, "Bad token")
    pid = json.loads(base64.urlsafe_b64decode(payload.encode()))["pid"]
    return persona(pid)


def can_view(user: dict, unit_type: str, unit: str | None) -> bool:
    """Row-level scoping: a user sees their own unit, its children, and aggregated parents/peers."""
    if user["role"] == "state":
        return True
    if unit_type == "state":
        return True  # state aggregates only (no school detail outside scope)
    if not db.table_exists("schools"):
        return True
    if unit_type == "district":
        return True  # district aggregates are visible for benchmarking
    if unit_type == "block":
        if user["role"] == "district":
            return True  # block aggregates, including peers in other districts, for benchmarking
        return True
    if unit_type == "school":
        r = db.query("SELECT district, block FROM schools WHERE udise_code=:c", {"c": unit})
        if not r:
            return False
        if user["role"] == "district":
            return r[0]["district"] == user["scope"]
        if user["role"] == "block":
            return r[0]["block"] == user["scope"]
        return unit == user["scope"]
    return False


def require_view(user: dict, unit_type: str, unit: str | None) -> None:
    if not can_view(user, unit_type, unit):
        raise HTTPException(403, "Outside your data scope")


def can_list_schools(user: dict, unit_type: str, unit: str | None) -> bool:
    """School-level detail (names, codes) is limited to the user's own scope."""
    if user["role"] == "state":
        return True
    if unit_type == "state":
        return False
    if user["role"] == "district":
        if unit_type == "district":
            return str(unit).casefold() == str(user["scope"]).casefold()
        if unit_type == "block":
            r = db.query("SELECT district FROM schools WHERE block=:b LIMIT 1", {"b": unit})
            return bool(r) and r[0]["district"] == user["scope"]
        return can_view(user, unit_type, unit)
    if user["role"] == "block":
        if unit_type == "block":
            return str(unit).casefold() == str(user["scope"]).casefold()
        return unit_type == "school" and can_view(user, unit_type, unit)
    return unit_type == "school" and unit == user["scope"]


def clamp_school_scope(user: dict, unit_type: str, unit: str | None) -> tuple[str, str | None]:
    return (unit_type, unit) if can_list_schools(user, unit_type, unit) else school_scope_filter(user)


def school_scope_filter(user: dict) -> tuple[str, str | None]:
    """Which schools a user may list individually."""
    if user["role"] == "state":
        return ("state", None)
    if user["role"] == "district":
        return ("district", user["scope"])
    if user["role"] == "block":
        return ("block", user["scope"])
    return ("school", user["scope"])


def audit(user: dict | None, action: str, detail: dict | str = "") -> None:
    db.execute(
        "INSERT INTO audit_log (user_id, user_name, role, action, detail, at) VALUES (:i,:n,:r,:a,:d,:t)",
        {
            "i": (user or {}).get("id"),
            "n": (user or {}).get("name"),
            "r": (user or {}).get("role"),
            "a": action,
            "d": detail if isinstance(detail, str) else json.dumps(detail, default=str),
            "t": datetime.now().isoformat(timespec="seconds"),
        },
    )
