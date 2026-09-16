"""J0 task 0.3 — /api/journal CRUD routes (REQ-2, 12)."""

from __future__ import annotations

import pytest

from app.services import llm_client

J = "/api/journal"

A = {"email": "ja@example.com", "password": "Sup3rSecret"}
B = {"email": "jb@example.com", "password": "Sup3rSecret"}


async def _token(client, creds) -> str:
    await client.post("/api/auth/register", json=creds)
    return (await client.post("/api/auth/login", json=creds)).json()["access_token"]


@pytest.fixture
async def two_users(client):
    a = await _token(client, A)
    b = await _token(client, B)
    return {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}


async def test_crud_round_trip(auth_client):
    created = await auth_client.post(
        J, json={"title": "Day one", "body": "Shipped J0.", "mood": "good", "tags": ["hadi-os"]}
    )
    assert created.status_code == 201
    eid = created.json()["id"]
    assert created.json()["tags"] == ["hadi-os"]

    assert [e["id"] for e in (await auth_client.get(J)).json()] == [eid]
    assert (await auth_client.get(f"{J}/{eid}")).json()["body"] == "Shipped J0."

    patched = await auth_client.patch(f"{J}/{eid}", json={"body": "edited", "mood": "flat"})
    assert patched.json()["body"] == "edited"
    assert patched.json()["mood"] == "flat"

    assert (await auth_client.delete(f"{J}/{eid}")).status_code == 204
    assert (await auth_client.get(f"{J}/{eid}")).status_code == 404
    assert (await auth_client.get(J)).json() == []


async def test_filter_by_linked_objective(auth_client):
    oid = (
        await auth_client.post("/api/objectives", json={"title": "O", "horizon": "year"})
    ).json()["id"]
    linked = (
        await auth_client.post(J, json={"body": "about the objective", "linked_objective_id": oid})
    ).json()["id"]
    await auth_client.post(J, json={"body": "unrelated"})

    filtered = (await auth_client.get(f"{J}?objective_id={oid}")).json()
    assert [e["id"] for e in filtered] == [linked]


async def test_foreign_link_is_422(auth_client):
    r = await auth_client.post(J, json={"body": "x", "linked_project_id": "not-mine"})
    assert r.status_code == 422


async def test_journal_is_user_scoped(client, two_users):
    a_hdr, b_hdr = two_users
    eid = (
        await client.post(J, json={"title": "A's entry", "body": "private"}, headers=a_hdr)
    ).json()["id"]

    assert (await client.get(J, headers=b_hdr)).json() == []
    assert (await client.get(f"{J}/{eid}", headers=b_hdr)).status_code == 404
    assert (
        await client.patch(f"{J}/{eid}", json={"body": "hijack"}, headers=b_hdr)
    ).status_code == 404
    assert (await client.delete(f"{J}/{eid}", headers=b_hdr)).status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
async def test_requires_auth(client, method):
    resp = await getattr(client, method)(J) if method == "get" else await client.post(J, json={})
    assert resp.status_code == 401


# --- J1: continue in my voice -------------------------------------


async def test_continue_503_without_key(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)
    eid = (await auth_client.post(J, json={"body": "started writing"})).json()["id"]
    assert (await auth_client.post(f"{J}/{eid}/continue")).status_code == 503


async def test_continue_404_for_missing_entry(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: True)
    assert (await auth_client.post(f"{J}/nope/continue")).status_code == 404


async def test_continue_returns_generated_text(auth_client, monkeypatch):
    captured: dict = {}

    async def fake_one_shot(*, system, user, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return "  and then the work continued into the evening.  "

    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "one_shot", fake_one_shot)

    eid = (
        await auth_client.post(J, json={"title": "Wed", "body": "Shipped the graph layer."})
    ).json()["id"]
    r = await auth_client.post(f"{J}/{eid}/continue")
    assert r.status_code == 200
    assert r.json()["text"] == "and then the work continued into the evening."
    assert "Shipped the graph layer." in captured["user"]
