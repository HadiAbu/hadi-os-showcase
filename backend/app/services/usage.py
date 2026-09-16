"""``usage(user_id, window)`` — token / cost / tool-call telemetry.

See ``.kiro/specs/phase-2-visual-and-graph/design.md`` § 5. Pure aggregation over
``messages.usage_json`` and ``tool_invocations``; no LLM call.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import client

# USD per 1M tokens (input, output). A model absent here makes cost unknown.
RATES: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.0, 0.0),
    "openai/gpt-oss-20b": (0.0, 0.0),
    "qwen/qwen3.8-27b": (0.0, 0.0),
    "gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "claude-sonnet-5": (3.0, 15.0),
}

_WINDOW_DAYS: dict[str, int | None] = {"7d": 7, "30d": 30, "all": None}
_TOP_CONVERSATIONS = 10


def _cutoff(window: str) -> str | None:
    days = _WINDOW_DAYS.get(window, 7)
    if days is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _parse_usage(raw: str | None) -> tuple[int, int, int]:
    try:
        u = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return (0, 0, 0)
    if not isinstance(u, dict):
        return (0, 0, 0)
    p = int(u.get("prompt_tokens") or 0)
    c = int(u.get("completion_tokens") or 0)
    t = int(u.get("total_tokens") or (p + c))
    return (p, c, t)


async def usage(user_id: str, window: str = "7d") -> dict[str, Any]:
    cutoff = _cutoff(window)

    msg_where = "user_id = ? AND role = 'assistant' AND usage_json IS NOT NULL"
    msg_params: list[Any] = [user_id]
    if cutoff is not None:
        msg_where += " AND created_at >= ?"
        msg_params.append(cutoff)
    rows = await client.db_execute(
        f"SELECT model, conversation_id, usage_json, created_at FROM messages WHERE {msg_where}",
        msg_params,
    )

    prompt = completion = total = 0
    by_day: dict[str, list[int]] = {}
    by_model: dict[str, list[int]] = {}
    by_conv: dict[str, int] = {}

    for r in rows:
        p, c, t = _parse_usage(r["usage_json"])
        prompt += p
        completion += c
        total += t

        day = (r["created_at"] or "")[:10]
        d = by_day.setdefault(day, [0, 0, 0])
        d[0] += p
        d[1] += c
        d[2] += t

        model = r["model"] or "unknown"
        m = by_model.setdefault(model, [0, 0, 0])
        m[0] += p
        m[1] += c
        m[2] += t

        by_conv[r["conversation_id"]] = by_conv.get(r["conversation_id"], 0) + t

    # tool calls in the same window
    tool_where = "user_id = ?"
    tool_params: list[Any] = [user_id]
    if cutoff is not None:
        tool_where += " AND created_at >= ?"
        tool_params.append(cutoff)
    tool_counts: dict[str, int] = {}
    for r in await client.db_execute(
        f"SELECT tool_name FROM tool_invocations WHERE {tool_where}", tool_params
    ):
        tool_counts[r["tool_name"]] = tool_counts.get(r["tool_name"], 0) + 1

    # titles for the top conversations
    top_conv_ids = sorted(by_conv, key=lambda k: by_conv[k], reverse=True)[:_TOP_CONVERSATIONS]
    titles: dict[str, str] = {}
    if top_conv_ids:
        placeholders = ",".join("?" * len(top_conv_ids))
        for r in await client.db_execute(
            f"SELECT id, title FROM conversations WHERE user_id = ? AND id IN ({placeholders})",
            [user_id, *top_conv_ids],
        ):
            titles[r["id"]] = r["title"] or ""

    cost = 0.0
    cost_known = True
    for model, (p, c, _t) in by_model.items():
        rate = RATES.get(model)
        if rate is None:
            cost_known = False
            continue
        cost += p / 1_000_000 * rate[0] + c / 1_000_000 * rate[1]

    return {
        "window": window,
        "tokens": {"prompt": prompt, "completion": completion, "total": total},
        "by_day": [
            {"day": day, "prompt": v[0], "completion": v[1], "total": v[2]}
            for day, v in sorted(by_day.items())
        ],
        "by_model": [
            {
                "model": model,
                "prompt": v[0],
                "completion": v[1],
                "total": v[2],
                "pct": round(v[2] / total * 100) if total else 0,
            }
            for model, v in sorted(by_model.items(), key=lambda kv: kv[1][2], reverse=True)
        ],
        "by_conversation": [
            {"conversation_id": cid, "title": titles.get(cid, ""), "total": by_conv[cid]}
            for cid in top_conv_ids
        ],
        "tool_calls_total": sum(tool_counts.values()),
        "tool_calls_by_name": [
            {"tool_name": name, "count": n}
            for name, n in sorted(tool_counts.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "estimated_cost_usd": round(cost, 4),
        "cost_known": cost_known,
    }
