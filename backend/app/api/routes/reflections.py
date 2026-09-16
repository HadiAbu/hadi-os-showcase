"""Reflection endpoints (Phase 2.5, REQ-8/9/12).

`generate` computes deterministic signals then writes a dated batch of
reflections — LLM-voiced when `LLM_API_KEY` is set, templated otherwise. All
routes are user-scoped.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import current_user
from app.models.reflections import GenerateOut, ReflectionOut, ReflectionPatch, ReflectionStatus
from app.services import insights

router = APIRouter(prefix="/reflections", tags=["reflections"])


@router.post("/generate", response_model=GenerateOut)
async def generate(user: dict = Depends(current_user)):
    return GenerateOut.model_validate(await insights.generate(user["id"]))


@router.get("", response_model=list[ReflectionOut])
async def list_reflections(
    status_: ReflectionStatus | None = Query(default=None, alias="status"),
    user: dict = Depends(current_user),
):
    rows = await insights.list_reflections(user["id"], status_)
    return [ReflectionOut.model_validate(r) for r in rows]


@router.patch("/{reflection_id}", response_model=ReflectionOut)
async def patch_reflection(
    reflection_id: str, body: ReflectionPatch, user: dict = Depends(current_user)
):
    row = await insights.set_reflection_status(user["id"], reflection_id, body.status)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reflection not found")
    return ReflectionOut.model_validate(row)
