"""Task 1.2 — password + token helpers (REQ-1, REQ-2, REQ-3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.security import (
    JWT_ALGORITHM,
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)


# --- Passwords ---------------------------------------------------------


def test_hash_verify_roundtrip():
    h = hash_password("Sup3rSecret")
    assert h != "Sup3rSecret"
    assert verify_password("Sup3rSecret", h) is True
    assert verify_password("wrong", h) is False


def test_hash_is_salted():
    assert hash_password("samepass1A") != hash_password("samepass1A")


# --- Access tokens --------------------------------------------------


def test_access_token_roundtrip():
    token = create_access_token("user-123")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-123"
    assert claims["type"] == "access"


def test_tampered_token_rejected():
    token = create_access_token("user-123")
    with pytest.raises(TokenError):
        decode_access_token(token + "x")


def test_expired_token_rejected():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = create_access_token("user-123", now=past)
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_non_access_token_rejected():
    forged = jwt.encode(
        {"sub": "user-123", "type": "refresh"},
        get_settings().jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(TokenError):
        decode_access_token(forged)


def test_token_signed_with_other_key_rejected():
    forged = jwt.encode({"sub": "x", "type": "access"}, "some-other-key", algorithm=JWT_ALGORITHM)
    with pytest.raises(TokenError):
        decode_access_token(forged)


# --- Refresh tokens ----------------------------------------------


def test_refresh_token_unique_and_hashable():
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b
    ha = hash_refresh_token(a)
    assert ha == hash_refresh_token(a)  # deterministic
    assert ha != a  # not the raw value
    assert len(ha) == 64  # sha256 hex


def test_refresh_expiry_is_in_the_future():
    assert refresh_expiry() > datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
