"""Builds the ``system`` prompt string for a chat turn (REQ-11, REQ-25).

The stable portion — base instructions, ``<about_me>``, ``<writing_style>``,
``<objectives>``, ``<projects>`` — comes first and must be byte-identical between
turns when no underlying record changed (deterministic ordering, nothing
time-varying). OpenAI-compatible providers cache a stable prefix automatically,
so keeping it stable still pays off. The current time is appended last.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db import client

BASE_SYSTEM_PROMPT = (
    "You are hadi-os, a personal assistant for one person (referred to below as "
    '"the owner"). Your focus is the owner\'s software projects and growth as an '
    "engineer. You hold durable context about them and use it to give specific, "
    "grounded help and to keep them oriented toward their objectives.\n\n"
    "Guidelines:\n"
    "- Ground every answer in the context below. If something needed is missing, "
    "ask or say so — do not invent facts about the owner.\n"
    "- Match the tone and phrasing described in <writing_style> in your prose "
    "responses only. Never mimic that style in code, lists, tables, or other "
    "structured output.\n"
    "- When the owner tells you something worth remembering about themselves, use "
    "the context tools to propose it. Proposed entries require the owner's "
    "confirmation before they take effect.\n"
    "- Be concise. Prefer concrete next actions over general advice."
)

_OPEN_ACTION_STATUSES = ("todo", "doing")

# Prompt-size caps. Providers (Groq free tier especially) count the whole
# request toward a per-minute token budget, so the system prompt must stay
# bounded as the owner's records accumulate. Pinned context entries are always
# included; everything else is capped by recency.
_MAX_CONTEXT_ENTRIES = 40
_MAX_ENTRY_VALUE_CHARS = 300
_MAX_STYLE_GUIDE_CHARS = 1500
_MAX_OBJECTIVES = 20
_MAX_ACTIONS_PER_OBJECTIVE = 6
_MAX_PROJECTS = 12
_MAX_PROJECT_TEXT_CHARS = 240


def _clip(text: str, limit: int) -> str:
    """Trim to at most ``limit`` characters, ellipsis included."""
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(t) for t in value] if isinstance(value, list) else []


async def _render_about_me(user_id: str) -> str:
    # pinned first, then newest-created (created_at never changes, so the
    # kept set is insensitive to unrelated edits — the prefix only shifts
    # when entries are added or archived, same as before the cap).
    rows = await client.db_execute(
        "SELECT category, key, value, pinned FROM context_entries "
        "WHERE user_id = ? AND status = 'active' "
        "ORDER BY pinned DESC, created_at DESC, category, key",
        [user_id],
    )
    if not rows:
        return "<about_me>\n(nothing recorded yet)\n</about_me>"

    kept: list[dict] = []
    for r in rows:
        if r["pinned"] or len(kept) < _MAX_CONTEXT_ENTRIES:
            kept.append(r)
    dropped = len(rows) - len(kept)

    # render in a stable, readable order (category/key), not the recency order
    kept.sort(key=lambda r: (r["category"], r["key"]))
    lines = [
        f"- {r['category']}/{r['key']}: {_clip(r['value'], _MAX_ENTRY_VALUE_CHARS)}"
        for r in kept
    ]
    if dropped:
        lines.append(f"- (+{dropped} older entries not shown — ask if you need them)")
    return "<about_me>\n" + "\n".join(lines) + "\n</about_me>"


async def _render_writing_style(user_id: str) -> str:
    rows = await client.db_execute(
        "SELECT guide_md FROM style_guide WHERE user_id = ? LIMIT 1", [user_id]
    )
    guide = (rows[0]["guide_md"].strip() if rows else "")
    if not guide:
        return ""
    return "<writing_style>\n" + _clip(guide, _MAX_STYLE_GUIDE_CHARS) + "\n</writing_style>"


async def _render_objectives(user_id: str) -> str:
    objectives = await client.db_execute(
        "SELECT id, title, horizon, status, priority, tags FROM objectives "
        "WHERE user_id = ? AND status = 'active' ORDER BY priority, created_at, id",
        [user_id],
    )
    if not objectives:
        return "<objectives>\n(none active)\n</objectives>"
    dropped = max(0, len(objectives) - _MAX_OBJECTIVES)
    objectives = objectives[:_MAX_OBJECTIVES]

    lines: list[str] = []
    for obj in objectives:
        tags = _parse_tags(obj.get("tags"))
        tag_note = f" [tags: {', '.join(sorted(tags))}]" if tags else ""
        lines.append(
            f"- [P{obj['priority']}] {obj['title']} ({obj['horizon']}, {obj['status']}){tag_note}"
        )
        actions = await client.db_execute(
            "SELECT title, status, due_date FROM actions "
            "WHERE user_id = ? AND objective_id = ? AND status IN (?, ?) "
            "ORDER BY created_at, id LIMIT ?",
            [user_id, obj["id"], *_OPEN_ACTION_STATUSES, _MAX_ACTIONS_PER_OBJECTIVE + 1],
        )
        for act in actions[:_MAX_ACTIONS_PER_OBJECTIVE]:
            due = f" [due {act['due_date']}]" if act.get("due_date") else ""
            lines.append(f"    - ({act['status']}) {act['title']}{due}")
        if len(actions) > _MAX_ACTIONS_PER_OBJECTIVE:
            lines.append("    - (+ more open actions)")
    if dropped:
        lines.append(f"- (+{dropped} more active objectives, lower priority)")
    return "<objectives>\n" + "\n".join(lines) + "\n</objectives>"


async def _render_projects(user_id: str) -> str:
    projects = await client.db_execute(
        "SELECT name, status, summary, next_steps FROM projects "
        "WHERE user_id = ? AND status IN ('active', 'paused') ORDER BY name, id",
        [user_id],
    )
    if not projects:
        return "<projects>\n(none active)\n</projects>"
    dropped = max(0, len(projects) - _MAX_PROJECTS)
    lines: list[str] = []
    for proj in projects[:_MAX_PROJECTS]:
        summary = (
            f" — {_clip(proj['summary'], _MAX_PROJECT_TEXT_CHARS)}"
            if proj.get("summary")
            else ""
        )
        lines.append(f"- {proj['name']} ({proj['status']}){summary}")
        if proj.get("next_steps"):
            lines.append(f"  next: {_clip(proj['next_steps'], _MAX_PROJECT_TEXT_CHARS)}")
    if dropped:
        lines.append(f"- (+{dropped} more)")
    return "<projects>\n" + "\n".join(lines) + "\n</projects>"


async def build_stable_prefix(user_id: str) -> str:
    """The deterministic, byte-stable part of the system prompt (no timestamps)."""
    sections = [BASE_SYSTEM_PROMPT, await _render_about_me(user_id)]
    writing_style = await _render_writing_style(user_id)
    if writing_style:
        sections.append(writing_style)
    sections.append(await _render_objectives(user_id))
    sections.append(await _render_projects(user_id))
    return "\n\n".join(sections)


async def build_system(user_id: str) -> str:
    """Return the full ``system`` prompt string (stable prefix + current time)."""
    now_utc = datetime.now(timezone.utc)
    local = now_utc.astimezone()
    time_line = (
        f"Current time: {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"(local: {local.strftime('%a %d %b %Y, %H:%M %Z')})"
    )
    return await build_stable_prefix(user_id) + "\n\n" + time_line
