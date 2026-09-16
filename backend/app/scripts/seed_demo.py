"""Seed one demo user with hardcoded, deterministic dummy data for the public showcase.

Run inside the container: docker compose exec api python -m app.scripts.seed_demo
Or locally from backend/: python -m app.scripts.seed_demo

Safe to re-run: wipes and reinserts only this fixed demo user's own rows.
"""

from __future__ import annotations

import asyncio
import json

from app.core.security import hash_password
from app.db import client
from app.db.client import new_id, utcnow_iso
from app.services import users

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "DemoPass123"

_USER_SCOPED_TABLES = [
    "reflections",
    "journal_entries",
    "entity_links",
    "tool_invocations",
    "messages",
    "conversations",
    "actions",
    "objectives",
    "projects",
    "context_entries",
    "onboarding_state",
    "onboarding_responses",
    "style_samples",
    "style_guide",
    "focus_snapshots",
    "refresh_tokens",
]


async def _wipe_existing(user_id: str) -> None:
    for table in _USER_SCOPED_TABLES:
        await client.db_execute(f"DELETE FROM {table} WHERE user_id = ?", [user_id])
    await client.db_execute("DELETE FROM users WHERE id = ?", [user_id])


async def run() -> None:
    existing = await users.get_user_by_email(DEMO_EMAIL)
    if existing is not None:
        await _wipe_existing(existing["id"])

    user = await users.create_user(DEMO_EMAIL, hash_password(DEMO_PASSWORD))
    user_id = user["id"]
    now = utcnow_iso()

    await client.db_execute(
        "INSERT INTO onboarding_state (user_id, completed_at, version) VALUES (?, ?, 1)",
        [user_id, now],
    )

    # --- Projects ---------------------------------------------------------
    project_ids: dict[str, str] = {}
    projects = [
        ("hadi-os", "Personal assistant system with a chat core, dashboard, knowledge graph, "
                    "and journal.", "active", ["FastAPI", "React", "Turso"],
         "Wire up the scheduled-jobs framework."),
        ("rust-cli-toolbox", "A growing collection of small CLI utilities, written to actually "
                              "learn Rust instead of just reading about it.", "active", ["Rust"],
         "Add a JSON-diff subcommand."),
        ("Recipe Sharing App", "A community recipe sharing platform, shipped as a weekend "
                                "project.", "shipped", ["Next.js", "PostgreSQL"], ""),
        ("Portfolio Site", "Personal portfolio and blog.", "paused", ["Astro", "Tailwind"], ""),
        ("ML Experiment Tracker", "A small training-run logger, retired in favor of an "
                                   "off-the-shelf tracker.", "archived", ["Python", "SQLite"], ""),
    ]
    for name, summary, status, tech, next_steps in projects:
        pid = new_id()
        project_ids[name] = pid
        await client.db_execute(
            "INSERT INTO projects (id, user_id, name, summary, status, tech, repo_path, "
            "repo_url, next_steps, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, '', ?, ?)",
            [pid, user_id, name, summary, status, json.dumps(tech), next_steps, now, now],
        )

    # --- Objectives ---------------------------------------------------------
    objective_ids: dict[str, str] = {}
    objectives = [
        ("Ship hadi-os Phase 3", "Get automations & integrations to a usable slice.",
         "quarter", 1, ["hadi-os", "backend"], "hadi-os"),
        ("Learn Rust for systems work", "Build real muscle memory, not just tutorial-following.",
         "year", 2, ["learning", "rust"], "rust-cli-toolbox"),
        ("Get the recipe app to 5K MRR", "Grow it from a weekend project into real revenue.",
         "quarter", 1, ["business"], None),
        ("Read 12 technical books this year", "Deliberate, not incidental, reading.",
         "year", 3, ["reading", "growth"], None),
    ]
    for title, description, horizon, priority, tags, project_name in objectives:
        oid = new_id()
        objective_ids[title] = oid
        project_id = project_ids.get(project_name) if project_name else None
        await client.db_execute(
            "INSERT INTO objectives (id, user_id, title, description, horizon, target_date, "
            "status, priority, tags, project_id, created_at, updated_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, 'active', ?, ?, ?, ?, ?, NULL)",
            [oid, user_id, title, description, horizon, priority, json.dumps(tags),
             project_id, now, now],
        )

    # --- Actions ---------------------------------------------------------
    actions = [
        ("Ship hadi-os Phase 3", "Design the scheduled-jobs table", "doing", None),
        ("Ship hadi-os Phase 3", "Write the daily briefing generator", "todo", None),
        ("Learn Rust for systems work", "Finish chapters 5-8 of the Rust book", "doing", None),
        ("Learn Rust for systems work", "Build a CLI todo app in Rust", "todo", None),
        ("Get the recipe app to 5K MRR", "Launch the new landing page", "done", now),
        ("Read 12 technical books this year",
         "Finish 'Designing Data-Intensive Applications'", "doing", None),
    ]
    for objective_title, title, status, completed_at in actions:
        await client.db_execute(
            "INSERT INTO actions (id, user_id, objective_id, title, status, notes, due_date, "
            "source, created_at, updated_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, '', NULL, 'manual', ?, ?, ?)",
            [new_id(), user_id, objective_ids[objective_title], title, status, now, now,
             completed_at],
        )

    # --- Context entries ---------------------------------------------------
    context_entries = [
        ("identity", "role", "Backend-leaning full-stack engineer, ships side projects on "
                              "weekends."),
        ("preference", "communication_style", "Direct and concise. Skip the preamble."),
        ("working_style", "focus_hours", "Deepest focus 9am-1pm; keep meetings out of that "
                                          "window."),
        ("goal_context", "current_priority", "hadi-os Phase 3 is the main focus this quarter."),
        ("project_context", "recipe_app_stack", "Next.js frontend, Postgres + Prisma backend."),
    ]
    for category, key, value in context_entries:
        await client.db_execute(
            "INSERT INTO context_entries (id, user_id, category, key, value, source, pinned, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'manual', 0, 'active', ?, ?)",
            [new_id(), user_id, category, key, value, now, now],
        )

    # --- Conversations + messages ---------------------------------------------------
    conversations = [
        ("Phase 3 planning", [
            ("user", "What should I tackle first for Phase 3?"),
            ("assistant", "Start with the scheduled-jobs framework — the daily/weekly "
                          "briefings and calendar reminders both depend on it."),
        ]),
        ("Rust learning check-in", [
            ("user", "I keep bouncing off the borrow checker on this CLI project."),
            ("assistant", "That's normal around chapter 4-6. Try writing the ownership on "
                          "paper before you write the function signature."),
        ]),
    ]
    for title, turns in conversations:
        cid = new_id()
        await client.db_execute(
            "INSERT INTO conversations (id, user_id, title, archived, created_at, updated_at, "
            "last_message_at) VALUES (?, ?, ?, 0, ?, ?, ?)",
            [cid, user_id, title, now, now, now],
        )
        for role, text in turns:
            usage_json = (
                json.dumps({"prompt_tokens": 180, "completion_tokens": 60, "total_tokens": 240})
                if role == "assistant"
                else None
            )
            await client.db_execute(
                "INSERT INTO messages (id, conversation_id, user_id, role, text, blocks_json, "
                "model, usage_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    new_id(), cid, user_id, role, text,
                    json.dumps({"role": role, "content": text}),
                    "openai/gpt-oss-120b" if role == "assistant" else None,
                    usage_json,
                    now,
                ],
            )

    # --- Journal entries ---------------------------------------------------
    journal_ids: dict[str, str] = {}
    journal_entries = [
        ("Good focus day", "Got the graph node cap tuned and actually enjoyed the debugging. "
                            "Momentum is real when the scope is this tight.", "good",
         ["hadi-os", "focus"], "Ship hadi-os Phase 3"),
        ("Rust is humbling", "Third rewrite of the same function today because of lifetimes. "
                              "Slow going but it's sticking better than last time I tried to "
                              "learn this from a book alone.", "flat", ["rust", "learning"],
         "Learn Rust for systems work"),
        ("Low-energy Tuesday", "Didn't get much done. Pushed the landing page copy by a day.",
         "low", ["recipe-app"], "Get the recipe app to 5K MRR"),
        ("Good conversation with a mentor", "Talked through the Phase 3 scope over coffee. Cut "
                                             "two features that weren't earning their keep.",
         "energised", ["hadi-os", "mentorship"], None),
        ("Reading streak", "Finished another chapter of DDIA on the train. The chapter on "
                            "replication finally clicked.", "good", ["reading"], None),
        ("Burnt out by Friday", "Long week. Taking the weekend fully off from all of this.",
         "drained", ["reflection"], None),
    ]
    for title, body, mood, tags, objective_title in journal_entries:
        jid = new_id()
        journal_ids[title] = jid
        linked_objective_id = objective_ids.get(objective_title) if objective_title else None
        await client.db_execute(
            "INSERT INTO journal_entries (id, user_id, title, body, mood, tags, "
            "linked_objective_id, linked_project_id, learn_from_style, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, ?, ?)",
            [jid, user_id, title, body, mood, json.dumps(tags), linked_objective_id, now, now],
        )

    # --- Reflections ---------------------------------------------------
    reflections = [
        ("momentum", "Steady progress on 'Ship hadi-os Phase 3' — 2 of 3 tracked actions "
                      "moved to doing/done in the last week.",
         {"objective_id": objective_ids["Ship hadi-os Phase 3"], "window_days": 30}),
        ("theme", "'focus' and 'learning' show up across several recent journal entries — "
                   "worth naming as an explicit priority.",
         {"terms": ["focus", "learning"], "window_days": 30}),
        ("drift", "'Get the recipe app to 5K MRR' was mentioned in 2 recent journal entries "
                   "with no linked action progress.",
         {"objective_id": objective_ids["Get the recipe app to 5K MRR"]}),
    ]
    for kind, body, evidence in reflections:
        await client.db_execute(
            "INSERT INTO reflections (id, user_id, kind, body, evidence_json, status, "
            "created_at) VALUES (?, ?, ?, ?, ?, 'active', ?)",
            [new_id(), user_id, kind, body, json.dumps(evidence), now],
        )

    # --- Entity links (so the knowledge graph renders connected) ---------------------
    links = [
        ("journal", journal_ids["Good focus day"], "objective",
         objective_ids["Ship hadi-os Phase 3"], "related"),
        ("journal", journal_ids["Rust is humbling"], "objective",
         objective_ids["Learn Rust for systems work"], "related"),
        ("project", project_ids["hadi-os"], "objective",
         objective_ids["Ship hadi-os Phase 3"], "related"),
    ]
    for from_type, from_id, to_type, to_id, kind in links:
        await client.db_execute(
            "INSERT OR IGNORE INTO entity_links (id, user_id, from_type, from_id, to_type, "
            "to_id, kind, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [new_id(), user_id, from_type, from_id, to_type, to_id, kind, now],
        )

    print(f"Seeded demo user {DEMO_EMAIL!r} (id={user_id}) with sample data.")
    print(f"Log in with email={DEMO_EMAIL!r} password={DEMO_PASSWORD!r}")


def main() -> None:
    async def _main() -> None:
        await run()
        await client.close_client()

    asyncio.run(_main())


if __name__ == "__main__":
    main()
