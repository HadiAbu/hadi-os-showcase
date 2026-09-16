"""Task 1.1 — every table is created on startup; re-running migrations is a no-op."""

from __future__ import annotations

from app.db import client
from app.db.migrations import run_migrations

EXPECTED_TABLES = {
    "users",
    "refresh_tokens",
    "context_entries",
    "style_samples",
    "style_guide",
    "objectives",
    "actions",
    "projects",
    "conversations",
    "messages",
    "onboarding_responses",
    "onboarding_state",
    "focus_snapshots",
    "tool_invocations",
    "entity_links",
    "journal_entries",
    "reflections",
}


async def _table_names() -> set[str]:
    rows = await client.db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {r["name"] for r in rows}


async def test_all_tables_created():
    # conftest already ran run_migrations() once
    assert EXPECTED_TABLES.issubset(await _table_names())


async def test_rerun_is_idempotent():
    before = await _table_names()
    await run_migrations()
    await run_migrations()
    assert await _table_names() == before
