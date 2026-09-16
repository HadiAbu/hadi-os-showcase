"""Project endpoints (REQ-14)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import current_user
from app.models.projects import ProjectCreate, ProjectOut, ProjectPatch
from app.services import projects_store

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    status_: str | None = Query(default=None, alias="status"),
    user: dict = Depends(current_user),
):
    rows = await projects_store.list_projects(user["id"], status=status_)
    return [ProjectOut.model_validate(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectOut)
async def create_project(body: ProjectCreate, user: dict = Depends(current_user)):
    row = await projects_store.create_project(user["id"], body.model_dump())
    return ProjectOut.model_validate(row)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, user: dict = Depends(current_user)):
    row = await projects_store.get_project(user["id"], project_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return ProjectOut.model_validate(row)


@router.patch("/{project_id}", response_model=ProjectOut)
async def patch_project(
    project_id: str, body: ProjectPatch, user: dict = Depends(current_user)
):
    row = await projects_store.patch_project(
        user["id"], project_id, body.model_dump(exclude_unset=True)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return ProjectOut.model_validate(row)
