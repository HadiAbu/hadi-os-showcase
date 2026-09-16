"""Task 0.3 — the patched db_execute round-trips through the in-memory backend."""

from __future__ import annotations

import pytest

from app.db import client
from app.db.client import new_id, normalize_db_url, utcnow_iso


async def test_db_execute_roundtrips():
    await client.db_execute("CREATE TABLE t (id TEXT PRIMARY KEY, n INTEGER)")
    await client.db_execute("INSERT INTO t (id, n) VALUES (?, ?)", ["a", 1])
    await client.db_execute("INSERT INTO t (id, n) VALUES (?, ?)", ["b", 2])

    rows = await client.db_execute("SELECT id, n FROM t ORDER BY n")
    assert rows == [{"id": "a", "n": 1}, {"id": "b", "n": 2}]


async def test_db_execute_returns_empty_list_for_writes():
    await client.db_execute("CREATE TABLE t (id TEXT)")
    result = await client.db_execute("INSERT INTO t (id) VALUES (?)", ["x"])
    assert result == []


def test_new_id_is_unique_uuid():
    a, b = new_id(), new_id()
    assert a != b
    assert len(a) == 36


def test_utcnow_iso_shape_is_sortable():
    a = utcnow_iso()
    b = utcnow_iso()
    assert a.endswith("Z") and "T" in a and "." in a
    assert a <= b  # lexicographic order == chronological order


@pytest.mark.parametrize(
    "raw",
    [
        "libsql://db-org.turso.io",
        "turso://db-org.turso.io",
        "wss://db-org.turso.io",
        "db-org.turso.io",
        " https://db-org.turso.io ",
    ],
)
def test_normalize_db_url_forces_https(raw):
    assert normalize_db_url(raw) == "https://db-org.turso.io"


def test_normalize_db_url_keeps_http():
    assert normalize_db_url("http://localhost:8080") == "http://localhost:8080"
