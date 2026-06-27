from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.shared.services import topic_monitoring

router = APIRouter(prefix="/topics", tags=["topics"])
_bearer = HTTPBearer(auto_error=True)


class TopicInterestItem(BaseModel):
    topic_id: str
    label: str
    normalized_query: str
    state: str
    interest_score: float
    auto_watch_reason: str | None = None
    last_checked_at: str | None = None
    last_notified_at: str | None = None
    updated_at: str | None = None


class TopicInterestListResponse(BaseModel):
    pause_all_in_app: bool
    items: list[TopicInterestItem]


class TopicInterestUpdateRequest(BaseModel):
    state: str


@router.get("/interests", response_model=TopicInterestListResponse)
async def list_topic_interests(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> TopicInterestListResponse:
    settings_row = await topic_monitoring.get_notification_settings(str(user.id))
    items = await topic_monitoring.list_user_topic_interests(str(user.id))
    return TopicInterestListResponse(
        pause_all_in_app=bool(settings_row.get("pause_all_in_app")),
        items=[TopicInterestItem(**item) for item in items],
    )


@router.patch("/interests/{topic_id}", response_model=TopicInterestItem)
async def update_topic_interest(
    topic_id: str,
    body: TopicInterestUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> TopicInterestItem:
    item = await topic_monitoring.update_user_topic_state(str(user.id), topic_id, state=body.state)
    return TopicInterestItem(**item)


@router.delete("/interests/{topic_id}", status_code=204, response_model=None)
async def delete_topic_interest(
    topic_id: str,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> None:
    await topic_monitoring.delete_user_topic_interest(str(user.id), topic_id)
