"""Reflection schemas (Phase 2.5, REQ-8/9/12)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReflectionKind = Literal["momentum", "drift", "theme"]
ReflectionStatus = Literal["active", "pinned", "dismissed"]

BODY_MAX = 2_000


class ReflectionOut(BaseModel):
    id: str
    kind: ReflectionKind
    body: str
    evidence: dict
    status: ReflectionStatus
    created_at: str


class ReflectionPatch(BaseModel):
    status: ReflectionStatus


class GenerateOut(BaseModel):
    reflections: list[ReflectionOut]
    reason: str | None = None
