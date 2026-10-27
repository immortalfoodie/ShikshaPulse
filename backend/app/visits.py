"""School visits by Cluster Resource Coordinators (CRCs).

A short classroom-observation checklist fills the biggest gap in the data: what actually happens
in the maths lesson. Visits can be recorded offline on a phone and synced later. Summaries feed
the Why? engine and the AI assistant as *field observations* (observed facts, not causes).
"""
from __future__ import annotations

import json
from datetime import timedelta

import numpy as np

from . import db
from .config import today

CHECKLIST = ["teacher_teaching", "materials_used", "level_groups", "children_practice", "checks_understanding",
             "time_on_maths"]
VALUES = {"yes": 2, "partly": 1, "no": 0}

TABLE = """
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT UNIQUE, udise_code TEXT, school_name TEXT, block TEXT, district TEXT,
    visitor TEXT, visitor_id TEXT, visit_date TEXT, answers TEXT, score REAL,
    children_present INTEGER, children_enrolled INTEGER, notes TEXT,
    recorded_offline INTEGER DEFAULT 0, synced_at TEXT, is_simulated INTEGER DEFAULT 0
)"""


def ensure_table() -> None:
    db.execute(TABLE)


def score(answers: dict) -> float:
    vals = [VALUES.get(answers.get(k, ""), None) for k in CHECKLIST]
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / (2 * len(vals)) * 100, 1) if vals else 0.0


def record(visit: dict, user: dict, simulated: bool = False) -> dict:
    ensure_table()
    if visit.get("client_id"):
        dup = db.query("SELECT id FROM visits WHERE client_id=:c", {"c": visit["client_id"]})
        if dup:
            return {"id": dup[0]["id"], "duplicate": True}
    s = db.query("SELECT school_name, block, district FROM schools WHERE udise_code=:c", {"c": visit["udise_code"]})
    if not s:
        raise ValueError("Unknown school")
    answers = {k: visit.get("answers", {}).get(k) for k in CHECKLIST}
    vid = db.execute(
        "INSERT INTO visits (client_id, udise_code, school_name, block, district, visitor, visitor_id, visit_date, answers,"
        " score, children_present, children_enrolled, notes, recorded_offline, synced_at, is_simulated) VALUES"
        " (:cid,:u,:sn,:b,:d,:v,:vid,:dt,:a,:sc,:cp,:ce,:n,:off,:sy,:sim)",
        {"cid": visit.get("client_id"), "u": visit["udise_code"], "sn": s[0]["school_name"], "b": s[0]["block"],
         "d": s[0]["district"], "v": user["name"], "vid": user["id"], "dt": visit.get("visit_date") or today().isoformat(),
         "a": json.dumps(answers), "sc": score(answers), "cp": visit.get("children_present"),
         "ce": visit.get("children_enrolled"), "n": visit.get("notes", ""), "off": int(bool(visit.get("recorded_offline"))),
         "sy": today().isoformat(), "sim": int(simulated)})
    db.bump_version()  # diagnosis caches must see new field evidence
    return {"id": vid, "score": score(answers)}


def list_visits(block: str | None = None, district: str | None = None, udise: str | None = None, limit: int = 50) -> list[dict]:
    ensure_table()
    where, p = [], {}
    if block:
        where.append("block=:b"); p["b"] = block
    if district:
        where.append("district=:d"); p["d"] = district
    if udise:
        where.append("udise_code=:u"); p["u"] = udise
    sql = "SELECT * FROM visits" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY visit_date DESC, id DESC LIMIT :l"
    p["l"] = limit
    rows = db.query(sql, p)
    for r in rows:
        r["answers"] = json.loads(r["answers"] or "{}")
        r["is_simulated"] = bool(r["is_simulated"])
    return rows


def summary(unit_type: str, unit: str | None) -> dict | None:
    """Field-observation summary for a unit (None when fewer than 3 visits)."""
    ensure_table()
    if unit_type == "state":
        rows = list_visits(limit=100000)
    elif unit_type == "district":
        rows = list_visits(district=unit, limit=100000)
    elif unit_type == "block":
        rows = list_visits(block=unit, limit=100000)
    else:
        rows = list_visits(udise=unit, limit=100000)
    if len(rows) < (1 if unit_type == "school" else 3):
        return None
    items = []
    for k in CHECKLIST:
        vals = [r["answers"].get(k) for r in rows if r["answers"].get(k)]
        if vals:
            items.append({"item": k, "pct_yes": round(100 * sum(v == "yes" for v in vals) / len(vals)),
                          "pct_no": round(100 * sum(v == "no" for v in vals) / len(vals))})
    items.sort(key=lambda i: i["pct_yes"])
    dates = sorted(r["visit_date"] for r in rows)
    return {"n_visits": len(rows), "n_schools": len({r["udise_code"] for r in rows}),
            "avg_score": round(float(np.mean([r["score"] for r in rows])), 1), "items": items,
            "weakest": [i["item"] for i in items[:2]], "first": dates[0], "last": dates[-1],
            "simulated": all(r["is_simulated"] for r in rows)}


def seed_demo_visits() -> int:
    """Clearly-labelled simulated visits that show how field evidence closes an open question."""
    ensure_table()
    if db.query("SELECT COUNT(*) AS n FROM visits")[0]["n"] > 0 or not db.table_exists("schools"):
        return 0
    rng = np.random.default_rng(11)
    crc = {"id": "crc-kerwa-1", "name": "Meena Kumari"}
    plans = {
        # block: probabilities of yes / partly / no per checklist item (story-specific)
        "Kerwa": {"teacher_teaching": (.75, .2, .05), "materials_used": (.1, .3, .6), "level_groups": (.05, .15, .8),
                  "children_practice": (.15, .35, .5), "checks_understanding": (.2, .3, .5), "time_on_maths": (.4, .4, .2)},
        "Poti": {"teacher_teaching": (.3, .2, .5), "materials_used": (.35, .35, .3), "level_groups": (.3, .3, .4),
                 "children_practice": (.4, .3, .3), "checks_understanding": (.35, .35, .3), "time_on_maths": (.2, .3, .5)},
        "Bhanpur": {k: (.65, .25, .1) for k in CHECKLIST},
    }
    sizes = {b: 8 for b in plans}
    # Every other block gets a few routine visits, shaped by its own data: fewer maths teachers
    # present where posts are empty or teacher attendance is low, otherwise a block-level practice mix.
    from .analytics.common import subset, years
    p = subset("state", None)
    if not p.empty:
        last = p[p.academic_year == years()[-1]]
        for block, g in last.groupby("block"):
            if block in plans:
                continue
            vac = float(g.maths_vacancy.mean()) if "maths_vacancy" in g and g.maths_vacancy.notna().any() else 15.0
            tatt = float(g.teacher_att.mean()) if "teacher_att" in g and g.teacher_att.notna().any() else 85.0
            present = float(np.clip(0.85 - vac / 100 - max(0.0, 85 - tatt) / 50, 0.25, 0.85))
            q = float(rng.uniform(0.3, 0.65))
            mix = lambda y: (y, (1 - y) * 0.55, (1 - y) * 0.45)  # noqa: E731  yes / partly / no
            plans[block] = {k: mix(present if k == "teacher_teaching" else float(np.clip(q + rng.normal(0, .1), .1, .85)))
                            for k in CHECKLIST}
            sizes[block] = int(rng.integers(4, 7))
    n = 0
    for block, probs in plans.items():
        schools = db.query("SELECT udise_code FROM schools WHERE block=:b ORDER BY udise_code LIMIT :n",
                           {"b": block, "n": sizes[block]})
        for i, s in enumerate(schools):
            answers = {k: str(rng.choice(["yes", "partly", "no"], p=probs[k])) for k in CHECKLIST}
            record({"udise_code": s["udise_code"], "answers": answers, "children_present": int(rng.integers(14, 32)),
                    "children_enrolled": int(rng.integers(30, 40)),
                    "visit_date": (today() - timedelta(days=int(5 + i * 4))).isoformat(),
                    "notes": "Demo visit (simulated)", "client_id": f"seed-{block}-{i}"},
                   {**crc, "name": crc["name"] if block == "Kerwa" else f"CRC {block}"}, simulated=True)
            n += 1
    return n
