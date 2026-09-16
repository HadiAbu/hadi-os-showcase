"""M6 task 6.2 — context_stats.stats()."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import client
from app.db.client import new_id
from app.services import context_stats


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


async def _entry(
    user_id: str,
    category: str,
    key: str,
    *,
    status: str = "active",
    created: float = 1,
    updated: float | None = None,
) -> None:
    await client.db_execute(
        "INSERT INTO context_entries "
        "(id, user_id, category, key, value, source, pinned, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'v', 'manual', 0, ?, ?, ?)",
        [
            new_id(),
            user_id,
            category,
            key,
            status,
            _iso(created),
            _iso(updated if updated is not None else created),
        ],
    )


async def test_by_status_and_by_category_counts(owner_id):
    await _entry(owner_id, "identity", "a", status="active")
    await _entry(owner_id, "identity", "b", status="active")
    await _entry(owner_id, "preference", "c", status="proposed")
    await _entry(owner_id, "misc", "d", status="archived")

    out = await context_stats.stats(owner_id)
    by_status = {s["status"]: s["count"] for s in out["by_status"]}
    assert by_status == {"active": 2, "proposed": 1, "archived": 1}

    by_category = {c["category"]: c["count"] for c in out["by_category"]}
    # archived excluded from the category breakdown
    assert by_category == {"identity": 2, "preference": 1}


async def test_stale_cutoff_at_45_days(owner_id):
    await _entry(owner_id, "identity", "fresh", status="active", created=60, updated=40)
    await _entry(owner_id, "identity", "stale", status="active", created=60, updated=50)
    await _entry(owner_id, "identity", "old-but-archived", status="archived", created=90, updated=90)

    out = await context_stats.stats(owner_id)
    assert out["stale"] == 1


async def test_growth_has_thirty_points_and_is_monotonic(owner_id):
    await _entry(owner_id, "identity", "old", status="active", created=20)
    await _entry(owner_id, "identity", "recent", status="active", created=2)

    growth = (await context_stats.stats(owner_id))["growth"]
    assert len(growth) == 30
    actives = [p["active"] for p in growth]
    assert actives == sorted(actives)  # non-decreasing
    assert actives[0] == 0 and actives[-1] == 2  # nothing 29d ago, both by today
