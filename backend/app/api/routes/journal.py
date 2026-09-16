"""Journal endpoints (Phase 2.5, REQ-2/12). `/{id}/continue` is added in J1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.deps import current_user
from app.models.journal import ContinueOut, JournalCreate, JournalOut, JournalPatch
from app.services import journal_store, llm_client, style

router = APIRouter(prefix="/journal", tags=["journal"])

_CONTINUE_SYSTEM = (
    "You continue the owner's journal entry in their own voice. Write one or two "
    "short paragraphs that pick up exactly where the text stops — no preamble, no "
    "summary, no headings, no meta commentary. Match the tone and rhythm of the "
    "reference material."
)
_FEWSHOT_ENTRIES = 3
_FEWSHOT_CHARS = 800


@router.get("", response_model=list[JournalOut])
async def list_entries(
    objective_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    user: dict = Depends(current_user),
):
    rows = await journal_store.list_entries(
        user["id"], objective_id=objective_id, project_id=project_id
    )
    return [JournalOut.model_validate(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=JournalOut)
async def create_entry(body: JournalCreate, user: dict = Depends(current_user)):
    try:
        row = await journal_store.create_entry(user["id"], body.model_dump())
    except journal_store.LinkNotOwned as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown link: {exc}")
    return JournalOut.model_validate(row)


@router.get("/{entry_id}", response_model=JournalOut)
async def get_entry(entry_id: str, user: dict = Depends(current_user)):
    row = await journal_store.get_entry(user["id"], entry_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return JournalOut.model_validate(row)


@router.patch("/{entry_id}", response_model=JournalOut)
async def patch_entry(
    entry_id: str, body: JournalPatch, user: dict = Depends(current_user)
):
    try:
        row = await journal_store.patch_entry(
            user["id"], entry_id, body.model_dump(exclude_unset=True)
        )
    except journal_store.LinkNotOwned as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown link: {exc}")
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return JournalOut.model_validate(row)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: str, user: dict = Depends(current_user)):
    if not await journal_store.delete_entry(user["id"], entry_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{entry_id}/continue", response_model=ContinueOut)
async def continue_entry(entry_id: str, user: dict = Depends(current_user)):
    entry = await journal_store.get_entry(user["id"], entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    if not llm_client.available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI features not configured")

    guide = (await style.get_style_guide(user["id"]))["guide_md"]
    others = [
        e
        for e in await journal_store.list_entries(user["id"])
        if e["id"] != entry_id and (e["body"] or "").strip()
    ][:_FEWSHOT_ENTRIES]
    fewshot = "\n\n---\n\n".join(e["body"][:_FEWSHOT_CHARS] for e in others)

    system = _CONTINUE_SYSTEM
    if guide:
        system += f"\n\nStyle guide:\n{guide}"
    if fewshot:
        system += f"\n\nRecent entries for voice reference:\n{fewshot}"

    prompt = f"Entry so far:\n\n{entry['title']}\n{entry['body']}".strip()
    text = await llm_client.one_shot(system=system, user=prompt, max_tokens=400)
    return ContinueOut(text=text.strip())
