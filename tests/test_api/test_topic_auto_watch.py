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

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return self.db.execute(self)


class TopicDBStub:
    def __init__(self):
        self.tables = {
            "research_topics": [],
            "user_topic_interests": [],
        }
        self._seq = 0

    def table(self, name):
        return TopicQueryStub(self, name)

    def _next_id(self, table_name):
        self._seq += 1
        prefix = {
            "research_topics": "topic",
            "user_topic_interests": "interest",
        }[table_name]
        return f"{prefix}-{self._seq}"

    def _now(self):
        self._seq += 1
        return f"2026-06-25T10:00:{self._seq:02d}Z"

    def execute(self, query):
        rows = self.tables[query.table_name]
        filtered = [row for row in rows if all(row.get(key) == value for key, value in query.filters.items())]

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
                "created_at": payload.get("created_at", now),
                "updated_at": payload.get("updated_at", now),
                **payload,
            }
            rows.append(row)
            return SimpleNamespace(data=[row])

        if query.method == "update":
            updated = []
            for row in rows:
                if all(row.get(key) == value for key, value in query.filters.items()):
                    row.update(query.payload)
                    row["updated_at"] = self._now()
                    updated.append(dict(row))
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=[])


@pytest.fixture
def topic_db(monkeypatch):
    from backend.shared.services import topic_monitoring

    db = TopicDBStub()
    monkeypatch.setattr(topic_monitoring, "_service_db_client", lambda: db)
    monkeypatch.setattr(
        topic_monitoring,
        "get_settings",
        lambda: SimpleNamespace(supabase_url="https://example.supabase.co", supabase_service_key="service", max_auto_topics_per_user=3),
    )
    return db


@pytest.mark.asyncio
async def test_topic_upsert_reuses_canonical_topic_by_normalized_query(topic_db):
    from backend.shared.services import topic_monitoring

    first = await topic_monitoring.upsert_user_topic_interest(
        "user-1",
        "  GraphRAG   evaluation!!! ",
        interest_score=4,
    )
    second = await topic_monitoring.upsert_user_topic_interest(
        "user-1",
        "graphrag evaluation",
        score_delta=2,
    )

    assert len(topic_db.tables["research_topics"]) == 1
    assert first["topic"]["id"] == second["topic"]["id"]
    assert second["interest"]["interest_score"] == 6.0
    assert len(topic_db.tables["user_topic_interests"]) == 1


@pytest.mark.asyncio
async def test_rebalance_keeps_only_top_three_auto_watching(topic_db):
    from backend.shared.services import topic_monitoring

    await topic_monitoring.upsert_user_topic_interest("user-1", "topic one", interest_score=1)
    await topic_monitoring.upsert_user_topic_interest("user-1", "topic two", interest_score=5)
    await topic_monitoring.upsert_user_topic_interest("user-1", "topic three", interest_score=3)
    await topic_monitoring.upsert_user_topic_interest("user-1", "topic four", interest_score=4)

    rows = topic_db.tables["user_topic_interests"]
    auto_labels = []
    candidate_labels = []
    topics_by_id = {row["id"]: row for row in topic_db.tables["research_topics"]}
    for row in rows:
        label = topics_by_id[row["topic_id"]]["label"]
        if row["state"] == "auto_watching":
            auto_labels.append(label)
            assert row["auto_watch_reason"]
        elif row["state"] == "candidate":
            candidate_labels.append(label)
            assert row["auto_watch_reason"] is None

    assert sorted(auto_labels) == ["topic four", "topic three", "topic two"]
    assert candidate_labels == ["topic one"]


@pytest.mark.asyncio
async def test_muted_and_deleted_topics_are_not_auto_promoted(topic_db):
    from backend.shared.services import topic_monitoring

    muted = await topic_monitoring.upsert_user_topic_interest("user-1", "muted topic", interest_score=10)
    deleted = await topic_monitoring.upsert_user_topic_interest("user-1", "deleted topic", interest_score=9)

    for row in topic_db.tables["user_topic_interests"]:
        if row["id"] == muted["interest"]["id"]:
            row["state"] = "muted"
            row["auto_watch_reason"] = None
        if row["id"] == deleted["interest"]["id"]:
            row["state"] = "deleted"
            row["auto_watch_reason"] = None

    await topic_monitoring.upsert_user_topic_interest("user-1", "candidate one", interest_score=8)
    await topic_monitoring.upsert_user_topic_interest("user-1", "candidate two", interest_score=7)
    await topic_monitoring.upsert_user_topic_interest("user-1", "candidate three", interest_score=6)
    await topic_monitoring.rebalance_auto_watch_topics("user-1")

    state_by_topic = {}
    topics_by_id = {row["id"]: row for row in topic_db.tables["research_topics"]}
    for row in topic_db.tables["user_topic_interests"]:
        state_by_topic[topics_by_id[row["topic_id"]]["label"]] = row["state"]

    assert state_by_topic["muted topic"] == "muted"
    assert state_by_topic["deleted topic"] == "deleted"
    assert state_by_topic["candidate one"] == "auto_watching"
    assert state_by_topic["candidate two"] == "auto_watching"
    assert state_by_topic["candidate three"] == "auto_watching"


def test_normalize_topic_identity_rejects_empty_payload(topic_db):
    from backend.shared.services import topic_monitoring

    with pytest.raises(HTTPException) as exc_info:
        topic_monitoring.normalize_topic_identity(" !!! ")

    assert exc_info.value.status_code == 400
