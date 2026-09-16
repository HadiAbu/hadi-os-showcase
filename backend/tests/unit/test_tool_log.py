"""M3 task 3.2 — tool_invocations writer + entity-touch derivation."""

from __future__ import annotations

import json

from app.db import client
from app.services import tool_log


async def _rows(user_id: str) -> list[dict]:
    return await client.db_execute(
        "SELECT * FROM tool_invocations WHERE user_id = ?", [user_id]
    )


def _by_tool(rows: list[dict]) -> dict[str, dict]:
    return {r["tool_name"]: r for r in rows}


async def test_record_invocations_writes_one_row_per_call(owner_id):
    calls = [
        {"tool_name": "list_projects", "args": {}, "result": "[]", "is_error": False},
        {
            "tool_name": "create_objective",
            "args": {"title": "Ship it", "horizon": "quarter"},
            "result": json.dumps({"id": "obj-1", "title": "Ship it", "status": "active"}),
            "is_error": False,
        },
    ]
    await tool_log.record_invocations("conv-1", owner_id, "msg-1", calls)

    rows = await _rows(owner_id)
    assert {r["tool_name"] for r in rows} == {"list_projects", "create_objective"}
    assert {r["message_id"] for r in rows} == {"msg-1"}
    assert {r["conversation_id"] for r in rows} == {"conv-1"}
    assert json.loads(_by_tool(rows)["create_objective"]["arguments_json"]) == {
        "title": "Ship it",
        "horizon": "quarter",
    }


async def test_is_error_flag_is_persisted(owner_id):
    await tool_log.record_invocations(
        "c",
        owner_id,
        "m",
        [
            {"tool_name": "create_objective", "args": {}, "result": '{"error": "x"}', "is_error": True},
            {"tool_name": "list_projects", "args": {}, "result": "[]", "is_error": False},
        ],
    )
    rows = _by_tool(await _rows(owner_id))
    assert rows["create_objective"]["is_error"] == 1
    assert rows["list_projects"]["is_error"] == 0


async def test_large_values_are_truncated_to_4kb(owner_id):
    big = "x" * 9000
    await tool_log.record_invocations(
        "c",
        owner_id,
        "m",
        [{"tool_name": "upsert_context_entry", "args": {"value": big}, "result": big, "is_error": False}],
    )
    row = (await _rows(owner_id))[0]
    for field in ("arguments_json", "result_json"):
        assert len(row[field]) <= tool_log.VALUE_MAX + 1
        assert row[field].endswith("…")


def test_touches_from_derives_created_and_updated_entities():
    calls = [
        {
            "tool_name": "create_objective",
            "result": json.dumps({"id": "obj-1", "status": "active"}),
            "is_error": False,
        },
        {
            "tool_name": "add_action",
            "result": json.dumps({"id": "act-9", "source": "suggested"}),
            "is_error": False,
        },
        {
            "tool_name": "update_project",
            "result": json.dumps({"id": "proj-3", "status": "paused"}),
            "is_error": False,
        },
    ]
    assert tool_log.touches_from(calls) == [
        ("objective", "obj-1"),
        ("action", "act-9"),
        ("project", "proj-3"),
    ]


def test_touches_from_skips_errors_reads_and_unparseable():
    calls = [
        {"tool_name": "list_objectives", "result": "[]", "is_error": False},  # read-only
        {"tool_name": "create_project", "result": '{"error": "boom"}', "is_error": True},  # errored
        {"tool_name": "update_action", "result": "not json", "is_error": False},  # unparseable
        {"tool_name": "update_style_guide", "result": '{"updated_at": "…"}', "is_error": False},  # no id tool
    ]
    assert tool_log.touches_from(calls) == []
