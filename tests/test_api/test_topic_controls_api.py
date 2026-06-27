from types import SimpleNamespace

import pytest

from backend.auth.dependencies import get_current_user
from backend.main import app


async def _override_user():
    return SimpleNamespace(id="user-1", email="user@example.com")


@pytest.mark.asyncio
async def test_list_topic_interests_is_owner_scoped(client, monkeypatch):
    from backend.api import topics as topics_api

    async def fake_get_notification_settings(user_id):
        assert user_id == "user-1"
        return {"pause_all_in_app": True}

    async def fake_list_user_topic_interests(user_id):
        assert user_id == "user-1"
        return [
            {
                "topic_id": "topic-1",
                "label": "GraphRAG evaluation",
                "normalized_query": "graphrag evaluation",
                "state": "auto_watching",
                "interest_score": 5.0,
                "auto_watch_reason": "new_session",
                "last_checked_at": None,
                "last_notified_at": None,
                "updated_at": "2026-06-25T12:00:00Z",
            },
            {
                "topic_id": "topic-2",
                "label": "RAG tracing",
                "normalized_query": "rag tracing",
                "state": "muted",
                "interest_score": 3.0,
                "auto_watch_reason": None,
                "last_checked_at": None,
                "last_notified_at": None,
                "updated_at": "2026-06-25T10:00:00Z",
            },
        ]

    monkeypatch.setattr(topics_api.topic_monitoring, "get_notification_settings", fake_get_notification_settings)
    monkeypatch.setattr(topics_api.topic_monitoring, "list_user_topic_interests", fake_list_user_topic_interests)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/topics/interests", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["pause_all_in_app"] is True
    assert [item["topic_id"] for item in data["items"]] == ["topic-1", "topic-2"]


@pytest.mark.asyncio
async def test_patch_topic_interest_updates_state(client, monkeypatch):
    from backend.api import topics as topics_api

    async def fake_update_user_topic_state(user_id, topic_id, *, state):
        assert (user_id, topic_id, state) == ("user-1", "topic-1", "muted")
        return {
            "topic_id": topic_id,
            "label": "GraphRAG evaluation",
            "normalized_query": "graphrag evaluation",
            "state": "muted",
            "interest_score": 5.0,
            "auto_watch_reason": None,
            "last_checked_at": None,
            "last_notified_at": None,
            "updated_at": "2026-06-25T12:00:00Z",
        }

    monkeypatch.setattr(topics_api.topic_monitoring, "update_user_topic_state", fake_update_user_topic_state)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.patch(
        "/api/topics/interests/topic-1",
        json={"state": "muted"},
        headers={"Authorization": "Bearer test-token"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["state"] == "muted"


@pytest.mark.asyncio
async def test_delete_topic_interest_soft_deletes(client, monkeypatch):
    from backend.api import topics as topics_api

    calls = []

    async def fake_delete_user_topic_interest(user_id, topic_id):
        calls.append((user_id, topic_id))

    monkeypatch.setattr(topics_api.topic_monitoring, "delete_user_topic_interest", fake_delete_user_topic_interest)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.delete("/api/topics/interests/topic-1", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 204
    assert calls == [("user-1", "topic-1")]
