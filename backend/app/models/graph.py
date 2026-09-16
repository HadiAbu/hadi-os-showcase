"""Knowledge-graph response + link-CRUD schemas.

See ``.kiro/specs/phase-2-visual-and-graph/design.md`` § 4. Node ids are
``"<type>:<row id>"`` so they stay unique across the source tables.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EntityType = Literal[
    "objective", "action", "project", "context", "conversation", "journal"
]


class GraphNode(BaseModel):
    id: str
    type: EntityType
    label: str
    meta: dict = Field(default_factory=dict)


class GraphLink(BaseModel):
    source: str
    target: str
    kind: str


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]
    truncated: bool = False


class LinkCreate(BaseModel):
    from_type: EntityType
    from_id: str = Field(min_length=1)
    to_type: EntityType
    to_id: str = Field(min_length=1)
    kind: str = Field(default="related", min_length=1, max_length=40)


class LinkOut(BaseModel):
    id: str
    from_type: EntityType
    from_id: str
    to_type: EntityType
    to_id: str
    kind: str
    created_at: str
