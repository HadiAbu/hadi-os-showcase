"""Dashboard + focus endpoints (REQ-19, REQ-20, REQ-24)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import current_user
from app.models.dashboard import DashboardOut, FocusOut
from app.services import dashboard, focus, llm_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def get_dashboard(user: dict = Depends(current_user)):
    return DashboardOut.model_validate(await dashboard.build_dashboard(user["id"]))


@router.get("/focus", response_model=FocusOut)
async def get_focus(user: dict = Depends(current_user)):
    return FocusOut.model_validate(await focus.get_focus(user["id"]))


@router.post("/focus/refresh", response_model=FocusOut)
async def refresh_focus(user: dict = Depends(current_user)):
    if not llm_client.available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI features not configured"
        )
    return FocusOut.model_validate(await focus.refresh_focus(user["id"]))
