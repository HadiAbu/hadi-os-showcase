"""The chat agent's toolset (REQ-18).

Two layers:

- ``_impl_*`` async functions take an explicit ``user_id``, do the work, and
  return JSON-serialisable data. Unit-tested directly. Provider-agnostic.
- ``TOOL_SPECS`` is the OpenAI-format function list handed to the model;
  ``dispatch(user_id, name, args)`` routes a tool call to the matching impl and
  returns a JSON string. ``user_id`` is bound by the caller, never model input.

Approval rule: ``upsert_context_entry`` writes ``status='proposed'`` (needs the
owner's confirmation); ``add_action`` writes ``source='suggested'``; objectives
and projects are created active.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import client
from app.services import context_store, objectives_store, projects_store, style

_OPEN = ("todo", "doing")


# --- impls -------------------------------------------------------


async def _impl_get_context(user_id: str, category: str | None = None) -> list[dict]:
    rows = await context_store.list_entries(user_id, category=category)
    return [
        {
            "id": r["id"],
            "category": r["category"],
            "key": r["key"],
            "value": r["value"],
            "status": r["status"],
        }
        for r in rows
        if r["status"] in ("active", "proposed")
    ]


async def _impl_list_objectives(
    user_id: str, status: str | None = None, tag: str | None = None
) -> list[dict]:
    objectives = await objectives_store.list_objectives(user_id, status=status, tag=tag)
    result = []
    for obj in objectives:
        actions = await objectives_store.list_actions(user_id, obj["id"])
        result.append(
            {
                "id": obj["id"],
                "title": obj["title"],
                "horizon": obj["horizon"],
                "status": obj["status"],
                "priority": obj["priority"],
                "tags": obj["tags"],
                "project_id": obj["project_id"],
                "open_actions": [
                    {"id": a["id"], "title": a["title"], "status": a["status"]}
                    for a in actions
                    if a["status"] in _OPEN
                ],
            }
        )
    return result


async def _impl_list_projects(user_id: str, status: str | None = None) -> list[dict]:
    rows = await projects_store.list_projects(user_id, status=status)
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "status": p["status"],
            "summary": p["summary"],
            "next_steps": p["next_steps"],
            "tech": p["tech"],
        }
        for p in rows
    ]


async def _impl_get_focus_snapshot(user_id: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT content_md, created_at FROM focus_snapshots WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        [user_id],
    )
    return rows[0] if rows else None


async def _impl_upsert_context_entry(
    user_id: str, category: str, key: str, value: str, pinned: bool = False
) -> dict:
    row = await context_store.create_entry(
        user_id, category, key, value, pinned=pinned, source="chat", status="proposed"
    )
    return {"id": row["id"], "status": row["status"], "key": row["key"]}


async def _impl_archive_context_entry(user_id: str, entry_id: str) -> dict:
    row = await context_store.set_status(user_id, entry_id, "archived")
    return {"ok": row is not None}


async def _impl_create_objective(user_id: str, **fields: Any) -> dict:
    try:
        row = await objectives_store.create_objective(user_id, fields)
    except objectives_store.ProjectNotOwned:
        return {"error": "unknown project_id"}
    return {"id": row["id"], "title": row["title"], "status": row["status"]}


async def _impl_update_objective(user_id: str, objective_id: str, **fields: Any) -> dict:
    try:
        row = await objectives_store.patch_objective(user_id, objective_id, fields)
    except objectives_store.ProjectNotOwned:
        return {"error": "unknown project_id"}
    if row is None:
        return {"error": "not found"}
    return {"id": row["id"], "title": row["title"], "status": row["status"]}


async def _impl_add_action(
    user_id: str, objective_id: str, title: str, due_date: str | None = None
) -> dict:
    row = await objectives_store.create_action(
        user_id, objective_id, title, due_date=due_date, source="suggested"
    )
    if row is None:
        return {"error": "objective not found"}
    return {"id": row["id"], "title": row["title"], "source": row["source"]}


async def _impl_update_action(user_id: str, action_id: str, **fields: Any) -> dict:
    row = await objectives_store.patch_action(user_id, action_id, fields)
    if row is None:
        return {"error": "not found"}
    return {"id": row["id"], "status": row["status"]}


async def _impl_create_project(user_id: str, **fields: Any) -> dict:
    row = await projects_store.create_project(user_id, fields)
    return {"id": row["id"], "name": row["name"], "status": row["status"]}


async def _impl_update_project(user_id: str, project_id: str, **fields: Any) -> dict:
    row = await projects_store.patch_project(user_id, project_id, fields)
    if row is None:
        return {"error": "not found"}
    return {"id": row["id"], "name": row["name"], "status": row["status"]}


async def _impl_update_style_guide(user_id: str, guide_md: str) -> dict:
    row = await style.put_style_guide(user_id, guide_md)
    return {"updated_at": row["updated_at"]}


# --- model-facing toolset (OpenAI function-calling format) ----------


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


_STR = {"type": "string"}
_STR_ARR = {"type": "array", "items": {"type": "string"}}
_CATEGORY = {
    "type": "string",
    "enum": [
        "identity",
        "preference",
        "goal_context",
        "project_context",
        "working_style",
        "misc",
    ],
}

TOOL_SPECS: list[dict] = [
    _fn(
        "get_context",
        "Read what you know about the owner. Optionally filter by category.",
        {"category": _CATEGORY},
        [],
    ),
    _fn(
        "list_objectives",
        "List the owner's objectives with their open actions. Filter by status "
        "(active, done, paused, dropped) or tag (e.g. skill, learning).",
        {"status": _STR, "tag": _STR},
        [],
    ),
    _fn(
        "list_projects",
        "List the owner's software projects. Filter by status "
        "(active, paused, shipped, archived).",
        {"status": _STR},
        [],
    ),
    _fn(
        "get_focus_snapshot",
        "Get the most recent cached 'what to focus on' note, if any.",
        {},
        [],
    ),
    _fn(
        "upsert_context_entry",
        "Propose a durable fact about the owner. Saved as 'proposed' and only "
        "takes effect once the owner confirms it.",
        {"category": _CATEGORY, "key": _STR, "value": _STR, "pinned": {"type": "boolean"}},
        ["category", "key", "value"],
    ),
    _fn(
        "archive_context_entry",
        "Archive a context entry by id.",
        {"entry_id": _STR},
        ["entry_id"],
    ),
    _fn(
        "create_objective",
        "Create an objective (created active). horizon is one of month, quarter, "
        "year, someday. priority is 1-3. Tag with 'skill' or 'learning' for growth.",
        {
            "title": _STR,
            "horizon": {"type": "string", "enum": ["month", "quarter", "year", "someday"]},
            "description": _STR,
            "priority": {"type": "integer"},
            "tags": _STR_ARR,
            "target_date": _STR,
            "project_id": _STR,
        },
        ["title", "horizon"],
    ),
    _fn(
        "update_objective",
        "Update fields on an objective. Set status to done/paused/dropped to "
        "change its state.",
        {
            "objective_id": _STR,
            "title": _STR,
            "horizon": _STR,
            "description": _STR,
            "priority": {"type": "integer"},
            "tags": _STR_ARR,
            "target_date": _STR,
            "project_id": _STR,
            "status": _STR,
        },
        ["objective_id"],
    ),
    _fn(
        "add_action",
        "Add a suggested next action under an objective. Saved with source "
        "'suggested' for the owner to accept or drop.",
        {"objective_id": _STR, "title": _STR, "due_date": _STR},
        ["objective_id", "title"],
    ),
    _fn(
        "update_action",
        "Update an action. status is one of todo, doing, done, dropped.",
        {"action_id": _STR, "title": _STR, "status": _STR, "notes": _STR, "due_date": _STR},
        ["action_id"],
    ),
    _fn(
        "create_project",
        "Create a project record (created active).",
        {
            "name": _STR,
            "summary": _STR,
            "status": _STR,
            "tech": _STR_ARR,
            "repo_path": _STR,
            "repo_url": _STR,
            "next_steps": _STR,
            "notes": _STR,
        },
        ["name"],
    ),
    _fn(
        "update_project",
        "Update fields on a project.",
        {
            "project_id": _STR,
            "name": _STR,
            "summary": _STR,
            "status": _STR,
            "tech": _STR_ARR,
            "repo_path": _STR,
            "repo_url": _STR,
            "next_steps": _STR,
            "notes": _STR,
        },
        ["project_id"],
    ),
    _fn(
        "update_style_guide",
        "Replace the owner's writing-style guide (markdown). Applied to prose "
        "replies only.",
        {"guide_md": _STR},
        ["guide_md"],
    ),
]

TOOL_NAMES = {t["function"]["name"] for t in TOOL_SPECS}


async def dispatch(user_id: str, name: str, args: dict) -> str:
    """Route one tool call to its impl; return a JSON string for the tool result."""
    # Models often send "" for optional filters they don't want to set — treat
    # empty strings as absent.
    args = {k: v for k, v in (args or {}).items() if v not in (None, "")}

    async def _call() -> Any:
        if name == "get_context":
            return await _impl_get_context(user_id, args.get("category"))
        if name == "list_objectives":
            return await _impl_list_objectives(user_id, args.get("status"), args.get("tag"))
        if name == "list_projects":
            return await _impl_list_projects(user_id, args.get("status"))
        if name == "get_focus_snapshot":
            return await _impl_get_focus_snapshot(user_id)
        if name == "upsert_context_entry":
            return await _impl_upsert_context_entry(
                user_id,
                args["category"],
                args["key"],
                args["value"],
                bool(args.get("pinned", False)),
            )
        if name == "archive_context_entry":
            return await _impl_archive_context_entry(user_id, args["entry_id"])
        if name == "create_objective":
            return await _impl_create_objective(
                user_id, **{k: v for k, v in args.items() if v is not None}
            )
        if name == "update_objective":
            oid = args.pop("objective_id")
            return await _impl_update_objective(
                user_id, oid, **{k: v for k, v in args.items() if v is not None}
            )
        if name == "add_action":
            return await _impl_add_action(
                user_id, args["objective_id"], args["title"], args.get("due_date")
            )
        if name == "update_action":
            aid = args.pop("action_id")
            return await _impl_update_action(
                user_id, aid, **{k: v for k, v in args.items() if v is not None}
            )
        if name == "create_project":
            return await _impl_create_project(
                user_id, **{k: v for k, v in args.items() if v is not None}
            )
        if name == "update_project":
            pid = args.pop("project_id")
            return await _impl_update_project(
                user_id, pid, **{k: v for k, v in args.items() if v is not None}
            )
        if name == "update_style_guide":
            return await _impl_update_style_guide(user_id, args["guide_md"])
        return {"error": f"unknown tool: {name}"}

    try:
        return json.dumps(await _call(), default=str)
    except KeyError as exc:
        return json.dumps({"error": f"missing argument: {exc}"})
    except Exception as exc:  # noqa: BLE001 - report tool failure to the model
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
