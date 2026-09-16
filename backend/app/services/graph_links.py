"""CRUD for ``entity_links`` — the user-drawn edges on the knowledge graph.

Both endpoints of a link must be rows the user owns; :func:`create_link` raises
:class:`UnknownEntity` otherwise (the route maps it to 422). Create is
idempotent on the natural key ``(user, from, to, kind)``.
"""

from __future__ import annotations

from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso

_TABLE_FOR_TYPE = {
    "objective": "objectives",
    "action": "actions",
    "project": "projects",
    "context": "context_entries",
    "conversation": "conversations",
}


class UnknownEntity(Exception):
    """A link endpoint is not one of the user's rows."""


async def _owns(user_id: str, entity_type: str, entity_id: str) -> bool:
    table = _TABLE_FOR_TYPE.get(entity_type)
    if table is None:
        return False
    rows = await client.db_execute(
        f"SELECT 1 FROM {table} WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, entity_id],
    )
    return bool(rows)


async def list_links(user_id: str) -> list[dict]:
    return await client.db_execute(
        "SELECT * FROM entity_links WHERE user_id = ? ORDER BY created_at, id",
        [user_id],
    )


async def _find(user_id: str, d: dict[str, Any]) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM entity_links WHERE user_id = ? AND from_type = ? AND from_id = ? "
        "AND to_type = ? AND to_id = ? AND kind = ? LIMIT 1",
        [user_id, d["from_type"], d["from_id"], d["to_type"], d["to_id"], d["kind"]],
    )
    return rows[0] if rows else None


async def create_link(user_id: str, data: dict[str, Any]) -> dict:
    for entity_type, entity_id in (
        (data["from_type"], data["from_id"]),
        (data["to_type"], data["to_id"]),
    ):
        if not await _owns(user_id, entity_type, entity_id):
            raise UnknownEntity(f"{entity_type}:{entity_id}")

    existing = await _find(user_id, data)
    if existing is not None:
        return existing

    link_id = new_id()
    await client.db_execute(
        "INSERT INTO entity_links "
        "(id, user_id, from_type, from_id, to_type, to_id, kind, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            link_id,
            user_id,
            data["from_type"],
            data["from_id"],
            data["to_type"],
            data["to_id"],
            data["kind"],
            utcnow_iso(),
        ],
    )
    rows = await client.db_execute("SELECT * FROM entity_links WHERE id = ?", [link_id])
    return rows[0]


async def delete_link(user_id: str, link_id: str) -> bool:
    rows = await client.db_execute(
        "SELECT 1 FROM entity_links WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, link_id],
    )
    if not rows:
        return False
    await client.db_execute(
        "DELETE FROM entity_links WHERE user_id = ? AND id = ?", [user_id, link_id]
    )
    return True
