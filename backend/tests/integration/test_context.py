"""Tasks 2.1-2.3 — context entries CRUD, review queue, style guide (REQ-8/9/10)."""

from __future__ import annotations

BASE = "/api/context"


# --- REQ-8 entries -------------------------------------------------


async def test_create_list_and_defaults(auth_client):
    r = await auth_client.post(
        f"{BASE}/entries", json={"category": "identity", "key": "role", "value": "engineer"}
    )
    assert r.status_code == 201
    entry = r.json()
    assert entry["status"] == "active"
    assert entry["source"] == "manual"
    assert entry["pinned"] is False

    rows = (await auth_client.get(f"{BASE}/entries")).json()
    assert [e["key"] for e in rows] == ["role"]


async def test_create_is_upsert_on_natural_key(auth_client):
    first = await auth_client.post(
        f"{BASE}/entries", json={"category": "identity", "key": "role", "value": "engineer"}
    )
    second = await auth_client.post(
        f"{BASE}/entries",
        json={"category": "identity", "key": "role", "value": "staff engineer"},
    )
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    rows = (await auth_client.get(f"{BASE}/entries")).json()
    assert len(rows) == 1
    assert rows[0]["value"] == "staff engineer"


async def test_patch_and_archive(auth_client):
    entry = (
        await auth_client.post(
            f"{BASE}/entries",
            json={"category": "preference", "key": "editor", "value": "vscode"},
        )
    ).json()

    patched = await auth_client.patch(
        f"{BASE}/entries/{entry['id']}", json={"value": "neovim", "pinned": True}
    )
    assert patched.status_code == 200
    assert patched.json()["value"] == "neovim"
    assert patched.json()["pinned"] is True

    archived = await auth_client.post(f"{BASE}/entries/{entry['id']}/archive")
    assert archived.status_code == 200 and archived.json()["status"] == "archived"

    assert (await auth_client.get(f"{BASE}/entries?status=active")).json() == []


async def test_patch_missing_entry_404(auth_client):
    assert (await auth_client.patch(f"{BASE}/entries/nope", json={"value": "x"})).status_code == 404


async def test_proposed_create_does_not_clobber_confirmed_entry(auth_client):
    """A later proposal on the same (category, key) must leave the active entry alone."""
    from app.services import context_store

    me = (await auth_client.get("/api/auth/me")).json()
    await context_store.create_entry(
        me["id"], "identity", "role", "full-stack engineer", source="onboarding", status="active"
    )
    # enrichment/agent proposes a different value for the same key
    result = await context_store.create_entry(
        me["id"], "identity", "role", "Software Engineer", source="chat", status="proposed"
    )
    assert result["status"] == "active"
    assert result["value"] == "full-stack engineer"
    assert (await auth_client.get(f"{BASE}/review")).json() == []


async def test_entries_are_user_scoped(auth_client, client):
    await auth_client.post(
        f"{BASE}/entries", json={"category": "misc", "key": "secret", "value": "mine"}
    )
    # a second, different user
    await client.post(
        "/api/auth/register", json={"email": "other@example.com", "password": "Sup3rSecret"}
    )
    tok = (
        await client.post(
            "/api/auth/login", json={"email": "other@example.com", "password": "Sup3rSecret"}
        )
    ).json()["access_token"]
    rows = (
        await client.get(f"{BASE}/entries", headers={"Authorization": f"Bearer {tok}"})
    ).json()
    assert rows == []


async def test_requires_auth(client):
    assert (await client.get(f"{BASE}/entries")).status_code == 401


# --- REQ-9 review queue -----------------------------------------


async def _make_proposed(auth_client) -> str:
    """No agent tools yet — simulate a proposed entry via create + patch to proposed
    is not exposed; instead post then archive+re-add is awkward. Use the entries
    endpoint then flip status directly through the DB-less path: create, then the
    review flow. Simplest: create active, then discard->archived is not proposed.
    So we insert through the store to get a proposed row."""
    from app.services import context_store

    me = (await auth_client.get("/api/auth/me")).json()
    entry = await context_store.create_entry(
        me["id"], "goal_context", "focus", "ship phase 1", source="chat", status="proposed"
    )
    return entry["id"]


async def test_review_lists_only_proposed_and_approve_activates(auth_client):
    entry_id = await _make_proposed(auth_client)

    review = (await auth_client.get(f"{BASE}/review")).json()
    assert [e["id"] for e in review] == [entry_id]
    # proposed entries are not in the active set
    assert (await auth_client.get(f"{BASE}/entries?status=active")).json() == []

    approved = await auth_client.post(f"{BASE}/review/{entry_id}/approve", json={})
    assert approved.status_code == 200 and approved.json()["status"] == "active"
    assert (await auth_client.get(f"{BASE}/review")).json() == []


async def test_edit_then_approve_persists_value(auth_client):
    entry_id = await _make_proposed(auth_client)
    approved = await auth_client.post(
        f"{BASE}/review/{entry_id}/approve", json={"value": "ship phase 1 by Friday"}
    )
    assert approved.json()["value"] == "ship phase 1 by Friday"
    assert approved.json()["status"] == "active"


async def test_discard_archives(auth_client):
    entry_id = await _make_proposed(auth_client)
    discarded = await auth_client.post(f"{BASE}/review/{entry_id}/discard")
    assert discarded.status_code == 200 and discarded.json()["status"] == "archived"


# --- REQ-10 style guide + samples --------------------------


async def test_style_guide_default_then_put(auth_client):
    got = await auth_client.get(f"{BASE}/style-guide")
    assert got.status_code == 200
    assert got.json() == {"guide_md": "", "updated_at": None}

    put = await auth_client.put(f"{BASE}/style-guide", json={"guide_md": "Terse. Dry."})
    assert put.status_code == 200
    assert put.json()["guide_md"] == "Terse. Dry."
    assert put.json()["updated_at"] is not None

    assert (await auth_client.get(f"{BASE}/style-guide")).json()["guide_md"] == "Terse. Dry."


async def test_style_samples_crud(auth_client):
    created = await auth_client.post(
        f"{BASE}/style-samples", json={"text": "hey — quick one:", "label": "slack"}
    )
    assert created.status_code == 201
    sample_id = created.json()["id"]

    listed = (await auth_client.get(f"{BASE}/style-samples")).json()
    assert [s["id"] for s in listed] == [sample_id]

    deleted = await auth_client.delete(f"{BASE}/style-samples/{sample_id}")
    assert deleted.status_code == 204
    assert (await auth_client.get(f"{BASE}/style-samples")).json() == []
    assert (await auth_client.delete(f"{BASE}/style-samples/{sample_id}")).status_code == 404
