"""Onboarding: state, and the one-shot submission that seeds the context store
(REQ-5, REQ-7).

Submission is re-runnable: raw answers append, context entries upsert by natural
key, and objectives/projects are only created when a same-titled/-named one does
not already exist.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import client
from app.db.client import new_id, utcnow_iso
from app.services import context_store, llm_client, objectives_store, projects_store, style

# structured answer id -> (context category, key)
_STRUCTURED_MAP: dict[str, tuple[str, str]] = {
    "identity_name": ("identity", "name"),
    "identity_role": ("identity", "role"),
    "identity_experience": ("identity", "experience_summary"),
    "style_tone": ("working_style", "preferred_tone"),
    "working_hours": ("working_style", "working_hours"),
    "growth_focus": ("goal_context", "growth_focus"),
}

_ENRICH_SYSTEM = (
    "You extract structured facts about a software engineer from their onboarding "
    "answers. Reply with ONLY a JSON object of the form "
    '{"facts": [{"category": "...", "key": "...", "value": "..."}], '
    '"style_guide": "..."}. `category` is one of identity, preference, goal_context, '
    "project_context, working_style, misc. Keep facts specific and non-redundant, at "
    "most 8. `style_guide` is a short markdown description of how this person writes "
    "(tone, sentence length, quirks, sign-offs) — empty string if there isn't enough "
    "signal."
)


async def get_state(user_id: str) -> dict:
    rows = await client.db_execute(
        "SELECT completed_at FROM onboarding_state WHERE user_id = ? LIMIT 1", [user_id]
    )
    completed_at = rows[0]["completed_at"] if rows else None
    return {"completed": completed_at is not None, "completed_at": completed_at}


def _as_text(value: Any) -> str:
    return ", ".join(value) if isinstance(value, list) else str(value)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [value.strip()] if isinstance(value, str) and value.strip() else []


async def _store_raw_answers(user_id: str, answers: dict[str, Any]) -> None:
    now = utcnow_iso()
    for question_id, value in answers.items():
        await client.db_execute(
            "INSERT INTO onboarding_responses (id, user_id, question_id, answer, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [new_id(), user_id, question_id, json.dumps(value), now],
        )


async def _seed_structured(user_id: str, answers: dict[str, Any]) -> None:
    for question_id, (category, key) in _STRUCTURED_MAP.items():
        if question_id not in answers:
            continue
        text = _as_text(answers[question_id]).strip()
        if text:
            await context_store.create_entry(
                user_id, category, key, text, source="onboarding", status="active"
            )

    existing_titles = {
        o["title"] for o in await objectives_store.list_objectives(user_id)
    }
    for title in _as_list(answers.get("objective_current")):
        if title not in existing_titles:
            await objectives_store.create_objective(
                user_id, {"title": title, "horizon": "quarter"}
            )

    existing_names = {p["name"] for p in await projects_store.list_projects(user_id)}
    for name in _as_list(answers.get("project_current")):
        if name not in existing_names:
            await projects_store.create_project(user_id, {"name": name})


async def _enrich(user_id: str, answers: dict[str, Any], sample_texts: list[str]) -> str:
    free_goal = _as_text(answers.get("free_goal", "")).strip()
    if not free_goal and not sample_texts:
        return "skipped"
    try:
        payload = await llm_client.extract_json(
            system=_ENRICH_SYSTEM,
            user=f"Free-text goal:\n{free_goal or '(none)'}\n\n"
            f"Writing samples:\n" + ("\n---\n".join(sample_texts) or "(none)"),
        )
        for fact in payload.get("facts", []):
            category, key, value = fact.get("category"), fact.get("key"), fact.get("value")
            if category and key and value:
                await context_store.create_entry(
                    user_id, category, key, str(value), source="onboarding", status="proposed"
                )
        guide = (payload.get("style_guide") or "").strip()
        if guide:
            await style.put_style_guide(user_id, guide)
        return "done"
    except Exception:  # noqa: BLE001 — best-effort; onboarding still completes
        return "error"


async def _mark_complete(user_id: str) -> str:
    now = utcnow_iso()
    existing = await client.db_execute(
        "SELECT user_id FROM onboarding_state WHERE user_id = ? LIMIT 1", [user_id]
    )
    if existing:
        await client.db_execute(
            "UPDATE onboarding_state SET completed_at = ? WHERE user_id = ?", [now, user_id]
        )
    else:
        await client.db_execute(
            "INSERT INTO onboarding_state (user_id, completed_at, version) VALUES (?, ?, 1)",
            [user_id, now],
        )
    return now


async def submit(user_id: str, answers_list: list[dict], samples: list[dict]) -> dict:
    answers = {a["question_id"]: a["value"] for a in answers_list}

    await _store_raw_answers(user_id, answers)
    await _seed_structured(user_id, answers)

    sample_texts: list[str] = []
    for s in samples:
        await style.add_sample(user_id, s["text"], s.get("label"))
        sample_texts.append(s["text"])
    for extra in _as_list(answers.get("style_samples")):
        await style.add_sample(user_id, extra, None)
        sample_texts.append(extra)

    enrichment = "skipped"
    if llm_client.available():
        enrichment = await _enrich(user_id, answers, sample_texts)

    completed_at = await _mark_complete(user_id)
    return {"completed_at": completed_at, "enrichment": enrichment}
