"""Task 5.2 — agent tool impls: user scoping + status/source defaults (REQ-18)."""

from __future__ import annotations

from app.services import agent_tools, context_store, style, users


async def _second_user() -> str:
    u = await users.create_user("other@example.com", "x")
    return u["id"]


async def test_upsert_context_entry_is_proposed_from_chat(owner_id):
    result = await agent_tools._impl_upsert_context_entry(
        owner_id, "preference", "editor", "neovim"
    )
    assert result["status"] == "proposed"
    stored = await context_store._find_by_natural_key(owner_id, "preference", "editor")
    assert stored["source"] == "chat"
    assert stored["status"] == "proposed"


async def test_create_objective_is_active(owner_id):
    result = await agent_tools._impl_create_objective(
        owner_id, title="Ship Phase 1", horizon="quarter"
    )
    assert result["status"] == "active"


async def test_add_action_is_suggested(owner_id):
    obj = await agent_tools._impl_create_objective(
        owner_id, title="Learn Rust", horizon="year"
    )
    action = await agent_tools._impl_add_action(owner_id, obj["id"], "read the book")
    assert action["source"] == "suggested"


async def test_add_action_unknown_objective(owner_id):
    assert (await agent_tools._impl_add_action(owner_id, "nope", "x"))["error"]


async def test_create_project_is_active(owner_id):
    result = await agent_tools._impl_create_project(owner_id, name="sentinel")
    assert result["status"] == "active"


async def test_update_style_guide(owner_id):
    await agent_tools._impl_update_style_guide(owner_id, "Terse. Dry.")
    assert (await style.get_style_guide(owner_id))["guide_md"] == "Terse. Dry."


async def test_tools_are_user_scoped(owner_id):
    other = await _second_user()
    await agent_tools._impl_upsert_context_entry(owner_id, "misc", "secret", "mine")

    assert await agent_tools._impl_get_context(other) == []
    # cross-user archive is a no-op
    entry = await context_store._find_by_natural_key(owner_id, "misc", "secret")
    assert (await agent_tools._impl_archive_context_entry(other, entry["id"]))["ok"] is False


async def test_tool_specs_are_thirteen_openai_functions(owner_id):
    assert len(agent_tools.TOOL_SPECS) == 13
    assert all(t["type"] == "function" and "name" in t["function"] for t in agent_tools.TOOL_SPECS)
    assert "get_context" in agent_tools.TOOL_NAMES


def test_as_str_list_coerces_bad_tool_input():
    from app.services.objectives_store import as_str_list

    assert as_str_list(["a", "b"]) == ["a", "b"]
    assert as_str_list("skill") == ["skill"]  # model sent a bare string
    assert as_str_list(None) == []
    assert as_str_list("") == []
    assert as_str_list([1, 2]) == ["1", "2"]


async def test_create_objective_tolerates_string_tags(owner_id):
    from app.services import objectives_store

    out = await agent_tools.dispatch(
        owner_id, "create_objective",
        {"title": "Learn X", "horizon": "year", "tags": "skill"},
    )
    oid = __import__("json").loads(out)["id"]
    obj = await objectives_store.get_objective(owner_id, oid)
    assert obj["tags"] == ["skill"]  # stored as a list, not the raw string


async def test_dispatch_routes_and_returns_json(owner_id):
    out = await agent_tools.dispatch(
        owner_id, "upsert_context_entry",
        {"category": "preference", "key": "editor", "value": "neovim"},
    )
    assert '"status": "proposed"' in out

    obj = await agent_tools.dispatch(
        owner_id, "create_objective", {"title": "Ship it", "horizon": "quarter"}
    )
    assert '"status": "active"' in obj

    unknown = await agent_tools.dispatch(owner_id, "no_such_tool", {})
    assert "unknown tool" in unknown

    missing = await agent_tools.dispatch(owner_id, "archive_context_entry", {})
    assert "missing argument" in missing
