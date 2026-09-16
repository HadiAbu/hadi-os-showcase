"""Cached "focus now" snapshot (REQ-20).

One LLM call per refresh; the result is stored and served until the caller asks
for a new one. A snapshot older than 24h (or absent) is reported ``stale``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.db import client
from app.db.client import new_id, utcnow_iso
from app.services import llm_client

STALE_AFTER_HOURS = 24

_SYSTEM = (
    "You are hadi-os, a personal assistant. Given the owner's current objectives "
    "and projects, write a short 'what to focus on now' note in markdown: 2-4 "
    "concrete, ranked suggestions weighing priority, horizon urgency, and "
    "staleness. Plain and direct, no preamble, 120 words max."
)


def _is_stale(created_at: str | None) -> bool:
    if not created_at:
        return True
    try:
        made = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - made > timedelta(hours=STALE_AFTER_HOURS)


async def get_focus(user_id: str) -> dict:
    rows = await client.db_execute(
        "SELECT content_md, created_at FROM focus_snapshots WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        [user_id],
    )
    if not rows:
        return {"content_md": None, "created_at": None, "stale": True}
    row = rows[0]
    return {
        "content_md": row["content_md"],
        "created_at": row["created_at"],
        "stale": _is_stale(row["created_at"]),
    }


async def _current_state(user_id: str) -> dict:
    objectives = await client.db_execute(
        "SELECT title, horizon, priority, status FROM objectives "
        "WHERE user_id = ? AND status IN ('active', 'paused') ORDER BY priority, created_at",
        [user_id],
    )
    projects = await client.db_execute(
        "SELECT name, status, summary, next_steps FROM projects "
        "WHERE user_id = ? AND status IN ('active', 'paused') ORDER BY name",
        [user_id],
    )
    return {"objectives": objectives, "projects": projects}


async def refresh_focus(user_id: str) -> dict:
    state = await _current_state(user_id)
    content = await llm_client.one_shot(
        system=_SYSTEM, user=json.dumps(state, default=str), max_tokens=1200
    )
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO focus_snapshots (id, user_id, content_md, based_on_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [new_id(), user_id, content, json.dumps(state, default=str), now],
    )
    return {"content_md": content, "created_at": now, "stale": False}
