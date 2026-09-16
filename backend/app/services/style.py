"""Writing-style guide + samples (REQ-10).

``style_guide`` is one row per user (``user_id`` PK). ``get_style_guide`` returns
an empty default without creating a row; ``put_style_guide`` upserts.
"""

from __future__ import annotations

from app.db import client
from app.db.client import new_id, utcnow_iso


async def get_style_guide(user_id: str) -> dict:
    rows = await client.db_execute(
        "SELECT guide_md, updated_at FROM style_guide WHERE user_id = ? LIMIT 1", [user_id]
    )
    if rows:
        return rows[0]
    return {"guide_md": "", "updated_at": None}


async def put_style_guide(user_id: str, guide_md: str) -> dict:
    now = utcnow_iso()
    existing = await client.db_execute(
        "SELECT user_id FROM style_guide WHERE user_id = ? LIMIT 1", [user_id]
    )
    if existing:
        await client.db_execute(
            "UPDATE style_guide SET guide_md = ?, updated_at = ? WHERE user_id = ?",
            [guide_md, now, user_id],
        )
    else:
        await client.db_execute(
            "INSERT INTO style_guide (user_id, guide_md, updated_at) VALUES (?, ?, ?)",
            [user_id, guide_md, now],
        )
    return {"guide_md": guide_md, "updated_at": now}


async def list_samples(user_id: str) -> list[dict]:
    return await client.db_execute(
        "SELECT id, text, label, created_at FROM style_samples WHERE user_id = ? "
        "ORDER BY created_at",
        [user_id],
    )


async def add_sample(user_id: str, text: str, label: str | None) -> dict:
    sample_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO style_samples (id, user_id, text, label, created_at) VALUES (?, ?, ?, ?, ?)",
        [sample_id, user_id, text, label, now],
    )
    return {"id": sample_id, "text": text, "label": label, "created_at": now}


async def delete_sample(user_id: str, sample_id: str) -> bool:
    existing = await client.db_execute(
        "SELECT id FROM style_samples WHERE user_id = ? AND id = ? LIMIT 1",
        [user_id, sample_id],
    )
    if not existing:
        return False
    await client.db_execute(
        "DELETE FROM style_samples WHERE user_id = ? AND id = ?", [user_id, sample_id]
    )
    return True


# --- Labelled samples (Phase 2.5) --------------------------------
# Other features (the journal) keep a single sample in sync with one of their
# rows, keyed on a stable label like "journal:<entry id>".


async def upsert_labelled_sample(user_id: str, label: str, text: str) -> None:
    now = utcnow_iso()
    existing = await client.db_execute(
        "SELECT id FROM style_samples WHERE user_id = ? AND label = ? LIMIT 1",
        [user_id, label],
    )
    if existing:
        await client.db_execute(
            "UPDATE style_samples SET text = ? WHERE user_id = ? AND label = ?",
            [text, user_id, label],
        )
    else:
        await client.db_execute(
            "INSERT INTO style_samples (id, user_id, text, label, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [new_id(), user_id, text, label, now],
        )


async def delete_labelled_sample(user_id: str, label: str) -> None:
    await client.db_execute(
        "DELETE FROM style_samples WHERE user_id = ? AND label = ?", [user_id, label]
    )
