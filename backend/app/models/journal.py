"""Journal schemas (Phase 2.5, REQ-1/2/12).

`body` is the substantive field; `title` may be empty. A long entry with
`learn_from_style` set is mirrored into `style_samples` by `journal_store` (J1).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JournalMood = Literal["", "good", "flat", "low", "energised", "drained"]

TITLE_MAX = 200
BODY_MAX = 20_000
TAGS_MAX = 12


class JournalCreate(BaseModel):
    title: str = Field(default="", max_length=TITLE_MAX)
    body: str = Field(default="", max_length=BODY_MAX)
    mood: JournalMood = ""
    tags: list[str] = Field(default_factory=list, max_length=TAGS_MAX)
    linked_objective_id: str | None = None
    linked_project_id: str | None = None
    learn_from_style: bool = True


class JournalPatch(BaseModel):
    title: str | None = Field(default=None, max_length=TITLE_MAX)
    body: str | None = Field(default=None, max_length=BODY_MAX)
    mood: JournalMood | None = None
    tags: list[str] | None = Field(default=None, max_length=TAGS_MAX)
    linked_objective_id: str | None = None
    linked_project_id: str | None = None
    learn_from_style: bool | None = None


class JournalOut(BaseModel):
    id: str
    title: str
    body: str
    mood: JournalMood
    tags: list[str]
    linked_objective_id: str | None
    linked_project_id: str | None
    learn_from_style: bool
    created_at: str
    updated_at: str


class ContinueOut(BaseModel):
    text: str
