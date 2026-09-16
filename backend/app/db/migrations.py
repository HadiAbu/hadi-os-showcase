"""Database schema.

``run_migrations()`` is called from the FastAPI lifespan on startup. Every
statement is idempotent (``IF NOT EXISTS``) so it is safe to run on every boot.
The DDL is the intersection of SQLite (tests) and libSQL/Turso (prod) syntax:
only ``TEXT``/``INTEGER`` columns, no engine-specific features.

Schema reference: ``.kiro/specs/phase-1-chat-core/design.md`` § 2.
"""

from __future__ import annotations

from app.db import client

# Order matters only for readability — there are no hard FK dependencies enforced
# at create time (FK enforcement is pragma-gated and not relied upon).
_STATEMENTS: list[str] = [
    # --- Auth ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens (token_hash)",
    # --- Context ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS context_entries (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        source TEXT NOT NULL,
        pinned INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (user_id, category, key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_context_entries_user_status "
    "ON context_entries (user_id, status)",
    """
    CREATE TABLE IF NOT EXISTS style_samples (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        text TEXT NOT NULL,
        label TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS style_guide (
        user_id TEXT PRIMARY KEY,
        guide_md TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """,
    # --- Objectives & actions -------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS objectives (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        horizon TEXT NOT NULL,
        target_date TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        priority INTEGER NOT NULL DEFAULT 2,
        tags TEXT NOT NULL DEFAULT '[]',
        project_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_objectives_user_status ON objectives (user_id, status)",
    """
    CREATE TABLE IF NOT EXISTS actions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        objective_id TEXT NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'todo',
        notes TEXT NOT NULL DEFAULT '',
        due_date TEXT,
        source TEXT NOT NULL DEFAULT 'manual',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_actions_user_objective ON actions (user_id, objective_id)",
    # --- Projects -------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        tech TEXT NOT NULL DEFAULT '[]',
        repo_path TEXT,
        repo_url TEXT,
        next_steps TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_projects_user_status ON projects (user_id, status)",
    # --- Chat ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_message_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_conversations_user "
    "ON conversations (user_id, archived, last_message_at)",
    """
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        text TEXT NOT NULL DEFAULT '',
        blocks_json TEXT NOT NULL,
        model TEXT,
        usage_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id, created_at)",
    # --- Onboarding & dashboard ---------------------------------------
    """
    CREATE TABLE IF NOT EXISTS onboarding_responses (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        question_id TEXT NOT NULL,
        answer TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS onboarding_state (
        user_id TEXT PRIMARY KEY,
        completed_at TEXT,
        version INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS focus_snapshots (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        content_md TEXT NOT NULL,
        based_on_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_focus_snapshots_user ON focus_snapshots (user_id, created_at)",
    # --- Telemetry (Phase 2) -----------------------------------------
    # One row per tool call taken in a chat turn, tagged with the assistant
    # tool_use message it belongs to. Written only on the success persist path
    # (phase-2-visual-and-graph/design.md § 3). arguments/result are truncated
    # to 4 KB by the writer.
    """
    CREATE TABLE IF NOT EXISTS tool_invocations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        message_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        arguments_json TEXT NOT NULL,
        result_json TEXT NOT NULL,
        is_error INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tool_invocations_user_created "
    "ON tool_invocations (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tool_invocations_conversation "
    "ON tool_invocations (conversation_id)",
    # User-drawn edges between any two entities, layered onto the derived graph
    # (phase-2-visual-and-graph/design.md § 2, § 4). Natural-key unique so a
    # repeated draw is a no-op.
    """
    CREATE TABLE IF NOT EXISTS entity_links (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        from_type TEXT NOT NULL,
        from_id TEXT NOT NULL,
        to_type TEXT NOT NULL,
        to_id TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'related',
        created_at TEXT NOT NULL,
        UNIQUE (user_id, from_type, from_id, to_type, to_id, kind)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_entity_links_user ON entity_links (user_id)",
    # --- Journal (Phase 2.5) ----------------------------------------
    # Freeform entries. A long entry with learn_from_style set is mirrored into
    # style_samples (label "journal:<id>") by journal_store; entries with a body
    # also appear as `journal` nodes in the knowledge graph
    # (phase-2.5-journal-and-reflections/design.md § 2).
    """
    CREATE TABLE IF NOT EXISTS journal_entries (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        mood TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '[]',
        linked_objective_id TEXT,
        linked_project_id TEXT,
        learn_from_style INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_journal_entries_user "
    "ON journal_entries (user_id, created_at)",
    # Dated reflections generated on demand from journal + objective signals
    # (phase-2.5-journal-and-reflections/design.md § 4). Not idempotent per run —
    # each generate() appends a batch; the default view shows the latest active.
    """
    CREATE TABLE IF NOT EXISTS reflections (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        body TEXT NOT NULL,
        evidence_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_reflections_user "
    "ON reflections (user_id, status, created_at)",
]


async def run_migrations() -> None:
    for statement in _STATEMENTS:
        await client.db_execute(statement)
