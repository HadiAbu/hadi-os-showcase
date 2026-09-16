"""Task 7.3 — security review: one user cannot see or touch another's data, and
missing resources return 404 without confirming existence (REQ-23, REQ-4)."""

from __future__ import annotations

import pytest

A = {"email": "a@example.com", "password": "Sup3rSecret"}
B = {"email": "b@example.com", "password": "Sup3rSecret"}


async def _token(client, creds) -> str:
    await client.post("/api/auth/register", json=creds)
    return (await client.post("/api/auth/login", json=creds)).json()["access_token"]


@pytest.fixture
async def two_users(client):
    a = await _token(client, A)
    b = await _token(client, B)
    return {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}


async def test_objective_is_invisible_and_unpatchable_across_users(client, two_users):
    a_hdr, b_hdr = two_users
    oid = (
        await client.post(
            "/api/objectives", json={"title": "A's goal", "horizon": "month"}, headers=a_hdr
        )
    ).json()["id"]

    assert (await client.get("/api/objectives", headers=b_hdr)).json() == []
    assert (await client.get(f"/api/objectives/{oid}", headers=b_hdr)).status_code == 404
    assert (
        await client.patch(f"/api/objectives/{oid}", json={"title": "hijack"}, headers=b_hdr)
    ).status_code == 404


async def test_conversation_and_context_are_scoped(client, two_users):
    a_hdr, b_hdr = two_users
    cid = (await client.post("/api/chat/conversations", headers=a_hdr)).json()["id"]
    await client.post(
        "/api/context/entries",
        json={"category": "misc", "key": "secret", "value": "A only"},
        headers=a_hdr,
    )

    assert (
        await client.get(f"/api/chat/conversations/{cid}/messages", headers=b_hdr)
    ).status_code == 404
    assert (await client.get("/api/chat/conversations", headers=b_hdr)).json() == []
    assert (await client.get("/api/context/entries", headers=b_hdr)).json() == []


async def test_security_headers_on_api_route(client, two_users):
    a_hdr, _ = two_users
    resp = await client.get("/api/auth/me", headers=a_hdr)
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "strict-transport-security" not in resp.headers  # dev
