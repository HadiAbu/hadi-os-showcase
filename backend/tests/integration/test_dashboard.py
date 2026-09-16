"""Tasks 6.1-6.2 — dashboard aggregation + focus snapshot (REQ-19, REQ-20, REQ-24)."""

from __future__ import annotations

from app.services import llm_client

OBJ = "/api/objectives"
DASH = "/api/dashboard"


async def _seed(auth_client):
    oid = (await auth_client.post(OBJ, json={"title": "Ship Phase 1", "horizon": "quarter", "priority": 1})).json()["id"]
    a1 = (await auth_client.post(f"{OBJ}/{oid}/actions", json={"title": "loop"})).json()["id"]
    (await auth_client.post(f"{OBJ}/{oid}/actions", json={"title": "ui"})).json()
    await auth_client.patch(f"/api/actions/{a1}", json={"status": "done"})
    await auth_client.post("/api/projects", json={"name": "sentinel"})
    return oid


async def test_dashboard_aggregates(auth_client):
    await _seed(auth_client)
    d = (await auth_client.get(DASH)).json()

    assert len(d["objectives"]) == 1
    prog = d["objectives"][0]
    assert prog["total_actions"] == 2
    assert prog["open_actions"] == 1
    assert prog["pct_done"] == 50

    m = d["momentum"]
    assert m["actions_done_7d"] == 1
    assert m["actions_done_30d"] == 1
    assert m["objectives_touched_7d"] == 1
    assert m["projects_touched_7d"] == 1

    kinds = {c["kind"] for c in d["changed_this_week"]}
    assert {"objective", "action", "project"}.issubset(kinds)
    ats = [c["at"] for c in d["changed_this_week"]]
    assert ats == sorted(ats, reverse=True)


async def test_dashboard_no_lLM_call_when_key_absent(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)
    await _seed(auth_client)
    assert (await auth_client.get(DASH)).status_code == 200


async def test_focus_default_is_stale_null(auth_client):
    got = (await auth_client.get(f"{DASH}/focus")).json()
    assert got == {"content_md": None, "created_at": None, "stale": True}


async def test_focus_refresh_503_without_key(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)
    assert (await auth_client.post(f"{DASH}/focus/refresh")).status_code == 503
    # GET still works, just empty
    assert (await auth_client.get(f"{DASH}/focus")).status_code == 200


async def test_focus_refresh_stores_and_serves(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: True)

    async def fake_one_shot(**_kwargs):
        return "## Focus\n- Finish the agent loop\n- Then the dashboard"

    monkeypatch.setattr(llm_client, "one_shot", fake_one_shot)
    await _seed(auth_client)

    refreshed = await auth_client.post(f"{DASH}/focus/refresh")
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["content_md"].startswith("## Focus")
    assert body["stale"] is False

    served = (await auth_client.get(f"{DASH}/focus")).json()
    assert served["content_md"] == body["content_md"]
    assert served["stale"] is False


async def test_requires_auth(client):
    assert (await client.get(DASH)).status_code == 401
