"""Tests for HyDE, SPECTER store wrappers, and hybrid ranking."""

from __future__ import annotations

import os
import random
from unittest.mock import AsyncMock, patch

import pytest

_HYDE = "backend.agent.gap_detection.hyde"
_RETRIEVAL = "backend.agent.gap_detection.retrieval"
_STORE = "backend.agent.gap_detection.gap_specter_store"

_DIM = 768


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _MockAsyncClient:
    def __init__(self, post_handler):
        self._post_handler = post_handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers, timeout):
        return self._post_handler(url, json)


def _rand_vec(dim: int = _DIM, seed: int = 42) -> list[float]:
    rng = random.Random(seed)
    values = [rng.gauss(0, 1) for _ in range(dim)]
    norm = sum(x * x for x in values) ** 0.5
    return [x / norm for x in values]


def _make_paper(paper_id: str, title: str = "Paper", year: int = 2023, citations: int = 10):
    from backend.shared.models.paper import Paper

    return Paper(paperId=paper_id, title=title, year=year, citationCount=citations)


@pytest.mark.asyncio
async def test_generate_hyde_vector_success() -> None:
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    vec = _rand_vec()
    with (
        patch(
            f"{_HYDE}.chat_completion", new=AsyncMock(return_value="This paper investigates attention mechanisms...")
        ),
        patch(f"{_HYDE}.embed_text", new=AsyncMock(return_value=vec)),
    ):
        result = await generate_hyde_vector("transformer long-context attention")

    assert isinstance(result, list)
    assert len(result) == _DIM


@pytest.mark.asyncio
async def test_generate_hyde_vector_llm_fail_returns_none() -> None:
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with patch(f"{_HYDE}.chat_completion", side_effect=RuntimeError("LLM down")):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


@pytest.mark.asyncio
async def test_generate_hyde_vector_embed_fail_returns_none() -> None:
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with (
        patch(f"{_HYDE}.chat_completion", new=AsyncMock(return_value="Abstract text...")),
        patch(f"{_HYDE}.embed_text", side_effect=RuntimeError("embed down")),
    ):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


@pytest.mark.asyncio
async def test_generate_hyde_vector_embed_returns_none() -> None:
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with (
        patch(f"{_HYDE}.chat_completion", new=AsyncMock(return_value="Abstract text...")),
        patch(f"{_HYDE}.embed_text", new=AsyncMock(return_value=None)),
    ):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


@pytest.mark.asyncio
async def test_generate_hyde_vector_empty_abstract_returns_none() -> None:
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with patch(f"{_HYDE}.chat_completion", new=AsyncMock(return_value="")):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


@pytest.mark.asyncio
async def test_specter_store_upsert_and_query() -> None:
    from backend.agent.gap_detection.gap_specter_store import clear_collection, query_by_vector, upsert_papers

    def _post_handler(url: str, payload: dict) -> _MockResponse:
        if url.endswith("match_gap_specter_papers"):
            return _MockResponse(
                [
                    {"paper_id": "p2"},
                    {"paper_id": "p4"},
                    {"paper_id": "p1"},
                ]
            )
        return _MockResponse({})

    papers = [
        {"paper_id": f"p{i}", "vector": _rand_vec(seed=i), "title": f"Paper {i}", "year": 2020 + i} for i in range(5)
    ]

    with patch(f"{_STORE}.httpx.AsyncClient", return_value=_MockAsyncClient(_post_handler)):
        await clear_collection()
        count = await upsert_papers(papers)
        results = await query_by_vector(_rand_vec(seed=99), top_k=3)

    assert count == 5
    assert results == ["p2", "p4", "p1"]


@pytest.mark.asyncio
async def test_specter_store_empty_query_returns_empty() -> None:
    from backend.agent.gap_detection.gap_specter_store import clear_collection, query_by_vector

    def _post_handler(url: str, payload: dict) -> _MockResponse:
        if url.endswith("match_gap_specter_papers"):
            return _MockResponse([])
        return _MockResponse({})

    with patch(f"{_STORE}.httpx.AsyncClient", return_value=_MockAsyncClient(_post_handler)):
        await clear_collection()
        result = await query_by_vector(_rand_vec(), top_k=5)

    assert result == []


@pytest.mark.asyncio
async def test_specter_store_upsert_skips_missing_vector() -> None:
    from backend.agent.gap_detection.gap_specter_store import clear_collection, upsert_papers

    def _post_handler(url: str, payload: dict) -> _MockResponse:
        return _MockResponse({})

    papers = [
        {"paper_id": "p0", "vector": _rand_vec(seed=0)},
        {"paper_id": "p1"},
        {"paper_id": "p2", "vector": None},
    ]

    with patch(f"{_STORE}.httpx.AsyncClient", return_value=_MockAsyncClient(_post_handler)):
        await clear_collection()
        count = await upsert_papers(papers)

    assert count == 1


@pytest.mark.asyncio
async def test_rank_hyde_none_fallback_bm25() -> None:
    from backend.agent.gap_detection.retrieval import rank

    papers = [_make_paper(f"p{i}", f"transformer attention paper {i}") for i in range(5)]

    with (
        patch(f"{_RETRIEVAL}.get_embeddings_batch", new=AsyncMock(return_value={})),
        patch(f"{_RETRIEVAL}.generate_hyde_vector_nim", new=AsyncMock(return_value=None)),
        patch(f"{_RETRIEVAL}.query_by_vector_nim", return_value=[]),
    ):
        result = await rank("transformer attention", papers, top_k=3)

    assert len(result) == 3
    assert all(hasattr(p, "paper_id") for p in result)


@pytest.mark.asyncio
async def test_rank_deterministic() -> None:
    from backend.agent.gap_detection.retrieval import rank

    papers = [_make_paper(f"p{i}", f"paper {i}", citations=i * 10) for i in range(6)]

    with (
        patch(f"{_RETRIEVAL}.get_embeddings_batch", new=AsyncMock(return_value={})),
        patch(f"{_RETRIEVAL}.generate_hyde_vector_nim", new=AsyncMock(return_value=None)),
        patch(f"{_RETRIEVAL}.query_by_vector_nim", return_value=[]),
    ):
        r1 = await rank("some topic", papers, top_k=4)
        r2 = await rank("some topic", papers, top_k=4)

    assert [p.paper_id for p in r1] == [p.paper_id for p in r2]


@pytest.mark.asyncio
async def test_rank_empty_papers_returns_empty() -> None:
    from backend.agent.gap_detection.retrieval import rank

    with (
        patch(f"{_RETRIEVAL}.get_embeddings_batch", new=AsyncMock(return_value={})),
        patch(f"{_RETRIEVAL}.generate_hyde_vector_nim", new=AsyncMock(return_value=None)),
        patch(f"{_RETRIEVAL}.query_by_vector_nim", return_value=[]),
    ):
        result = await rank("topic", [], top_k=5)

    assert result == []


@pytest.mark.asyncio
async def test_rank_semantic_arm_changes_order() -> None:
    from backend.agent.gap_detection.retrieval import rank

    papers = [
        _make_paper("p0", "unrelated topic alpha beta", year=2020, citations=1000),
        _make_paper("p1", "transformer attention NLP", year=2022, citations=50),
        _make_paper("p2", "transformer NLP deep learning", year=2023, citations=10),
        _make_paper("p3", "transformer attention long context", year=2024, citations=1),
    ]
    hyde_vec = _rand_vec(seed=3)
    specter_map = {
        "p0": _rand_vec(seed=0),
        "p1": _rand_vec(seed=1),
        "p2": _rand_vec(seed=2),
        "p3": _rand_vec(seed=3),
    }

    with (
        patch(f"{_RETRIEVAL}.get_embeddings_batch", new=AsyncMock(return_value=specter_map)),
        patch(f"{_RETRIEVAL}.generate_hyde_vector_nim", new=AsyncMock(return_value=hyde_vec)),
        patch(f"{_RETRIEVAL}.query_by_vector_nim", return_value=["p3", "p2", "p1", "p0"]),
    ):
        result = await rank("transformer attention long context", papers, top_k=4)

    ids = [p.paper_id for p in result]
    assert ids[0] != "p0" or ids.index("p3") < ids.index("p0")


def test_hyde_abstract_words_default() -> None:
    from backend.agent.gap_detection.settings import get_hyde_abstract_words

    os.environ.pop("HYDE_ABSTRACT_WORDS", None)
    assert get_hyde_abstract_words() == 80


def test_hyde_abstract_words_env_override() -> None:
    from backend.agent.gap_detection.settings import get_hyde_abstract_words

    os.environ["HYDE_ABSTRACT_WORDS"] = "120"
    try:
        assert get_hyde_abstract_words() == 120
    finally:
        os.environ.pop("HYDE_ABSTRACT_WORDS")


def test_specter2_weight_default() -> None:
    from backend.agent.gap_detection.settings import get_specter2_weight

    os.environ.pop("SPECTER2_WEIGHT", None)
    assert get_specter2_weight() == pytest.approx(0.4)


def test_specter2_weight_clamped() -> None:
    from backend.agent.gap_detection.settings import get_specter2_weight

    os.environ["SPECTER2_WEIGHT"] = "1.5"
    try:
        assert get_specter2_weight() == pytest.approx(1.0)
    finally:
        os.environ.pop("SPECTER2_WEIGHT")
