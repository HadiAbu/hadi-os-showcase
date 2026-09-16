"""R1 task 1.3 — /api/reflections routes (REQ-8/9/12/13)."""

from __future__ import annotations

import pytest

from app.services import insights, llm_client

R = "/api/reflections"

A = {"email": "ra@example.com", "password": "Sup3rSecret"}
B = {"email": "rb@example.com", "password": "Sup3rSecret"}


async def _token(client, creds) -> str:
    await client.post("/api/auth/register", json=creds)
    return (await client.post("/api/auth/login", json=creds)).json()["access_token"]


@pytest.fixture
async def two_users(client):
    a = await _token(client, A)
    b = await _token(client, B)
    return {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}


async def _seed_signal(auth_client) -> None:
    await auth_client.post("/api/objectives", json={"title": "Ship it", "horizon": "quarter"})
    await auth_client.post("/api/journal", json={"body": "notes on shipping the thing"})


async def test_generate_writes_templated_rows_without_a_key(auth_client):
    await _seed_signal(auth_client)
    out = (await auth_client.post(f"{R}/generate")).json()
    assert out["reason"] is None
    assert out["reflections"] and all(
        r["kind"] in ("momentum", "drift", "theme") for r in out["reflections"]
    )
    listed = (await auth_client.get(R)).json()
    assert {r["id"] for r in listed} == {r["id"] for r in out["reflections"]}


async def test_generate_empty_input_returns_reason(auth_client):
    out = (await auth_client.post(f"{R}/generate")).json()
    assert out["reflections"] == [] and out["reason"]


async def test_generate_uses_llm_when_available(auth_client, monkeypatch):
    async def fake_extract_json(*, system, user, **kwargs):
        return {"reflections": [{"kind": "theme", "body": "Consensus recurs.", "evidence": {}}]}

    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "extract_json", fake_extract_json)
    await _seed_signal(auth_client)

    out = (await auth_client.post(f"{R}/generate")).json()
    assert [r["body"] for r in out["reflections"]] == ["Consensus recurs."]


async def test_get_excludes_dismissed_and_patch_lifecycle(auth_client):
    await _seed_signal(auth_client)
    rid = (await auth_client.post(f"{R}/generate")).json()["reflections"][0]["id"]

    pinned = await auth_client.patch(f"{R}/{rid}", json={"status": "pinned"})
    assert pinned.json()["status"] == "pinned"
    assert rid in {r["id"] for r in (await auth_client.get(R)).json()}

    await auth_client.patch(f"{R}/{rid}", json={"status": "dismissed"})
    assert rid not in {r["id"] for r in (await auth_client.get(R)).json()}
    assert rid in {
        r["id"] for r in (await auth_client.get(f"{R}?status=dismissed")).json()
    }
    assert (await auth_client.patch(f"{R}/nope", json={"status": "pinned"})).status_code == 404


async def test_reflections_are_user_scoped(client, two_users):
    a_hdr, b_hdr = two_users
    await client.post(
        "/api/objectives", json={"title": "A's goal", "horizon": "year"}, headers=a_hdr
    )
    await client.post("/api/journal", json={"body": "A's private notes"}, headers=a_hdr)
    await client.post(f"{R}/generate", headers=a_hdr)

    assert (await client.get(R, headers=b_hdr)).json() == []
    assert (await client.post(f"{R}/generate", headers=b_hdr)).json()["reflections"] == []


@pytest.mark.parametrize("path", [R, f"{R}/generate"])
async def test_requires_auth(client, path):
    method = client.get if path == R else client.post
    assert (await method(path)).status_code == 401


async def test_generate_needs_no_llm_key(auth_client, monkeypatch):
    """REQ-13: reflections still generate (templated) with the AI disabled."""
    monkeypatch.setattr(llm_client, "available", lambda: False)
    monkeypatch.setattr(insights.llm_client, "available", lambda: False)
    await _seed_signal(auth_client)
    assert (await auth_client.post(f"{R}/generate")).status_code == 200
