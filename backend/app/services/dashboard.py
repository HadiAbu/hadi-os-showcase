"""Dashboard aggregation (REQ-19). Timestamp arithmetic only — no LLM call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import client

_CHANGE_LIMIT = 20


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _objective_progress(user_id: str) -> list[dict]:
    objectives = await client.db_execute(
        "SELECT id, title, horizon, priority FROM objectives "
        "WHERE user_id = ? AND status = 'active' ORDER BY priority, created_at, id",
        [user_id],
    )
    rows: list[dict] = []
    for obj in objectives:
        actions = await client.db_execute(
            "SELECT status FROM actions WHERE user_id = ? AND objective_id = ?",
            [user_id, obj["id"]],
        )
        total = len(actions)
        done = sum(1 for a in actions if a["status"] == "done")
        open_ = sum(1 for a in actions if a["status"] in ("todo", "doing"))
        rows.append(
            {
                "id": obj["id"],
                "title": obj["title"],
                "horizon": obj["horizon"],
                "priority": obj["priority"],
                "open_actions": open_,
                "total_actions": total,
                "pct_done": round(done / total * 100) if total else 0,
            }
        )
    return rows


async def _count(sql: str, params: list) -> int:
    rows = await client.db_execute(sql, params)
    return int(next(iter(rows[0].values()))) if rows else 0


async def _momentum(user_id: str) -> dict:
    d7, d30 = _days_ago(7), _days_ago(30)
    return {
        "actions_done_7d": await _count(
            "SELECT COUNT(*) c FROM actions WHERE user_id = ? AND status = 'done' "
            "AND completed_at IS NOT NULL AND completed_at >= ?",
            [user_id, d7],
        ),
        "actions_done_30d": await _count(
            "SELECT COUNT(*) c FROM actions WHERE user_id = ? AND status = 'done' "
            "AND completed_at IS NOT NULL AND completed_at >= ?",
            [user_id, d30],
        ),
        "objectives_touched_7d": await _count(
            "SELECT COUNT(*) c FROM objectives WHERE user_id = ? AND updated_at >= ?",
            [user_id, d7],
        ),
        "projects_touched_7d": await _count(
            "SELECT COUNT(*) c FROM projects WHERE user_id = ? AND updated_at >= ?",
            [user_id, d7],
        ),
    }


async def _changed_this_week(user_id: str) -> list[dict]:
    d7 = _days_ago(7)
    items: list[dict] = []

    for row in await client.db_execute(
        "SELECT title, status, updated_at, completed_at FROM objectives "
        "WHERE user_id = ? AND (updated_at >= ? OR completed_at >= ?)",
        [user_id, d7, d7],
    ):
        at = max(row["updated_at"], row["completed_at"] or "")
        items.append({"kind": "objective", "title": row["title"], "at": at, "detail": row["status"]})

    for row in await client.db_execute(
        "SELECT title, status, updated_at, completed_at FROM actions "
        "WHERE user_id = ? AND (updated_at >= ? OR completed_at >= ?)",
        [user_id, d7, d7],
    ):
        at = max(row["updated_at"], row["completed_at"] or "")
        items.append({"kind": "action", "title": row["title"], "at": at, "detail": row["status"]})

    for row in await client.db_execute(
        "SELECT name, status, updated_at FROM projects WHERE user_id = ? AND updated_at >= ?",
        [user_id, d7],
    ):
        items.append(
            {"kind": "project", "title": row["name"], "at": row["updated_at"], "detail": row["status"]}
        )

    items.sort(key=lambda i: i["at"], reverse=True)
    return items[:_CHANGE_LIMIT]


async def build_dashboard(user_id: str) -> dict:
    return {
        "objectives": await _objective_progress(user_id),
        "momentum": await _momentum(user_id),
        "changed_this_week": await _changed_this_week(user_id),
    }
