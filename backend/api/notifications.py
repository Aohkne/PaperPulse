from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client, create_client

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.shared.services import topic_monitoring

router = APIRouter(tags=["notifications"])
_bearer = HTTPBearer(auto_error=True)
log = logging.getLogger(__name__)


class NotificationPaperRef(BaseModel):
    id: str | None = None
    title: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract_snippet: str | None = None
    year: int | None = None


class NotificationItem(BaseModel):
    id: str
    type: str
    content: str
    is_read: bool
    topic_id: str | None = None
    paper_id: str | None = None
    reason: str | None = None
    score: float | None = None
    paper_ref: NotificationPaperRef
    created_at: str


class NotificationListResponse(BaseModel):
    unread_count: int
    items: list[NotificationItem]


class NotificationUpdateRequest(BaseModel):
    is_read: bool = True


class MarkAllReadResponse(BaseModel):
    updated: int


class NotificationSettingsResponse(BaseModel):
    pause_all_in_app: bool


class NotificationSettingsUpdateRequest(BaseModel):
    pause_all_in_app: bool


def _db_client(token: str) -> Client:
    settings = get_settings()
    if settings.supabase_service_key:
        return create_client(settings.supabase_url, settings.supabase_service_key)
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.auth(token)
    return client


def _map_notification(row: dict[str, Any]) -> NotificationItem:
    return NotificationItem(
        id=row["id"],
        type=row["type"],
        content=row["content"],
        is_read=bool(row.get("is_read")),
        topic_id=row.get("topic_id"),
        paper_id=row.get("paper_id"),
        reason=row.get("reason"),
        score=float(row["score"]) if row.get("score") is not None else None,
        paper_ref=NotificationPaperRef(**(row.get("paper_ref") or {})),
        created_at=row["created_at"],
    )


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> NotificationListResponse:
    try:
        await topic_monitoring.run_topic_monitor(user_id=str(user.id))
    except HTTPException as exc:
        if exc.status_code >= 500:
            log.warning("notification-triggered topic monitor failed for user_id=%s: %s", user.id, exc.detail)
    except Exception as exc:
        log.warning("notification-triggered topic monitor failed for user_id=%s: %s", user.id, exc)

    try:
        await topic_monitoring.deliver_in_app_notifications(user_id=str(user.id))
    except HTTPException as exc:
        if exc.status_code >= 500:
            log.warning("notification lazy delivery failed for user_id=%s: %s", user.id, exc.detail)
    except Exception as exc:
        log.warning("notification lazy delivery failed for user_id=%s: %s", user.id, exc)

    db = _db_client(credentials.credentials)
    res = (
        db.table("notifications")
        .select("id,type,content,paper_ref,is_read,created_at,topic_id,paper_id,reason,score")
        .eq("user_id", str(user.id))
        .order("is_read")
        .order("created_at", desc=True)
        .execute()
    )
    items = [_map_notification(row) for row in (res.data or [])]
    unread_count = sum(1 for item in items if not item.is_read)
    return NotificationListResponse(unread_count=unread_count, items=items)


@router.patch("/notifications/{notification_id}", response_model=NotificationItem)
async def mark_notification_read(
    notification_id: str,
    body: NotificationUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> NotificationItem:
    db = _db_client(credentials.credentials)
    res = (
        db.table("notifications")
        .update({"is_read": body.is_read})
        .eq("id", notification_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _map_notification(res.data[0])


@router.post("/notifications/mark-all-read", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> MarkAllReadResponse:
    db = _db_client(credentials.credentials)
    unread = (
        db.table("notifications")
        .select("id")
        .eq("user_id", str(user.id))
        .eq("is_read", False)
        .execute()
    )
    unread_ids = [row["id"] for row in (unread.data or [])]
    if not unread_ids:
        return MarkAllReadResponse(updated=0)

    updated = 0
    for notification_id in unread_ids:
        res = (
            db.table("notifications")
            .update({"is_read": True})
            .eq("id", notification_id)
            .eq("user_id", str(user.id))
            .execute()
        )
        if res.data:
            updated += 1

    return MarkAllReadResponse(updated=updated)


@router.get("/notification-settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> NotificationSettingsResponse:
    row = await topic_monitoring.get_notification_settings(str(user.id))
    return NotificationSettingsResponse(pause_all_in_app=bool(row.get("pause_all_in_app")))


@router.patch("/notification-settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    body: NotificationSettingsUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> NotificationSettingsResponse:
    row = await topic_monitoring.update_notification_settings(str(user.id), pause_all_in_app=body.pause_all_in_app)
    return NotificationSettingsResponse(pause_all_in_app=bool(row.get("pause_all_in_app")))


