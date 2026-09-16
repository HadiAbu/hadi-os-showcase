"""One chat turn: assemble context -> manual tool-call loop -> SSE events ->
persist (REQ-16, REQ-17, REQ-25).

Provider-agnostic: drives an OpenAI-compatible chat API (default Groq) through a
hand-written loop — request, run any tool calls, feed results back, repeat until
the model answers with no tool calls or the 12-cycle cap is hit.

Persistence is buffered: the user message is written immediately (so it survives
a failed turn); assistant / tool rows are written only after the turn completes
without error.

``run_turn`` yields ``(event_name, data)`` pairs; the route serialises them as
``event: <name>\\ndata: <json>\\n\\n``.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.db import client
from app.services import agent_tools, chat_store, context_assembly, llm_client, tool_log

MAX_TOOL_CYCLES = 12
_CHUNK = 240
_SUMMARY_VALUE_MAX = 40
_REASONING_KEYS = ("reasoning", "reasoning_content")

SSEEvent = tuple[str, dict]


class AIUnavailable(Exception):
    """Raised when the chat is invoked without an LLM API key."""


# --- helpers --------------------------------------------------------


def _clean_assistant(msg: Any) -> dict:
    """Turn an SDK assistant message into a plain, replay-safe dict."""
    out: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in tool_calls
        ]
    return out


def _strip_reasoning(message: dict) -> dict:
    return {k: v for k, v in message.items() if k not in _REASONING_KEYS}


def _dump_usage(completion: Any) -> dict | None:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump(mode="json")
    return dict(usage) if isinstance(usage, dict) else None


def _add_usage(total: dict, delta: dict | None) -> None:
    if not delta:
        return
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = delta.get(key)
        if isinstance(value, (int, float)):
            total[key] = total.get(key, 0) + int(value)


def _tool_summary(name: str, args: dict) -> str:
    parts = []
    for key, value in list(args.items())[:3]:
        text = str(value)
        if len(text) > _SUMMARY_VALUE_MAX:
            text = text[:_SUMMARY_VALUE_MAX] + "…"
        parts.append(f"{key}={text}")
    return f"{name}({', '.join(parts)})"


def _result_is_error(result: str) -> bool:
    try:
        parsed = json.loads(result)
    except ValueError:
        return False
    return isinstance(parsed, dict) and "error" in parsed


async def _rebuild_messages(user_id: str, conv_id: str) -> list[dict]:
    rows = await chat_store.list_messages(user_id, conv_id)
    out: list[dict] = []
    for row in rows:
        try:
            message = json.loads(row["blocks_json"])
        except (TypeError, ValueError):
            continue
        # Only replay-safe OpenAI-shaped rows. Legacy list-shaped rows (from
        # before the provider swap, design.md §11.7) are skipped rather than
        # crashing the turn.
        if isinstance(message, dict) and message.get("role"):
            out.append(_strip_reasoning(message))
    return out


async def _resolve_model(user_id: str) -> str:
    rows = await client.db_execute(
        "SELECT value FROM context_entries WHERE user_id = ? AND category = 'misc' "
        "AND key = 'chat_model' AND status = 'active' LIMIT 1",
        [user_id],
    )
    return llm_client.chat_model_for(rows[0]["value"] if rows else None)


def _chunks(text: str) -> list[str]:
    return [text[i : i + _CHUNK] for i in range(0, len(text), _CHUNK)]


def _parse_args(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


# --- the turn ------------------------------------------------------


async def run_turn(
    user: dict, conversation_id: str, user_text: str
) -> AsyncIterator[SSEEvent]:
    if not llm_client.available():
        raise AIUnavailable()

    user_id = user["id"]
    system = await context_assembly.build_system(user_id)
    prior = await _rebuild_messages(user_id, conversation_id)
    # Title the conversation until it has an actual assistant reply — covers the
    # case where an earlier turn failed after persisting only the user message.
    needs_title = not any(m.get("role") == "assistant" for m in prior)

    user_msg = {"role": "user", "content": user_text}
    messages: list[dict] = [{"role": "system", "content": system}, *prior, user_msg]

    # Persist the user message now (REQ-17: it survives a failed turn).
    await chat_store.append_message(conversation_id, user_id, "user", user_text, user_msg)
    await chat_store.touch_conversation(
        conversation_id, user_id, title=user_text[:60] if needs_title else None
    )

    model = await _resolve_model(user_id)
    produced: list[dict] = []  # rows to persist only if the turn succeeds
    # One record per tool call, tagged with the index in ``produced`` of the
    # assistant message it belongs to; persisted as tool_invocations rows on the
    # success path only (design.md § 3).
    tool_records: list[dict] = []
    turn_usage: dict = {}
    cycles = 0
    capped = False
    truncated = False
    final_text = ""

    try:
        while True:
            completion = await llm_client.create_chat(
                model=model, messages=messages, tools=agent_tools.TOOL_SPECS
            )
            _add_usage(turn_usage, _dump_usage(completion))
            choice = completion.choices[0]
            assistant = _clean_assistant(choice.message)
            messages.append(assistant)
            produced.append(assistant)
            assistant_idx = len(produced) - 1
            if assistant["content"]:
                final_text = assistant["content"]

            tool_calls = assistant.get("tool_calls") or []
            if not tool_calls:
                if choice.finish_reason == "content_filter":
                    yield ("error", {"detail": "The model declined to respond to that."})
                    return
                truncated = choice.finish_reason == "length"
                break

            for tc in tool_calls:
                name = tc["function"]["name"]
                args = _parse_args(tc["function"]["arguments"])
                yield ("tool", {"name": name, "status": "running", "summary": _tool_summary(name, args)})
                result = await agent_tools.dispatch(user_id, name, args)
                tool_msg = {"role": "tool", "tool_call_id": tc["id"], "content": result}
                messages.append(tool_msg)
                produced.append(tool_msg)
                is_error = _result_is_error(result)
                tool_records.append(
                    {
                        "assistant_idx": assistant_idx,
                        "tool_name": name,
                        "args": args,
                        "result": result,
                        "is_error": is_error,
                    }
                )
                yield ("tool", {"name": name, "status": "error" if is_error else "done", "summary": ""})

            cycles += 1
            if cycles >= MAX_TOOL_CYCLES:
                capped = True
                break
    except Exception as exc:  # noqa: BLE001 - surface any API/loop failure to the client
        yield ("error", {"detail": f"{type(exc).__name__}: {exc}"[:200]})
        return

    # Success -> persist everything produced (usage on the final assistant row).
    last_assistant_idx = max(
        (i for i, m in enumerate(produced) if m["role"] == "assistant"), default=-1
    )
    last_assistant: dict | None = None
    for i, msg in enumerate(produced):
        role = msg["role"]
        text = msg.get("content", "") if role == "assistant" else ""
        usage = turn_usage if (i == last_assistant_idx and turn_usage) else None
        saved = await chat_store.append_message(
            conversation_id,
            user_id,
            role,
            text,
            msg,
            model=model if role == "assistant" else None,
            usage=usage,
        )
        if role == "assistant":
            last_assistant = saved
            calls = [r for r in tool_records if r["assistant_idx"] == i]
            if calls:
                await tool_log.record_invocations(
                    conversation_id, user_id, saved["id"], calls
                )
    await chat_store.touch_conversation(conversation_id, user_id)

    if capped:
        yield (
            "tool",
            {"name": "(loop)", "status": "error", "summary": "stopped after 12 tool cycles"},
        )
    if truncated:
        yield (
            "tool",
            {"name": "(truncated)", "status": "error", "summary": "response hit the token limit"},
        )

    for chunk in _chunks(final_text):
        yield ("token", {"delta": chunk})

    if last_assistant is not None:
        last_assistant = {**last_assistant, "text": final_text}
    yield ("message", {"message": last_assistant})
    yield ("done", {})
