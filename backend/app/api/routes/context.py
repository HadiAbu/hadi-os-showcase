"""Context store endpoints (REQ-8, REQ-9, REQ-10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.deps import current_user
from app.models.context import (
    ContextEntryCreate,
    ContextEntryOut,
    ContextEntryPatch,
    ContextStatsOut,
    ReviewApprove,
    StyleGuideOut,
    StyleGuidePut,
    StyleSampleCreate,
    StyleSampleOut,
)
from app.services import context_stats, context_store, style

router = APIRouter(prefix="/context", tags=["context"])


# --- Entries -------------------------------------------------------


@router.get("/entries", response_model=list[ContextEntryOut])
async def list_entries(
    category: str | None = None,
    status_: str | None = Query(default=None, alias="status"),
    user: dict = Depends(current_user),
):
    rows = await context_store.list_entries(
        user["id"], category=category, status=status_
    )
    return [ContextEntryOut.model_validate(r) for r in rows]


@router.post("/entries", status_code=status.HTTP_201_CREATED, response_model=ContextEntryOut)
async def create_entry(body: ContextEntryCreate, user: dict = Depends(current_user)):
    row = await context_store.create_entry(
        user["id"],
        body.category,
        body.key,
        body.value,
        pinned=body.pinned,
        source="manual",
        status="active",
    )
    return ContextEntryOut.model_validate(row)


@router.patch("/entries/{entry_id}", response_model=ContextEntryOut)
async def patch_entry(
    entry_id: str, body: ContextEntryPatch, user: dict = Depends(current_user)
):
    try:
        row = await context_store.patch_entry(
            user["id"], entry_id, **body.model_dump(exclude_unset=True)
        )
    except context_store.EntryConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Entry {exc} already exists")
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return ContextEntryOut.model_validate(row)


@router.post("/entries/{entry_id}/archive", response_model=ContextEntryOut)
async def archive_entry(entry_id: str, user: dict = Depends(current_user)):
    row = await context_store.set_status(user["id"], entry_id, "archived")
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return ContextEntryOut.model_validate(row)


# --- Telemetry --------------------------------------------------


@router.get("/stats", response_model=ContextStatsOut)
async def context_stats_endpoint(user: dict = Depends(current_user)):
    return ContextStatsOut.model_validate(await context_stats.stats(user["id"]))


# --- Review queue -----------------------------------------------


@router.get("/review", response_model=list[ContextEntryOut])
async def list_review(user: dict = Depends(current_user)):
    rows = await context_store.list_review(user["id"])
    return [ContextEntryOut.model_validate(r) for r in rows]


@router.post("/review/{entry_id}/approve", response_model=ContextEntryOut)
async def approve_entry(
    entry_id: str, body: ReviewApprove, user: dict = Depends(current_user)
):
    if body.value is not None:
        patched = await context_store.patch_entry(user["id"], entry_id, value=body.value)
        if patched is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    row = await context_store.set_status(user["id"], entry_id, "active")
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return ContextEntryOut.model_validate(row)


@router.post("/review/{entry_id}/discard", response_model=ContextEntryOut)
async def discard_entry(entry_id: str, user: dict = Depends(current_user)):
    row = await context_store.set_status(user["id"], entry_id, "archived")
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return ContextEntryOut.model_validate(row)


# --- Style guide + samples ----------------------------------


@router.get("/style-guide", response_model=StyleGuideOut)
async def get_style_guide(user: dict = Depends(current_user)):
    return StyleGuideOut.model_validate(await style.get_style_guide(user["id"]))


@router.put("/style-guide", response_model=StyleGuideOut)
async def put_style_guide(body: StyleGuidePut, user: dict = Depends(current_user)):
    return StyleGuideOut.model_validate(
        await style.put_style_guide(user["id"], body.guide_md)
    )


@router.get("/style-samples", response_model=list[StyleSampleOut])
async def list_style_samples(user: dict = Depends(current_user)):
    return [StyleSampleOut.model_validate(r) for r in await style.list_samples(user["id"])]


@router.post(
    "/style-samples", status_code=status.HTTP_201_CREATED, response_model=StyleSampleOut
)
async def add_style_sample(body: StyleSampleCreate, user: dict = Depends(current_user)):
    return StyleSampleOut.model_validate(
        await style.add_sample(user["id"], body.text, body.label)
    )


@router.delete("/style-samples/{sample_id}")
async def delete_style_sample(sample_id: str, user: dict = Depends(current_user)):
    ok = await style.delete_sample(user["id"], sample_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sample not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
