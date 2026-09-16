"""Dashboard + focus schemas (REQ-19, REQ-20)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ObjectiveProgress(BaseModel):
    id: str
    title: str
    horizon: str
    priority: int
    open_actions: int
    total_actions: int
    pct_done: int


class Momentum(BaseModel):
    actions_done_7d: int
    actions_done_30d: int
    objectives_touched_7d: int
    projects_touched_7d: int


class ChangeItem(BaseModel):
    kind: Literal["objective", "action", "project"]
    title: str
    at: str
    detail: str


class DashboardOut(BaseModel):
    objectives: list[ObjectiveProgress]
    momentum: Momentum
    changed_this_week: list[ChangeItem]


class FocusOut(BaseModel):
    content_md: str | None
    created_at: str | None
    stale: bool
