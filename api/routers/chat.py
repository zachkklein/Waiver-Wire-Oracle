# Streaming chat endpoint — frontend owns conversation history, backend is stateless.
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.chat_service import stream_chat
from api.deps import LeagueDep, UserDep

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
def post_chat(req: ChatRequest, user: UserDep, league: LeagueDep):
    history = [m.model_dump() for m in req.messages]

    def event_stream():
        for event in stream_chat(history, user, league):
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
