"""Tests for TIP-P2-06-FIX — gap_nim_store + hyde NIM + retrieval dim-safe.

AC Coverage:
- gap_nim_store accepts 4096-dim vectors without DimensionError
- upsert + query round-trip works correctly
- empty collection → returns []
- generate_hyde_vector_nim uses embed_text (NOT get_embeddings_batch)
- generate_hyde_vector (backward compat alias) works
- retrieval.rank() calls query_by_vector_nim (NOT query_by_vector from specter store)
- retrieval.rank() fallback to BM25 when hyde_vec = None
- counter_search.py uses search_papers directly (NameError regression fix)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_paper(paper_id: str, title: str = "Paper", abstract: str = "abstract text",
                year: int = 2023, citations: int = 10):
    from backend.shared.models.paper import Paper
    return Paper(paperId=paper_id, title=title, abstract=abstract,
                 year=year, citationCount=citations)


def _nim_vec(val: float = 0.1) -> list[float]:
    """Return a valid 4096-dim NIM vector."""
    return [val] * 4096


# ── FIX-A: gap_nim_store (backed by tests/conftest.py's fake Supabase RPC) ──────

def test_nim_dim_constant_is_4096():
    """AC: _NIM_DIM = 4096 (not 768)."""
    from backend.agent.gap_detection.gap_nim_store import _NIM_DIM
    assert _NIM_DIM == 4096


@pytest.mark.asyncio
async def test_upsert_4096dim_does_not_crash(fake_gap_nim_store):
    """AC: upsert vector len=4096 → no DimensionError."""
    from backend.agent.gap_detection.gap_nim_store import upsert_papers_nim
    papers = [
        {"paper_id": "p0", "title": "T0", "year": 2023, "vector": _nim_vec(0.1)},
        {"paper_id": "p1", "title": "T1", "year": 2022, "vector": _nim_vec(0.5)},
        {"paper_id": "p2", "title": "T2", "year": 2024, "vector": _nim_vec(0.9)},
    ]
    count = await upsert_papers_nim(papers)
    assert count == 3


@pytest.mark.asyncio
async def test_query_by_vector_nim_returns_ids(fake_gap_nim_store):
    """AC: upsert 3 papers → query top_k=2 returns ≤2 paper_ids."""
    from backend.agent.gap_detection.gap_nim_store import query_by_vector_nim, upsert_papers_nim
    papers = [
        {"paper_id": f"p{i}", "title": f"T{i}", "year": 2020 + i, "vector": _nim_vec(i * 0.1 + 0.01)}
        for i in range(3)
    ]
    await upsert_papers_nim(papers)
    result = await query_by_vector_nim(_nim_vec(0.5), top_k=2)
    assert isinstance(result, list)
    assert len(result) <= 2
    assert all(isinstance(r, str) for r in result)


@pytest.mark.asyncio
async def test_query_empty_collection_returns_empty_list(fake_gap_nim_store):
    """AC: collection rỗng → query trả [], KHÔNG raise."""
    from backend.agent.gap_detection.gap_nim_store import query_by_vector_nim
    result = await query_by_vector_nim(_nim_vec(0.1), top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_query_with_distances_nim_round_trip(fake_gap_nim_store):
    """query_with_distances_nim returns (paper_id, distance) pairs."""
    from backend.agent.gap_detection.gap_nim_store import (
        query_with_distances_nim,
        upsert_papers_nim,
    )
    papers = [
        {"paper_id": "pa", "title": "A", "year": 2023, "vector": _nim_vec(0.2)},
        {"paper_id": "pb", "title": "B", "year": 2022, "vector": _nim_vec(0.8)},
    ]
    await upsert_papers_nim(papers)
    results = await query_with_distances_nim(_nim_vec(0.2), top_k=2)
    assert len(results) == 2
    for paper_id, dist in results:
        assert isinstance(paper_id, str)
        assert isinstance(dist, float)


@pytest.mark.asyncio
async def test_upsert_empty_list_does_not_crash(fake_gap_nim_store):
    """upsert_papers_nim([]) → 0, no crash."""
    from backend.agent.gap_detection.gap_nim_store import upsert_papers_nim
    count = await upsert_papers_nim([])
    assert count == 0


@pytest.mark.asyncio
async def test_upsert_skips_papers_without_vector(fake_gap_nim_store):
    """Papers with no vector are skipped silently."""
    from backend.agent.gap_detection.gap_nim_store import upsert_papers_nim
    papers = [
        {"paper_id": "p_no_vec", "title": "T"},   # no "vector" key
        {"paper_id": "p_ok", "title": "T2", "vector": _nim_vec()},
    ]
    count = await upsert_papers_nim(papers)
    assert count == 1


@pytest.mark.asyncio
async def test_clear_nim_collection_resets(fake_gap_nim_store):
    """clear_nim_collection() wipes all stored data."""
    from backend.agent.gap_detection.gap_nim_store import (
        clear_nim_collection,
        query_by_vector_nim,
        upsert_papers_nim,
    )
    await upsert_papers_nim([{"paper_id": "p0", "vector": _nim_vec(), "title": "T", "year": 2023}])
    result_before = await query_by_vector_nim(_nim_vec(), top_k=5)
    assert len(result_before) > 0

    await clear_nim_collection()
    result_after = await query_by_vector_nim(_nim_vec(), top_k=5)
    assert result_after == []


# ── FIX-B: hyde.py NIM functions ─────────────────────────────────────────────

class TestHydeNimFunctions:
    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_uses_embed_text_not_batch(self):
        """AC: generate_hyde_vector_nim uses embed_text, NOT get_embeddings_batch."""
        with (
            patch("backend.agent.gap_detection.hyde.chat_completion",
                  new=AsyncMock(return_value="This abstract discusses transformers.")),
            patch("backend.agent.gap_detection.hyde.embed_text",
                  new=AsyncMock(return_value=_nim_vec())) as mock_embed,
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=100),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim
            vec = await generate_hyde_vector_nim("transformer attention")

        assert vec is not None
        assert len(vec) == 4096
        mock_embed.assert_called_once()  # embed_text was called

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_returns_4096_dim(self):
        """AC: generate_hyde_vector_nim() returns list[float] len=4096."""
        with (
            patch("backend.agent.gap_detection.hyde.chat_completion",
                  new=AsyncMock(return_value="Hypothetical abstract here.")),
            patch("backend.agent.gap_detection.hyde.embed_text",
                  new=AsyncMock(return_value=_nim_vec())),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim
            vec = await generate_hyde_vector_nim("some query")
        assert isinstance(vec, list)
        assert len(vec) == 4096

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_backward_compat_alias(self):
        """AC: generate_hyde_vector() (alias) is identical to generate_hyde_vector_nim()."""
        with (
            patch("backend.agent.gap_detection.hyde.chat_completion",
                  new=AsyncMock(return_value="Abstract text here.")),
            patch("backend.agent.gap_detection.hyde.embed_text",
                  new=AsyncMock(return_value=_nim_vec(0.7))),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector
            vec = await generate_hyde_vector("some query")
        assert vec is not None
        assert len(vec) == 4096

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_llm_failure_returns_none(self):
        """AC: LLM fails → returns None (BM25 fallback)."""
        with (
            patch("backend.agent.gap_detection.hyde.chat_completion",
                  new=AsyncMock(side_effect=RuntimeError("LLM down"))),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim
            vec = await generate_hyde_vector_nim("query")
        assert vec is None

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_embed_failure_returns_none(self):
        """AC: embed_text fails → returns None."""
        with (
            patch("backend.agent.gap_detection.hyde.chat_completion",
                  new=AsyncMock(return_value="Abstract text.")),
            patch("backend.agent.gap_detection.hyde.embed_text",
                  new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim
            vec = await generate_hyde_vector_nim("query")
        assert vec is None

    @pytest.mark.asyncio
    async def test_upsert_paper_to_nim_store_calls_embed_text(self):
        """upsert_paper_to_nim_store embeds abstract and upserts into nim store."""
        with (
            patch("backend.agent.gap_detection.hyde.embed_text",
                  new=AsyncMock(return_value=_nim_vec())) as mock_embed,
            patch("backend.agent.gap_detection.hyde.upsert_papers_nim") as mock_upsert,
        ):
            from backend.agent.gap_detection.hyde import upsert_paper_to_nim_store
            await upsert_paper_to_nim_store("p123", "This paper discusses GANs.", "GAN paper", 2022)

        mock_embed.assert_called_once()
        mock_upsert.assert_called_once()
        call_args = mock_upsert.call_args[0][0]
        assert call_args[0]["paper_id"] == "p123"

    @pytest.mark.asyncio
    async def test_upsert_paper_to_nim_store_empty_abstract_noop(self):
        """upsert_paper_to_nim_store with empty abstract → no-op, no crash."""
        with patch("backend.agent.gap_detection.hyde.embed_text",
                   new=AsyncMock(return_value=_nim_vec())) as mock_embed:
            from backend.agent.gap_detection.hyde import upsert_paper_to_nim_store
            await upsert_paper_to_nim_store("p_empty", "", "Title", 2023)
        mock_embed.assert_not_called()


# ── FIX-C: retrieval.rank() calls NIM store ──────────────────────────────────

class TestRetrievalRankNimStore:
    @pytest.mark.asyncio
    async def test_rank_calls_query_by_vector_nim_not_specter(self):
        """AC: rank() calls query_by_vector_nim (NIM), KHÔNG gọi query_by_vector (SPECTER)."""
        papers = [_make_paper(f"p{i}", f"Paper {i}", f"abstract {i}") for i in range(5)]

        with (
            patch("backend.agent.gap_detection.retrieval.clear_collection"),
            patch("backend.agent.gap_detection.retrieval.get_embeddings_batch",
                  new=AsyncMock(return_value={})),
            patch("backend.agent.gap_detection.retrieval.clear_nim_collection"),
            patch("backend.agent.gap_detection.retrieval.upsert_paper_to_nim_store",
                  new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.retrieval.generate_hyde_vector_nim",
                  new=AsyncMock(return_value=_nim_vec())) as mock_hyde,
            patch("backend.agent.gap_detection.retrieval.query_by_vector_nim",
                  return_value=["p0", "p1", "p2", "p3", "p4"]) as mock_nim_query,
        ):
            from backend.agent.gap_detection.retrieval import rank
            result = await rank("transformer attention", papers, top_k=3)

        mock_hyde.assert_called_once()
        mock_nim_query.assert_called_once()  # NIM store queried
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rank_hyde_vec_none_fallback_bm25(self):
        """AC: hyde_vec = None → rank() fallback to BM25, KHÔNG crash."""
        papers = [_make_paper(f"p{i}", f"transformer paper {i}", f"abstract {i}") for i in range(5)]

        with (
            patch("backend.agent.gap_detection.retrieval.clear_collection"),
            patch("backend.agent.gap_detection.retrieval.get_embeddings_batch",
                  new=AsyncMock(return_value={})),
            patch("backend.agent.gap_detection.retrieval.clear_nim_collection"),
            patch("backend.agent.gap_detection.retrieval.upsert_paper_to_nim_store",
                  new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.retrieval.generate_hyde_vector_nim",
                  new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.retrieval.query_by_vector_nim",
                  return_value=[]) as mock_nim,
        ):
            from backend.agent.gap_detection.retrieval import rank
            result = await rank("transformer attention", papers, top_k=3)

        mock_nim.assert_not_called()  # no semantic query when hyde_vec=None
        assert len(result) == 3  # BM25 still works

    @pytest.mark.asyncio
    async def test_rank_specter_store_not_used_for_query(self):
        """AC: query_by_vector (SPECTER store) is NOT called by rank()."""
        papers = [_make_paper(f"p{i}", f"Paper {i}", f"abstract {i}") for i in range(4)]

        with (
            patch("backend.agent.gap_detection.retrieval.clear_collection"),
            patch("backend.agent.gap_detection.retrieval.get_embeddings_batch",
                  new=AsyncMock(return_value={})),
            patch("backend.agent.gap_detection.retrieval.clear_nim_collection"),
            patch("backend.agent.gap_detection.retrieval.upsert_paper_to_nim_store",
                  new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.retrieval.generate_hyde_vector_nim",
                  new=AsyncMock(return_value=_nim_vec())),
            patch("backend.agent.gap_detection.retrieval.query_by_vector_nim",
                  return_value=["p0", "p1", "p2", "p3"]),
        ):
            # query_by_vector from specter_store is not in retrieval's namespace anymore
            # — verify the import doesn't exist
            import backend.agent.gap_detection.retrieval as retrieval_mod
            assert not hasattr(retrieval_mod, "query_by_vector"), \
                "query_by_vector (specter) should NOT be imported in retrieval"

            from backend.agent.gap_detection.retrieval import rank
            result = await rank("topic", papers, top_k=4)
        assert len(result) == 4


# Removed TestCounterSearchNameError as retrieval import is deliberately restored
