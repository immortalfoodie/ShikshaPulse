"""Who sees and who may update a task; match-review queue scoped to the officer's area."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScopeFixture:
    """Two blocks in different districts, one school in the first block, and one persona per role."""

    users: dict[str, dict[str, Any]]
    block_a: str
    block_b: str
    school: str

    def task(self, **overrides: Any) -> dict[str, Any]:
        """A block-level task in `block_a`; keyword overrides replace any field."""
        return {
            "unit_type": "block",
            "unit": self.block_a,
            "owner_id": None,
            "owner_name": "x",
            "created_by": "y",
            "schools": [],
            **overrides,
        }


def _setup() -> ScopeFixture:
    from app import db

    rows = db.query("SELECT DISTINCT district, block FROM schools ORDER BY district, block")
    district_a, block_a = rows[0]["district"], rows[0]["block"]
    block_b = next(r["block"] for r in rows if r["district"] != district_a)
    school = db.query("SELECT udise_code FROM schools WHERE block=:b LIMIT 1", {"b": block_a})[0]["udise_code"]
    users = {
        "state": {"id": "s", "name": "State", "role": "state", "scope": None},
        "deo1": {"id": "d1", "name": "DEO 1", "role": "district", "scope": district_a},
        "beo1": {"id": "b1", "name": "BEO 1", "role": "block", "scope": block_a},
        "beo2": {"id": "b2", "name": "BEO 2", "role": "block", "scope": block_b},
        "crc1": {"id": "c1", "name": "CRC 1", "role": "block", "scope": block_a, "crc": True},
        "hm": {"id": "hm", "name": "HM", "role": "headmaster", "scope": school},
        "teacher": {"id": "tc", "name": "Teacher", "role": "headmaster", "scope": school, "teacher": True},
    }
    return ScopeFixture(users=users, block_a=block_a, block_b=block_b, school=school)


def test_task_visibility_follows_area(warehouse):
    from app.actions.service import in_scope

    fx = _setup()
    users, school = fx.users, fx.school
    task = fx.task()
    assert in_scope(users["state"], task) and in_scope(users["deo1"], task) and in_scope(users["beo1"], task)
    assert not in_scope(users["beo2"], task)  # another block's tasks are not shown
    assert not in_scope(users["hm"], task)  # a block task not involving the school
    assert in_scope(users["hm"], fx.task(schools=[{"udise_code": school, "school_name": "S"}]))
    assert in_scope(users["teacher"], fx.task(unit_type="school", unit=school))


def test_only_owner_or_responsible_officer_can_update(warehouse):
    from app.actions.service import can_update

    fx = _setup()
    users, school = fx.users, fx.school
    task = fx.task(owner_id="b1", owner_name="BEO 1")
    assert can_update(users["beo1"], task) and can_update(users["deo1"], task) and can_update(users["state"], task)
    assert not can_update(users["beo2"], task)  # other block
    assert not can_update(users["crc1"], task)  # CRC updates only her own tasks
    assert can_update(users["crc1"], fx.task(owner_id="c1", owner_name="CRC 1"))
    shared = fx.task(owner_id="b1", schools=[{"udise_code": school, "school_name": "S"}])
    assert not can_update(users["hm"], shared) and not can_update(users["teacher"], shared)  # visible, read-only
    hm_task = fx.task(unit_type="school", unit=school, owner_id="hm", owner_name="HM")
    assert can_update(users["hm"], hm_task) and not can_update(users["teacher"], hm_task)
    teacher_task = fx.task(unit_type="school", unit=school, owner_id="tc", owner_name="Teacher")
    assert can_update(users["teacher"], teacher_task) and can_update(users["hm"], teacher_task)  # HM runs the school


def test_match_review_scoped(warehouse):
    from app.api.routes import _review_in_scope

    fx = _setup()
    users = fx.users
    review = {"district": users["deo1"]["scope"], "block": fx.block_a}
    assert all(_review_in_scope(users[k], review) for k in ("state", "deo1", "beo1"))
    assert not any(_review_in_scope(users[k], review) for k in ("beo2", "crc1", "hm"))
