"""Persistence for ``context_entries`` (REQ-8, REQ-9).

Create is an upsert on ``(user_id, category, key)`` — never a duplicate row.
Agent-tool creates pass ``status="proposed"``; UI / onboarding creates use the
default ``status="active"``.
"""

from __future__ import annotations

from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso


class EntryConflict(Exception):
    """A patch would collide with another (user_id, category, key)."""


async def list_entries(
    user_id: str, *, category: str | None = None, status: str | None = None
) -> list[dict]:
    sql = "SELECT * FROM context_entries WHERE user_id = ?"
    params: list[Any] = [user_id]
    if category is not None:
        sql += " AND category = ?"
        params.append(category)
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY category, key"
    return await client.db_execute(sql, params)


async def list_review(user_id: str) -> list[dict]:
    return await list_entries(user_id, status="proposed")


async def get_entry(user_id: str, entry_id: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM context_entries WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, entry_id],
    )
    return rows[0] if rows else None


async def _find_by_natural_key(
    user_id: str, category: str, key: str
) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM context_entries WHERE user_id = ? AND category = ? AND key = ? LIMIT 1",
        [user_id, category, key],
    )
    return rows[0] if rows else None


async def create_entry(
    user_id: str,
    category: str,
    key: str,
    value: str,
    *,
    pinned: bool = False,
    source: str = "manual",
    status: str = "active",
) -> dict:
    now = utcnow_iso()
    existing = await _find_by_natural_key(user_id, category, key)
    if existing is not None:
        # A proposal (agent tool, onboarding enrichment) must never overwrite a
        # fact the owner has already confirmed.
        if status == "proposed" and existing["status"] == "active":
            return existing
        await client.db_execute(
            "UPDATE context_entries SET value = ?, pinned = ?, status = ?, source = ?, "
            "updated_at = ? WHERE id = ?",
            [value, 1 if pinned else 0, status, source, now, existing["id"]],
        )
        return await get_entry(user_id, existing["id"])  # type: ignore[return-value]

    entry_id = new_id()
    await client.db_execute(
        "INSERT INTO context_entries "
        "(id, user_id, category, key, value, source, pinned, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [entry_id, user_id, category, key, value, source, 1 if pinned else 0, status, now, now],
    )
    return await get_entry(user_id, entry_id)  # type: ignore[return-value]


async def patch_entry(user_id: str, entry_id: str, **fields: Any) -> dict | None:
    current = await get_entry(user_id, entry_id)
    if current is None:
        return None

    updates = {k: v for k, v in fields.items() if v is not None}
    if not updates:
        return current

    new_category = updates.get("category", current["category"])
    new_key = updates.get("key", current["key"])
    if (new_category, new_key) != (current["category"], current["key"]):
        clash = await _find_by_natural_key(user_id, new_category, new_key)
        if clash is not None and clash["id"] != entry_id:
            raise EntryConflict(f"{new_category}/{new_key}")

    if "pinned" in updates:
        updates["pinned"] = 1 if updates["pinned"] else 0
    updates["updated_at"] = utcnow_iso()

    cols = ", ".join(f"{c} = ?" for c in updates)
    await client.db_execute(
        f"UPDATE context_entries SET {cols} WHERE user_id = ? AND id = ?",
        [*updates.values(), user_id, entry_id],
    )
    return await get_entry(user_id, entry_id)


async def set_status(user_id: str, entry_id: str, status: str) -> dict | None:
    current = await get_entry(user_id, entry_id)
    if current is None:
        return None
    await client.db_execute(
        "UPDATE context_entries SET status = ?, updated_at = ? WHERE user_id = ? AND id = ?",
        [status, utcnow_iso(), user_id, entry_id],
    )
    return await get_entry(user_id, entry_id)
