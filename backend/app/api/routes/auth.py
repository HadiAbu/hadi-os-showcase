"""Auth endpoints (REQ-1..REQ-4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.deps import current_user
from app.core.security import (
    REFRESH_TOKEN_TTL_DAYS,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from app.db.client import utcnow_iso
from app.models.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api/auth"

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
)


def _set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw,
        httponly=True,
        samesite="strict",
        secure=get_settings().is_prod,
        path=COOKIE_PATH,
        max_age=REFRESH_TOKEN_TTL_DAYS * 24 * 3600,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(body: RegisterRequest) -> UserResponse:
    try:
        user = await users.create_user(str(body.email), hash_password(body.password))
    except users.EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return UserResponse(id=user["id"], email=user["email"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response) -> TokenResponse:
    user = await users.get_user_by_email(str(body.email))
    if user is None:
        raise _INVALID_CREDENTIALS
    if users.is_locked(user):
        raise HTTPException(
            status.HTTP_423_LOCKED, "Account temporarily locked; try again later"
        )
    if not verify_password(body.password, user["password_hash"]):
        await users.register_failed_attempt(user)
        raise _INVALID_CREDENTIALS

    await users.reset_failed_attempts(user["id"])
    await users.purge_stale_refresh_tokens(user["id"])
    raw = new_refresh_token()
    await users.store_refresh_token(user["id"], hash_refresh_token(raw), refresh_expiry())
    _set_refresh_cookie(response, raw)
    return TokenResponse(access_token=create_access_token(user["id"]))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        _clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")

    token_hash = hash_refresh_token(raw)
    row = await users.get_refresh_token(token_hash)
    if row is None or row["revoked"] or row["expires_at"] <= utcnow_iso():
        _clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    user = await users.get_user_by_id(row["user_id"])
    if user is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    await users.revoke_refresh_token(token_hash)
    new_raw = new_refresh_token()
    await users.store_refresh_token(
        user["id"], hash_refresh_token(new_raw), refresh_expiry()
    )
    await users.purge_stale_refresh_tokens(user["id"])
    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=create_access_token(user["id"]))


@router.post("/logout")
async def logout(request: Request) -> Response:
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        await users.revoke_refresh_token(hash_refresh_token(raw))
    _clear_refresh_cookie(resp)
    return resp


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(current_user)) -> UserResponse:
    return UserResponse(id=user["id"], email=user["email"])
