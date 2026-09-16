"""Task 3.1 — projects CRUD (REQ-14)."""

from __future__ import annotations

BASE = "/api/projects"


async def test_create_defaults_and_tech_roundtrip(auth_client):
    r = await auth_client.post(
        BASE, json={"name": "sentinel", "tech": ["python", "react"], "repo_path": "/c/dev/sentinel"}
    )
    assert r.status_code == 201
    p = r.json()
    assert p["status"] == "active"
    assert p["tech"] == ["python", "react"]
    assert p["repo_path"] == "/c/dev/sentinel"
    assert p["summary"] == "" and p["next_steps"] == ""


async def test_list_get_patch(auth_client):
    pid = (await auth_client.post(BASE, json={"name": "alpha"})).json()["id"]

    assert [p["name"] for p in (await auth_client.get(BASE)).json()] == ["alpha"]

    patched = await auth_client.patch(
        f"{BASE}/{pid}", json={"status": "shipped", "next_steps": "write the README"}
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "shipped"
    assert patched.json()["next_steps"] == "write the README"

    assert (await auth_client.get(f"{BASE}?status=shipped")).json()[0]["id"] == pid


async def test_get_missing_404(auth_client):
    assert (await auth_client.get(f"{BASE}/nope")).status_code == 404
    assert (await auth_client.patch(f"{BASE}/nope", json={"name": "x"})).status_code == 404


async def test_projects_user_scoped(auth_client, client):
    await auth_client.post(BASE, json={"name": "mine"})
    await client.post(
        "/api/auth/register", json={"email": "other@example.com", "password": "Sup3rSecret"}
    )
    tok = (
        await client.post(
            "/api/auth/login", json={"email": "other@example.com", "password": "Sup3rSecret"}
        )
    ).json()["access_token"]
    rows = (await client.get(BASE, headers={"Authorization": f"Bearer {tok}"})).json()
    assert rows == []
