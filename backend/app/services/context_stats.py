"""``stats(user_id)`` — counts / growth / staleness for the context store.

See ``.kiro/specs/phase-2-visual-and-graph/design.md`` § 6. Timestamp arithmetic
only, no LLM call.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import client

STALE_DAYS = 45
GROWTH_DAYS = 30


def _days_ago_iso(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


async def stats(user_id: str) -> dict[str, Any]:
    by_status = await client.db_execute(
        "SELECT status, COUNT(*) c FROM context_entries WHERE user_id = ? GROUP BY status",
        [user_id],
    )
    by_category = await client.db_execute(
        "SELECT category, COUNT(*) c FROM context_entries "
        "WHERE user_id = ? AND status != 'archived' GROUP BY category",
        [user_id],
    )

    # growth: for each of the last 30 days, how many non-archived entries existed
    # by that day's end. Approximate — archives carry no archived-at timestamp,
    # so a since-archived entry drops off the whole curve rather than at its
    # archive date.
    entries = await client.db_execute(
        "SELECT created_at, status FROM context_entries WHERE user_id = ?", [user_id]
    )
    today = datetime.now(timezone.utc).date()
    growth: list[dict[str, Any]] = []
    for offset in range(GROWTH_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_end = day.strftime("%Y-%m-%dT23:59:59.999999Z")
        active = sum(
            1
            for e in entries
            if e["status"] != "archived" and (e["created_at"] or "") <= day_end
        )
        growth.append({"day": day.isoformat(), "active": active})

    stale_rows = await client.db_execute(
        "SELECT COUNT(*) c FROM context_entries "
        "WHERE user_id = ? AND status = 'active' AND updated_at < ?",
        [user_id, _days_ago_iso(STALE_DAYS)],
    )

    return {
        "by_status": [{"status": r["status"], "count": r["c"]} for r in by_status],
        "by_category": [{"category": r["category"], "count": r["c"]} for r in by_category],
        "growth": growth,
        "stale": int(stale_rows[0]["c"]) if stale_rows else 0,
    }
