"""Chat endpoints (REQ-15, REQ-16, REQ-17)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.deps import current_user
from app.models.chat import ConversationOut, MessageOut, NewConversation, NewMessage
from app.services import chat_agent, chat_store, llm_client

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(archived: bool = False, user: dict = Depends(current_user)):
    rows = await chat_store.list_conversations(user["id"], archived=archived)
    return [ConversationOut.model_validate(r) for r in rows]


@router.post(
    "/conversations", status_code=status.HTTP_201_CREATED, response_model=NewConversation
)
async def create_conversation(user: dict = Depends(current_user)):
    conv = await chat_store.create_conversation(user["id"])
    return NewConversation(id=conv["id"])


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(conversation_id: str, user: dict = Depends(current_user)):
    if await chat_store.get_conversation(user["id"], conversation_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    rows = await chat_store.list_display_messages(user["id"], conversation_id)
    return [MessageOut.model_validate(r) for r in rows]


@router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(conversation_id: str, user: dict = Depends(current_user)):
    if not await chat_store.archive_conversation(user["id"], conversation_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return {"ok": True}


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: str, body: NewMessage, user: dict = Depends(current_user)
):
    if await chat_store.get_conversation(user["id"], conversation_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    if not llm_client.available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI features not configured"
        )

    async def event_stream():
        try:
            async for name, data in chat_agent.run_turn(
                user, conversation_id, body.text
            ):
                yield f"event: {name}\ndata: {json.dumps(data)}\n\n"
        except chat_agent.AIUnavailable:
            payload = json.dumps({"detail": "AI features not configured"})
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
