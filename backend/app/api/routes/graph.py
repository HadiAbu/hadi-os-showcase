"""Knowledge-graph endpoints (REQ-5, REQ-6, REQ-14).

``GET /api/graph`` returns the assembled node/edge set; ``/api/graph/links`` is
CRUD over the user-drawn edges. All routes are user-scoped via ``current_user``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import current_user
from app.models.graph import GraphOut, LinkCreate, LinkOut
from app.services import graph, graph_links

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphOut)
async def get_graph(user: dict = Depends(current_user)):
    return GraphOut.model_validate(await graph.build_graph(user["id"]))


@router.get("/links", response_model=list[LinkOut])
async def list_links(user: dict = Depends(current_user)):
    return [LinkOut.model_validate(r) for r in await graph_links.list_links(user["id"])]


@router.post("/links", status_code=status.HTTP_201_CREATED, response_model=LinkOut)
async def create_link(body: LinkCreate, user: dict = Depends(current_user)):
    try:
        row = await graph_links.create_link(user["id"], body.model_dump())
    except graph_links.UnknownEntity as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown entity: {exc}")
    return LinkOut.model_validate(row)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(link_id: str, user: dict = Depends(current_user)):
    if not await graph_links.delete_link(user["id"], link_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "link not found")
