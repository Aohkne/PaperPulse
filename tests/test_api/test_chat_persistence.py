from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.auth.dependencies import get_current_user
from backend.main import app


class QueryStub:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.filters = {}
        self.payload = None
        self.method = None

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

    def is_(self, key, value):
        self.filters[key] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return self.db.execute(self)


class DBStub:
    def __init__(self):
        self.chats = [
            {
                "id": "chat-a",
                "user_id": "user-1",
                "title": "Older active",
                "feature": "research",
                "status": "idle",
                "summary": None,
                "thread_id": None,
                "created_at": "2026-06-25T10:00:00Z",
                "updated_at": "2026-06-25T10:00:00Z",
                "last_message_at": "2026-06-25T10:05:00Z",
                "deleted_at": None,
            },
            {
                "id": "chat-new-empty",
                "user_id": "user-1",
                "title": "Newest empty",
                "feature": "research",
                "status": "idle",
                "summary": None,
                "thread_id": None,
                "created_at": "2026-06-25T12:00:00Z",
                "updated_at": "2026-06-25T12:00:00Z",
                "last_message_at": None,
                "deleted_at": None,
            },
            {
                "id": "chat-b",
                "user_id": "user-1",
                "title": "Deleted",
                "feature": "research",
                "status": "idle",
                "summary": None,
                "thread_id": None,
                "created_at": "2026-06-24T10:00:00Z",
                "updated_at": "2026-06-24T10:00:00Z",
                "last_message_at": None,
                "deleted_at": "2026-06-24T11:00:00Z",
            },
            {
                "id": "chat-other",
                "user_id": "user-2",
                "title": "Other user",
                "feature": "research",
                "status": "idle",
                "summary": None,
                "thread_id": None,
                "created_at": "2026-06-23T10:00:00Z",
                "updated_at": "2026-06-23T10:00:00Z",
                "last_message_at": None,
                "deleted_at": None,
            },
        ]
        self.messages = [
            {
                "id": "msg-2",
                "chat_id": "chat-a",
                "role": "assistant",
                "content": "second",
                "seq": 2,
                "status": "done",
                "client_message_id": None,
                "metadata": {},
                "created_at": "2026-06-25T10:02:00Z",
            },
            {
                "id": "msg-1",
                "chat_id": "chat-a",
                "role": "user",
                "content": "first",
                "seq": 1,
                "status": "done",
                "client_message_id": "client-1",
                "metadata": {},
                "created_at": "2026-06-25T10:01:00Z",
            },
        ]

    def table(self, name):
        return QueryStub(self, name)

    def execute(self, query):
        if query.table_name == "chats" and query.method == "select":
            rows = self.chats[:]
            for key, value in query.filters.items():
                if value == "null":
                    rows = [row for row in rows if row.get(key) is None]
                else:
                    rows = [row for row in rows if row.get(key) == value]
            rows.sort(
                key=lambda row: (
                    (row.get("last_message_at") is None),
                    row.get("last_message_at") or "",
                    row["created_at"],
                ),
                reverse=False,
            )
            return SimpleNamespace(data=rows)

        if query.table_name == "messages" and query.method == "select":
            rows = [row for row in self.messages if row["chat_id"] == query.filters.get("chat_id")]
            rows.sort(key=lambda row: ((row.get("seq") is None), row.get("seq") or 0, row["created_at"]))
            return SimpleNamespace(data=rows)

        if query.table_name == "chats" and query.method == "insert":
            row = {
                "id": "chat-new",
                "created_at": "2026-06-25T12:00:00Z",
                "updated_at": "2026-06-25T12:00:00Z",
                "last_message_at": None,
                **query.payload,
            }
            self.chats.append({**row, "deleted_at": None})
            return SimpleNamespace(data=[row])

        if query.table_name == "chats" and query.method == "update":
            rows = []
            for row in self.chats:
                if row["id"] != query.filters.get("id"):
                    continue
                if row["user_id"] != query.filters.get("user_id"):
                    continue
                if query.filters.get("deleted_at") == "null" and row.get("deleted_at") is not None:
                    continue
                row.update(query.payload)
                rows.append({k: v for k, v in row.items() if k != "deleted_at"})
            return SimpleNamespace(data=rows)

        return SimpleNamespace(data=[])


async def _override_user():
    return SimpleNamespace(id="user-1", email="user@example.com")


@pytest.mark.asyncio
async def test_list_chats_filters_and_sorts(client, monkeypatch):
    from backend.api import chat as chat_api

    monkeypatch.setattr(chat_api, "_db_client", lambda _token: DBStub())
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/chats", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == ["chat-new-empty", "chat-a"]


@pytest.mark.asyncio
async def test_create_chat_sets_owner(client, monkeypatch):
    from backend.api import chat as chat_api

    monkeypatch.setattr(chat_api, "_db_client", lambda _token: DBStub())
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.post("/api/chats", json={}, headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "chat-new"
    assert data["title"] == "New chat"


@pytest.mark.asyncio
async def test_get_chat_detail_returns_ordered_messages(client, monkeypatch):
    from backend.api import chat as chat_api

    monkeypatch.setattr(chat_api, "_db_client", lambda _token: DBStub())
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/chats/chat-a", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["chat"]["id"] == "chat-a"
    assert [item["id"] for item in data["messages"]] == ["msg-1", "msg-2"]


@pytest.mark.asyncio
async def test_get_chat_detail_schedules_reopen_topic_signal_without_blocking_response(client, monkeypatch):
    from backend.api import chat as chat_api

    calls = []

    def schedule_chat_reopen_signal(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(chat_api, "_db_client", lambda _token: DBStub())
    monkeypatch.setattr(chat_api, "_schedule_chat_reopen_signal", schedule_chat_reopen_signal)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/chats/chat-a", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert calls == [{"user_id": "user-1", "chat_id": "chat-a", "token": "test-token"}]
    assert response.json()["chat"]["topic_id"] is None


@pytest.mark.asyncio
async def test_cross_user_chat_is_hidden(client, monkeypatch):
    from backend.api import chat as chat_api

    monkeypatch.setattr(chat_api, "_db_client", lambda _token: DBStub())
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.get("/api/chats/chat-other", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_chat_soft_deletes_owned_chat(client, monkeypatch):
    db = DBStub()
    from backend.api import chat as chat_api

    monkeypatch.setattr(chat_api, "_db_client", lambda _token: db)
    app.dependency_overrides[get_current_user] = _override_user

    response = await client.delete("/api/chats/chat-a", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 204
    assert next(row for row in db.chats if row["id"] == "chat-a")["deleted_at"] is not None
    assert len([row for row in db.messages if row["chat_id"] == "chat-a"]) == 2


@pytest.mark.asyncio
async def test_update_chat_rejects_deleted_chat(monkeypatch):
    db = DBStub()
    from backend.shared.services import chat_persistence

    next(row for row in db.chats if row["id"] == "chat-a")["deleted_at"] = "2026-06-25T10:06:00Z"
    monkeypatch.setattr(chat_persistence, "_db_client", lambda _token: db)

    with pytest.raises(chat_persistence.ChatDeletedError) as exc_info:
        await chat_persistence.update_chat("test-token", "user-1", "chat-a", status="complete")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Chat deleted"


def test_update_assistant_message_requires_service_role(monkeypatch):
    from backend.shared.services import chat_persistence

    monkeypatch.setattr(
        chat_persistence,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://example.supabase.co", supabase_key="anon", supabase_service_key=""
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        chat_persistence._service_db_client()

    assert exc_info.value.status_code == 500
    assert "SUPABASE_SERVICE_KEY" in exc_info.value.detail
