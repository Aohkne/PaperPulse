from types import SimpleNamespace

import pytest

from backend.auth.dependencies import get_current_user
from backend.main import app


async def _override_user():
    return SimpleNamespace(id="user-1", email="user@example.com")


@pytest.mark.asyncio
async def test_get_notification_settings_returns_owner_row(client, monkeypatch):
    from backend.api import notifications as notifications_api

    async def fake_get_notification_settings(user_id):
        assert user_id == "user-1"
        return {"pause_all_in_app": True}

    monkeypatch.setattr(notifications_api.topic_monitoring, "get_notification_settings", fake_get_notification_settings)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/notification-settings", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"pause_all_in_app": True}


@pytest.mark.asyncio
async def test_patch_notification_settings_updates_pause_all(client, monkeypatch):
    from backend.api import notifications as notifications_api

    async def fake_update_notification_settings(user_id, *, pause_all_in_app):
        assert (user_id, pause_all_in_app) == ("user-1", True)
        return {"pause_all_in_app": True}

    monkeypatch.setattr(
        notifications_api.topic_monitoring, "update_notification_settings", fake_update_notification_settings
    )
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.patch(
        "/api/notification-settings",
        json={"pause_all_in_app": True},
        headers={"Authorization": "Bearer test-token"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"pause_all_in_app": True}
