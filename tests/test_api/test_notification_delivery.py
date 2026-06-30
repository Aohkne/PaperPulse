from datetime import UTC, datetime
from types import SimpleNamespace

import pytest


class DeliveryQueryStub:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.method = None
        self.payload = None
        self.filters = {}
        self.limit_value = None
        self.is_filters = {}

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
        self.is_filters[key] = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return self.db.execute(self)


class DeliveryDBStub:
    def __init__(self):
        self.tables = {
            "research_topics": [
                {
                    "id": "topic-1",
                    "label": "GraphRAG evaluation",
                    "normalized_query": "graphrag evaluation",
                    "keywords": [],
                    "created_at": "2026-06-25T00:00:00Z",
                    "updated_at": "2026-06-25T00:00:00Z",
                }
            ],
            "user_topic_interests": [
                {
                    "id": "interest-1",
                    "user_id": "user-1",
                    "topic_id": "topic-1",
                    "interest_score": 5.0,
                    "state": "auto_watching",
                    "auto_watch_reason": "new_session",
                    "last_checked_at": None,
                    "last_notified_at": None,
                    "created_at": "2026-06-25T00:00:00Z",
                    "updated_at": "2026-06-25T00:00:00Z",
                }
            ],
            "notification_settings": [
                {
                    "user_id": "user-1",
                    "pause_all_in_app": False,
                    "created_at": "2026-06-25T00:00:00Z",
                    "updated_at": "2026-06-25T00:00:00Z",
                }
            ],
            "papers": [
                {
                    "id": "paper-1",
                    "doi": "10.1000/graphrag-1",
                    "arxiv_id": None,
                    "s2_paper_id": "s2-1",
                    "openalex_id": None,
                    "pubmed_id": None,
                    "title": "GraphRAG evaluation benchmark design",
                    "abstract": "A benchmark paper about GraphRAG evaluation and retrieval quality.",
                    "authors": ["Alice"],
                    "year": 2026,
                    "published_at": "2026-01-01T00:00:00Z",
                    "url": "https://example.org/paper-1",
                    "open_access_pdf": {"url": "https://example.org/paper-1.pdf"},
                    "source_metadata": {},
                    "created_at": "2026-06-25T00:00:00Z",
                    "updated_at": "2026-06-25T00:00:00Z",
                }
            ],
            "topic_paper_matches": [
                {
                    "id": "match-1",
                    "topic_id": "topic-1",
                    "paper_id": "paper-1",
                    "vector_score": 0.82,
                    "lexical_score": 0.76,
                    "recency_score": 1.0,
                    "authority_score": 0.55,
                    "hybrid_score": 0.82,
                    "reason": "strong keyword overlap, recent publication",
                    "first_seen_at": "2026-06-25T00:00:00Z",
                    "created_at": "2026-06-25T00:00:00Z",
                    "updated_at": "2026-06-25T00:00:00Z",
                }
            ],
            "notification_events": [
                {
                    "id": "event-1",
                    "user_id": "user-1",
                    "topic_id": "topic-1",
                    "paper_id": "paper-1",
                    "channel": "in_app",
                    "status": "created",
                    "created_at": "2026-06-25T01:00:00Z",
                    "updated_at": "2026-06-25T01:00:00Z",
                }
            ],
            "notifications": [],
        }
        self._seq = 0

    def table(self, name):
        return DeliveryQueryStub(self, name)

    def _next_id(self, table_name):
        self._seq += 1
        return f"{table_name[:-1]}-{self._seq}"

    def _now(self):
        self._seq += 1
        return f"2026-06-25T12:00:{self._seq:02d}Z"

    def execute(self, query):
        rows = self.tables[query.table_name]
        filtered = []
        for row in rows:
            if not all(row.get(key) == value for key, value in query.filters.items()):
                continue
            keep = True
            for key, value in query.is_filters.items():
                keep = row.get(key) is None if value == "null" else row.get(key) is value
                if not keep:
                    break
            if keep:
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
                "id": payload.get("id", self._next_id(query.table_name)),
                "created_at": payload.get("created_at", now),
                "updated_at": payload.get("updated_at", now),
                **payload,
            }
            rows.append(row)
            return SimpleNamespace(data=[row])

        if query.method == "update":
            updated = []
            for row in rows:
                if not all(row.get(key) == value for key, value in query.filters.items()):
                    continue
                row.update(query.payload)
                row["updated_at"] = self._now()
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=[])


@pytest.fixture
def delivery_db(monkeypatch):
    from backend.shared.services import topic_monitoring

    db = DeliveryDBStub()
    monkeypatch.setattr(topic_monitoring, "_service_db_client", lambda: db)
    return db


@pytest.mark.asyncio
async def test_deliver_in_app_notifications_creates_notification_and_marks_event_sent(delivery_db):
    from backend.shared.services import topic_monitoring

    result = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")

    assert result == {"processed": 1, "created": 1, "sent": 1, "skipped": 0, "failed": 0}
    assert len(delivery_db.tables["notifications"]) == 1
    notification = delivery_db.tables["notifications"][0]
    assert notification["type"] == "new_paper"
    assert notification["topic_id"] == "topic-1"
    assert notification["paper_id"] == "paper-1"
    assert notification["paper_ref"]["title"] == "GraphRAG evaluation benchmark design"
    assert delivery_db.tables["notification_events"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_deliver_in_app_notifications_is_idempotent_for_existing_notification(delivery_db):
    from backend.shared.services import topic_monitoring

    delivery_db.tables["notifications"].append(
        {
            "id": "notification-1",
            "user_id": "user-1",
            "type": "new_paper",
            "content": 'New paper for your topic "GraphRAG evaluation"',
            "paper_ref": {"id": "paper-1", "title": "GraphRAG evaluation benchmark design"},
            "is_read": False,
            "created_at": "2026-06-25T01:05:00Z",
            "topic_id": "topic-1",
            "paper_id": "paper-1",
            "reason": "strong keyword overlap, recent publication",
            "score": 0.82,
        }
    )

    result = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")

    assert result == {"processed": 1, "created": 0, "sent": 1, "skipped": 0, "failed": 0}
    assert len(delivery_db.tables["notifications"]) == 1
    assert delivery_db.tables["notification_events"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_deliver_in_app_notifications_leaves_created_events_queued_while_paused(delivery_db):
    from backend.shared.services import topic_monitoring

    delivery_db.tables["notification_settings"][0]["pause_all_in_app"] = True

    result = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")

    assert result == {"processed": 1, "created": 0, "sent": 0, "skipped": 0, "failed": 0}
    assert delivery_db.tables["notification_events"][0]["status"] == "created"
    assert delivery_db.tables["notifications"] == []


@pytest.mark.asyncio
async def test_deliver_in_app_notifications_releases_queued_event_after_unpause_without_duplication(delivery_db):
    from backend.shared.services import topic_monitoring

    delivery_db.tables["notification_settings"][0]["pause_all_in_app"] = True

    paused = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")

    assert paused == {"processed": 1, "created": 0, "sent": 0, "skipped": 0, "failed": 0}
    assert delivery_db.tables["notification_events"][0]["status"] == "created"
    assert delivery_db.tables["notifications"] == []

    delivery_db.tables["notification_settings"][0]["pause_all_in_app"] = False

    unpaused = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")
    repeated = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")

    assert unpaused == {"processed": 1, "created": 1, "sent": 1, "skipped": 0, "failed": 0}
    assert repeated == {"processed": 0, "created": 0, "sent": 0, "skipped": 0, "failed": 0}
    assert len(delivery_db.tables["notifications"]) == 1
    assert delivery_db.tables["notification_events"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_deliver_in_app_notifications_skips_muted_or_deleted_topics(delivery_db):
    from backend.shared.services import topic_monitoring

    delivery_db.tables["user_topic_interests"][0]["state"] = "muted"

    result = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")

    assert result == {"processed": 1, "created": 0, "sent": 0, "skipped": 1, "failed": 0}
    assert delivery_db.tables["notification_events"][0]["status"] == "skipped"
    assert delivery_db.tables["notifications"] == []


@pytest.mark.asyncio
async def test_notification_open_flow_can_monitor_then_deliver_new_notification(monkeypatch, delivery_db):
    from backend.shared.models.paper import Paper
    from backend.shared.services import topic_monitoring

    delivery_db.tables["notification_events"] = []
    delivery_db.tables["notifications"] = []
    delivery_db.tables["papers"] = []
    delivery_db.tables["topic_paper_matches"] = []
    delivery_db.tables["user_topic_interests"][0]["last_checked_at"] = "2026-06-20T00:00:00Z"

    async def fake_s2(query, limit=0, fields_of_study=None):
        return [
            Paper(
                paperId="s2-new",
                title="GraphRAG evaluation benchmark design",
                abstract="A benchmark paper about GraphRAG evaluation and retrieval quality.",
                year=2026,
                citationCount=120,
                authors=["Alice"],
                url="https://example.org/paper-1",
                openAccessPdf="https://example.org/paper-1.pdf",
                externalIds={"DOI": "10.1000/graphrag-1"},
                source="semantic_scholar",
            )
        ]

    async def fake_empty(*_args, **_kwargs):
        return []

    monkeypatch.setattr(topic_monitoring.semantic_scholar, "search_papers", fake_s2)
    monkeypatch.setattr(topic_monitoring, "search_openalex", fake_empty)
    monkeypatch.setattr(topic_monitoring.arxiv_fetcher, "arxiv_search", fake_empty)
    monkeypatch.setattr(topic_monitoring, "search_pubmed", fake_empty)

    monitor_result = await topic_monitoring.run_topic_monitor(
        now=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        user_id="user-1",
    )
    delivery_result = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")
    repeated_delivery = await topic_monitoring.deliver_in_app_notifications(user_id="user-1")

    assert monitor_result["processed_topics"] == 1
    assert len(delivery_db.tables["notification_events"]) == 1
    assert delivery_result == {"processed": 1, "created": 1, "sent": 1, "skipped": 0, "failed": 0}
    assert repeated_delivery == {"processed": 0, "created": 0, "sent": 0, "skipped": 0, "failed": 0}
    assert len(delivery_db.tables["notifications"]) == 1
