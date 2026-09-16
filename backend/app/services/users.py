"""Persistence for users and refresh tokens (REQ-1..REQ-4).

Routes call these; routes do not touch the DB directly (see structure.md).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import client
from app.db.client import new_id, utcnow_iso

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class EmailTaken(Exception):
    pass


# --- Users -----------------------------------------------------------


async def get_user_by_email(email: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM users WHERE email = ? LIMIT 1", [email.lower()]
    )
    return rows[0] if rows else None


async def get_user_by_id(user_id: str) -> dict | None:
    rows = await client.db_execute("SELECT * FROM users WHERE id = ? LIMIT 1", [user_id])
    return rows[0] if rows else None


async def create_user(email: str, password_hash: str) -> dict:
    email = email.lower()
    if await get_user_by_email(email) is not None:
        raise EmailTaken(email)
    user_id = new_id()
    now = utcnow_iso()
    await client.db_execute(
        "INSERT INTO users (id, email, password_hash, failed_attempts, locked_until, created_at) "
        "VALUES (?, ?, ?, 0, NULL, ?)",
        [user_id, email, password_hash, now],
    )
    return {
        "id": user_id,
        "email": email,
        "password_hash": password_hash,
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": now,
    }


# --- Lockout ------------------------------------------------------


def is_locked(user: dict, *, now: datetime | None = None) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    ref = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return locked_until > ref


async def register_failed_attempt(user: dict) -> None:
    new_count = int(user.get("failed_attempts", 0)) + 1
    if new_count >= MAX_FAILED_ATTEMPTS:
        locked_until = (
            datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        await client.db_execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
            [new_count, locked_until, user["id"]],
        )
    else:
        await client.db_execute(
            "UPDATE users SET failed_attempts = ? WHERE id = ?", [new_count, user["id"]]
        )


async def reset_failed_attempts(user_id: str) -> None:
    await client.db_execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", [user_id]
    )


# --- Refresh tokens --------------------------------------------


async def store_refresh_token(user_id: str, token_hash: str, expires_at: str) -> None:
    await client.db_execute(
        "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, revoked, created_at) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        [new_id(), user_id, token_hash, expires_at, utcnow_iso()],
    )


async def get_refresh_token(token_hash: str) -> dict | None:
    rows = await client.db_execute(
        "SELECT * FROM refresh_tokens WHERE token_hash = ? LIMIT 1", [token_hash]
    )
    return rows[0] if rows else None


async def revoke_refresh_token(token_hash: str) -> None:
    await client.db_execute(
        "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?", [token_hash]
    )


async def purge_stale_refresh_tokens(user_id: str) -> None:
    """Delete this user's revoked or expired rows (called on every login/refresh)."""
    await client.db_execute(
        "DELETE FROM refresh_tokens WHERE user_id = ? AND (revoked = 1 OR expires_at <= ?)",
        [user_id, utcnow_iso()],
    )
