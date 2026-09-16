"""Context store schemas (REQ-8, REQ-9, REQ-10)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ContextCategory = Literal[
    "identity", "preference", "goal_context", "project_context", "working_style", "misc"
]
ContextStatus = Literal["active", "proposed", "archived"]
ContextSource = Literal["onboarding", "chat", "import", "manual"]


class ContextEntryCreate(BaseModel):
    category: ContextCategory
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1)
    pinned: bool = False


class ContextEntryPatch(BaseModel):
    category: ContextCategory | None = None
    key: str | None = Field(default=None, min_length=1, max_length=120)
    value: str | None = Field(default=None, min_length=1)
    pinned: bool | None = None


class ContextEntryOut(BaseModel):
    id: str
    category: ContextCategory
    key: str
    value: str
    source: ContextSource
    pinned: bool
    status: ContextStatus
    created_at: str
    updated_at: str


class ReviewApprove(BaseModel):
    value: str | None = Field(default=None, min_length=1)


class StyleGuideOut(BaseModel):
    guide_md: str
    updated_at: str | None


class StyleGuidePut(BaseModel):
    guide_md: str


class StyleSampleCreate(BaseModel):
    text: str = Field(min_length=1)
    label: str | None = None


class StyleSampleOut(BaseModel):
    id: str
    text: str
    label: str | None
    created_at: str


# --- Context telemetry (phase 2, design.md § 6) --------------------


class StatusCount(BaseModel):
    status: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class GrowthPoint(BaseModel):
    day: str  # YYYY-MM-DD
    active: int


class ContextStatsOut(BaseModel):
    by_status: list[StatusCount]
    by_category: list[CategoryCount]
    growth: list[GrowthPoint]
    stale: int
