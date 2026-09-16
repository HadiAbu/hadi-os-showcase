"""Tasks 3.2-3.3 — objectives + actions CRUD (REQ-12, REQ-13)."""

from __future__ import annotations

OBJ = "/api/objectives"


async def test_create_defaults(auth_client):
    r = await auth_client.post(OBJ, json={"title": "Ship Phase 1", "horizon": "quarter"})
    assert r.status_code == 201
    o = r.json()
    assert o["status"] == "active"
    assert o["priority"] == 2
    assert o["tags"] == []
    assert o["completed_at"] is None


async def test_priority_bounds_422(auth_client):
    for p in (0, 4):
        r = await auth_client.post(
            OBJ, json={"title": "x", "horizon": "month", "priority": p}
        )
        assert r.status_code == 422


async def test_done_sets_and_clears_completed_at(auth_client):
    oid = (
        await auth_client.post(OBJ, json={"title": "Learn Rust", "horizon": "year"})
    ).json()["id"]

    done = await auth_client.patch(f"{OBJ}/{oid}", json={"status": "done"})
    assert done.json()["completed_at"] is not None

    reopened = await auth_client.patch(f"{OBJ}/{oid}", json={"status": "active"})
    assert reopened.json()["completed_at"] is None


async def test_unknown_project_id_422_valid_links(auth_client):
    bad = await auth_client.post(
        OBJ, json={"title": "x", "horizon": "month", "project_id": "nope"}
    )
    assert bad.status_code == 422

    pid = (await auth_client.post("/api/projects", json={"name": "sentinel"})).json()["id"]
    good = await auth_client.post(
        OBJ, json={"title": "ship sentinel", "horizon": "quarter", "project_id": pid}
    )
    assert good.status_code == 201
    assert good.json()["project_id"] == pid


async def test_tag_filter_and_ordering(auth_client):
    await auth_client.post(
        OBJ, json={"title": "low prio skill", "horizon": "year", "priority": 3, "tags": ["skill"]}
    )
    await auth_client.post(
        OBJ, json={"title": "top prio", "horizon": "month", "priority": 1}
    )
    ordered = (await auth_client.get(OBJ)).json()
    assert [o["title"] for o in ordered] == ["top prio", "low prio skill"]

    skilled = (await auth_client.get(f"{OBJ}?tag=skill")).json()
    assert [o["title"] for o in skilled] == ["low prio skill"]


async def test_actions_lifecycle_and_objective_detail(auth_client):
    oid = (
        await auth_client.post(OBJ, json={"title": "Ship Phase 1", "horizon": "quarter"})
    ).json()["id"]

    a = await auth_client.post(f"{OBJ}/{oid}/actions", json={"title": "write the loop"})
    assert a.status_code == 201
    action = a.json()
    assert action["source"] == "manual"
    assert action["status"] == "todo"

    done = await auth_client.patch(f"/api/actions/{action['id']}", json={"status": "done"})
    assert done.json()["completed_at"] is not None
    cleared = await auth_client.patch(f"/api/actions/{action['id']}", json={"status": "doing"})
    assert cleared.json()["completed_at"] is None

    detail = (await auth_client.get(f"{OBJ}/{oid}")).json()
    assert detail["objective"]["id"] == oid
    assert [x["id"] for x in detail["actions"]] == [action["id"]]


async def test_action_under_missing_objective_404(auth_client):
    assert (
        await auth_client.post("/api/objectives/nope/actions", json={"title": "x"})
    ).status_code == 404


async def test_dropped_objective_keeps_actions(auth_client):
    oid = (
        await auth_client.post(OBJ, json={"title": "Old goal", "horizon": "month"})
    ).json()["id"]
    aid = (
        await auth_client.post(f"{OBJ}/{oid}/actions", json={"title": "leftover"})
    ).json()["id"]

    await auth_client.patch(f"{OBJ}/{oid}", json={"status": "dropped"})

    detail = (await auth_client.get(f"{OBJ}/{oid}")).json()
    assert detail["objective"]["status"] == "dropped"
    assert [x["id"] for x in detail["actions"]] == [aid]
