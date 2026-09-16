"""Persistence for ``projects`` (REQ-14)."""

from __future__ import annotations

import json
from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso

_JSON_FIELDS = ("tech",)


def _as_str_list(value: object) -> list[str]:
    """Coerce a tech value to a list of strings — a misbehaving tool call can
    send a bare string or null instead of an array."""
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _hydrate(row: dict) -> dict:
    row = dict(row)
    for field in _JSON_FIELDS:
        raw = row.get(field)
        try:
            row[field] = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            row[field] = []
    return row


async def list_projects(user_id: str, *, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM projects WHERE user_id = ?"
    params: list[Any] = [user_id]
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY name, id"
    return [_hydrate(r) for r in await client.db_execute(sql, params)]


async def get_project(user_id: str, project_id: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM projects WHERE user_id = ? AND id = ? LIMIT 1", [user_id, project_id]
    )
    return _hydrate(rows[0]) if rows else None


async def project_exists(user_id: str, project_id: str) -> bool:
    rows = await client.db_execute(
        "SELECT 1 FROM projects WHERE user_id = ? AND id = ? LIMIT 1", [user_id, project_id]
    )
    return bool(rows)


async def create_project(user_id: str, data: dict) -> dict:
    project_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO projects "
        "(id, user_id, name, summary, status, tech, repo_path, repo_url, next_steps, notes, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            project_id,
            user_id,
            data["name"],
            data.get("summary", ""),
            data.get("status", "active"),
            json.dumps(_as_str_list(data.get("tech"))),
            data.get("repo_path"),
            data.get("repo_url"),
            data.get("next_steps", ""),
            data.get("notes", ""),
            now,
            now,
        ],
    )
    return await get_project(user_id, project_id)  # type: ignore[return-value]


async def patch_project(user_id: str, project_id: str, fields: dict) -> dict | None:
    current = await get_project(user_id, project_id)
    if current is None:
        return None
    updates = {k: v for k, v in fields.items() if v is not None}
    if not updates:
        return current
    if "tech" in updates:
        updates["tech"] = json.dumps(_as_str_list(updates["tech"]))
    updates["updated_at"] = utcnow_iso()
    cols = ", ".join(f"{c} = ?" for c in updates)
    await client.db_execute(
        f"UPDATE projects SET {cols} WHERE user_id = ? AND id = ?",
        [*updates.values(), user_id, project_id],
    )
    return await get_project(user_id, project_id)
