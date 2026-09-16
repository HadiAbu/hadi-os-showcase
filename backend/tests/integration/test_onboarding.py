"""Tasks 4.1-4.3 — onboarding state, questions, submit (REQ-5, REQ-6, REQ-7)."""

from __future__ import annotations

import pytest

from app.services import llm_client

ANSWERS = [
    {"question_id": "identity_name", "value": "Hadi"},
    {"question_id": "identity_role", "value": "backend engineer"},
    {"question_id": "style_tone", "value": ["direct", "terse"]},
    {"question_id": "working_hours", "value": "mornings"},
    {"question_id": "growth_focus", "value": "distributed systems"},
    {"question_id": "objective_current", "value": ["Ship hadi-os Phase 1", "Learn Rust"]},
    {"question_id": "project_current", "value": ["hadi-os"]},
    {"question_id": "free_goal", "value": "Become a strong staff engineer"},
]
SAMPLES = [{"text": "hey — quick one, can you check the PR?", "label": "slack"}]


async def test_state_starts_incomplete_and_questions_served(auth_client):
    state = await auth_client.get("/api/onboarding/state")
    assert state.json() == {"completed": False, "completed_at": None}

    qs = (await auth_client.get("/api/onboarding/questions")).json()
    ids = [q["id"] for q in qs]
    assert "free_goal" in ids and "style_samples" in ids
    tone = next(q for q in qs if q["id"] == "style_tone")
    assert tone["type"] == "multi_select" and "direct" in tone["options"]


async def test_submit_structured_without_ai(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)

    r = await auth_client.post(
        "/api/onboarding/submit", json={"answers": ANSWERS, "samples": SAMPLES}
    )
    assert r.status_code == 200
    assert r.json()["enrichment"] == "skipped"

    assert (await auth_client.get("/api/onboarding/state")).json()["completed"] is True

    entries = (await auth_client.get("/api/context/entries?status=active")).json()
    by_key = {(e["category"], e["key"]): e["value"] for e in entries}
    assert by_key[("identity", "name")] == "Hadi"
    assert by_key[("working_style", "preferred_tone")] == "direct, terse"
    assert by_key[("goal_context", "growth_focus")] == "distributed systems"

    objectives = (await auth_client.get("/api/objectives")).json()
    assert {o["title"] for o in objectives} == {"Ship hadi-os Phase 1", "Learn Rust"}
    assert (await auth_client.get("/api/projects")).json()[0]["name"] == "hadi-os"

    assert (await auth_client.get("/api/context/style-samples")).json()[0]["label"] == "slack"


async def test_submit_with_ai_enrichment(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: True)

    async def fake_extract(**_kwargs):
        return {
            "facts": [{"category": "preference", "key": "editor", "value": "neovim"}],
            "style_guide": "Terse. Dry. Lowercase.",
        }

    monkeypatch.setattr(llm_client, "extract_json", fake_extract)

    r = await auth_client.post(
        "/api/onboarding/submit", json={"answers": ANSWERS, "samples": SAMPLES}
    )
    assert r.json()["enrichment"] == "done"

    review = (await auth_client.get("/api/context/review")).json()
    assert any(e["key"] == "editor" and e["value"] == "neovim" for e in review)
    # proposed => not in the active set
    active = (await auth_client.get("/api/context/entries?status=active")).json()
    assert not any(e["key"] == "editor" for e in active)

    assert (await auth_client.get("/api/context/style-guide")).json()["guide_md"] == (
        "Terse. Dry. Lowercase."
    )


async def test_submit_ai_error_still_completes(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: True)

    async def boom(**_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(llm_client, "extract_json", boom)

    r = await auth_client.post(
        "/api/onboarding/submit", json={"answers": ANSWERS, "samples": SAMPLES}
    )
    assert r.status_code == 200
    assert r.json()["enrichment"] == "error"
    assert (await auth_client.get("/api/onboarding/state")).json()["completed"] is True
    # structured seeding still happened
    objectives = (await auth_client.get("/api/objectives")).json()
    assert len(objectives) == 2


async def test_rerun_does_not_duplicate(auth_client, monkeypatch):
    monkeypatch.setattr(llm_client, "available", lambda: False)
    payload = {"answers": ANSWERS, "samples": []}
    await auth_client.post("/api/onboarding/submit", json=payload)
    await auth_client.post("/api/onboarding/submit", json=payload)

    objectives = (await auth_client.get("/api/objectives")).json()
    assert [o["title"] for o in objectives].count("Learn Rust") == 1
    assert len((await auth_client.get("/api/projects")).json()) == 1
    # natural-key upsert keeps context entries unique too
    entries = (await auth_client.get("/api/context/entries?status=active")).json()
    assert [(e["category"], e["key"]) for e in entries].count(("identity", "name")) == 1


@pytest.mark.parametrize("path", ["/api/onboarding/state"])
async def test_requires_auth(client, path):
    assert (await client.get(path)).status_code == 401
