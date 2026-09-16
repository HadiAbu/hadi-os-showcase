"""Tasks 5.3-5.6 + 7.1 — conversations CRUD + manual tool-call turn engine
(REQ-15/16/17/25)."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from app.services import chat_agent, chat_store, llm_client

CHAT = "/api/chat"


# --- fakes: an OpenAI-compatible chat completion ---------------


def _tc(call_id: str, name: str, args: dict):
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args))
    )


def _completion(content=None, tool_calls=None, finish_reason="stop"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


class FakeChat:
    """Returns a scripted sequence of completions, one per call."""

    def __init__(self, completions, capture: dict | None = None):
        self._c = list(completions)
        self._capture = capture

    async def __call__(self, **kwargs):
        if self._capture is not None:
            # copy — run_turn keeps mutating the messages list it passed in
            self._capture.update(copy.deepcopy(kwargs))
        return self._c.pop(0)


def _install(monkeypatch, completions, *, capture: dict | None = None):
    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(
        chat_agent.llm_client, "create_chat", FakeChat(completions, capture)
    )


async def _run(client, conv_id, text):
    events = []
    async with client.stream(
        "POST", f"{CHAT}/conversations/{conv_id}/messages", json={"text": text}
    ) as resp:
        assert resp.status_code == 200
        name = None
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[6:])))
    return events


# one tool call, then a text answer
SCRIPT = [
    _completion(tool_calls=[_tc("call_1", "list_projects", {})], finish_reason="tool_calls"),
    _completion(content="You have no active projects."),
]
TEXT_ONLY = [_completion(content="hello")]


# --- REQ-15 conversations -------------------------------------


async def test_conversation_crud(auth_client):
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    assert [c["id"] for c in (await auth_client.get(f"{CHAT}/conversations")).json()] == [cid]
    assert (await auth_client.get(f"{CHAT}/conversations/{cid}/messages")).json() == []

    assert (await auth_client.post(f"{CHAT}/conversations/{cid}/archive")).status_code == 200
    assert (await auth_client.get(f"{CHAT}/conversations")).json() == []
    archived = (await auth_client.get(f"{CHAT}/conversations?archived=true")).json()
    assert [c["id"] for c in archived] == [cid]


async def test_messages_missing_conversation_404(auth_client):
    assert (await auth_client.get(f"{CHAT}/conversations/nope/messages")).status_code == 404


# --- REQ-17 degraded -----------------------------------------


async def test_post_message_503_without_key(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    r = await auth_client.post(f"{CHAT}/conversations/{cid}/messages", json={"text": "hi"})
    assert r.status_code == 503


# --- REQ-16 happy path -------------------------------------


async def test_turn_streams_events_and_persists_rows(auth_client, monkeypatch):
    _install(monkeypatch, SCRIPT)
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]

    events = await _run(auth_client, cid, "what am I working on?")
    names = [n for n, _ in events]
    assert names == ["tool", "tool", "token", "message", "done"]
    assert events[0][1] == {"name": "list_projects", "status": "running", "summary": "list_projects()"}
    assert events[1][1]["status"] == "done"
    assert events[2][1]["delta"] == "You have no active projects."
    assert events[3][1]["message"]["text"] == "You have no active projects."

    # transcript endpoint: only user + assistant rows with visible text
    shown = (await auth_client.get(f"{CHAT}/conversations/{cid}/messages")).json()
    assert [(m["role"], m["text"]) for m in shown] == [
        ("user", "what am I working on?"),
        ("assistant", "You have no active projects."),
    ]
    # internal history: user, assistant(tool_calls), tool, assistant(text)
    all_rows = await chat_store.list_messages(
        (await auth_client.get("/api/auth/me")).json()["id"], cid
    )
    assert [r["role"] for r in all_rows] == ["user", "assistant", "tool", "assistant"]

    convs = (await auth_client.get(f"{CHAT}/conversations")).json()
    assert convs[0]["title"] == "what am I working on?"


async def test_rebuild_skips_legacy_list_shaped_rows(auth_client, monkeypatch):
    # a row from before the provider swap: blocks_json is a JSON *list*
    from app.db import client as db
    from app.db.client import new_id, utcnow_iso

    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    uid = (await auth_client.get("/api/auth/me")).json()["id"]
    await db.db_execute(
        "INSERT INTO messages (id, conversation_id, user_id, role, text, blocks_json, created_at) "
        "VALUES (?, ?, ?, 'assistant', 'old', ?, ?)",
        [new_id(), cid, uid, '[{"type": "text", "text": "old"}]', utcnow_iso()],
    )

    capture: dict = {}
    _install(monkeypatch, list(TEXT_ONLY), capture=capture)
    await _run(auth_client, cid, "hi")  # must not raise
    # the malformed row was dropped, not replayed
    assert all(m.get("content") != "old" for m in capture["messages"])


async def test_history_is_rebuilt_well_formed_on_continue(auth_client, monkeypatch):
    _install(monkeypatch, SCRIPT)
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    await _run(auth_client, cid, "first")

    capture: dict = {}
    _install(monkeypatch, list(TEXT_ONLY), capture=capture)
    await _run(auth_client, cid, "second")

    roles = [m["role"] for m in capture["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert capture["messages"][2]["tool_calls"][0]["function"]["name"] == "list_projects"
    assert capture["messages"][3]["role"] == "tool"
    assert capture["messages"][3]["tool_call_id"] == "call_1"
    assert capture["messages"][-1] == {"role": "user", "content": "second"}


# --- REQ-17 failure modes ---------------------------------


async def test_content_filter_emits_error_and_persists_only_user(auth_client, monkeypatch):
    _install(monkeypatch, [_completion(content="", finish_reason="content_filter")])
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]

    events = await _run(auth_client, cid, "do something disallowed")
    assert events[-1][0] == "error"

    uid = (await auth_client.get("/api/auth/me")).json()["id"]
    assert [r["role"] for r in await chat_store.list_messages(uid, cid)] == ["user"]


async def test_tool_cycle_cap(auth_client, monkeypatch):
    loop = [
        _completion(tool_calls=[_tc(f"c{i}", "list_projects", {})], finish_reason="tool_calls")
        for i in range(20)
    ]
    _install(monkeypatch, loop)
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]

    events = await _run(auth_client, cid, "loop forever")
    caps = [d for n, d in events if n == "tool" and "12 tool cycles" in d.get("summary", "")]
    assert caps
    assert events[-1][0] == "done"


async def test_tool_error_is_reported_and_loop_continues(auth_client, monkeypatch):
    _install(
        monkeypatch,
        [
            _completion(
                tool_calls=[_tc("call_1", "archive_context_entry", {"entry_id": "nope"})],
                finish_reason="tool_calls",
            ),
            _completion(content="done"),
        ],
    )
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    events = await _run(auth_client, cid, "archive something missing")
    # archive of a missing id returns {"ok": false} (not an error) -> status done,
    # and the loop still reaches a final answer
    assert [n for n, _ in events][-2:] == ["message", "done"]


async def test_tool_result_error_marks_status_error(auth_client, monkeypatch):
    # create_objective without the required `title` -> dispatch returns {"error": ...}
    _install(
        monkeypatch,
        [
            _completion(
                tool_calls=[_tc("call_1", "create_objective", {"horizon": "year"})],
                finish_reason="tool_calls",
            ),
            _completion(content="couldn't do that"),
        ],
    )
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    events = await _run(auth_client, cid, "make an objective")
    tool_done = [d for n, d in events if n == "tool" and d["status"] in ("done", "error")]
    assert tool_done and tool_done[0]["status"] == "error"


async def test_truncated_completion_emits_notice(auth_client, monkeypatch):
    _install(monkeypatch, [_completion(content="half a sen", finish_reason="length")])
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    events = await _run(auth_client, cid, "write a long thing")
    assert any(
        n == "tool" and d.get("name") == "(truncated)" for n, d in events
    )
    assert events[-1][0] == "done"


# --- REQ-18 / 7.1 model override ---------------------------


async def test_chat_model_override_from_settings(auth_client, monkeypatch):
    await auth_client.post(
        "/api/context/entries",
        json={"category": "misc", "key": "chat_model", "value": "openai/gpt-4o-mini"},
    )
    capture: dict = {}
    _install(monkeypatch, list(TEXT_ONLY), capture=capture)
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    await _run(auth_client, cid, "hi")
    assert capture["model"] == "openai/gpt-4o-mini"


async def test_chat_model_defaults_when_unset(auth_client, monkeypatch):
    capture: dict = {}
    _install(monkeypatch, list(TEXT_ONLY), capture=capture)
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    await _run(auth_client, cid, "hi")
    assert capture["model"] == "openai/gpt-oss-120b"


@pytest.mark.parametrize("path", ["/api/chat/conversations"])
async def test_requires_auth(client, path):
    assert (await client.get(path)).status_code == 401


# --- M3 / REQ-4 tool_invocations capture ---------------------------


async def _invocations(auth_client):
    from app.db import client as db

    uid = (await auth_client.get("/api/auth/me")).json()["id"]
    return await db.db_execute(
        "SELECT * FROM tool_invocations WHERE user_id = ? ORDER BY created_at, id", [uid]
    )


async def test_turn_records_one_row_per_tool_call(auth_client, monkeypatch):
    _install(monkeypatch, SCRIPT)
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    await _run(auth_client, cid, "what am I working on?")

    rows = await _invocations(auth_client)
    assert len(rows) == 1
    (row,) = rows
    assert row["tool_name"] == "list_projects"
    assert row["conversation_id"] == cid
    assert row["is_error"] == 0

    # message_id points at a persisted assistant tool_use row in this conversation
    from app.db import client as db

    msgs = await db.db_execute(
        "SELECT id, blocks_json FROM messages WHERE conversation_id = ? AND role = 'assistant'",
        [cid],
    )
    tool_use_ids = [m["id"] for m in msgs if '"tool_calls"' in m["blocks_json"]]
    assert row["message_id"] in tool_use_ids


async def test_refusal_turn_records_no_invocations(auth_client, monkeypatch):
    # a tool call runs, then the follow-up completion is a content-filter refusal
    _install(
        monkeypatch,
        [
            _completion(
                tool_calls=[_tc("call_1", "list_projects", {})], finish_reason="tool_calls"
            ),
            _completion(content="", finish_reason="content_filter"),
        ],
    )
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    events = await _run(auth_client, cid, "do the disallowed thing")

    assert events[-1][0] == "error"
    assert await _invocations(auth_client) == []


async def test_invocation_is_error_flag(auth_client, monkeypatch):
    _install(
        monkeypatch,
        [
            _completion(
                tool_calls=[_tc("call_1", "create_objective", {"horizon": "year"})],
                finish_reason="tool_calls",
            ),
            _completion(content="couldn't"),
        ],
    )
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    await _run(auth_client, cid, "make an objective badly")

    (row,) = await _invocations(auth_client)
    assert row["tool_name"] == "create_objective"
    assert row["is_error"] == 1


async def test_invocation_truncates_large_arguments(auth_client, monkeypatch):
    big = "x" * 6000
    _install(
        monkeypatch,
        [
            _completion(
                tool_calls=[
                    _tc(
                        "call_1",
                        "upsert_context_entry",
                        {"category": "misc", "key": "note", "value": big},
                    )
                ],
                finish_reason="tool_calls",
            ),
            _completion(content="noted"),
        ],
    )
    cid = (await auth_client.post(f"{CHAT}/conversations")).json()["id"]
    await _run(auth_client, cid, "remember this long note")

    (row,) = await _invocations(auth_client)
    assert len(row["arguments_json"]) <= 4097
    assert row["arguments_json"].endswith("…")
