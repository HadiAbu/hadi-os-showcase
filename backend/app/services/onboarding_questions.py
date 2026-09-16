"""The fixed onboarding question bank (design.md § 7).

Defined in code, not the database, so copy changes need no migration. ``id`` is
stable — the submit handler maps by ``id``.
"""

from __future__ import annotations

QUESTIONS: list[dict] = [
    {"id": "identity_name", "type": "text", "prompt": "What should I call you?"},
    {"id": "identity_role", "type": "text", "prompt": "What's your current role or title?"},
    {
        "id": "identity_experience",
        "type": "long_text",
        "prompt": "Briefly — your experience as an engineer so far.",
    },
    {
        "id": "style_tone",
        "type": "multi_select",
        "prompt": "How should I sound when I write to you?",
        "options": ["direct", "warm", "terse", "playful", "formal", "plain"],
    },
    {
        "id": "style_samples",
        "type": "repeatable",
        "prompt": "Paste a few things you've written — emails, messages, notes.",
    },
    {
        "id": "working_hours",
        "type": "text",
        "prompt": "When do you usually do focused work?",
    },
    {
        "id": "objective_current",
        "type": "repeatable",
        "prompt": "What are you working toward right now? One objective per entry.",
    },
    {
        "id": "project_current",
        "type": "repeatable",
        "prompt": "Which software projects are active? One per entry.",
    },
    {
        "id": "growth_focus",
        "type": "long_text",
        "prompt": "Where do you most want to grow as an engineer?",
    },
    {
        "id": "free_goal",
        "type": "long_text",
        "prompt": "Anything else about what you're trying to achieve?",
    },
]

QUESTION_IDS = {q["id"] for q in QUESTIONS}
