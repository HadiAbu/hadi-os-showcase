"""Onboarding schemas (REQ-5, REQ-6, REQ-7)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OnboardingState(BaseModel):
    completed: bool
    completed_at: str | None


class OnboardingQuestion(BaseModel):
    id: str
    type: Literal["text", "long_text", "single_select", "multi_select", "repeatable"]
    prompt: str
    options: list[str] | None = None


class OnboardingAnswer(BaseModel):
    question_id: str
    value: str | list[str]


class OnboardingSampleIn(BaseModel):
    text: str = Field(min_length=1)
    label: str | None = None


class OnboardingSubmit(BaseModel):
    answers: list[OnboardingAnswer] = Field(default_factory=list)
    samples: list[OnboardingSampleIn] = Field(default_factory=list)


class OnboardingResult(BaseModel):
    completed_at: str
    enrichment: Literal["done", "skipped", "error"]
