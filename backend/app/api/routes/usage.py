"""Usage-telemetry endpoint (REQ-10, REQ-11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import current_user
from app.models.usage import UsageOut, UsageWindow
from app.services import usage as usage_service

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageOut)
async def get_usage(
    window: UsageWindow = Query(default="7d"),
    user: dict = Depends(current_user),
):
    return UsageOut.model_validate(await usage_service.usage(user["id"], window))
