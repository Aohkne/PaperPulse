from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class TopicQueryStub:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.method = None
        self.payload = None
        self.filters = {}
        self.limit_value = None

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

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return self.db.execute(self)


class TopicSignalDBStub:
    def __init__(self):
        self.tables = {
            "research_topics": [],
            "user_topic_interests": [],
            "chats": [
                {
                    "id": "chat-1",
                    "user_id": "user-1",
                    "title": "Topic chat",
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
            ],
        }
        self._seq = 0

    def table(self, name):
        return TopicQueryStub(self, name)

    def _next_id(self, table_name):
        self._seq += 1
        return {
            "research_topics": f"topic-{self._seq}",
            "user_topic_interests": f"interest-{self._seq}",
        }.get(table_name, f"row-{self._seq}")

    def _now(self):
        self._seq += 1
        return f"2026-06-25T10:00:{self._seq:02d}Z"

    def execute(self, query):
        rows = self.tables[query.table_name]
        filtered = []
        for row in rows:
            ok = True
            for key, value in query.filters.items():
                if value == "null":
                    ok = ok and row.get(key) is None
                else:
                    ok = ok and row.get(key) == value
            if ok:
                filtered.append(row)

        if query.method == "select":
            data = list(filtered)
            if query.limit_value is not None:
                data = data[: query.limit_value]
            return SimpleNamespace(data=data)

        if query.method == "insert":
            payload = dict(query.payload)
            now = self._now()
            row = {
                "id": self._next_id(query.table_name),
                "created_at": now,
                "updated_at": now,
                **payload,
            }
            rows.append(row)
            return SimpleNamespace(data=[row])

        if query.method == "update":
            updated = []
            for row in rows:
                ok = True
                for key, value in query.filters.items():
                    if value == "null":
                        ok = ok and row.get(key) is None
                    else:
                        ok = ok and row.get(key) == value
                if ok:
                    row.update(query.payload)
                    row["updated_at"] = self._now()
                    updated.append(dict(row))
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=[])


@pytest.fixture
def topic_signal_db(monkeypatch):
    from backend.shared.services import topic_monitoring

    db = TopicSignalDBStub()
    monkeypatch.setattr(topic_monitoring, "_service_db_client", lambda: db)
    monkeypatch.setattr(
        topic_monitoring,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_service_key="service",
            max_auto_topics_per_user=3,
            topic_extraction_max_query_length=200,
            topic_extraction_min_alnum_chars=3,
        ),
    )
    return db


@pytest.mark.asyncio
async def test_new_session_scores_topic_and_sets_chat_marker(topic_signal_db):
    from backend.shared.services import topic_monitoring

    result = await topic_monitoring.score_topic_signal(
        "user-1",
        signal="new_session",
        query="Find papers about GraphRAG evaluation methods",
        chat_id="chat-1",
        token="token",
    )

    assert result["interest"]["interest_score"] == topic_monitoring.TOPIC_SCORE_NEW_SESSION
    assert topic_signal_db.tables["chats"][0]["topic_id"] == result["topic"]["id"]


@pytest.mark.asyncio
async def test_followup_reuses_same_topic_interest_row(topic_signal_db):
    from backend.shared.services import topic_monitoring

    first = await topic_monitoring.score_topic_signal(
        "user-1", signal="new_session", query="GraphRAG evaluation", chat_id="chat-1", token="token"
    )
    second = await topic_monitoring.score_topic_signal(
        "user-1", signal="followup", query="  graphrag   evaluation!! ", chat_id="chat-1", token="token"
    )

    assert len(topic_signal_db.tables["research_topics"]) == 1
    assert len(topic_signal_db.tables["user_topic_interests"]) == 1
    assert first["topic"]["id"] == second["topic"]["id"]
    assert second["interest"]["interest_score"] == (
        topic_monitoring.TOPIC_SCORE_NEW_SESSION + topic_monitoring.TOPIC_SCORE_FOLLOWUP
    )


@pytest.mark.asyncio
async def test_resume_and_reopen_reinforce_existing_chat_topic(topic_signal_db):
    from backend.shared.services import topic_monitoring

    await topic_monitoring.score_topic_signal(
        "user-1", signal="new_session", query="retrieval evaluation benchmarks", chat_id="chat-1", token="token"
    )
    resumed = await topic_monitoring.score_topic_signal(
        "user-1", signal="plan_approval", chat_id="chat-1", token="token"
    )
    resumed_score = resumed["interest"]["interest_score"]
    reopened = await topic_monitoring.score_topic_signal(
        "user-1", signal="reopen", chat_id="chat-1", token="token"
    )

    assert resumed_score == (
        topic_monitoring.TOPIC_SCORE_NEW_SESSION + topic_monitoring.TOPIC_SCORE_PLAN_APPROVAL
    )
    assert reopened["interest"]["interest_score"] == (
        topic_monitoring.TOPIC_SCORE_NEW_SESSION
        + topic_monitoring.TOPIC_SCORE_PLAN_APPROVAL
        + topic_monitoring.TOPIC_SCORE_REOPEN
    )


@pytest.mark.asyncio
async def test_junk_input_does_not_create_topic_rows(topic_signal_db):
    from backend.shared.services import topic_monitoring

    result = await topic_monitoring.score_topic_signal(
        "user-1", signal="new_session", query=" !!! ", chat_id="chat-1", token="token"
    )

    assert result is None
    assert topic_signal_db.tables["research_topics"] == []
    assert topic_signal_db.tables["user_topic_interests"] == []


def test_extract_topic_candidate_strips_boilerplate(topic_signal_db):
    from backend.shared.services import topic_monitoring

    candidate = topic_monitoring.extract_topic_candidate("Find papers about GraphRAG evaluation methods")

    assert candidate == {
        "label": "GraphRAG evaluation methods",
        "normalized_query": "graphrag evaluation methods",
    }


@pytest.mark.asyncio
async def test_score_topic_signal_rejects_unsupported_signal(topic_signal_db):
    from backend.shared.services import topic_monitoring

    with pytest.raises(HTTPException) as exc_info:
        await topic_monitoring.score_topic_signal("user-1", signal="unknown", query="topic")

    assert exc_info.value.status_code == 400
