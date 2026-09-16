"""Integration test for the public-showcase demo seed script."""

from __future__ import annotations

import httpx

from app.scripts import seed_demo


async def test_seed_demo_creates_full_demo_dataset(client: httpx.AsyncClient) -> None:
    await seed_demo.run()

    login = await client.post(
        "/api/auth/login",
        json={"email": seed_demo.DEMO_EMAIL, "password": seed_demo.DEMO_PASSWORD},
    )
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    objectives = await client.get("/api/objectives")
    assert objectives.status_code == 200
    assert len(objectives.json()) == 4

    projects = await client.get("/api/projects")
    assert projects.status_code == 200
    assert len(projects.json()) == 5

    journal = await client.get("/api/journal")
    assert journal.status_code == 200
    assert len(journal.json()) == 6

    reflections = await client.get("/api/reflections")
    assert reflections.status_code == 200
    assert len(reflections.json()) == 3


async def test_seed_demo_is_idempotent(client: httpx.AsyncClient) -> None:
    await seed_demo.run()
    await seed_demo.run()

    login = await client.post(
        "/api/auth/login",
        json={"email": seed_demo.DEMO_EMAIL, "password": seed_demo.DEMO_PASSWORD},
    )
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    objectives = await client.get("/api/objectives")
    assert len(objectives.json()) == 4  # not 8 — re-run replaces, doesn't duplicate
