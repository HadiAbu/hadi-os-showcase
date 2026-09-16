"""M4 task 4.1 / 4.2 — /api/graph + /api/graph/links routes (REQ-5, REQ-6, REQ-14)."""

from __future__ import annotations

import pytest

GRAPH = "/api/graph"
LINKS = "/api/graph/links"

A = {"email": "ga@example.com", "password": "Sup3rSecret"}
B = {"email": "gb@example.com", "password": "Sup3rSecret"}


async def _token(client, creds) -> str:
    await client.post("/api/auth/register", json=creds)
    return (await client.post("/api/auth/login", json=creds)).json()["access_token"]


@pytest.fixture
async def two_users(client):
    a = await _token(client, A)
    b = await _token(client, B)
    return {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}


async def test_graph_reflects_seeded_rows(auth_client):
    oid = (
        await auth_client.post(
            "/api/objectives", json={"title": "Ship it", "horizon": "quarter"}
        )
    ).json()["id"]
    pid = (await auth_client.post("/api/projects", json={"name": "hadi-os"})).json()["id"]
    await auth_client.patch(f"/api/objectives/{oid}", json={"project_id": pid})

    body = (await auth_client.get(GRAPH)).json()
    ids = {n["id"] for n in body["nodes"]}
    assert {f"objective:{oid}", f"project:{pid}"} <= ids
    assert {"source": f"objective:{oid}", "target": f"project:{pid}", "kind": "for_project"} in body[
        "links"
    ]
    assert body["truncated"] is False
    # every link endpoint is a node
    for link_ in body["links"]:
        assert link_["source"] in ids and link_["target"] in ids


async def test_graph_serialises_journal_nodes(auth_client):
    oid = (
        await auth_client.post("/api/objectives", json={"title": "O", "horizon": "year"})
    ).json()["id"]
    eid = (
        await auth_client.post(
            "/api/journal", json={"body": "a real entry", "linked_objective_id": oid}
        )
    ).json()["id"]

    body = (await auth_client.get(GRAPH)).json()  # 500 here if EntityType lacks 'journal'
    node = next(n for n in body["nodes"] if n["id"] == f"journal:{eid}")
    assert node["type"] == "journal"
    assert {
        "source": f"journal:{eid}",
        "target": f"objective:{oid}",
        "kind": "mentions",
    } in body["links"]


async def test_link_crud_roundtrip(auth_client):
    oid = (
        await auth_client.post("/api/objectives", json={"title": "O", "horizon": "year"})
    ).json()["id"]
    pid = (await auth_client.post("/api/projects", json={"name": "P"})).json()["id"]

    created = await auth_client.post(
        LINKS,
        json={"from_type": "objective", "from_id": oid, "to_type": "project", "to_id": pid},
    )
    assert created.status_code == 201
    link_id = created.json()["id"]
    assert created.json()["kind"] == "related"

    listed = (await auth_client.get(LINKS)).json()
    assert [link_["id"] for link_ in listed] == [link_id]

    # the explicit edge shows up in the graph
    graph_links_ = (await auth_client.get(GRAPH)).json()["links"]
    assert any(link_["kind"] == "related" for link_ in graph_links_)

    assert (await auth_client.delete(f"{LINKS}/{link_id}")).status_code == 204
    assert (await auth_client.get(LINKS)).json() == []
    assert (await auth_client.delete(f"{LINKS}/{link_id}")).status_code == 404


async def test_create_link_unknown_endpoint_is_422(auth_client):
    oid = (
        await auth_client.post("/api/objectives", json={"title": "O", "horizon": "year"})
    ).json()["id"]
    r = await auth_client.post(
        LINKS,
        json={
            "from_type": "objective",
            "from_id": oid,
            "to_type": "project",
            "to_id": "does-not-exist",
        },
    )
    assert r.status_code == 422


async def test_links_are_user_scoped(client, two_users):
    a_hdr, b_hdr = two_users
    oid = (
        await client.post(
            "/api/objectives", json={"title": "A", "horizon": "year"}, headers=a_hdr
        )
    ).json()["id"]
    pid = (
        await client.post("/api/projects", json={"name": "A-proj"}, headers=a_hdr)
    ).json()["id"]
    link_id = (
        await client.post(
            LINKS,
            json={"from_type": "objective", "from_id": oid, "to_type": "project", "to_id": pid},
            headers=a_hdr,
        )
    ).json()["id"]

    # B sees nothing and cannot delete A's link or reference A's entities
    assert (await client.get(LINKS, headers=b_hdr)).json() == []
    assert (await client.get(GRAPH, headers=b_hdr)).json()["nodes"] == []
    assert (await client.delete(f"{LINKS}/{link_id}", headers=b_hdr)).status_code == 404
    assert (
        await client.post(
            LINKS,
            json={"from_type": "objective", "from_id": oid, "to_type": "project", "to_id": pid},
            headers=b_hdr,
        )
    ).status_code == 422


@pytest.mark.parametrize("path", [GRAPH, LINKS])
async def test_requires_auth(client, path):
    assert (await client.get(path)).status_code == 401
