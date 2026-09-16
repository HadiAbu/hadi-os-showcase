"""Task 7.2 — with no ANTHROPIC_API_KEY, everything except the AI endpoints works
(REQ-24)."""

from __future__ import annotations

import pytest

from app.services import llm_client


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)


async def test_core_loop_works_without_ai(auth_client):
    # onboarding (structured only)
    submit = await auth_client.post(
        "/api/onboarding/submit",
        json={
            "answers": [
                {"question_id": "identity_name", "value": "Hadi"},
                {"question_id": "objective_current", "value": ["Ship Phase 1"]},
            ],
            "samples": [],
        },
    )
    assert submit.status_code == 200
    assert submit.json()["enrichment"] == "skipped"

    # CRUD
    assert (
        await auth_client.post(
            "/api/context/entries",
            json={"category": "identity", "key": "role", "value": "engineer"},
        )
    ).status_code == 201
    pid = (await auth_client.post("/api/projects", json={"name": "sentinel"})).json()["id"]
    assert pid
    assert (
        await auth_client.post(
            "/api/objectives", json={"title": "Learn Rust", "horizon": "year"}
        )
    ).status_code == 201

    # dashboard aggregation + last focus snapshot
    assert (await auth_client.get("/api/dashboard")).status_code == 200
    focus = await auth_client.get("/api/dashboard/focus")
    assert focus.status_code == 200
    assert focus.json()["content_md"] is None

    # phase-2 telemetry + graph — all pure reads, no LLM
    assert (await auth_client.get("/api/graph")).status_code == 200
    assert (await auth_client.get("/api/graph/links")).status_code == 200
    assert (await auth_client.get("/api/usage?window=30d")).status_code == 200
    assert (await auth_client.get("/api/context/stats")).status_code == 200

    # phase-2.5 journal + reflections — journal CRUD and templated reflections work
    eid = (await auth_client.post("/api/journal", json={"body": "a note"})).json()["id"]
    assert (await auth_client.get("/api/journal")).status_code == 200
    assert (await auth_client.get(f"/api/journal/{eid}")).status_code == 200
    assert (await auth_client.post("/api/reflections/generate")).status_code == 200
    assert (await auth_client.get("/api/reflections")).status_code == 200


async def test_ai_endpoints_return_503(auth_client):
    cid = (await auth_client.post("/api/chat/conversations")).json()["id"]
    turn = await auth_client.post(
        f"/api/chat/conversations/{cid}/messages", json={"text": "hi"}
    )
    assert turn.status_code == 503
    assert (await auth_client.post("/api/dashboard/focus/refresh")).status_code == 503

    eid = (await auth_client.post("/api/journal", json={"body": "x"})).json()["id"]
    assert (await auth_client.post(f"/api/journal/{eid}/continue")).status_code == 503
