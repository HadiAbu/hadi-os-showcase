"""Objective + action schemas (REQ-12, REQ-13). Two-tier: an objective has
child actions/milestones."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Horizon = Literal["month", "quarter", "year", "someday"]
ObjectiveStatus = Literal["active", "done", "paused", "dropped"]
ActionStatus = Literal["todo", "doing", "done", "dropped"]


class ObjectiveCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    horizon: Horizon
    description: str = ""
    priority: int = Field(default=2, ge=1, le=3)
    tags: list[str] = Field(default_factory=list)
    target_date: str | None = None
    project_id: str | None = None


class ObjectivePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    horizon: Horizon | None = None
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    tags: list[str] | None = None
    target_date: str | None = None
    project_id: str | None = None
    status: ObjectiveStatus | None = None


class ObjectiveOut(BaseModel):
    id: str
    title: str
    description: str
    horizon: Horizon
    target_date: str | None
    status: ObjectiveStatus
    priority: int
    tags: list[str]
    project_id: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class ActionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_date: str | None = None


class ActionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    status: ActionStatus | None = None
    notes: str | None = None
    due_date: str | None = None


class ActionOut(BaseModel):
    id: str
    objective_id: str
    title: str
    status: ActionStatus
    notes: str
    due_date: str | None
    source: Literal["manual", "suggested"]
    created_at: str
    updated_at: str
    completed_at: str | None


class ObjectiveDetail(BaseModel):
    objective: ObjectiveOut
    actions: list[ActionOut]
