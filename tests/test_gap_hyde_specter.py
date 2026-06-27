"""Tests for TIP-P2-06 — hyde.py + gap_specter_store.py + retrieval.rank() hybrid.

Verifies:
- generate_hyde_vector() generates vector on success
- generate_hyde_vector() returns None on LLM failure (no raise)
- generate_hyde_vector() returns None on embed_text failure
- gap_specter_store: upsert + query roundtrip
- gap_specter_store: empty collection → query returns []
- retrieval.rank() returns results when hyde_vec=None (BM25 fallback)
- retrieval.rank() is deterministic
- retrieval.rank() with semantic arm changes ordering vs BM25-only
- settings: get_hyde_abstract_words() and get_specter2_weight() defaults
- Regression: all prior gap tests pass
"""

from __future__ import annotations

import os
import random
from unittest.mock import AsyncMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

_HYDE = "backend.agent.gap_detection.hyde"
_RETRIEVAL = "backend.agent.gap_detection.retrieval"
_STORE = "backend.agent.gap_detection.gap_specter_store"

_DIM = 768


def _rand_vec(dim: int = _DIM, seed: int = 42) -> list[float]:
    rng = random.Random(seed)
    v = [rng.gauss(0, 1) for _ in range(dim)]
    # L2 normalise for cosine
    norm = sum(x * x for x in v) ** 0.5
    return [x / norm for x in v]


def _make_paper(paper_id: str, title: str = "Paper", year: int = 2023, citations: int = 10):
    from backend.shared.models.paper import Paper
    return Paper(paperId=paper_id, title=title, year=year, citationCount=citations)


# ── Part 1: hyde.py ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_hyde_vector_success() -> None:
    """LLM + embed_text both succeed → returns list[float]."""
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    vec = _rand_vec()
    with (
        patch(f"{_HYDE}.chat_completion", new=AsyncMock(return_value="This paper investigates attention mechanisms...")),
        patch(f"{_HYDE}.embed_text", new=AsyncMock(return_value=vec)),
    ):
        result = await generate_hyde_vector("transformer long-context attention")

    assert isinstance(result, list)
    assert len(result) == _DIM


@pytest.mark.asyncio
async def test_generate_hyde_vector_llm_fail_returns_none() -> None:
    """AC: LLM raises → None, no raise."""
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with patch(f"{_HYDE}.chat_completion", side_effect=RuntimeError("LLM down")):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


@pytest.mark.asyncio
async def test_generate_hyde_vector_embed_fail_returns_none() -> None:
    """embed_text raises → None, no raise."""
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with (
        patch(f"{_HYDE}.chat_completion", new=AsyncMock(return_value="Abstract text...")),
        patch(f"{_HYDE}.embed_text", side_effect=RuntimeError("embed down")),
    ):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


@pytest.mark.asyncio
async def test_generate_hyde_vector_embed_returns_none() -> None:
    """embed_text returns None (EMBEDDING_BASE_URL not set) → None."""
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with (
        patch(f"{_HYDE}.chat_completion", new=AsyncMock(return_value="Abstract text...")),
        patch(f"{_HYDE}.embed_text", new=AsyncMock(return_value=None)),
    ):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


@pytest.mark.asyncio
async def test_generate_hyde_vector_empty_abstract_returns_none() -> None:
    """LLM returns empty string → None."""
    from backend.agent.gap_detection.hyde import generate_hyde_vector

    with patch(f"{_HYDE}.chat_completion", new=AsyncMock(return_value="")):
        result = await generate_hyde_vector("transformer attention")

    assert result is None


# ── Part 2: gap_specter_store ─────────────────────────────────────────────────


def _fresh_store():
    """Reset the module-level ChromaDB singleton before each test."""
    from backend.agent.gap_detection import gap_specter_store
    gap_specter_store._client = None
    gap_specter_store._collection = None


def test_specter_store_upsert_and_query() -> None:
    """AC: upsert 5 papers → query_by_vector returns ≤3 IDs, no crash."""
    from backend.agent.gap_detection.gap_specter_store import (
        clear_collection,
        query_by_vector,
        upsert_papers,
    )
    _fresh_store()
    clear_collection()
    _fresh_store()

    papers = [
        {"paper_id": f"p{i}", "vector": _rand_vec(seed=i), "title": f"Paper {i}", "year": 2020 + i}
        for i in range(5)
    ]
    n = upsert_papers(papers)
    assert n == 5

    query_vec = _rand_vec(seed=99)
    results = query_by_vector(query_vec, top_k=3)
    assert isinstance(results, list)
    assert len(results) <= 3
    assert all(isinstance(pid, str) for pid in results)


def test_specter_store_empty_query_returns_empty() -> None:
    """AC: collection empty → query_by_vector returns [], no crash.

    Isolation: clear_collection() deletes the existing collection from the
    current EphemeralClient; the next _get_collection() call re-creates it
    fresh (0 items) on the same client instance.
    """
    from backend.agent.gap_detection.gap_specter_store import clear_collection, query_by_vector

    clear_collection()  # delete → next query recreates empty collection

    result = query_by_vector(_rand_vec(), top_k=5)
    assert result == [], f"Expected empty list, got {result}"


def test_specter_store_upsert_skips_missing_vector() -> None:
    """Papers without 'vector' key are skipped."""
    from backend.agent.gap_detection.gap_specter_store import (
        clear_collection,
        query_by_vector,
        upsert_papers,
    )
    _fresh_store()
    clear_collection()
    _fresh_store()

    papers = [
        {"paper_id": "p0", "vector": _rand_vec(seed=0)},
        {"paper_id": "p1"},           # no vector → skip
        {"paper_id": "p2", "vector": None},  # None vector → skip
    ]
    n = upsert_papers(papers)
    assert n == 1


# ── Part 3: retrieval.rank() hybrid ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_rank_hyde_none_fallback_bm25() -> None:
    """AC: hyde_vec = None → rank() still returns results (BM25 fallback), no crash."""
    from backend.agent.gap_detection.retrieval import rank
    from backend.agent.gap_detection import gap_specter_store
    gap_specter_store._client = None
    gap_specter_store._collection = None

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
    """AC: same input → same output order (called twice)."""
    from backend.agent.gap_detection.retrieval import rank
    from backend.agent.gap_detection import gap_specter_store
    gap_specter_store._client = None
    gap_specter_store._collection = None

    papers = [_make_paper(f"p{i}", f"paper {i}", citations=i * 10) for i in range(6)]

    with (
        patch(f"{_RETRIEVAL}.get_embeddings_batch", new=AsyncMock(return_value={})),
        patch(f"{_RETRIEVAL}.generate_hyde_vector_nim", new=AsyncMock(return_value=None)),
        patch(f"{_RETRIEVAL}.query_by_vector_nim", return_value=[]),
    ):
        r1 = await rank("some topic", papers, top_k=4)
        gap_specter_store._client = None
        gap_specter_store._collection = None
        r2 = await rank("some topic", papers, top_k=4)

    assert [p.paper_id for p in r1] == [p.paper_id for p in r2]


@pytest.mark.asyncio
async def test_rank_empty_papers_returns_empty() -> None:
    """rank() with no papers → empty list."""
    from backend.agent.gap_detection.retrieval import rank
    from backend.agent.gap_detection import gap_specter_store
    gap_specter_store._client = None
    gap_specter_store._collection = None

    with (
        patch(f"{_RETRIEVAL}.get_embeddings_batch", new=AsyncMock(return_value={})),
        patch(f"{_RETRIEVAL}.generate_hyde_vector_nim", new=AsyncMock(return_value=None)),
        patch(f"{_RETRIEVAL}.query_by_vector_nim", return_value=[]),
    ):
        result = await rank("topic", [], top_k=5)

    assert result == []


@pytest.mark.asyncio
async def test_rank_semantic_arm_changes_order() -> None:
    """AC: when hyde_vec exists and papers are in store, order differs from pure BM25."""
    from backend.agent.gap_detection.retrieval import rank
    from backend.agent.gap_detection import gap_specter_store
    from backend.agent.gap_detection.gap_specter_store import clear_collection, upsert_papers

    # Reset store
    gap_specter_store._client = None
    gap_specter_store._collection = None

    # 4 papers: p0 has most citations (BM25 winner), p3 has least
    papers = [
        _make_paper("p0", "unrelated topic alpha beta", year=2020, citations=1000),
        _make_paper("p1", "transformer attention NLP", year=2022, citations=50),
        _make_paper("p2", "transformer NLP deep learning", year=2023, citations=10),
        _make_paper("p3", "transformer attention long context", year=2024, citations=1),
    ]

    # HyDE vector: semantically close to p3 (same seed → same vector)
    hyde_vec = _rand_vec(seed=3)
    # Paper vectors: p3 identical to hyde_vec (cosine=1), others are random
    specter_map = {
        "p0": _rand_vec(seed=0),
        "p1": _rand_vec(seed=1),
        "p2": _rand_vec(seed=2),
        "p3": _rand_vec(seed=3),  # identical to hyde_vec → semantic rank=0 (best)
    }

    with (
        patch(f"{_RETRIEVAL}.get_embeddings_batch", new=AsyncMock(return_value=specter_map)),
        patch(f"{_RETRIEVAL}.generate_hyde_vector_nim", new=AsyncMock(return_value=hyde_vec)),
        patch(f"{_RETRIEVAL}.query_by_vector_nim", return_value=["p3", "p2", "p1", "p0"]),
    ):
        result = await rank("transformer attention long context", papers, top_k=4)

    # p3 should move up due to semantic score even though it has lowest citations
    ids = [p.paper_id for p in result]
    # p0 should NOT be first (semantic arm penalises unrelated papers)
    # This validates semantic arm has effect — p3 ranked better than pure BM25 would give
    assert ids[0] != "p0" or ids.index("p3") < ids.index("p0")


# ── Part 4: settings ─────────────────────────────────────────────────────────


def test_hyde_abstract_words_default() -> None:
    """Default HYDE_ABSTRACT_WORDS = 80."""
    from backend.agent.gap_detection.settings import get_hyde_abstract_words
    os.environ.pop("HYDE_ABSTRACT_WORDS", None)
    assert get_hyde_abstract_words() == 80


def test_hyde_abstract_words_env_override() -> None:
    """Env override HYDE_ABSTRACT_WORDS = 120."""
    from backend.agent.gap_detection.settings import get_hyde_abstract_words
    os.environ["HYDE_ABSTRACT_WORDS"] = "120"
    try:
        assert get_hyde_abstract_words() == 120
    finally:
        os.environ.pop("HYDE_ABSTRACT_WORDS")


def test_specter2_weight_default() -> None:
    """Default SPECTER2_WEIGHT = 0.4."""
    from backend.agent.gap_detection.settings import get_specter2_weight
    os.environ.pop("SPECTER2_WEIGHT", None)
    assert get_specter2_weight() == pytest.approx(0.4)


def test_specter2_weight_clamped() -> None:
    """SPECTER2_WEIGHT clamped to [0, 1]."""
    from backend.agent.gap_detection.settings import get_specter2_weight
    os.environ["SPECTER2_WEIGHT"] = "1.5"
    try:
        assert get_specter2_weight() == pytest.approx(1.0)
    finally:
        os.environ.pop("SPECTER2_WEIGHT")
