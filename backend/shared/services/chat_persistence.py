from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from supabase import Client, create_client

from backend.config import get_settings


DEFAULT_CHAT_TITLE = "New chat"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_client(token: str) -> Client:
    settings = get_settings()
    if settings.supabase_service_key:
        return create_client(settings.supabase_url, settings.supabase_service_key)
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.auth(token)
    return client


def _service_db_client() -> Client:
    settings = get_settings()
    if not settings.supabase_service_key:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_SERVICE_KEY is required for assistant message updates.",
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _short_title(query: str) -> str:
    title = (query or "").strip()
    if not title:
        return DEFAULT_CHAT_TITLE
    return title[:70]


def _chat_select(db: Client):
    return db.table("chats").select(
        "id,user_id,title,feature,status,summary,thread_id,topic_id,created_at,updated_at,last_message_at,deleted_at"
    )


def _message_select(db: Client):
    return db.table("messages").select(
        "id,chat_id,role,content,seq,status,client_message_id,metadata,created_at"
    )


async def get_owned_chat(token: str, user_id: str, chat_id: str, include_deleted: bool = False) -> dict[str, Any]:
    db = _db_client(token)
    query = _chat_select(db).eq("id", chat_id).eq("user_id", user_id).limit(1)
    if not include_deleted:
        query = query.is_("deleted_at", "null")
    res = query.execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return res.data[0]


async def get_owned_chat_by_thread(token: str, user_id: str, thread_id: str) -> dict[str, Any] | None:
    db = _db_client(token)
    res = (
        _chat_select(db)
        .eq("user_id", user_id)
        .eq("thread_id", thread_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def create_chat(token: str, user_id: str, title: str, thread_id: str | None = None) -> dict[str, Any]:
    db = _db_client(token)
    res = db.table("chats").insert({
        "user_id": user_id,
        "title": title or DEFAULT_CHAT_TITLE,
        "feature": "research",
        "status": "idle",
        "thread_id": thread_id,
        "topic_id": None,
    }).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create chat")
    return {**res.data[0], "deleted_at": None, "last_message_at": res.data[0].get("last_message_at")}


async def update_chat(token: str, user_id: str, chat_id: str, **fields: Any) -> dict[str, Any]:
    payload = {key: value for key, value in fields.items() if value is not None}
    if not payload:
        return await get_owned_chat(token, user_id, chat_id, include_deleted=True)
    db = _db_client(token)
    res = (
        db.table("chats")
        .update(payload)
        .eq("id", chat_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {**res.data[0], "deleted_at": res.data[0].get("deleted_at")}


async def _next_seq(token: str, chat_id: str) -> int:
    db = _db_client(token)
    res = (
        db.table("messages")
        .select("seq")
        .eq("chat_id", chat_id)
        .order("seq", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data or res.data[0].get("seq") is None:
        return 1
    return int(res.data[0]["seq"]) + 1


async def get_user_message_by_client_id(token: str, chat_id: str, client_message_id: str) -> dict[str, Any] | None:
    db = _db_client(token)
    res = (
        _message_select(db)
        .eq("chat_id", chat_id)
        .eq("role", "user")
        .eq("client_message_id", client_message_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def insert_user_message(
    token: str,
    chat_id: str,
    query: str,
    thread_id: str,
    request_kind: str,
    client_message_id: str | None = None,
) -> dict[str, Any]:
    if client_message_id:
        existing = await get_user_message_by_client_id(token, chat_id, client_message_id)
        if existing:
            return existing

    db = _db_client(token)
    seq = await _next_seq(token, chat_id)
    created_at = _now_iso()
    res = db.table("messages").insert({
        "chat_id": chat_id,
        "role": "user",
        "content": query,
        "seq": seq,
        "client_message_id": client_message_id,
        "status": "done",
        "metadata": {
            "source": "research_stream",
            "thread_id": thread_id,
            "request_kind": request_kind,
        },
        "created_at": created_at,
    }).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to persist user message")
    return res.data[0]


async def create_assistant_message(
    token: str,
    chat_id: str,
    thread_id: str,
    request_kind: str,
) -> dict[str, Any]:
    db = _db_client(token)
    seq = await _next_seq(token, chat_id)
    created_at = _now_iso()
    res = db.table("messages").insert({
        "chat_id": chat_id,
        "role": "assistant",
        "content": "",
        "seq": seq,
        "status": "streaming",
        "metadata": {
            "source": "research_stream",
            "thread_id": thread_id,
            "request_kind": request_kind,
            "steps": [],
        },
        "created_at": created_at,
    }).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create assistant message")
    return res.data[0]


async def find_assistant_message_for_turn(
    token: str,
    chat_id: str,
    thread_id: str,
    request_kind: str,
) -> dict[str, Any] | None:
    db = _db_client(token)
    res = (
        _message_select(db)
        .eq("chat_id", chat_id)
        .eq("role", "assistant")
        .order("seq", desc=True)
        .limit(10)
        .execute()
    )
    for row in res.data or []:
        metadata = row.get("metadata") or {}
        if metadata.get("thread_id") != thread_id:
            continue
        if metadata.get("request_kind") != request_kind:
            continue
        if row.get("status") in {"streaming", "awaiting_plan"}:
            return row
    return None


async def find_resume_assistant_message(token: str, chat_id: str, thread_id: str) -> dict[str, Any] | None:
    db = _db_client(token)
    res = (
        _message_select(db)
        .eq("chat_id", chat_id)
        .eq("role", "assistant")
        .order("seq", desc=True)
        .limit(10)
        .execute()
    )
    for row in res.data or []:
        metadata = row.get("metadata") or {}
        if metadata.get("thread_id") != thread_id:
            continue
        if row.get("status") == "awaiting_plan":
            return row
    for row in res.data or []:
        metadata = row.get("metadata") or {}
        if metadata.get("thread_id") == thread_id:
            return row
    return None


async def update_assistant_message(
    token: str,
    message_id: str,
    *,
    content: str | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if content is not None:
        payload["content"] = content
    if status is not None:
        payload["status"] = status
    if metadata is not None:
        payload["metadata"] = metadata
    if not payload:
        raise HTTPException(status_code=500, detail="No assistant message update payload")

    db = _service_db_client()
    res = db.table("messages").update(payload).eq("id", message_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Assistant message not found")
    return res.data[0]


async def ensure_stream_chat(
    token: str,
    user_id: str,
    query: str,
    thread_id: str,
    chat_id: str | None,
) -> dict[str, Any]:
    if chat_id:
        chat = await get_owned_chat(token, user_id, chat_id)
        if chat.get("thread_id") and chat["thread_id"] != thread_id:
            raise HTTPException(status_code=409, detail="chat_id and thread_id refer to different sessions")
        return chat

    existing = await get_owned_chat_by_thread(token, user_id, thread_id)
    if existing:
        return existing
    return await create_chat(token, user_id, _short_title(query), thread_id=thread_id)


async def ensure_resume_chat(
    token: str,
    user_id: str,
    thread_id: str,
    chat_id: str | None,
) -> dict[str, Any]:
    if chat_id:
        chat = await get_owned_chat(token, user_id, chat_id)
        if chat.get("thread_id") and chat["thread_id"] != thread_id:
            raise HTTPException(status_code=409, detail="chat_id and thread_id refer to different sessions")
        return chat

    chat = await get_owned_chat_by_thread(token, user_id, thread_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


async def start_stream_turn(
    token: str,
    user_id: str,
    query: str,
    thread_id: str,
    chat_id: str | None,
    client_message_id: str | None,
    request_kind: str,
) -> dict[str, Any]:
    chat = await ensure_stream_chat(token, user_id, query, thread_id, chat_id)
    title_update = _short_title(query) if chat.get("title") in (None, "", DEFAULT_CHAT_TITLE) else None
    user_message = await insert_user_message(token, chat["id"], query, thread_id, request_kind, client_message_id)
    assistant_message = await find_assistant_message_for_turn(token, chat["id"], thread_id, request_kind)
    if assistant_message is None:
        assistant_message = await create_assistant_message(token, chat["id"], thread_id, request_kind)
    chat = await update_chat(
        token,
        user_id,
        chat["id"],
        thread_id=thread_id,
        status="running",
        last_message_at=user_message.get("created_at") or _now_iso(),
        title=title_update,
    )
    return {"chat": chat, "user_message": user_message, "assistant_message": assistant_message}


async def start_resume_turn(
    token: str,
    user_id: str,
    thread_id: str,
    chat_id: str | None,
) -> dict[str, Any]:
    chat = await ensure_resume_chat(token, user_id, thread_id, chat_id)
    assistant_message = await find_resume_assistant_message(token, chat["id"], thread_id)
    if assistant_message is None:
        assistant_message = await create_assistant_message(token, chat["id"], thread_id, "resume")
    chat = await update_chat(token, user_id, chat["id"], thread_id=thread_id, status="running")
    return {"chat": chat, "assistant_message": assistant_message}
