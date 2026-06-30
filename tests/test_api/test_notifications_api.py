from types import SimpleNamespace

import pytest

from backend.auth.dependencies import get_current_user
from backend.main import app


class NotificationQueryStub:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.filters = {}
        self.payload = None
        self.method = None
        self.orders = []

    def select(self, _fields):
        self.method = "select"
        return self

    def insert(self, payload):
        self.method = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.method = "update"
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, desc=False, **_kwargs):
        self.orders.append((key, desc))
        return self

    def execute(self):
        return self.db.execute(self)


class NotificationDBStub:
    def __init__(self):
        self.notifications = [
            {
                "id": "note-1",
                "user_id": "user-1",
                "type": "new_paper",
                "content": 'New paper for your topic "GraphRAG evaluation"',
                "paper_ref": {"id": "paper-1", "title": "Paper One", "url": "https://example.org/1"},
                "is_read": False,
                "created_at": "2026-06-25T12:00:00Z",
                "topic_id": "topic-1",
                "paper_id": "paper-1",
                "reason": "strong keyword overlap",
                "score": 0.83,
            },
            {
                "id": "note-2",
                "user_id": "user-1",
                "type": "new_paper",
                "content": 'New paper for your topic "RAG evaluation"',
                "paper_ref": {"id": "paper-2", "title": "Paper Two"},
                "is_read": True,
                "created_at": "2026-06-24T12:00:00Z",
                "topic_id": "topic-2",
                "paper_id": "paper-2",
                "reason": "recent publication",
                "score": 0.75,
            },
            {
                "id": "note-other",
                "user_id": "user-2",
                "type": "new_paper",
                "content": "Other user notice",
                "paper_ref": {"id": "paper-3", "title": "Paper Three"},
                "is_read": False,
                "created_at": "2026-06-25T10:00:00Z",
                "topic_id": "topic-3",
                "paper_id": "paper-3",
                "reason": "semantic-topic similarity",
                "score": 0.79,
            },
        ]

    def table(self, name):
        return NotificationQueryStub(self, name)

    def execute(self, query):
        if query.table_name != "notifications":
            return SimpleNamespace(data=[])

        rows = [row for row in self.notifications if all(row.get(key) == value for key, value in query.filters.items())]

        if query.method == "select":
            for key, desc in reversed(query.orders):
                rows.sort(key=lambda row: row.get(key), reverse=desc)
            return SimpleNamespace(data=list(rows))

        if query.method == "update":
            updated = []
            for row in self.notifications:
                if not all(row.get(key) == value for key, value in query.filters.items()):
                    continue
                row.update(query.payload)
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=[])


async def _override_user():
    return SimpleNamespace(id="user-1", email="user@example.com")


@pytest.mark.asyncio
async def test_list_notifications_is_owner_scoped_and_triggers_monitor_then_lazy_delivery(client, monkeypatch):
    from backend.api import notifications as notifications_api

    monitor_calls = []
    delivery_calls = []
    call_order = []

    async def fake_run_topic_monitor(**kwargs):
        monitor_calls.append(kwargs)
        call_order.append("monitor")
        return {"processed_topics": 0, "skipped_topics": 0, "results": []}

    async def fake_deliver_in_app_notifications(**kwargs):
        delivery_calls.append(kwargs)
        call_order.append("deliver")
        return {"processed": 0, "created": 0, "sent": 0, "skipped": 0, "failed": 0}

    monkeypatch.setattr(notifications_api, "_db_client", lambda _token: NotificationDBStub())
    monkeypatch.setattr(notifications_api.topic_monitoring, "run_topic_monitor", fake_run_topic_monitor)
    monkeypatch.setattr(
        notifications_api.topic_monitoring, "deliver_in_app_notifications", fake_deliver_in_app_notifications
    )
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/notifications", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert monitor_calls == [{"user_id": "user-1"}]
    assert delivery_calls == [{"user_id": "user-1"}]
    assert call_order == ["monitor", "deliver"]
    assert data["unread_count"] == 1
    assert [item["id"] for item in data["items"]] == ["note-1", "note-2"]


@pytest.mark.asyncio
async def test_list_notifications_degrades_safely_when_monitor_trigger_fails(client, monkeypatch):
    from backend.api import notifications as notifications_api

    delivery_calls = []

    async def fake_run_topic_monitor(**kwargs):
        raise RuntimeError(f"source timeout for {kwargs['user_id']}")

    async def fake_deliver_in_app_notifications(**kwargs):
        delivery_calls.append(kwargs)
        return {"processed": 0, "created": 0, "sent": 0, "skipped": 0, "failed": 0}

    monkeypatch.setattr(notifications_api, "_db_client", lambda _token: NotificationDBStub())
    monkeypatch.setattr(notifications_api.topic_monitoring, "run_topic_monitor", fake_run_topic_monitor)
    monkeypatch.setattr(
        notifications_api.topic_monitoring, "deliver_in_app_notifications", fake_deliver_in_app_notifications
    )
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/notifications", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert delivery_calls == [{"user_id": "user-1"}]
    assert [item["id"] for item in response.json()["items"]] == ["note-1", "note-2"]


@pytest.mark.asyncio
async def test_mark_one_notification_read_is_owner_safe(client, monkeypatch):
    from backend.api import notifications as notifications_api

    db = NotificationDBStub()
    monkeypatch.setattr(notifications_api, "_db_client", lambda _token: db)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.patch(
        "/api/notifications/note-1",
        json={"is_read": True},
        headers={"Authorization": "Bearer test-token"},
    )
    missing = await client.patch(
        "/api/notifications/note-other",
        json={"is_read": True},
        headers={"Authorization": "Bearer test-token"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert missing.status_code == 404
    assert next(row for row in db.notifications if row["id"] == "note-1")["is_read"] is True
    assert next(row for row in db.notifications if row["id"] == "note-other")["is_read"] is False


@pytest.mark.asyncio
async def test_mark_all_notifications_read_updates_only_owned_rows(client, monkeypatch):
    from backend.api import notifications as notifications_api

    db = NotificationDBStub()
    monkeypatch.setattr(notifications_api, "_db_client", lambda _token: db)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.post("/api/notifications/mark-all-read", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"updated": 1}
    assert all(row["is_read"] is True for row in db.notifications if row["user_id"] == "user-1")
    assert next(row for row in db.notifications if row["id"] == "note-other")["is_read"] is False
