"""Streaming API for the embedded De Anza College chatbot."""
import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from backend.deanza_chatbot.chat import stream_chat
from backend.deanza_chatbot.rate_limiter import chat_limiter, get_client_ip
from backend.deanza_chatbot.schemas import ChatRequest


router = APIRouter(tags=["De Anza Chat"])


@router.post("/api/deanza-chat")
async def deanza_chat_endpoint(req: ChatRequest, request: Request):
    """Stream a grounded De Anza answer using the chatbot's own RAG database."""
    device_id = request.headers.get("x-device-id")
    client_key = device_id.strip() if device_id and device_id.strip() else get_client_ip(request)
    allowed, retry_after = chat_limiter.check(client_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You're asking questions a bit too fast! Please wait {retry_after} seconds before sending your next message.",
        )

    async def event_generator():
        async for item in stream_chat(req.message, [message.model_dump() for message in req.history]):
            payload = item if isinstance(item, dict) else {"text": item}
            yield f"data: {json.dumps(payload)}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
