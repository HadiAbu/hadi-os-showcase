"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import TokenError, decode_access_token
from app.services import users

_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Resolve the user from the ``Authorization: Bearer`` access token.

    Identity comes only from the verified token — never from the request body or
    query string (REQ-4).
    """
    if creds is None or not creds.credentials:
        raise _UNAUTHENTICATED
    try:
        claims = decode_access_token(creds.credentials)
    except TokenError:
        raise _UNAUTHENTICATED
    user = await users.get_user_by_id(claims["sub"])
    if user is None:
        raise _UNAUTHENTICATED
    return user
