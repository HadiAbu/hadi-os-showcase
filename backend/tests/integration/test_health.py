"""Task 0.1 — the app boots and serves /health."""

from __future__ import annotations

import httpx
from httpx import ASGITransport

from app.main import app


async def test_health_ok():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
