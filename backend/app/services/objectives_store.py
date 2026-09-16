"""Persistence for ``objectives`` and their child ``actions`` (REQ-12, REQ-13).

- ``completed_at`` is set when status becomes ``done`` and cleared when it leaves.
- Objectives are never hard-deleted in Phase 1 (moved to ``dropped``); child
  actions remain reachable by ``objective_id``.
- Agent-tool action creates pass ``source='suggested'``; the UI path uses
  ``source='manual'``.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso
from app.services import projects_store


class ProjectNotOwned(Exception):
    """A write references a ``project_id`` that isn't one of the user's projects."""


def as_str_list(value: object) -> list[str]:
    """Coerce a tags/tech value to a list of strings — a misbehaving tool call
    can send a bare string or null instead of an array."""
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _hydrate_objective(row: dict) -> dict:
    row = dict(row)
    raw = row.get("tags")
    try:
        row["tags"] = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        row["tags"] = []
    return row


def _completion_delta(new_status: str, current_status: str) -> dict:
    if new_status == "done" and current_status != "done":
        return {"completed_at": utcnow_iso()}
    if new_status != "done" and current_status == "done":
        return {"completed_at": None}
    return {}


# --- Objectives -------------------------------------------------


async def list_objectives(
    user_id: str, *, status: str | None = None, tag: str | None = None
) -> list[dict]:
    sql = "SELECT * FROM objectives WHERE user_id = ?"
    params: list[Any] = [user_id]
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY priority, created_at, id"
    rows = [_hydrate_objective(r) for r in await client.db_execute(sql, params)]
    if tag is not None:
        rows = [r for r in rows if tag in r["tags"]]
    return rows


async def get_objective(user_id: str, objective_id: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM objectives WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, objective_id],
    )
    return _hydrate_objective(rows[0]) if rows else None


async def create_objective(user_id: str, data: dict) -> dict:
    project_id = data.get("project_id")
    if project_id and not await projects_store.project_exists(user_id, project_id):
        raise ProjectNotOwned(project_id)

    objective_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO objectives "
        "(id, user_id, title, description, horizon, target_date, status, priority, tags, "
        "project_id, created_at, updated_at, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, NULL)",
        [
            objective_id,
            user_id,
            data["title"],
            data.get("description", ""),
            data["horizon"],
            data.get("target_date"),
            data.get("priority", 2),
            json.dumps(as_str_list(data.get("tags"))),
            project_id,
            now,
            now,
        ],
    )
    return await get_objective(user_id, objective_id)  # type: ignore[return-value]


async def patch_objective(user_id: str, objective_id: str, fields: dict) -> dict | None:
    current = await get_objective(user_id, objective_id)
    if current is None:
        return None

    updates = {k: v for k, v in fields.items() if v is not None}
    if "project_id" in updates and updates["project_id"]:
        if not await projects_store.project_exists(user_id, updates["project_id"]):
            raise ProjectNotOwned(updates["project_id"])

    if "status" in updates:
        updates.update(_completion_delta(updates["status"], current["status"]))
    if "tags" in updates:
        updates["tags"] = json.dumps(as_str_list(updates["tags"]))
    updates["updated_at"] = utcnow_iso()

    cols = ", ".join(f"{c} = ?" for c in updates)
    await client.db_execute(
        f"UPDATE objectives SET {cols} WHERE user_id = ? AND id = ?",
        [*updates.values(), user_id, objective_id],
    )
    return await get_objective(user_id, objective_id)


# --- Actions ---------------------------------------------------


async def list_actions(user_id: str, objective_id: str) -> list[dict]:
    return await client.db_execute(
        "SELECT * FROM actions WHERE user_id = ? AND objective_id = ? ORDER BY created_at, id",
        [user_id, objective_id],
    )


async def get_action(user_id: str, action_id: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM actions WHERE user_id = ? AND id = ? LIMIT 1", [user_id, action_id]
    )
    return rows[0] if rows else None


async def create_action(
    user_id: str,
    objective_id: str,
    title: str,
    *,
    due_date: str | None = None,
    source: str = "manual",
) -> dict | None:
    if await get_objective(user_id, objective_id) is None:
        return None
    action_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO actions "
        "(id, user_id, objective_id, title, status, notes, due_date, source, "
        "created_at, updated_at, completed_at) "
        "VALUES (?, ?, ?, ?, 'todo', '', ?, ?, ?, ?, NULL)",
        [action_id, user_id, objective_id, title, due_date, source, now, now],
    )
    return await get_action(user_id, action_id)


async def patch_action(user_id: str, action_id: str, fields: dict) -> dict | None:
    current = await get_action(user_id, action_id)
    if current is None:
        return None
    updates = {k: v for k, v in fields.items() if v is not None}
    if "status" in updates:
        updates.update(_completion_delta(updates["status"], current["status"]))
    updates["updated_at"] = utcnow_iso()
    cols = ", ".join(f"{c} = ?" for c in updates)
    await client.db_execute(
        f"UPDATE actions SET {cols} WHERE user_id = ? AND id = ?",
        [*updates.values(), user_id, action_id],
    )
    return await get_action(user_id, action_id)
