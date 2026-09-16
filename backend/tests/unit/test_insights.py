"""R0 task 0.1 — insights.compute_signals (deterministic, no LLM)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import client
from app.db.client import new_id
from app.services import insights, llm_client, objectives_store


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


async def _obj(user_id: str, title: str, *, tags: list[str] | None = None) -> str:
    row = await objectives_store.create_objective(
        user_id, {"title": title, "horizon": "quarter", "tags": tags or []}
    )
    return row["id"]


async def _action(user_id: str, objective_id: str, *, created: float = 1, completed: float | None = None) -> None:
    await client.db_execute(
        "INSERT INTO actions "
        "(id, user_id, objective_id, title, status, notes, due_date, source, "
        "created_at, updated_at, completed_at) "
        "VALUES (?, ?, ?, 'a', ?, '', NULL, 'manual', ?, ?, ?)",
        [
            new_id(),
            user_id,
            objective_id,
            "done" if completed is not None else "todo",
            _iso(created),
            _iso(created),
            _iso(completed) if completed is not None else None,
        ],
    )


async def _entry(user_id: str, body: str, *, created: float = 1, title: str = "") -> str:
    entry_id = new_id()
    await client.db_execute(
        "INSERT INTO journal_entries "
        "(id, user_id, title, body, mood, tags, linked_objective_id, linked_project_id, "
        "learn_from_style, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, '', '[]', NULL, NULL, 1, ?, ?)",
        [entry_id, user_id, title, body, _iso(created), _iso(created)],
    )
    return entry_id


def _by_obj(items: list[dict]) -> dict[str, dict]:
    return {i["objective_id"]: i for i in items}


async def test_momentum_windows_and_stall(owner_id):
    a = await _obj(owner_id, "Fresh")
    b = await _obj(owner_id, "Old")
    c = await _obj(owner_id, "Untouched")
    await _action(owner_id, a, completed=5)
    await _action(owner_id, b, completed=40)

    m = _by_obj((await insights.compute_signals(owner_id))["momentum"])
    assert m[a] == {"objective_id": a, "title": "Fresh", "done_30d": 1, "done_60d": 1, "stalled": False}
    assert m[b]["done_30d"] == 0 and m[b]["done_60d"] == 1 and m[b]["stalled"] is True
    assert m[c]["done_30d"] == 0 and m[c]["done_60d"] == 0 and m[c]["stalled"] is True


async def test_drift_fires_only_on_repeated_mention_without_progress(owner_id):
    drifting = await _obj(owner_id, "Learn Rust")
    once = await _obj(owner_id, "Study Kafka")
    progressing = await _obj(owner_id, "Ship docs")

    e1 = await _entry(owner_id, "Spent an hour on Learn Rust today.", created=3)
    e2 = await _entry(owner_id, "Learn Rust is slower going than hoped.", created=10)
    await _entry(owner_id, "A note about Study Kafka, just once.", created=5)
    await _entry(owner_id, "Ship docs keeps coming up.", created=4)
    await _entry(owner_id, "More on Ship docs.", created=6)
    await _action(owner_id, progressing, created=8)  # new action -> not drift

    drift = {d["objective_id"]: d for d in (await insights.compute_signals(owner_id))["drift"]}
    assert set(drift) == {drifting}
    assert set(drift[drifting]["journal_entry_ids"]) == {e1, e2}
    assert drift[drifting]["mentions_30d"] == 2
    assert once not in drift and progressing not in drift


async def test_themes_count_filter_and_prior_window(owner_id):
    await _entry(owner_id, "distributed systems again. distributed systems everywhere.", created=2)
    await _entry(owner_id, "thinking about distributed systems and consensus.", created=9)
    await _entry(owner_id, "distributed systems were the theme last month too.", created=45)

    themes = {t["term"]: t for t in (await insights.compute_signals(owner_id))["themes"]}
    assert "distributed systems" in themes
    ds = themes["distributed systems"]
    assert ds["count_30d"] == 3  # 2 + 1 occurrences in the last 30 days
    assert ds["count_prev_30d"] == 1  # the 45-day-old entry
    assert len(ds["journal_entry_ids"]) == 2
    # stopwords / short tokens excluded
    assert "and" not in themes and "the" not in themes


async def test_counts_and_empty_input(owner_id):
    empty = await insights.compute_signals(owner_id)
    assert empty["momentum"] == [] and empty["drift"] == [] and empty["themes"] == []
    assert empty["counts"] == {"entries_30d": 0, "active_objectives": 0}

    await _obj(owner_id, "O")
    await _entry(owner_id, "one entry", created=2)
    await _entry(owner_id, "old entry", created=40)
    filled = await insights.compute_signals(owner_id)
    assert filled["counts"] == {"entries_30d": 1, "active_objectives": 1}


# --- generate (R1) ---------------------------------------------


async def _rows(user_id: str) -> list[dict]:
    return await client.db_execute(
        "SELECT * FROM reflections WHERE user_id = ? ORDER BY created_at, id", [user_id]
    )


async def test_generate_empty_input_returns_reason_and_writes_nothing(owner_id):
    out = await insights.generate(owner_id)
    assert out["reflections"] == []
    assert out["reason"] and "nothing" in out["reason"].lower()
    assert await _rows(owner_id) == []


async def test_generate_templated_without_a_key(owner_id, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)
    drifting = await _obj(owner_id, "Learn Rust")
    await _entry(owner_id, "Learn Rust again today.", created=2)
    await _entry(owner_id, "Still stuck on Learn Rust.", created=6)
    await _entry(owner_id, "distributed systems distributed systems.", created=3)

    out = await insights.generate(owner_id)
    kinds = {r["kind"] for r in out["reflections"]}
    assert kinds == {"momentum", "drift", "theme"}
    assert out["reason"] is None
    assert len(await _rows(owner_id)) == len(out["reflections"])
    drift = next(r for r in out["reflections"] if r["kind"] == "drift")
    assert drifting in drift["evidence"]["objective_ids"]


async def test_generate_uses_the_llm_when_available(owner_id, monkeypatch):
    async def fake_extract_json(*, system, user, **kwargs):
        assert "momentum" in user  # the signal payload is passed through
        return {
            "reflections": [
                {"kind": "momentum", "body": "You kept 'Ship it' moving.",
                 "evidence": {"objective_ids": ["o1"]}},
                {"kind": "theme", "body": "Consensus keeps coming up.", "evidence": {}},
            ]
        }

    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "extract_json", fake_extract_json)
    await _obj(owner_id, "Ship it")
    await _entry(owner_id, "notes on consensus", created=2)

    out = await insights.generate(owner_id)
    assert [r["body"] for r in out["reflections"]] == [
        "You kept 'Ship it' moving.",
        "Consensus keeps coming up.",
    ]
    assert out["reflections"][0]["evidence"] == {"objective_ids": ["o1"]}
    assert len(await _rows(owner_id)) == 2


async def test_generate_falls_back_to_templated_on_bad_llm_output(owner_id, monkeypatch):
    async def broken(*, system, user, **kwargs):
        raise ValueError("no JSON object in model response")

    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "extract_json", broken)
    await _obj(owner_id, "O")
    await _entry(owner_id, "an entry", created=2)

    out = await insights.generate(owner_id)
    assert out["reflections"] and out["reason"] is None
    assert all(r["kind"] in ("momentum", "drift", "theme") for r in out["reflections"])


async def test_list_and_status_lifecycle(owner_id, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)
    await _obj(owner_id, "O")
    await _entry(owner_id, "an entry", created=2)
    generated = (await insights.generate(owner_id))["reflections"]
    rid = generated[0]["id"]

    assert {r["id"] for r in await insights.list_reflections(owner_id)} == {
        r["id"] for r in generated
    }

    await insights.set_reflection_status(owner_id, rid, "dismissed")
    remaining = {r["id"] for r in await insights.list_reflections(owner_id)}
    assert rid not in remaining
    assert rid in {r["id"] for r in await insights.list_reflections(owner_id, "dismissed")}

    assert await insights.set_reflection_status(owner_id, "nope", "pinned") is None
