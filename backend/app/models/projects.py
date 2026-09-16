"""Project schemas (REQ-14). ``repo_path`` / ``repo_url`` are stored but never
read from disk or network in Phase 1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ProjectStatus = Literal["active", "paused", "shipped", "archived"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    summary: str = ""
    status: ProjectStatus = "active"
    tech: list[str] = Field(default_factory=list)
    repo_path: str | None = None
    repo_url: str | None = None
    next_steps: str = ""
    notes: str = ""


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = None
    status: ProjectStatus | None = None
    tech: list[str] | None = None
    repo_path: str | None = None
    repo_url: str | None = None
    next_steps: str | None = None
    notes: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    summary: str
    status: ProjectStatus
    tech: list[str]
    repo_path: str | None
    repo_url: str | None
    next_steps: str
    notes: str
    created_at: str
    updated_at: str
