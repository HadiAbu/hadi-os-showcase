"""Auth request/response schemas. Password policy per REQ-1 / tech.md."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator

MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 72  # bcrypt hard limit


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        if not (MIN_PASSWORD_LEN <= len(v) <= MAX_PASSWORD_LEN):
            raise ValueError(
                f"password must be {MIN_PASSWORD_LEN}-{MAX_PASSWORD_LEN} characters"
            )
        if not any(c.isupper() for c in v):
            raise ValueError("password must contain an uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("password must contain a digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
