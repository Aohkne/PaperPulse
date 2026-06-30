from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.shared.models.paper import Paper


class TopicMonitorQueryStub:
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


class TopicMonitorDBStub:
    def __init__(self):
        self.tables = {
            "research_topics": [],
            "user_topic_interests": [],
            "papers": [],
            "topic_paper_matches": [],
            "notification_events": [],
            "chats": [],
        }
        self._seq = 0

    def table(self, name):
        return TopicMonitorQueryStub(self, name)

    def _next_id(self, table_name):
        self._seq += 1
        prefix = {
            "research_topics": "topic",
            "user_topic_interests": "interest",
            "papers": "paper",
            "topic_paper_matches": "match",
            "notification_events": "event",
            "chats": "chat",
        }[table_name]
        return f"{prefix}-{self._seq}"

    def _now(self):
        self._seq += 1
        return f"2026-06-25T10:00:{self._seq:02d}Z"

    def execute(self, query):
        rows = self.tables[query.table_name]
        filtered = []
        for row in rows:
            if not all(row.get(key) == value for key, value in query.filters.items()):
                continue
            keep = True
            for key, value in query.is_filters.items():
                if value == "null":
                    keep = row.get(key) is None
                else:
                    keep = row.get(key) is value
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
                "id": self._next_id(query.table_name),
                "created_at": payload.get("created_at", now),
                "updated_at": payload.get("updated_at", now),
                **payload,
            }
            if query.table_name == "topic_paper_matches":
                row.setdefault("first_seen_at", now)
            rows.append(row)
            return SimpleNamespace(data=[row])

        if query.method == "update":
            updated = []
            for row in rows:
                if not all(row.get(key) == value for key, value in query.filters.items()):
                    continue
                is_match = True
                for key, value in query.is_filters.items():
                    if value == "null":
                        is_match = row.get(key) is None
                    else:
                        is_match = row.get(key) is value
                    if not is_match:
                        break
                if not is_match:
                    continue
                first_seen_at = row.get("first_seen_at")
                row.update(query.payload)
                row["updated_at"] = self._now()
                if first_seen_at is not None:
                    row["first_seen_at"] = first_seen_at
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=[])


@pytest.fixture
def monitor_db(monkeypatch):
    from backend.shared.services import topic_monitoring

    db = TopicMonitorDBStub()
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
            topic_monitor_max_papers_per_topic_per_run=50,
            topic_monitor_cooldown_hours=24,
            topic_monitor_in_app_threshold=0.72,
        ),
    )
    return db


def _seed_topic(db, *, topic_id, label, normalized_query):
    db.tables["research_topics"].append(
        {
            "id": topic_id,
            "label": label,
            "normalized_query": normalized_query,
            "keywords": [],
            "created_at": "2026-06-24T00:00:00Z",
            "updated_at": "2026-06-24T00:00:00Z",
        }
    )


def _seed_interest(db, *, interest_id, user_id, topic_id, score, state, last_checked_at=None):
    db.tables["user_topic_interests"].append(
        {
            "id": interest_id,
            "user_id": user_id,
            "topic_id": topic_id,
            "interest_score": score,
            "state": state,
            "auto_watch_reason": "new_session" if state == "auto_watching" else None,
            "last_checked_at": last_checked_at,
            "last_notified_at": None,
            "created_at": "2026-06-24T00:00:00Z",
            "updated_at": "2026-06-24T12:00:00Z",
        }
    )


@pytest.mark.asyncio
async def test_list_monitor_candidates_filters_auto_watching_and_cooldown(monitor_db):
    from backend.shared.services import topic_monitoring

    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    fresh = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    stale = (now - timedelta(hours=30)).isoformat().replace("+00:00", "Z")

    _seed_topic(monitor_db, topic_id="topic-1", label="GraphRAG", normalized_query="graphrag")
    _seed_topic(monitor_db, topic_id="topic-2", label="RAG Eval", normalized_query="rag eval")
    _seed_topic(monitor_db, topic_id="topic-3", label="Muted", normalized_query="muted")
    _seed_interest(
        monitor_db,
        interest_id="interest-1",
        user_id="user-1",
        topic_id="topic-1",
        score=8,
        state="auto_watching",
        last_checked_at=stale,
    )
    _seed_interest(
        monitor_db,
        interest_id="interest-2",
        user_id="user-1",
        topic_id="topic-2",
        score=7,
        state="auto_watching",
        last_checked_at=fresh,
    )
    _seed_interest(
        monitor_db,
        interest_id="interest-3",
        user_id="user-1",
        topic_id="topic-3",
        score=9,
        state="muted",
        last_checked_at=stale,
    )

    candidates = await topic_monitoring.list_monitor_candidates(now=now)

    assert [item["topic"]["id"] for item in candidates] == ["topic-1"]


@pytest.mark.asyncio
async def test_run_topic_monitor_upserts_matches_and_notification_events_idempotently(monkeypatch, monitor_db):
    from backend.shared.services import topic_monitoring

    _seed_topic(monitor_db, topic_id="topic-1", label="GraphRAG evaluation", normalized_query="graphrag evaluation")
    _seed_interest(
        monitor_db,
        interest_id="interest-1",
        user_id="user-1",
        topic_id="topic-1",
        score=9,
        state="auto_watching",
        last_checked_at="2026-06-20T00:00:00Z",
    )

    calls = []

    async def fake_s2(query, limit=0, fields_of_study=None):
        calls.append(("s2", query, limit))
        return [
            Paper(
                paperId="s2-1",
                title="GraphRAG evaluation benchmarks for retrieval quality",
                abstract="A recent benchmark for GraphRAG evaluation and retrieval quality.",
                year=2026,
                citationCount=120,
                authors=["Alice"],
                url="https://example.org/s2-1",
                openAccessPdf="https://example.org/s2-1.pdf",
                externalIds={"DOI": "10.1000/graphrag-1"},
                source="semantic_scholar",
            )
        ]

    async def fake_openalex(query, limit=0):
        calls.append(("openalex", query, limit))
        return [
            Paper(
                paperId="OA_W123",
                title="GraphRAG evaluation benchmarks for retrieval quality",
                abstract="Duplicate DOI from OpenAlex.",
                year=2026,
                citationCount=30,
                authors=["Bob"],
                url="https://openalex.org/W123",
                externalIds={"DOI": "10.1000/graphrag-1"},
                source="openalex",
            )
        ]

    async def fake_arxiv(query, limit=0):
        calls.append(("arxiv", query, limit))
        return [
            Paper(
                paperId="arxiv:0901.0001",
                title="Legacy retrieval systems overview",
                abstract="An old unrelated survey.",
                year=2010,
                citationCount=1,
                authors=["Carol"],
                url="https://arxiv.org/abs/0901.0001",
                externalIds={"ArXiv": "0901.0001"},
                source="arxiv",
            )
        ]

    async def fake_pubmed(query, limit=0):
        calls.append(("pubmed", query, limit))
        return []

    monkeypatch.setattr(topic_monitoring.semantic_scholar, "search_papers", fake_s2)
    monkeypatch.setattr(topic_monitoring, "search_openalex", fake_openalex)
    monkeypatch.setattr(topic_monitoring.arxiv_fetcher, "arxiv_search", fake_arxiv)
    monkeypatch.setattr(topic_monitoring, "search_pubmed", fake_pubmed)

    first = await topic_monitoring.run_topic_monitor(now=datetime(2026, 6, 25, 12, 0, tzinfo=UTC))
    monitor_db.tables["user_topic_interests"][0]["last_checked_at"] = "2026-06-20T00:00:00Z"
    second = await topic_monitoring.run_topic_monitor(now=datetime(2026, 6, 27, 12, 0, tzinfo=UTC))

    assert first["processed_topics"] == 1
    assert second["processed_topics"] == 1
    assert {call[0] for call in calls} == {"s2", "openalex", "arxiv", "pubmed"}
    assert all(call[1] == "graphrag evaluation" for call in calls)

    assert len(monitor_db.tables["papers"]) == 2
    assert len(monitor_db.tables["topic_paper_matches"]) == 2
    assert len(monitor_db.tables["notification_events"]) == 1

    strong_match = next(
        row
        for row in monitor_db.tables["topic_paper_matches"]
        if row["paper_id"] == monitor_db.tables["papers"][0]["id"]
    )
    assert strong_match["hybrid_score"] >= 0.72
    assert strong_match["reason"]

    event = monitor_db.tables["notification_events"][0]
    assert event["channel"] == "in_app"
    assert event["status"] == "created"
    assert monitor_db.tables["user_topic_interests"][0]["last_checked_at"]


@pytest.mark.asyncio
async def test_run_topic_monitor_skips_recent_topics_and_soft_fails_per_topic(monkeypatch, monitor_db):
    from backend.shared.services import topic_monitoring

    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    _seed_topic(monitor_db, topic_id="topic-1", label="Failing", normalized_query="failing")
    _seed_topic(monitor_db, topic_id="topic-2", label="Healthy", normalized_query="healthy")
    _seed_interest(
        monitor_db,
        interest_id="interest-1",
        user_id="user-1",
        topic_id="topic-1",
        score=9,
        state="auto_watching",
        last_checked_at="2026-06-20T00:00:00Z",
    )
    _seed_interest(
        monitor_db,
        interest_id="interest-2",
        user_id="user-1",
        topic_id="topic-2",
        score=8,
        state="auto_watching",
        last_checked_at="2026-06-20T00:00:00Z",
    )

    async def fake_process(interest, topic):
        if topic["id"] == "topic-1":
            raise RuntimeError("remote timeout")
        return {"topic_id": topic["id"], "matches": 0, "events_created": 0}

    monkeypatch.setattr(topic_monitoring, "process_monitor_topic", fake_process)

    result = await topic_monitoring.run_topic_monitor(now=now)

    assert result["processed_topics"] == 1
    assert result["skipped_topics"] == 1
    assert result["results"] == [{"topic_id": "topic-2", "matches": 0, "events_created": 0}]


def test_compute_topic_paper_scores_and_threshold_guard(monitor_db):
    from backend.shared.services import topic_monitoring

    topic = {"label": "GraphRAG evaluation", "normalized_query": "graphrag evaluation"}
    strong = Paper(
        paperId="s2-strong",
        title="GraphRAG evaluation benchmark design",
        abstract="This paper studies GraphRAG evaluation benchmark design and retrieval quality.",
        year=2026,
        citationCount=150,
        authors=["Alice"],
        url="https://example.org/strong",
        openAccessPdf="https://example.org/strong.pdf",
        externalIds={"DOI": "10.1000/strong"},
        source="semantic_scholar",
    )
    weak = Paper(
        paperId="s2-weak",
        title="A historical overview of databases",
        abstract="A broad retrospective article.",
        year=2005,
        citationCount=0,
        authors=["Bob"],
        url="https://example.org/weak",
        externalIds={"DOI": "10.1000/weak"},
        source="semantic_scholar",
    )

    strong_scores = topic_monitoring.compute_topic_paper_scores(topic, strong)
    weak_scores = topic_monitoring.compute_topic_paper_scores(topic, weak)

    assert strong_scores["hybrid_score"] > weak_scores["hybrid_score"]
    assert topic_monitoring.paper_passes_in_app_threshold(strong_scores) is True
    assert topic_monitoring.paper_passes_in_app_threshold(weak_scores) is False
