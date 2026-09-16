"""``tool_invocations`` persistence + entity-touch derivation.

See ``.kiro/specs/phase-2-visual-and-graph/design.md`` § 3. ``run_turn`` collects
a ``{tool_name, args, result, is_error}`` record per tool call during its loop
and, on the success persist path, calls :func:`record_invocations` once per
assistant ``tool_use`` message. :func:`touches_from` turns those same records
into ``(entity_type, entity_id)`` pairs for the knowledge graph's
conversation→entity edges.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso

# Truncation budget for arguments_json / result_json (design.md § 2).
VALUE_MAX = 4096

# Tools whose success result carries the id of an entity the turn created or
# changed. ``update_style_guide`` / ``archive_context_entry`` return no id and
# are deliberately absent.
_TOUCH_ENTITY_TYPE: dict[str, str] = {
    "create_objective": "objective",
    "update_objective": "objective",
    "add_action": "action",
    "update_action": "action",
    "create_project": "project",
    "update_project": "project",
    "upsert_context_entry": "context",
}

CallRecord = dict[str, Any]  # {"tool_name": str, "args": dict, "result": str, "is_error": bool}


def _truncate(value: str) -> str:
    return value if len(value) <= VALUE_MAX else value[:VALUE_MAX] + "…"


async def record_invocations(
    conversation_id: str,
    user_id: str,
    message_id: str,
    calls: list[CallRecord],
) -> None:
    """Write one ``tool_invocations`` row per call, all against ``message_id``
    (the saved assistant ``tool_use`` message)."""
    now = utcnow_iso()
    for call in calls:
        await client.db_execute(
            "INSERT INTO tool_invocations "
            "(id, user_id, conversation_id, message_id, tool_name, arguments_json, "
            "result_json, is_error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                new_id(),
                user_id,
                conversation_id,
                message_id,
                call["tool_name"],
                _truncate(json.dumps(call.get("args") or {}, default=str)),
                _truncate(str(call.get("result") or "")),
                1 if call.get("is_error") else 0,
                now,
            ],
        )


def touches_from(calls: list[CallRecord]) -> list[tuple[str, str]]:
    """``(entity_type, entity_id)`` for each successful create/update/add_action
    call. Errored calls and read-only tools yield nothing."""
    touches: list[tuple[str, str]] = []
    for call in calls:
        entity_type = _TOUCH_ENTITY_TYPE.get(call.get("tool_name", ""))
        if entity_type is None or call.get("is_error"):
            continue
        try:
            parsed = json.loads(call.get("result") or "")
        except (TypeError, ValueError):
            continue
        entity_id = parsed.get("id") if isinstance(parsed, dict) else None
        if entity_id:
            touches.append((entity_type, str(entity_id)))
    return touches
