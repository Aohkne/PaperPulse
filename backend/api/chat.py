from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.shared.services.llm_client import chat_completion

router = APIRouter()

_SYSTEM = (
    "You are PaperPulse, an academic research assistant. "
    "Help users explore research topics, identify key papers, find research gaps, "
    "and synthesize literature. Be concise and cite papers when possible."
)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


def _merge_consecutive(messages: list[dict]) -> list[dict]:
    """Merge back-to-back messages with the same role into one."""
    merged: list[dict] = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append({"role": m["role"], "content": m["content"]})
    return merged


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send conversation history to LLM and return assistant reply."""
    try:
        history = _merge_consecutive([{"role": m.role, "content": m.content} for m in request.messages])
        messages = [{"role": "system", "content": _SYSTEM}] + history
        reply = await chat_completion(messages)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
