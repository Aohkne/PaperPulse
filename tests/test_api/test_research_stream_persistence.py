import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.auth.dependencies import get_current_user
from backend.main import app


async def _override_user():
    return SimpleNamespace(id="user-1", email="user@example.com")


@pytest.fixture(autouse=True)
def _stub_is_chat_deleted(monkeypatch):
    from backend.module.research_agent.api import research

    async def _not_deleted(*_args, **_kwargs):
        return False

    monkeypatch.setattr(research.chat_persistence, "is_chat_deleted", _not_deleted)


class MessageQueryStub:
    def __init__(self, db):
        self.db = db
        self.filters = {}
        self.method = None
        self.payload = None
        self.order_desc = False
        self.limit_value = None

    def select(self, _fields):
        self.method = "select"
        return self

    def insert(self, payload):
        self.method = "insert"
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, field, desc=False):
        if field == "seq":
            self.order_desc = desc
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = list(self.db.messages)
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        if self.method == "select":
            rows.sort(key=lambda row: row.get("seq") or 0, reverse=self.order_desc)
            if self.limit_value is not None:
                rows = rows[: self.limit_value]
            return SimpleNamespace(data=rows)
        if self.method == "insert":
            row = {"id": f"msg-{len(self.db.messages) + 1}", **self.payload}
            self.db.messages.append(row)
            return SimpleNamespace(data=[row])
        return SimpleNamespace(data=[])


class ChatQueryStub:
    def __init__(self, db):
        self.db = db
        self.filters = {}
        self.method = None
        self.payload = None

    def select(self, _fields):
        self.method = "select"
        return self

    def update(self, payload):
        self.method = "update"
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, _value):
        return self

    def is_(self, key, value):
        self.filters[key] = value
        return self

    def execute(self):
        rows = list(self.db.chats)
        for key, value in self.filters.items():
            if value == "null":
                rows = [row for row in rows if row.get(key) is None]
            else:
                rows = [row for row in rows if row.get(key) == value]
        if self.method == "select":
            return SimpleNamespace(data=rows[:1])
        if self.method == "update":
            for row in self.db.chats:
                if row["id"] == self.filters.get("id") and row["user_id"] == self.filters.get("user_id"):
                    row.update(self.payload)
                    return SimpleNamespace(data=[row])
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=[])


class PersistenceDBStub:
    def __init__(self):
        self.chats = [
            {
                "id": "chat-1",
                "user_id": "user-1",
                "title": "New chat",
                "feature": "research",
                "status": "idle",
                "summary": None,
                "thread_id": "thread-1",
                "topic_id": None,
                "created_at": "2026-06-25T10:00:00Z",
                "updated_at": "2026-06-25T10:00:00Z",
                "last_message_at": None,
                "deleted_at": None,
            }
        ]
        self.messages = [
            {
                "id": "msg-1",
                "chat_id": "chat-1",
                "role": "user",
                "content": "same query",
                "seq": 1,
                "status": "done",
                "client_message_id": "client-1",
                "metadata": {"thread_id": "thread-1", "request_kind": "followup"},
                "created_at": "2026-06-25T10:01:00Z",
            },
            {
                "id": "msg-2",
                "chat_id": "chat-1",
                "role": "assistant",
                "content": "",
                "seq": 2,
                "status": "streaming",
                "client_message_id": None,
                "metadata": {"thread_id": "thread-1", "request_kind": "followup", "steps": []},
                "created_at": "2026-06-25T10:02:00Z",
            },
        ]

    def table(self, name):
        if name == "messages":
            return MessageQueryStub(self)
        if name == "chats":
            return ChatQueryStub(self)
        raise AssertionError(name)


@pytest.mark.asyncio
async def test_start_stream_turn_reuses_existing_client_message_and_assistant(monkeypatch):
    from backend.shared.services import chat_persistence

    db = PersistenceDBStub()
    monkeypatch.setattr(chat_persistence, "_db_client", lambda _token: db)

    turn = await chat_persistence.start_stream_turn(
        token="token",
        user_id="user-1",
        query="same query",
        thread_id="thread-1",
        chat_id="chat-1",
        client_message_id="client-1",
        request_kind="followup",
    )

    assert turn["user_message"]["id"] == "msg-1"
    assert turn["assistant_message"]["id"] == "msg-2"
    assert len(db.messages) == 2


@pytest.mark.asyncio
async def test_research_stream_creates_or_binds_chat_and_persists_done_state(client, monkeypatch):
    from backend.module.research_agent.api import research

    calls = {"start_session": [], "turn": None, "assistant": [], "chat": [], "topic": []}

    async def start_session(user_id, feature, session_id):
        calls["start_session"].append((user_id, feature, session_id))
        return {"source": "subscription"}

    async def start_stream_turn(**kwargs):
        calls["turn"] = kwargs
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {"id": "assistant-1"},
            "user_message": {"id": "user-1", "created_at": "2026-06-25T10:01:00Z"},
        }

    async def score_topic_signal(user_id, **kwargs):
        calls["topic"].append({"user_id": user_id, **kwargs})
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 5}}

    async def update_assistant_message(token, message_id, **kwargs):
        calls["assistant"].append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        calls["chat"].append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id, **kwargs}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse(
            {"type": "step", "step_type": "observation", "stepNum": "0", "content": "Plan ready", "stat": "1 sub-query"}
        )
        yield research._sse({"type": "done", "content": "Final answer", "bib": "refs"})

    monkeypatch.setattr(research.billing_db, "start_session", start_session)
    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_stream_turn", start_stream_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/stream",
        json={"query": "Test durable chat", "client_message_id": "client-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.text
    assert '"type": "thread_id"' in body
    assert '"chat_id": "chat-1"' in body
    assert calls["start_session"] and calls["start_session"][0][1] == "lr"
    assert calls["turn"]["chat_id"] is None
    assert calls["turn"]["client_message_id"] == "client-1"
    assert calls["topic"] == [
        {
            "user_id": "user-1",
            "signal": "new_session",
            "query": "Test durable chat",
            "chat_id": "chat-1",
            "token": "test-token",
        }
    ]
    assert calls["assistant"][-1]["status"] == "done"
    assert calls["assistant"][-1]["content"] == "Final answer"
    assert calls["chat"][-1]["status"] == "complete"


@pytest.mark.asyncio
async def test_research_stream_existing_chat_new_thread_charges_quota_once(client, monkeypatch):
    from backend.module.research_agent.api import research

    calls = {"start_session": 0, "turn": None}

    async def start_session(_user_id, _feature, _session_id):
        calls["start_session"] += 1
        return {"source": "subscription"}

    async def start_stream_turn(**kwargs):
        calls["turn"] = kwargs
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {"id": "assistant-1"},
            "user_message": {"id": "user-1", "created_at": "2026-06-25T10:01:00Z"},
        }

    async def update_assistant_message(*_args, **_kwargs):
        return {"id": "assistant-1"}

    async def update_chat(*_args, **_kwargs):
        return {"id": "chat-1"}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse({"type": "done", "content": "Fresh session answer", "bib": ""})

    monkeypatch.setattr(research.billing_db, "start_session", start_session)
    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_stream_turn", start_stream_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/stream",
        json={
            "query": "Fresh session in persisted chat",
            "thread_id": None,
            "chat_id": "chat-1",
            "client_message_id": "client-2",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls["start_session"] == 1
    assert calls["turn"]["chat_id"] == "chat-1"
    assert calls["turn"]["thread_id"] is not None
    assert calls["turn"]["client_message_id"] == "client-2"


@pytest.mark.asyncio
async def test_research_stream_followup_existing_thread_still_skips_new_quota_charge(client, monkeypatch):
    from backend.module.research_agent.api import research

    calls = {"start_session": 0, "turn": None, "topic": []}

    async def start_session(_user_id, _feature, _session_id):
        calls["start_session"] += 1
        return {"source": "subscription"}

    async def start_stream_turn(**kwargs):
        calls["turn"] = kwargs
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {"id": "assistant-1"},
            "user_message": {"id": "user-1", "created_at": "2026-06-25T10:01:00Z"},
        }

    async def score_topic_signal(user_id, **kwargs):
        calls["topic"].append({"user_id": user_id, **kwargs})
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 8}}

    async def update_assistant_message(*_args, **_kwargs):
        return {"id": "assistant-1"}

    async def update_chat(*_args, **_kwargs):
        return {"id": "chat-1"}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse({"type": "done", "content": "Follow-up answer", "bib": ""})

    monkeypatch.setattr(research.billing_db, "start_session", start_session)
    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_stream_turn", start_stream_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/stream",
        json={"query": "Follow-up", "thread_id": "thread-1", "chat_id": "chat-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls["start_session"] == 0
    assert calls["topic"] == [
        {"user_id": "user-1", "signal": "followup", "query": "Follow-up", "chat_id": "chat-1", "token": "test-token"}
    ]
    assert calls["turn"]["chat_id"] == "chat-1"
    assert calls["turn"]["thread_id"] == "thread-1"


@pytest.mark.asyncio
async def test_research_stream_interrupt_persists_awaiting_plan(client, monkeypatch):
    from backend.module.research_agent.api import research

    assistant_updates = []
    chat_updates = []

    async def start_stream_turn(**_kwargs):
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {"id": "assistant-1"},
            "user_message": {"id": "user-1", "created_at": "2026-06-25T10:01:00Z"},
        }

    async def update_assistant_message(token, message_id, **kwargs):
        assistant_updates.append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        chat_updates.append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, thread_id):
        yield research._sse(
            {"type": "interrupt", "thread_id": thread_id, "data": {"sub_queries": ["q1"], "plan_description": "Plan"}}
        )

    async def start_session(_user_id, _feature, _session_id):
        return {"source": "subscription"}

    monkeypatch.setattr(research.billing_db, "start_session", start_session)
    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_stream_turn", start_stream_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/stream",
        json={"query": "Need a plan"},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert assistant_updates[-1]["status"] == "awaiting_plan"
    assert assistant_updates[-1]["content"] == ""
    assert assistant_updates[-1]["metadata"]["pending_plan"]["sub_queries"] == ["q1"]
    assert chat_updates[-1]["status"] == "awaiting_plan"


@pytest.mark.asyncio
async def test_research_stream_rejects_missing_owned_chat(client, monkeypatch):
    from backend.module.research_agent.api import research

    async def start_stream_turn(**_kwargs):
        raise HTTPException(status_code=404, detail="Chat not found")

    monkeypatch.setattr(research, "get_research_graph", lambda: object())
    monkeypatch.setattr(research.chat_persistence, "start_stream_turn", start_stream_turn)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/stream",
        json={"query": "Test", "thread_id": "thread-1", "chat_id": "chat-missing"},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_research_resume_updates_same_chat_without_quota_charge(client, monkeypatch):
    from backend.module.research_agent.api import research

    calls = {"assistant": [], "chat": [], "start_session": 0, "topic": []}

    async def start_session(_user_id, _feature, _session_id):
        calls["start_session"] += 1
        return {"source": "subscription"}

    async def start_resume_turn(**kwargs):
        assert kwargs["chat_id"] == "chat-1"
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {
                "id": "assistant-1",
                "content": "",
                "metadata": {"steps": [], "pending_plan": {"sub_queries": ["q1"]}},
            },
        }

    async def score_topic_signal(user_id, **kwargs):
        calls["topic"].append({"user_id": user_id, **kwargs})
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 8}}

    async def update_assistant_message(token, message_id, **kwargs):
        calls["assistant"].append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        calls["chat"].append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse({"type": "done", "content": "Resumed answer", "bib": "refs"})

    monkeypatch.setattr(research.billing_db, "start_session", start_session)
    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_resume_turn", start_resume_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/resume",
        json={"thread_id": "thread-1", "chat_id": "chat-1", "resume_value": True},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls["start_session"] == 0
    assert calls["topic"] == [
        {"user_id": "user-1", "signal": "plan_approval", "chat_id": "chat-1", "token": "test-token"}
    ]
    assert calls["assistant"][0]["status"] == "streaming"
    assert calls["assistant"][0]["content"] == ""
    assert calls["assistant"][0]["metadata"].get("pending_plan") is None
    assert calls["chat"][0]["status"] == "running"
    assert calls["assistant"][-1]["status"] == "done"
    assert calls["assistant"][-1]["metadata"].get("pending_plan") is None
    assert calls["assistant"][-1]["content"] == "Resumed answer"
    assert calls["chat"][-1]["status"] == "complete"


@pytest.mark.asyncio
async def test_research_resume_clears_stale_pending_plan_before_first_resume_event(client, monkeypatch):
    from backend.module.research_agent.api import research

    assistant_updates = []
    chat_updates = []

    async def start_resume_turn(**kwargs):
        assert kwargs["chat_id"] == "chat-1"
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {
                "id": "assistant-1",
                "content": "User wants to search ...\n\nAwaiting approval to continue.",
                "metadata": {
                    "steps": [{"stepNum": "0", "type": "observation", "content": "Plan ready", "stat": "1 sub-query"}],
                    "pending_plan": {"sub_queries": ["q1"], "plan_description": "User wants to search ..."},
                },
            },
        }

    async def score_topic_signal(*_args, **_kwargs):
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 8}}

    async def update_assistant_message(token, message_id, **kwargs):
        assistant_updates.append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        chat_updates.append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse({"type": "done", "content": "Resumed answer", "bib": "refs"})

    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_resume_turn", start_resume_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/resume",
        json={"thread_id": "thread-1", "chat_id": "chat-1", "resume_value": True},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert assistant_updates[0]["status"] == "streaming"
    assert assistant_updates[0]["content"] == ""
    assert assistant_updates[0]["metadata"].get("pending_plan") is None
    assert assistant_updates[0]["metadata"]["steps"][0]["stepNum"] == "0"
    assert chat_updates[0]["status"] == "running"
    assert assistant_updates[-1]["status"] == "done"
    assert assistant_updates[-1]["content"] == "Resumed answer"
    assert assistant_updates[-1]["metadata"].get("pending_plan") is None
    assert chat_updates[-1]["status"] == "complete"


@pytest.mark.asyncio
async def test_research_resume_clears_stale_pending_plan_and_content_once_steps_continue(client, monkeypatch):
    from backend.module.research_agent.api import research

    assistant_updates = []
    chat_updates = []

    async def start_resume_turn(**kwargs):
        assert kwargs["chat_id"] == "chat-1"
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {
                "id": "assistant-1",
                "content": "User wants to search ...\n\nAwaiting approval to continue.",
                "metadata": {
                    "steps": [{"stepNum": "0", "type": "observation", "content": "Plan ready", "stat": "1 sub-query"}],
                    "pending_plan": {"sub_queries": ["q1"], "plan_description": "User wants to search ..."},
                },
            },
        }

    async def score_topic_signal(*_args, **_kwargs):
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 8}}

    async def update_assistant_message(token, message_id, **kwargs):
        assistant_updates.append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        chat_updates.append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse(
            {
                "type": "step",
                "step_type": "observation",
                "stepNum": "1",
                "content": "10 papers fetched.",
                "stat": "total:10",
            }
        )
        yield research._sse({"type": "done", "content": "Resumed answer", "bib": "refs"})

    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_resume_turn", start_resume_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/resume",
        json={"thread_id": "thread-1", "chat_id": "chat-1", "resume_value": True},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert assistant_updates[0]["status"] == "streaming"
    assert assistant_updates[0]["content"] == ""
    assert assistant_updates[0]["metadata"].get("pending_plan") is None
    assert assistant_updates[0]["metadata"]["steps"][0]["stepNum"] == "0"
    assert assistant_updates[0]["metadata"]["steps"][-1]["stepNum"] == "1"
    assert assistant_updates[-1]["status"] == "done"
    assert assistant_updates[-1]["content"] == "Resumed answer"
    assert assistant_updates[-1]["metadata"].get("pending_plan") is None
    assert chat_updates[-1]["status"] == "complete"


@pytest.mark.asyncio
async def test_research_stream_stops_when_chat_is_deleted_mid_run(client, monkeypatch):
    from backend.module.research_agent.api import research
    from backend.shared.services.chat_persistence import ChatDeletedError

    assistant_updates = []
    chat_updates = []
    deleted = {"value": False}

    async def start_stream_turn(**_kwargs):
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {"id": "assistant-1"},
            "user_message": {"id": "user-1", "created_at": "2026-06-25T10:01:00Z"},
        }

    async def update_assistant_message(token, message_id, **kwargs):
        if deleted["value"]:
            raise ChatDeletedError()
        assistant_updates.append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        if deleted["value"]:
            raise ChatDeletedError()
        chat_updates.append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse(
            {
                "type": "step",
                "step_type": "observation",
                "stepNum": "1",
                "content": "First running step",
                "stat": "phase-1",
            }
        )
        deleted["value"] = True
        yield research._sse(
            {
                "type": "step",
                "step_type": "observation",
                "stepNum": "2",
                "content": "Second running step",
                "stat": "phase-2",
            }
        )
        yield research._sse({"type": "done", "content": "Final answer after delete", "bib": "refs"})

    async def start_session(_user_id, _feature, _session_id):
        return {"source": "subscription"}

    monkeypatch.setattr(research.billing_db, "start_session", start_session)
    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)

    async def is_chat_deleted(*_args, **_kwargs):
        return deleted["value"]

    monkeypatch.setattr(research.chat_persistence, "start_stream_turn", start_stream_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.chat_persistence, "is_chat_deleted", is_chat_deleted)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/stream",
        json={"query": "Delete mid-run"},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.text
    assert '"code": "chat_deleted"' in body
    assert "Final answer after delete" not in body
    assert len(assistant_updates) == 1
    assert assistant_updates[0]["status"] == "streaming"
    assert len(chat_updates) == 0


@pytest.mark.asyncio
async def test_research_resume_stops_when_chat_is_deleted_mid_run(client, monkeypatch):
    from backend.module.research_agent.api import research
    from backend.shared.services.chat_persistence import ChatDeletedError

    assistant_updates = []
    chat_updates = []
    deleted = {"value": False}

    async def start_resume_turn(**kwargs):
        assert kwargs["chat_id"] == "chat-1"
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {
                "id": "assistant-1",
                "content": "",
                "metadata": {
                    "steps": [{"stepNum": "0", "type": "observation", "content": "Plan ready", "stat": "1 sub-query"}]
                },
            },
        }

    async def score_topic_signal(*_args, **_kwargs):
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 8}}

    async def update_assistant_message(token, message_id, **kwargs):
        if deleted["value"]:
            raise ChatDeletedError()
        assistant_updates.append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        if deleted["value"]:
            raise ChatDeletedError()
        chat_updates.append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse(
            {
                "type": "step",
                "step_type": "observation",
                "stepNum": "1",
                "content": "Resumed running step",
                "stat": "phase-1",
            }
        )
        deleted["value"] = True
        yield research._sse({"type": "done", "content": "Resumed answer after delete", "bib": "refs"})

    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_resume_turn", start_resume_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/resume",
        json={"thread_id": "thread-1", "chat_id": "chat-1", "resume_value": True},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.text
    assert '"code": "chat_deleted"' in body
    assert "Resumed answer after delete" not in body
    assert len(assistant_updates) == 1
    assert assistant_updates[0]["status"] == "streaming"
    assert not any(item.get("status") == "complete" for item in chat_updates)


@pytest.mark.asyncio
async def test_research_resume_rejects_deleted_or_cross_user_chat(client, monkeypatch):
    from backend.module.research_agent.api import research

    async def start_resume_turn(**_kwargs):
        raise HTTPException(status_code=404, detail="Chat not found")

    monkeypatch.setattr(research.chat_persistence, "start_resume_turn", start_resume_turn)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/resume",
        json={"thread_id": "thread-1", "chat_id": "chat-deleted", "resume_value": True},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stream_graph_stops_heartbeats_and_late_steps_once_delete_is_observed(monkeypatch):
    from backend.module.research_agent.api import research

    class GraphStub:
        def __init__(self):
            self.state_requested = False

        async def astream_events(self, _input, _config, version="v2"):
            yield {
                "event": "on_chain_end",
                "name": "parallel_search",
                "data": {"output": {"search_stats": {"s2": 3}}},
                "metadata": {"langgraph_node": "parallel_search"},
            }
            await asyncio.sleep(0)
            yield {
                "event": "on_chain_end",
                "name": "dedup",
                "data": {"output": {"papers": [1, 2]}},
                "metadata": {"langgraph_node": "dedup"},
            }

        async def aget_state(self, _config):
            self.state_requested = True
            return SimpleNamespace(next=(), tasks=[])

    deleted = {"value": False}
    graph = GraphStub()

    async def stop_requested():
        return deleted["value"]

    events = []
    with pytest.raises(research._DeletedChatTerminationError):
        async for raw_event in research._stream_graph(
            graph,
            {"query": "Delete during later phase"},
            {"configurable": {"thread_id": "thread-1"}},
            "thread-1",
            stop_requested=stop_requested,
        ):
            payload = research._parse_sse(raw_event)
            events.append(payload)
            if payload and payload.get("stepNum") == "1":
                deleted["value"] = True

    assert [event.get("stepNum") for event in events if event and event.get("type") == "step"] == ["1"]
    assert not any(event.get("type") == "heartbeat" for event in events if event)
    assert graph.state_requested is False


@pytest.mark.asyncio
async def test_research_resume_emits_chat_deleted_during_early_step_token_phase(client, monkeypatch):
    from backend.module.research_agent.api import research

    deleted_poll_calls = {"count": 0}

    class Chunk:
        def __init__(self, content):
            self.content = content

    class GraphStub:
        async def astream_events(self, _input, _config, version="v2"):
            yield {
                "event": "on_chat_model_stream",
                "name": "parallel_search",
                "data": {"chunk": Chunk("token-1")},
                "metadata": {"langgraph_node": "parallel_search"},
            }
            yield {
                "event": "on_chat_model_stream",
                "name": "parallel_search",
                "data": {"chunk": Chunk("token-2")},
                "metadata": {"langgraph_node": "parallel_search"},
            }
            yield {
                "event": "on_chain_end",
                "name": "final_answer",
                "data": {"output": {"answer": "should not finish", "bib_markdown": "refs"}},
                "metadata": {"langgraph_node": "final_answer"},
            }

    async def start_resume_turn(**kwargs):
        assert kwargs["chat_id"] == "chat-1"
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {
                "id": "assistant-1",
                "content": "",
                "metadata": {"steps": []},
            },
        }

    async def score_topic_signal(*_args, **_kwargs):
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 8}}

    async def get_graph():
        return GraphStub()

    async def is_chat_deleted(*_args, **_kwargs):
        deleted_poll_calls["count"] += 1
        return deleted_poll_calls["count"] >= 5

    def immediate_deleted_poller(*, poll_deleted, chat_id, interval_seconds=0.5):
        async def _poll():
            return await poll_deleted()

        return _poll

    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_build_deleted_chat_poller", immediate_deleted_poller)
    monkeypatch.setattr(research.chat_persistence, "start_resume_turn", start_resume_turn)
    monkeypatch.setattr(research.chat_persistence, "is_chat_deleted", is_chat_deleted)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/resume",
        json={"thread_id": "thread-1", "chat_id": "chat-1", "resume_value": True},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.text
    assert "token-1" in body
    assert "token-2" not in body
    assert "should not finish" not in body
    assert '"code": "chat_deleted"' in body


@pytest.mark.asyncio
async def test_deleted_chat_poller_throttles_reads_within_interval(monkeypatch):
    from backend.module.research_agent.api import research

    polls = []
    times = iter([100.0, 100.1, 100.2, 100.8])
    original_monotonic = research.time.monotonic

    async def poll_deleted():
        polls.append("poll")
        return False

    monkeypatch.setattr(research.time, "monotonic", lambda: next(times, original_monotonic()))
    poller = research._build_deleted_chat_poller(poll_deleted=poll_deleted, chat_id="chat-1", interval_seconds=0.5)

    assert await poller() is False
    assert await poller() is False
    assert await poller() is False
    assert await poller() is False
    assert len(polls) == 2


@pytest.mark.asyncio
async def test_deleted_chat_poller_fails_open_on_transport_error_then_recovers(monkeypatch):
    import httpx

    from backend.module.research_agent.api import research

    calls = {"count": 0}
    times = iter([200.0, 200.6, 201.2])
    original_monotonic = research.time.monotonic

    async def poll_deleted():
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.RemoteProtocolError("Server disconnected")
        return True

    monkeypatch.setattr(research.time, "monotonic", lambda: next(times, original_monotonic()))
    poller = research._build_deleted_chat_poller(poll_deleted=poll_deleted, chat_id="chat-1", interval_seconds=0.5)

    assert await poller() is False
    assert await poller() is True
    assert await poller() is True


@pytest.mark.asyncio
async def test_research_resume_ignores_transient_deleted_poll_transport_error(client, monkeypatch):
    import httpx

    from backend.module.research_agent.api import research

    assistant_updates = []
    chat_updates = []
    deleted_checks = {"count": 0}

    async def start_resume_turn(**kwargs):
        assert kwargs["chat_id"] == "chat-1"
        return {
            "chat": {"id": "chat-1"},
            "assistant_message": {
                "id": "assistant-1",
                "content": "",
                "metadata": {"steps": []},
            },
        }

    async def score_topic_signal(*_args, **_kwargs):
        return {"topic": {"id": "topic-1"}, "interest": {"id": "interest-1", "interest_score": 8}}

    async def update_assistant_message(token, message_id, **kwargs):
        assistant_updates.append({"token": token, "message_id": message_id, **kwargs})
        return {"id": message_id}

    async def update_chat(token, user_id, chat_id, **kwargs):
        chat_updates.append({"token": token, "user_id": user_id, "chat_id": chat_id, **kwargs})
        return {"id": chat_id}

    async def get_graph():
        return object()

    async def stream_graph(_graph, _input, _config, _thread_id):
        yield research._sse(
            {
                "type": "step",
                "step_type": "observation",
                "stepNum": "1",
                "content": "Resumed running step",
                "stat": "phase-1",
            }
        )
        yield research._sse({"type": "done", "content": "Resumed answer", "bib": "refs"})

    async def is_chat_deleted(*_args, **_kwargs):
        deleted_checks["count"] += 1
        if deleted_checks["count"] == 1:
            raise httpx.RemoteProtocolError("Server disconnected")
        return False

    monkeypatch.setattr(research, "get_research_graph", get_graph)
    monkeypatch.setattr(research, "_stream_graph", stream_graph)
    monkeypatch.setattr(research.chat_persistence, "start_resume_turn", start_resume_turn)
    monkeypatch.setattr(research.chat_persistence, "update_assistant_message", update_assistant_message)
    monkeypatch.setattr(research.chat_persistence, "update_chat", update_chat)
    monkeypatch.setattr(research.chat_persistence, "is_chat_deleted", is_chat_deleted)
    monkeypatch.setattr(research.topic_monitoring, "score_topic_signal", score_topic_signal)

    app.dependency_overrides[get_current_user] = _override_user
    response = await client.post(
        "/api/research/resume",
        json={"thread_id": "thread-1", "chat_id": "chat-1", "resume_value": True},
        headers={"Authorization": "Bearer test-token"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.text
    assert "Server disconnected" not in body
    assert '"type": "error"' not in body
    assert "Resumed answer" in body
    assert assistant_updates[-1]["status"] == "done"
    assert chat_updates[-1]["status"] == "complete"
