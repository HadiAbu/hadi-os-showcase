"""Test harness.

- Sets placeholder env vars *before* ``app.core.config`` is imported, so the app
  is importable without a real ``.env``.
- Replaces ``app.db.client.db_execute`` with an in-memory SQLite implementation
  (same ``list[dict]`` contract) for the duration of each test. No test touches
  the network.
"""

from __future__ import annotations

import os

os.environ.setdefault("TURSO_DATABASE_URL", "https://test.turso.io")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from typing import Any, AsyncIterator, Sequence  # noqa: E402

import aiosqlite  # noqa: E402
import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.db import client as db_client  # noqa: E402
from app.db.migrations import run_migrations  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def db(monkeypatch):
    """In-memory SQLite standing in for Turso, with the real schema applied."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")

    async def _execute(sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        cur = await conn.execute(sql, tuple(params) if params else ())
        if cur.description is not None:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
        await conn.commit()
        return []

    monkeypatch.setattr(db_client, "db_execute", _execute)
    await run_migrations()
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """ASGI test client. The autouse ``db`` fixture has already patched the DB."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


OWNER = {"email": "owner@example.com", "password": "Sup3rSecret"}


@pytest_asyncio.fixture
async def auth_client(client: httpx.AsyncClient) -> httpx.AsyncClient:
    """A test client already registered + logged in as a single owner."""
    await client.post("/api/auth/register", json=OWNER)
    r = await client.post("/api/auth/login", json=OWNER)
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client


@pytest_asyncio.fixture
async def owner_id() -> str:
    """Create a user row directly (no HTTP) and return its id, for unit tests."""
    from app.services import users

    user = await users.create_user("owner@example.com", "x")
    return user["id"]
