"""Persistence for ``conversations`` and ``messages`` (REQ-15, REQ-16).

``messages.blocks_json`` is the source of truth for replaying history to the
Tool Runner; ``text`` is the display/search convenience view.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso

LIST_LIMIT = 50


async def create_conversation(user_id: str) -> dict:
    conv_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO conversations "
        "(id, user_id, title, archived, created_at, updated_at, last_message_at) "
        "VALUES (?, ?, '', 0, ?, ?, NULL)",
        [conv_id, user_id, now, now],
    )
    return {
        "id": conv_id,
        "title": "",
        "archived": False,
        "created_at": now,
        "last_message_at": None,
    }


async def list_conversations(user_id: str, *, archived: bool = False) -> list[dict]:
    return await client.db_execute(
        "SELECT id, title, archived, created_at, last_message_at FROM conversations "
        "WHERE user_id = ? AND archived = ? "
        "ORDER BY COALESCE(last_message_at, created_at) DESC LIMIT ?",
        [user_id, 1 if archived else 0, LIST_LIMIT],
    )


async def get_conversation(user_id: str, conv_id: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM conversations WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, conv_id],
    )
    return rows[0] if rows else None


async def archive_conversation(user_id: str, conv_id: str) -> bool:
    if await get_conversation(user_id, conv_id) is None:
        return False
    await client.db_execute(
        "UPDATE conversations SET archived = 1, updated_at = ? WHERE user_id = ? AND id = ?",
        [utcnow_iso(), user_id, conv_id],
    )
    return True


async def list_messages(user_id: str, conv_id: str) -> list[dict]:
    """All rows (user/assistant/tool) in order — for rebuilding the LLM history."""
    return await client.db_execute(
        "SELECT role, text, blocks_json, created_at FROM messages "
        "WHERE user_id = ? AND conversation_id = ? ORDER BY created_at, id",
        [user_id, conv_id],
    )


async def list_display_messages(user_id: str, conv_id: str) -> list[dict]:
    """User + assistant rows with visible text — for the transcript endpoint."""
    return await client.db_execute(
        "SELECT role, text, created_at FROM messages "
        "WHERE user_id = ? AND conversation_id = ? AND role IN ('user', 'assistant') "
        "AND text != '' ORDER BY created_at, id",
        [user_id, conv_id],
    )


async def append_message(
    conv_id: str,
    user_id: str,
    role: str,
    text: str,
    raw: dict,
    *,
    model: str | None = None,
    usage: dict | None = None,
) -> dict:
    """``raw`` is the full OpenAI-format message dict (source of truth for replay);
    ``text`` is the display/search convenience view; ``role`` may be
    ``user`` / ``assistant`` / ``tool``."""
    msg_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO messages "
        "(id, conversation_id, user_id, role, text, blocks_json, model, usage_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            msg_id,
            conv_id,
            user_id,
            role,
            text,
            json.dumps(raw),
            model,
            json.dumps(usage) if usage is not None else None,
            now,
        ],
    )
    return {"id": msg_id, "role": role, "text": text, "created_at": now}


async def touch_conversation(
    conv_id: str, user_id: str, *, title: str | None = None
) -> None:
    now = utcnow_iso()
    if title is not None:
        await client.db_execute(
            "UPDATE conversations SET last_message_at = ?, updated_at = ?, title = ? "
            "WHERE user_id = ? AND id = ?",
            [now, now, title, user_id, conv_id],
        )
    else:
        await client.db_execute(
            "UPDATE conversations SET last_message_at = ?, updated_at = ? "
            "WHERE user_id = ? AND id = ?",
            [now, now, user_id, conv_id],
        )


async def last_message(user_id: str, conv_id: str, role: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT role, text, created_at FROM messages "
        "WHERE user_id = ? AND conversation_id = ? AND role = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        [user_id, conv_id, role],
    )
    return rows[0] if rows else None


def count_messages(rows: list[dict]) -> int:
    return len(rows)


def parse_blocks(row: dict) -> Any:
    return json.loads(row["blocks_json"])
