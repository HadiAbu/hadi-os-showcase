"""M6 task 6.1 — usage.usage() aggregation + RATES."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.db import client
from app.db.client import new_id
from app.services import usage as usage_service


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


async def _conv(user_id: str, title: str = "") -> str:
    cid = new_id()
    await client.db_execute(
        "INSERT INTO conversations (id, user_id, title, archived, created_at, updated_at, last_message_at) "
        "VALUES (?, ?, ?, 0, ?, ?, ?)",
        [cid, user_id, title, _iso(1), _iso(1), _iso(1)],
    )
    return cid


async def _assistant_msg(
    user_id: str, conv_id: str, model: str, prompt: int, completion: int, when: str
) -> None:
    await client.db_execute(
        "INSERT INTO messages (id, conversation_id, user_id, role, text, blocks_json, model, usage_json, created_at) "
        "VALUES (?, ?, ?, 'assistant', '', '{}', ?, ?, ?)",
        [
            new_id(),
            conv_id,
            user_id,
            model,
            json.dumps(
                {
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "total_tokens": prompt + completion,
                }
            ),
            when,
        ],
    )


async def _tool_row(user_id: str, conv_id: str, name: str, when: str) -> None:
    await client.db_execute(
        "INSERT INTO tool_invocations "
        "(id, user_id, conversation_id, message_id, tool_name, arguments_json, result_json, is_error, created_at) "
        "VALUES (?, ?, ?, 'm', ?, '{}', '{}', 0, ?)",
        [new_id(), user_id, conv_id, name, when],
    )


async def test_window_cutoffs(owner_id):
    cid = await _conv(owner_id)
    await _assistant_msg(owner_id, cid, "openai/gpt-oss-120b", 100, 50, _iso(2))
    await _assistant_msg(owner_id, cid, "openai/gpt-oss-120b", 100, 50, _iso(20))
    await _assistant_msg(owner_id, cid, "openai/gpt-oss-120b", 100, 50, _iso(90))

    assert (await usage_service.usage(owner_id, "7d"))["tokens"]["total"] == 150
    assert (await usage_service.usage(owner_id, "30d"))["tokens"]["total"] == 300
    assert (await usage_service.usage(owner_id, "all"))["tokens"]["total"] == 450


async def test_token_sums_and_by_day(owner_id):
    cid = await _conv(owner_id)
    day = _iso(1)
    await _assistant_msg(owner_id, cid, "openai/gpt-oss-20b", 10, 5, day)
    await _assistant_msg(owner_id, cid, "openai/gpt-oss-20b", 20, 10, day)
    await _assistant_msg(owner_id, cid, "openai/gpt-oss-20b", 1, 1, _iso(3))

    out = await usage_service.usage(owner_id, "7d")
    assert out["tokens"] == {"prompt": 31, "completion": 16, "total": 47}
    assert len(out["by_day"]) == 2
    heaviest = max(out["by_day"], key=lambda d: d["total"])
    assert heaviest["total"] == 45


async def test_by_model_pct(owner_id):
    cid = await _conv(owner_id)
    await _assistant_msg(owner_id, cid, "model-a", 60, 15, _iso(1))  # 75
    await _assistant_msg(owner_id, cid, "model-b", 20, 5, _iso(1))  # 25

    by_model = {m["model"]: m for m in (await usage_service.usage(owner_id, "7d"))["by_model"]}
    assert by_model["model-a"]["pct"] == 75
    assert by_model["model-b"]["pct"] == 25
    # sorted heaviest-first
    assert (await usage_service.usage(owner_id, "7d"))["by_model"][0]["model"] == "model-a"


async def test_by_conversation_top10_and_titles(owner_id):
    heavy = await _conv(owner_id, "Heavy thread")
    light = await _conv(owner_id, "Light thread")
    await _assistant_msg(owner_id, heavy, "openai/gpt-oss-120b", 500, 500, _iso(1))
    await _assistant_msg(owner_id, light, "openai/gpt-oss-120b", 5, 5, _iso(1))

    by_conv = (await usage_service.usage(owner_id, "7d"))["by_conversation"]
    assert by_conv[0]["conversation_id"] == heavy
    assert by_conv[0]["title"] == "Heavy thread"
    assert by_conv[0]["total"] == 1000


async def test_tool_calls_from_invocations(owner_id):
    cid = await _conv(owner_id)
    await _tool_row(owner_id, cid, "list_projects", _iso(1))
    await _tool_row(owner_id, cid, "list_projects", _iso(2))
    await _tool_row(owner_id, cid, "create_objective", _iso(1))
    await _tool_row(owner_id, cid, "list_projects", _iso(40))  # outside 7d/30d

    out = await usage_service.usage(owner_id, "7d")
    assert out["tool_calls_total"] == 3
    counts = {t["tool_name"]: t["count"] for t in out["tool_calls_by_name"]}
    assert counts == {"list_projects": 2, "create_objective": 1}

    assert (await usage_service.usage(owner_id, "all"))["tool_calls_total"] == 4


async def test_cost_sum_and_cost_known(owner_id):
    cid = await _conv(owner_id)
    # 1M prompt + 1M completion on gpt-4o-mini => 0.15 + 0.60 = 0.75
    await _assistant_msg(owner_id, cid, "gpt-4o-mini", 1_000_000, 1_000_000, _iso(1))
    priced = await usage_service.usage(owner_id, "7d")
    assert priced["estimated_cost_usd"] == 0.75
    assert priced["cost_known"] is True

    await _assistant_msg(owner_id, cid, "some-unpriced-model", 100, 100, _iso(1))
    mixed = await usage_service.usage(owner_id, "7d")
    assert mixed["cost_known"] is False
    assert mixed["estimated_cost_usd"] == 0.75  # priced portion still counted


async def test_empty_window_is_zeroed_and_cost_known(owner_id):
    out = await usage_service.usage(owner_id, "7d")
    assert out["tokens"] == {"prompt": 0, "completion": 0, "total": 0}
    assert out["by_day"] == [] and out["by_model"] == [] and out["by_conversation"] == []
    assert out["tool_calls_total"] == 0
    assert out["estimated_cost_usd"] == 0.0
    assert out["cost_known"] is True


def test_rates_table_shape():
    assert usage_service.RATES
    for name, rate in usage_service.RATES.items():
        assert isinstance(name, str)
        assert isinstance(rate, tuple) and len(rate) == 2
        assert all(isinstance(x, (int, float)) for x in rate)
    assert usage_service.RATES["openai/gpt-oss-120b"] == (0.0, 0.0)
