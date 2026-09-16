"""Objective + action endpoints (REQ-12, REQ-13)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import current_user
from app.models.objectives import (
    ActionCreate,
    ActionOut,
    ActionPatch,
    ObjectiveCreate,
    ObjectiveDetail,
    ObjectiveOut,
    ObjectivePatch,
)
from app.services import objectives_store

router = APIRouter(tags=["objectives"])


@router.get("/objectives", response_model=list[ObjectiveOut])
async def list_objectives(
    status_: str | None = Query(default=None, alias="status"),
    tag: str | None = None,
    user: dict = Depends(current_user),
):
    rows = await objectives_store.list_objectives(user["id"], status=status_, tag=tag)
    return [ObjectiveOut.model_validate(r) for r in rows]


@router.post(
    "/objectives", status_code=status.HTTP_201_CREATED, response_model=ObjectiveOut
)
async def create_objective(body: ObjectiveCreate, user: dict = Depends(current_user)):
    try:
        row = await objectives_store.create_objective(user["id"], body.model_dump())
    except objectives_store.ProjectNotOwned:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown project_id")
    return ObjectiveOut.model_validate(row)


@router.get("/objectives/{objective_id}", response_model=ObjectiveDetail)
async def get_objective(objective_id: str, user: dict = Depends(current_user)):
    obj = await objectives_store.get_objective(user["id"], objective_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Objective not found")
    actions = await objectives_store.list_actions(user["id"], objective_id)
    return ObjectiveDetail(
        objective=ObjectiveOut.model_validate(obj),
        actions=[ActionOut.model_validate(a) for a in actions],
    )


@router.patch("/objectives/{objective_id}", response_model=ObjectiveOut)
async def patch_objective(
    objective_id: str, body: ObjectivePatch, user: dict = Depends(current_user)
):
    try:
        row = await objectives_store.patch_objective(
            user["id"], objective_id, body.model_dump(exclude_unset=True)
        )
    except objectives_store.ProjectNotOwned:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown project_id")
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Objective not found")
    return ObjectiveOut.model_validate(row)


@router.post(
    "/objectives/{objective_id}/actions",
    status_code=status.HTTP_201_CREATED,
    response_model=ActionOut,
)
async def create_action(
    objective_id: str, body: ActionCreate, user: dict = Depends(current_user)
):
    row = await objectives_store.create_action(
        user["id"], objective_id, body.title, due_date=body.due_date, source="manual"
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Objective not found")
    return ActionOut.model_validate(row)


@router.patch("/actions/{action_id}", response_model=ActionOut)
async def patch_action(
    action_id: str, body: ActionPatch, user: dict = Depends(current_user)
):
    row = await objectives_store.patch_action(
        user["id"], action_id, body.model_dump(exclude_unset=True)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    return ActionOut.model_validate(row)
