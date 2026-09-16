"""Onboarding endpoints (REQ-5, REQ-6, REQ-7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import current_user
from app.models.onboarding import (
    OnboardingQuestion,
    OnboardingResult,
    OnboardingState,
    OnboardingSubmit,
)
from app.services import onboarding
from app.services.onboarding_questions import QUESTIONS

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/state", response_model=OnboardingState)
async def get_state(user: dict = Depends(current_user)):
    return OnboardingState.model_validate(await onboarding.get_state(user["id"]))


@router.get("/questions", response_model=list[OnboardingQuestion])
async def get_questions():
    return [OnboardingQuestion.model_validate(q) for q in QUESTIONS]


@router.post("/submit", response_model=OnboardingResult)
async def submit(body: OnboardingSubmit, user: dict = Depends(current_user)):
    result = await onboarding.submit(
        user["id"],
        [a.model_dump() for a in body.answers],
        [s.model_dump() for s in body.samples],
    )
    return OnboardingResult.model_validate(result)
