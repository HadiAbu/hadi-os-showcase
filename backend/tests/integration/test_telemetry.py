"""M6 tasks 6.1-6.3 — /api/usage + /api/context/stats routes (REQ-10, 11, 12, 13, 14)."""

from __future__ import annotations

import pytest

USAGE = "/api/usage"
STATS = "/api/context/stats"

A = {"email": "ta@example.com", "password": "Sup3rSecret"}
B = {"email": "tb@example.com", "password": "Sup3rSecret"}


async def _token(client, creds) -> str:
    await client.post("/api/auth/register", json=creds)
    return (await client.post("/api/auth/login", json=creds)).json()["access_token"]


@pytest.fixture
async def two_users(client):
    a = await _token(client, A)
    b = await _token(client, B)
    return {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}


@pytest.mark.parametrize("path", [USAGE, STATS])
async def test_requires_auth(client, path):
    assert (await client.get(path)).status_code == 401


async def test_usage_window_param_is_validated(auth_client):
    assert (await auth_client.get(f"{USAGE}?window=7d")).status_code == 200
    assert (await auth_client.get(f"{USAGE}?window=30d")).status_code == 200
    assert (await auth_client.get(f"{USAGE}?window=all")).status_code == 200
    assert (await auth_client.get(f"{USAGE}?window=nonsense")).status_code == 422


async def test_usage_zeroed_for_a_fresh_user(auth_client):
    body = (await auth_client.get(USAGE)).json()
    assert body["window"] == "7d"
    assert body["tokens"] == {"prompt": 0, "completion": 0, "total": 0}
    assert body["by_day"] == [] and body["by_model"] == []
    assert body["tool_calls_total"] == 0
    assert body["estimated_cost_usd"] == 0.0
    assert body["cost_known"] is True


async def test_context_stats_reflects_entries(auth_client):
    await auth_client.post(
        "/api/context/entries", json={"category": "identity", "key": "role", "value": "eng"}
    )
    await auth_client.post(
        "/api/context/entries", json={"category": "misc", "key": "note", "value": "x"}
    )
    body = (await auth_client.get(STATS)).json()
    by_status = {s["status"]: s["count"] for s in body["by_status"]}
    assert by_status.get("active") == 2
    assert len(body["growth"]) == 30
    assert body["stale"] == 0


async def test_telemetry_is_user_scoped(client, two_users):
    a_hdr, b_hdr = two_users
    await client.post(
        "/api/context/entries",
        json={"category": "identity", "key": "role", "value": "eng"},
        headers=a_hdr,
    )
    # B sees only its own (empty) figures
    b_stats = (await client.get(STATS, headers=b_hdr)).json()
    assert b_stats["by_status"] == []
    b_usage = (await client.get(USAGE, headers=b_hdr)).json()
    assert b_usage["tokens"]["total"] == 0
