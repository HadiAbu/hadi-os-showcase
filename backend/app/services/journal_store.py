"""Persistence for ``journal_entries`` (Phase 2.5, REQ-1/2/12).

Mirrors ``projects_store`` / ``objectives_store``. The two ``linked_*`` fields
must reference rows the user owns. Style-sample mirroring for long entries is
added in J1 (``_sync_style_sample``), not here.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso
from app.services import objectives_store, projects_store, style
from app.services.objectives_store import as_str_list

_LINK_FIELDS = ("linked_objective_id", "linked_project_id")

# An entry this long (trimmed) with learn_from_style set is mirrored into
# style_samples so the writing-style model tracks what the owner actually writes.
STYLE_SAMPLE_MIN_CHARS = 200


def _sample_label(entry_id: str) -> str:
    return f"journal:{entry_id}"


async def _sync_style_sample(entry: dict) -> None:
    label = _sample_label(entry["id"])
    body = (entry.get("body") or "").strip()
    if entry.get("learn_from_style") and len(body) >= STYLE_SAMPLE_MIN_CHARS:
        await style.upsert_labelled_sample(entry["user_id"], label, entry["body"])
    else:
        await style.delete_labelled_sample(entry["user_id"], label)


class LinkNotOwned(Exception):
    """A journal entry references a linked objective/project the user doesn't own."""


def _hydrate(row: dict) -> dict:
    row = dict(row)
    raw = row.get("tags")
    try:
        row["tags"] = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        row["tags"] = []
    row["learn_from_style"] = bool(row.get("learn_from_style"))
    return row


async def _check_links(user_id: str, data: dict) -> None:
    oid = data.get("linked_objective_id")
    if oid and await objectives_store.get_objective(user_id, oid) is None:
        raise LinkNotOwned(f"objective:{oid}")
    pid = data.get("linked_project_id")
    if pid and not await projects_store.project_exists(user_id, pid):
        raise LinkNotOwned(f"project:{pid}")


async def list_entries(
    user_id: str, *, objective_id: str | None = None, project_id: str | None = None
) -> list[dict]:
    sql = "SELECT * FROM journal_entries WHERE user_id = ?"
    params: list[Any] = [user_id]
    if objective_id:
        sql += " AND linked_objective_id = ?"
        params.append(objective_id)
    if project_id:
        sql += " AND linked_project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC, id"
    return [_hydrate(r) for r in await client.db_execute(sql, params)]


async def get_entry(user_id: str, entry_id: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM journal_entries WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, entry_id],
    )
    return _hydrate(rows[0]) if rows else None


async def create_entry(user_id: str, data: dict) -> dict:
    await _check_links(user_id, data)
    entry_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO journal_entries "
        "(id, user_id, title, body, mood, tags, linked_objective_id, linked_project_id, "
        "learn_from_style, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            entry_id,
            user_id,
            data.get("title", ""),
            data.get("body", ""),
            data.get("mood", "") or "",
            json.dumps(as_str_list(data.get("tags"))),
            data.get("linked_objective_id") or None,
            data.get("linked_project_id") or None,
            1 if data.get("learn_from_style", True) else 0,
            now,
            now,
        ],
    )
    entry = await get_entry(user_id, entry_id)
    assert entry is not None
    await _sync_style_sample(entry)
    return entry


async def patch_entry(user_id: str, entry_id: str, fields: dict) -> dict | None:
    current = await get_entry(user_id, entry_id)
    if current is None:
        return None
    await _check_links(user_id, fields)

    updates: dict[str, Any] = {}
    for key, value in fields.items():
        if key in _LINK_FIELDS:
            updates[key] = value or None  # "" / None clears the link
        elif key == "tags" and value is not None:
            updates[key] = json.dumps(as_str_list(value))
        elif key == "learn_from_style" and value is not None:
            updates[key] = 1 if value else 0
        elif value is not None:
            updates[key] = value

    if not updates:
        return current
    updates["updated_at"] = utcnow_iso()
    cols = ", ".join(f"{c} = ?" for c in updates)
    await client.db_execute(
        f"UPDATE journal_entries SET {cols} WHERE user_id = ? AND id = ?",
        [*updates.values(), user_id, entry_id],
    )
    entry = await get_entry(user_id, entry_id)
    assert entry is not None
    await _sync_style_sample(entry)
    return entry


async def delete_entry(user_id: str, entry_id: str) -> bool:
    if await get_entry(user_id, entry_id) is None:
        return False
    await client.db_execute(
        "DELETE FROM journal_entries WHERE user_id = ? AND id = ?", [user_id, entry_id]
    )
    await style.delete_labelled_sample(user_id, _sample_label(entry_id))
    return True
