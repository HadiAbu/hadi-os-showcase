"""Tasks 1.3-1.7 — auth flow (REQ-1, REQ-2, REQ-3, REQ-4, REQ-23)."""

from __future__ import annotations

import pytest

REG = {"email": "hadi@example.com", "password": "Sup3rSecret"}
WRONG = {**REG, "password": "WrongPass1"}


# --- REQ-1 registration ---------------------------------------------


async def test_register_success_hides_secret(client):
    r = await client.post("/api/auth/register", json=REG)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "hadi@example.com"
    assert "password" not in body and "password_hash" not in body
    assert body["id"]


@pytest.mark.parametrize(
    "password",
    ["short1A", "alllowercase1", "NoDigitsHERE", "a" * 80 + "A1"],
)
async def test_register_weak_password_422(client, password):
    r = await client.post("/api/auth/register", json={"email": "a@b.com", "password": password})
    assert r.status_code == 422


async def test_register_duplicate_email_409(client):
    assert (await client.post("/api/auth/register", json=REG)).status_code == 201
    assert (await client.post("/api/auth/register", json=REG)).status_code == 409


# --- REQ-2 login & lockout ----------------------------------------


async def test_login_success_issues_token_and_cookie(client):
    await client.post("/api/auth/register", json=REG)
    r = await client.post("/api/auth/login", json=REG)
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert client.cookies.get("refresh_token")


async def test_login_unknown_email_401(client):
    r = await client.post("/api/auth/login", json=REG)
    assert r.status_code == 401


async def test_five_failures_lock_account_423(client):
    await client.post("/api/auth/register", json=REG)
    for i in range(5):
        r = await client.post("/api/auth/login", json=WRONG)
        assert r.status_code == 401, f"failure {i} should be 401"
    # correct password now, but the account is locked
    r = await client.post("/api/auth/login", json=REG)
    assert r.status_code == 423


async def test_successful_login_resets_failed_attempts(client):
    await client.post("/api/auth/register", json=REG)
    for _ in range(4):
        assert (await client.post("/api/auth/login", json=WRONG)).status_code == 401
    assert (await client.post("/api/auth/login", json=REG)).status_code == 200
    # counter reset — four more failures still don't lock
    for _ in range(4):
        assert (await client.post("/api/auth/login", json=WRONG)).status_code == 401
    assert (await client.post("/api/auth/login", json=REG)).status_code == 200


# --- REQ-3 refresh & logout -------------------------------------


async def test_refresh_rotates_token_and_rejects_the_old_one(client):
    await client.post("/api/auth/register", json=REG)
    await client.post("/api/auth/login", json=REG)
    old = client.cookies.get("refresh_token")

    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    new = client.cookies.get("refresh_token")
    assert new and new != old

    replay = await client.post("/api/auth/refresh", cookies={"refresh_token": old})
    assert replay.status_code == 401


async def test_refresh_without_cookie_401(client):
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_logout_revokes_refresh_token(client):
    await client.post("/api/auth/register", json=REG)
    await client.post("/api/auth/login", json=REG)
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.post("/api/auth/refresh")).status_code == 401


# --- REQ-4 protected routes -----------------------------------


async def test_me_returns_current_user_with_valid_token(client):
    await client.post("/api/auth/register", json=REG)
    token = (await client.post("/api/auth/login", json=REG)).json()["access_token"]
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == REG["email"]


async def test_me_without_token_401(client):
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_me_with_garbage_token_401(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


# --- REQ-23 security headers ---------------------------------


async def test_security_headers_present_no_hsts_in_dev(client):
    h = (await client.get("/health")).headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "content-security-policy" in h
    assert "strict-transport-security" not in h
