import math
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock


class _FakeRpcResponse:
    """Mimics httpx.Response just enough for the gap_*_store RPC call sites."""

    def __init__(self, data):
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._data


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    return 1.0 - dot / (na * nb)


class FakeVectorRpcBackend:
    """In-memory stand-in for a gap-detection pgvector table + its RPC functions
    (supabase/schema.sql §17) — lets tests exercise upsert/query/clear without a
    real Supabase connection, with the same contract (cosine distance, ascending
    = closer) as the real `match_gap_nim_papers`/`match_gap_specter_papers` RPCs.
    """

    def __init__(self, upsert_fn: str, match_fn: str, clear_fn: str, get_by_ids_fn: str | None = None):
        self.rows: dict[str, dict] = {}
        self._upsert_fn = upsert_fn
        self._match_fn = match_fn
        self._clear_fn = clear_fn
        self._get_by_ids_fn = get_by_ids_fn

    async def post(self, url, json=None, headers=None, timeout=None):
        payload = json or {}
        if url.endswith(f"/{self._upsert_fn}"):
            self.rows[payload["p_paper_id"]] = {
                "embedding": payload["p_embedding"],
                "title": payload.get("p_title", ""),
                "year": payload.get("p_year"),
            }
            return _FakeRpcResponse(None)
        if url.endswith(f"/{self._match_fn}"):
            q = payload["query_embedding"]
            n = payload["match_count"]
            scored = sorted(
                ((pid, _cosine_distance(q, r["embedding"])) for pid, r in self.rows.items()),
                key=lambda x: x[1],
            )
            return _FakeRpcResponse([{"paper_id": pid, "distance": d} for pid, d in scored[:n]])
        if self._get_by_ids_fn and url.endswith(f"/{self._get_by_ids_fn}"):
            ids = payload["p_paper_ids"]
            return _FakeRpcResponse(
                [{"paper_id": pid, "embedding": self.rows[pid]["embedding"]} for pid in ids if pid in self.rows]
            )
        if url.endswith(f"/{self._clear_fn}"):
            self.rows.clear()
            return _FakeRpcResponse(None)
        raise AssertionError(f"unexpected RPC url in fake backend: {url}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def fake_gap_specter_store(monkeypatch):
    """Patches gap_specter_store's httpx.AsyncClient with an in-memory fake table."""
    backend = FakeVectorRpcBackend(
        upsert_fn="upsert_gap_specter_embedding",
        match_fn="match_gap_specter_papers",
        clear_fn="clear_gap_specter_embeddings",
        get_by_ids_fn="get_gap_specter_embeddings_by_ids",
    )
    monkeypatch.setattr(
        "backend.agent.gap_detection.gap_specter_store.httpx.AsyncClient",
        lambda *a, **k: backend,
    )
    return backend


@pytest.fixture
def fake_gap_nim_store(monkeypatch):
    """Patches gap_nim_store's httpx.AsyncClient with an in-memory fake table."""
    backend = FakeVectorRpcBackend(
        upsert_fn="upsert_gap_nim_embedding",
        match_fn="match_gap_nim_papers",
        clear_fn="clear_gap_nim_embeddings",
    )
    monkeypatch.setattr(
        "backend.agent.gap_detection.gap_nim_store.httpx.AsyncClient",
        lambda *a, **k: backend,
    )
    return backend
