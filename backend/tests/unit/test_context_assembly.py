"""Task 2.4 — system-prompt assembly (REQ-11, REQ-25)."""

from __future__ import annotations

from app.db import client
from app.db.client import new_id, utcnow_iso
from app.services import style
from app.services.context_assembly import (
    BASE_SYSTEM_PROMPT,
    build_stable_prefix,
    build_system,
)


async def _add_entry(user_id, category, key, value, status="active"):
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO context_entries "
        "(id, user_id, category, key, value, source, pinned, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'manual', 0, ?, ?, ?)",
        [new_id(), user_id, category, key, value, status, now, now],
    )


async def _add_objective(user_id, title, priority=2, status="active"):
    now = utcnow_iso()
    oid = new_id()
    await client.db_execute(
        "INSERT INTO objectives "
        "(id, user_id, title, description, horizon, status, priority, tags, created_at, updated_at) "
        "VALUES (?, ?, ?, '', 'quarter', ?, ?, '[]', ?, ?)",
        [oid, user_id, title, status, priority, now, now],
    )
    return oid


async def _add_action(user_id, objective_id, title, status="todo"):
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO actions "
        "(id, user_id, objective_id, title, status, notes, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, '', 'manual', ?, ?)",
        [new_id(), user_id, objective_id, title, status, now, now],
    )


async def _add_project(user_id, name, status="active"):
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO projects "
        "(id, user_id, name, summary, status, tech, next_steps, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, 'a thing', ?, '[]', 'ship it', '', ?, ?)",
        [new_id(), user_id, name, status, now, now],
    )


async def test_system_is_a_string_with_prefix_and_time(owner_id):
    system = await build_system(owner_id)
    assert isinstance(system, str)
    assert system.startswith(BASE_SYSTEM_PROMPT[:40])
    assert "Current time:" in system


async def test_active_entries_included_proposed_and_archived_excluded(owner_id):
    await _add_entry(owner_id, "identity", "role", "backend engineer", status="active")
    await _add_entry(owner_id, "preference", "editor", "neovim", status="proposed")
    await _add_entry(owner_id, "misc", "old", "stale", status="archived")

    prefix = await build_stable_prefix(owner_id)
    assert "identity/role: backend engineer" in prefix
    assert "neovim" not in prefix
    assert "stale" not in prefix


async def test_writing_style_section_omitted_when_empty_present_when_set(owner_id):
    # the closing tag only appears in the rendered section, not the base prompt
    assert "</writing_style>" not in await build_stable_prefix(owner_id)
    await style.put_style_guide(owner_id, "Short sentences. Dry humour. No exclamation marks.")
    prefix = await build_stable_prefix(owner_id)
    assert "</writing_style>" in prefix
    assert "Dry humour" in prefix


async def test_objectives_show_open_actions_only(owner_id):
    oid = await _add_objective(owner_id, "Ship hadi-os Phase 1", priority=1)
    await _add_action(owner_id, oid, "write the agent loop", status="doing")
    await _add_action(owner_id, oid, "old milestone", status="done")

    prefix = await build_stable_prefix(owner_id)
    assert "[P1] Ship hadi-os Phase 1" in prefix
    assert "write the agent loop" in prefix
    assert "old milestone" not in prefix


async def test_projects_active_and_paused_only(owner_id):
    await _add_project(owner_id, "alpha", status="active")
    await _add_project(owner_id, "beta", status="paused")
    await _add_project(owner_id, "gamma", status="archived")

    prefix = await build_stable_prefix(owner_id)
    assert "alpha (active)" in prefix
    assert "beta (paused)" in prefix
    assert "gamma" not in prefix


async def test_stable_prefix_is_byte_identical_across_calls(owner_id):
    await _add_entry(owner_id, "identity", "role", "engineer")
    oid = await _add_objective(owner_id, "Learn distributed systems")
    await _add_action(owner_id, oid, "read DDIA")
    await _add_project(owner_id, "sentinel")
    await style.put_style_guide(owner_id, "Terse.")

    assert await build_stable_prefix(owner_id) == await build_stable_prefix(owner_id)
