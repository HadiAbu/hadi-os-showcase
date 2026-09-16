"""Usage-telemetry schemas.

See ``.kiro/specs/phase-2-visual-and-graph/design.md`` § 5. Figures come from
``messages.usage_json`` (one row per successful turn) and ``tool_invocations``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

UsageWindow = Literal["7d", "30d", "all"]


class TokenTotals(BaseModel):
    prompt: int
    completion: int
    total: int


class DayUsage(BaseModel):
    day: str  # YYYY-MM-DD
    prompt: int
    completion: int
    total: int


class ModelUsage(BaseModel):
    model: str
    prompt: int
    completion: int
    total: int
    pct: int  # share of total tokens in the window


class ConversationUsage(BaseModel):
    conversation_id: str
    title: str
    total: int


class ToolUsage(BaseModel):
    tool_name: str
    count: int


class UsageOut(BaseModel):
    window: UsageWindow
    tokens: TokenTotals
    by_day: list[DayUsage]
    by_model: list[ModelUsage]
    by_conversation: list[ConversationUsage]
    tool_calls_total: int
    tool_calls_by_name: list[ToolUsage]
    estimated_cost_usd: float
    cost_known: bool
