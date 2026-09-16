"""Turso (libSQL) access.

One entry point: :func:`db_execute`. It returns a list of plain dicts (one per
row) so callers never depend on the libSQL ``ResultSet`` shape and tests can
swap in an in-memory SQLite backend transparently.

Convention: callers do ``from app.db import client`` and call
``client.db_execute(...)`` via the module, so a single monkeypatch of
``app.db.client.db_execute`` in tests covers every caller.

IDs are generated in Python (UUID v4) — see :func:`new_id` — so we never rely on
``last_insert_rowid``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Sequence

from app.core.config import get_settings

if TYPE_CHECKING:
    import libsql_client

_client: "libsql_client.Client | None" = None


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow_iso() -> str:
    # Microsecond precision: rows written within the same second during one
    # request must still sort by insertion order (ids are random UUIDs).
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def normalize_db_url(url: str) -> str:
    """Force the ``https://`` scheme (see .kiro/steering/tech.md).

    Turso hands out URLs under several schemes depending on where you copy from
    (``libsql://``, ``turso://``, ``wss://``, sometimes a bare host); the HTTP
    client only accepts ``http(s)://``.
    """
    url = url.strip()
    if "://" in url:
        scheme, rest = url.split("://", 1)
        return url if scheme in ("http", "https") else "https://" + rest
    return "https://" + url


def get_client() -> "libsql_client.Client":
    global _client
    if _client is None:
        import libsql_client

        settings = get_settings()
        _client = libsql_client.create_client(
            url=normalize_db_url(settings.turso_database_url),
            auth_token=settings.turso_auth_token,
        )
    return _client


async def db_execute(sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    """Run a statement. Returns rows as dicts for SELECTs, ``[]`` otherwise."""
    result = await get_client().execute(sql, list(params) if params else [])
    columns = list(result.columns)
    return [dict(zip(columns, row)) for row in result.rows]


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
