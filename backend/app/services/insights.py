"""Reflection signals + generation (Phase 2.5, REQ-7/8).

``compute_signals`` is pure SQL + Python — momentum / drift / themes over the
journal and objective progress, no LLM. ``generate`` (R1) turns a signal set into
stored ``reflections`` rows, LLM-voiced when a key is set and templated otherwise.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import client
from app.db.client import new_id
from app.models.reflections import BODY_MAX
from app.services import llm_client, style
from app.services._stopwords import STOPWORDS

_WORD = re.compile(r"[a-z0-9']+")

WINDOW_DAYS = 30
DRIFT_MIN_MENTIONS = 2
MOMENTUM_STALL_DAYS = 21
THEME_TOP_N = 8
THEME_MIN_LEN = 3
_MAX_THEME_ENTRY_IDS = 5
REFLECTION_MAX = 5
_EMPTY_REASON = "nothing to reflect on yet — write an entry or add an objective"


def _days_ago_iso(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in _WORD.findall(text.lower())
        if len(t) >= THEME_MIN_LEN and t not in STOPWORDS
    ]


def _count_grams(rows: list[dict]) -> tuple[Counter, dict[str, set[str]]]:
    counts: Counter = Counter()
    term_entries: dict[str, set[str]] = {}
    for row in rows:
        toks = _tokens(row.get("body", ""))
        for i, tok in enumerate(toks):
            grams = [tok] + ([f"{toks[i - 1]} {tok}"] if i else [])
            for gram in grams:
                counts[gram] += 1
                term_entries.setdefault(gram, set()).add(row["id"])
    return counts, term_entries


async def _count(sql: str, params: list[Any]) -> int:
    rows = await client.db_execute(sql, params)
    return int(rows[0]["c"]) if rows else 0


async def compute_signals(user_id: str) -> dict[str, Any]:
    d30, d60, d21 = _days_ago_iso(30), _days_ago_iso(60), _days_ago_iso(MOMENTUM_STALL_DAYS)

    objectives = await client.db_execute(
        "SELECT id, title, tags FROM objectives WHERE user_id = ? AND status = 'active'",
        [user_id],
    )
    entries_30d = await client.db_execute(
        "SELECT id, title, body, created_at FROM journal_entries "
        "WHERE user_id = ? AND created_at >= ? AND TRIM(body) != ''",
        [user_id, d30],
    )
    entries_prev = await client.db_execute(
        "SELECT id, body FROM journal_entries "
        "WHERE user_id = ? AND created_at >= ? AND created_at < ? AND TRIM(body) != ''",
        [user_id, d60, d30],
    )

    momentum: list[dict] = []
    drift: list[dict] = []
    for obj in objectives:
        try:
            tags = json.loads(obj["tags"]) if obj["tags"] else []
        except (TypeError, ValueError):
            tags = []
        done_30d = await _count(
            "SELECT COUNT(*) c FROM actions WHERE user_id = ? AND objective_id = ? "
            "AND completed_at IS NOT NULL AND completed_at >= ?",
            [user_id, obj["id"], d30],
        )
        done_60d = await _count(
            "SELECT COUNT(*) c FROM actions WHERE user_id = ? AND objective_id = ? "
            "AND completed_at IS NOT NULL AND completed_at >= ?",
            [user_id, obj["id"], d60],
        )
        done_recent = await _count(
            "SELECT COUNT(*) c FROM actions WHERE user_id = ? AND objective_id = ? "
            "AND completed_at IS NOT NULL AND completed_at >= ?",
            [user_id, obj["id"], d21],
        )
        new_actions_30d = await _count(
            "SELECT COUNT(*) c FROM actions WHERE user_id = ? AND objective_id = ? "
            "AND created_at >= ?",
            [user_id, obj["id"], d30],
        )
        momentum.append(
            {
                "objective_id": obj["id"],
                "title": obj["title"],
                "done_30d": done_30d,
                "done_60d": done_60d,
                "stalled": done_recent == 0,
            }
        )

        needles = [obj["title"].lower(), *[t.lower() for t in tags if t]]
        patterns = [re.compile(r"\b" + re.escape(n) + r"\b") for n in needles if n]
        hit_ids: list[str] = []
        for entry in entries_30d:
            hay = f"{entry['title']} {entry['body']}".lower()
            if any(p.search(hay) for p in patterns):
                hit_ids.append(entry["id"])
        distinct_hits = list(dict.fromkeys(hit_ids))
        if (
            len(distinct_hits) >= DRIFT_MIN_MENTIONS
            and done_30d == 0
            and new_actions_30d == 0
        ):
            drift.append(
                {
                    "objective_id": obj["id"],
                    "title": obj["title"],
                    "journal_entry_ids": distinct_hits,
                    "mentions_30d": len(distinct_hits),
                }
            )

    counts_30d, term_entries = _count_grams(entries_30d)
    counts_prev, _ = _count_grams(entries_prev)
    themes = [
        {
            "term": term,
            "count_30d": count,
            "count_prev_30d": counts_prev.get(term, 0),
            "journal_entry_ids": list(term_entries.get(term, set()))[:_MAX_THEME_ENTRY_IDS],
        }
        for term, count in counts_30d.most_common(THEME_TOP_N)
    ]

    return {
        "generated_at": _days_ago_iso(0),
        "momentum": momentum,
        "drift": drift,
        "themes": themes,
        "counts": {
            "entries_30d": len(entries_30d),
            "active_objectives": len(objectives),
        },
    }


# --- generation (R1) ---------------------------------------------


def _momentum_body(items: list[dict]) -> str:
    movers = [i for i in items if i["done_30d"] > 0]
    stalled = [i for i in items if i["stalled"]]
    parts: list[str] = []
    if movers:
        top = max(movers, key=lambda i: i["done_30d"])
        parts.append(f"{top['done_30d']} actions done on '{top['title']}' in the last 30 days")
    if stalled:
        parts.append(f"'{stalled[0]['title']}' hasn't moved in three weeks")
    if not parts:
        parts.append("no action progress on your objectives in the last 30 days")
    return "; ".join(parts) + "."


def _templated(signals: dict[str, Any]) -> list[dict]:
    out: list[dict] = []
    if signals["momentum"]:
        out.append(
            {
                "kind": "momentum",
                "body": _momentum_body(signals["momentum"]),
                "evidence": {"objective_ids": [m["objective_id"] for m in signals["momentum"]]},
            }
        )
    if signals["drift"]:
        top = max(signals["drift"], key=lambda d: d["mentions_30d"])
        out.append(
            {
                "kind": "drift",
                "body": (
                    f"'{top['title']}' comes up in your journal but hasn't moved — "
                    f"{top['mentions_30d']} mentions, no progress."
                ),
                "evidence": {
                    "objective_ids": [d["objective_id"] for d in signals["drift"]],
                    "journal_entry_ids": top["journal_entry_ids"],
                },
            }
        )
    if signals["themes"]:
        top = signals["themes"][0]
        out.append(
            {
                "kind": "theme",
                "body": (
                    f"'{top['term']}' is recurring — {top['count_30d']} times this month "
                    f"vs {top['count_prev_30d']} the month before."
                ),
                "evidence": {
                    "terms": [t["term"] for t in signals["themes"]],
                    "journal_entry_ids": top["journal_entry_ids"],
                },
            }
        )
    return out


def _validate_llm(payload: Any) -> list[dict]:
    items = payload.get("reflections") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("no reflections in model response")
    out: list[dict] = []
    for item in items:
        kind = item.get("kind")
        body = item.get("body")
        if kind not in ("momentum", "drift", "theme") or not isinstance(body, str) or not body.strip():
            continue
        evidence = item.get("evidence")
        out.append({"kind": kind, "body": body.strip(), "evidence": evidence if isinstance(evidence, dict) else {}})
    if not out:
        raise ValueError("no valid reflections in model response")
    return out


async def _llm_draft(user_id: str, signals: dict[str, Any]) -> list[dict]:
    guide = (await style.get_style_guide(user_id))["guide_md"]
    system = (
        "You write short first-person reflections in the owner's voice about their "
        "recent work — grounded strictly in the signals given, no invention. Return "
        'JSON: {"reflections": [{"kind": "momentum|drift|theme", "body": "<= 60 words", '
        '"evidence": {"objective_ids": [...], "journal_entry_ids": [...], "terms": [...]}}]}. '
        "3 to 5 items, each a different observation."
    )
    if guide:
        system += f"\n\nStyle guide:\n{guide}"
    user = json.dumps(
        {k: signals[k] for k in ("momentum", "drift", "themes", "counts")}, default=str
    )
    return _validate_llm(await llm_client.extract_json(system=system, user=user, max_tokens=900))


async def _draft_reflections(user_id: str, signals: dict[str, Any]) -> list[dict]:
    if llm_client.available():
        try:
            return await _llm_draft(user_id, signals)
        except (ValueError, KeyError, TypeError):
            pass  # fall through to the templated bodies
    return _templated(signals)


def _hydrate(row: dict) -> dict:
    row = dict(row)
    try:
        row["evidence"] = json.loads(row.pop("evidence_json", None) or "{}")
    except (TypeError, ValueError):
        row["evidence"] = {}
    return row


async def generate(user_id: str) -> dict[str, Any]:
    signals = await compute_signals(user_id)
    if signals["counts"]["entries_30d"] == 0 and signals["counts"]["active_objectives"] == 0:
        return {"reflections": [], "reason": _EMPTY_REASON}

    drafts = (await _draft_reflections(user_id, signals))[:REFLECTION_MAX]
    now = _days_ago_iso(0)
    rows: list[dict] = []
    for draft in drafts:
        reflection_id = new_id()
        body = draft["body"][:BODY_MAX]
        evidence = draft.get("evidence") or {}
        await client.db_execute(
            "INSERT INTO reflections "
            "(id, user_id, kind, body, evidence_json, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'active', ?)",
            [reflection_id, user_id, draft["kind"], body, json.dumps(evidence), now],
        )
        rows.append(
            {
                "id": reflection_id,
                "kind": draft["kind"],
                "body": body,
                "evidence": evidence,
                "status": "active",
                "created_at": now,
            }
        )
    return {"reflections": rows, "reason": None}


async def list_reflections(user_id: str, status: str | None = None) -> list[dict]:
    if status:
        rows = await client.db_execute(
            "SELECT * FROM reflections WHERE user_id = ? AND status = ? "
            "ORDER BY created_at DESC, id",
            [user_id, status],
        )
    else:
        rows = await client.db_execute(
            "SELECT * FROM reflections WHERE user_id = ? AND status != 'dismissed' "
            "ORDER BY created_at DESC, id",
            [user_id],
        )
    return [_hydrate(r) for r in rows]


async def set_reflection_status(
    user_id: str, reflection_id: str, status: str
) -> dict | None:
    existing = await client.db_execute(
        "SELECT id FROM reflections WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, reflection_id],
    )
    if not existing:
        return None
    await client.db_execute(
        "UPDATE reflections SET status = ? WHERE user_id = ? AND id = ?",
        [status, user_id, reflection_id],
    )
    rows = await client.db_execute(
        "SELECT * FROM reflections WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, reflection_id],
    )
    return _hydrate(rows[0])
