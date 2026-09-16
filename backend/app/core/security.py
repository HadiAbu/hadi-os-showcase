"""Password hashing and token helpers.

See ``.kiro/steering/tech.md`` § Security posture — these values are
non-negotiable:

- bcrypt, cost 12
- HS256 access JWT, 15-minute expiry, ``type: "access"`` claim verified on decode
- refresh token: UUID v4 raw value (returned to the caller for the cookie),
  SHA-256 hex stored in the DB
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

BCRYPT_ROUNDS = 12
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MINUTES = 15
REFRESH_TOKEN_TTL_DAYS = 30


class TokenError(Exception):
    """Raised for any invalid/expired/wrong-type access token."""


# --- Passwords -----------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# --- Access tokens -----------------------------------------------------


def create_access_token(subject: str, *, now: datetime | None = None) -> str:
    issued = now or datetime.now(timezone.utc)
    claims = {
        "sub": subject,
        "type": "access",
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)).timestamp()),
    }
    return jwt.encode(claims, get_settings().jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret_key, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:  # bad signature, expired, malformed
        raise TokenError(str(exc)) from exc
    if claims.get("type") != "access":
        raise TokenError("wrong token type")
    if not claims.get("sub"):
        raise TokenError("missing subject")
    return claims


# --- Refresh tokens --------------------------------------------------


def new_refresh_token() -> str:
    """Opaque raw value — goes into the HttpOnly cookie, never stored as-is."""
    return uuid.uuid4().hex


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_expiry(now: datetime | None = None) -> str:
    issued = now or datetime.now(timezone.utc)
    return (issued + timedelta(days=REFRESH_TOKEN_TTL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
