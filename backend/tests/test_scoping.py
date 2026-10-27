"""Who sees and who may update a task; match-review queue scoped to the officer's area."""


def _setup():
    from app import db
    rows = db.query("SELECT DISTINCT district, block FROM schools ORDER BY district, block")
    (d1, b1), (d2, b2) = (rows[0]["district"], rows[0]["block"]), next(
        (r["district"], r["block"]) for r in rows if r["district"] != rows[0]["district"])
    school = db.query("SELECT udise_code FROM schools WHERE block=:b LIMIT 1", {"b": b1})[0]["udise_code"]
    U = {
        "state": {"id": "s", "name": "State", "role": "state", "scope": None},
        "deo1": {"id": "d1", "name": "DEO 1", "role": "district", "scope": d1},
        "beo1": {"id": "b1", "name": "BEO 1", "role": "block", "scope": b1},
        "beo2": {"id": "b2", "name": "BEO 2", "role": "block", "scope": b2},
        "crc1": {"id": "c1", "name": "CRC 1", "role": "block", "scope": b1, "crc": True},
        "hm": {"id": "hm", "name": "HM", "role": "headmaster", "scope": school},
        "teacher": {"id": "tc", "name": "Teacher", "role": "headmaster", "scope": school, "teacher": True},
    }
    task = lambda **k: {"unit_type": "block", "unit": b1, "owner_id": None, "owner_name": "x", "created_by": "y",  # noqa: E731
                        "schools": [], **k}
    return U, task, b1, b2, school


def test_task_visibility_follows_area(warehouse):
    from app.actions.service import in_scope
    U, task, b1, b2, school = _setup()
    t = task()
    assert in_scope(U["state"], t) and in_scope(U["deo1"], t) and in_scope(U["beo1"], t)
    assert not in_scope(U["beo2"], t)  # another block's tasks are not shown
    assert not in_scope(U["hm"], t)  # a block task not involving the school
    assert in_scope(U["hm"], task(schools=[{"udise_code": school, "school_name": "S"}]))
    assert in_scope(U["teacher"], task(unit_type="school", unit=school))


def test_only_owner_or_responsible_officer_can_update(warehouse):
    from app.actions.service import can_update
    U, task, b1, b2, school = _setup()
    t = task(owner_id="b1", owner_name="BEO 1")
    assert can_update(U["beo1"], t) and can_update(U["deo1"], t) and can_update(U["state"], t)
    assert not can_update(U["beo2"], t)  # other block
    assert not can_update(U["crc1"], t)  # CRC updates only her own tasks
    assert can_update(U["crc1"], task(owner_id="c1", owner_name="CRC 1"))
    shared = task(owner_id="b1", schools=[{"udise_code": school, "school_name": "S"}])
    assert not can_update(U["hm"], shared) and not can_update(U["teacher"], shared)  # visible, read-only
    st = task(unit_type="school", unit=school, owner_id="hm", owner_name="HM")
    assert can_update(U["hm"], st) and not can_update(U["teacher"], st)
    tt = task(unit_type="school", unit=school, owner_id="tc", owner_name="Teacher")
    assert can_update(U["teacher"], tt) and can_update(U["hm"], tt)  # headmaster runs the school


def test_match_review_scoped(warehouse):
    from app.api.routes import _review_in_scope
    U, task, b1, b2, school = _setup()
    r = {"district": U["deo1"]["scope"], "block": b1}
    assert _review_in_scope(U["state"], r) and _review_in_scope(U["deo1"], r) and _review_in_scope(U["beo1"], r)
    assert not _review_in_scope(U["beo2"], r) and not _review_in_scope(U["crc1"], r) and not _review_in_scope(U["hm"], r)
