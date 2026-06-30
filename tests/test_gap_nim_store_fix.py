"""Tests for NIM store wrappers, NIM HyDE helpers, and retrieval integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class _MockResponse:
    def __init__(self, payload=None):
        self._payload = payload if payload is not None else {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _RecordingAsyncClient:
    def __init__(self, post_handler):
        self._post_handler = post_handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers, timeout):
        return self._post_handler(url, json)


def _nim_vec(val: float = 0.1, dim: int = 4096) -> list[float]:
    return [val] * dim


def _make_paper(paper_id: str, title: str, abstract: str = "abstract", year: int = 2023):
    from backend.shared.models.paper import Paper

    return Paper(paperId=paper_id, title=title, abstract=abstract, year=year)


class TestGapNimStore:
    def test_nim_dim_constant_is_4096(self):
        from backend.agent.gap_detection.gap_nim_store import _NIM_DIM

        assert _NIM_DIM == 4096

    @pytest.mark.asyncio
    async def test_upsert_uses_nim_upsert_rpc(self):
        from backend.agent.gap_detection.gap_nim_store import upsert_papers_nim

        called_urls = []

        def _post_handler(url: str, payload: dict) -> _MockResponse:
            called_urls.append(url)
            return _MockResponse({})

        papers = [
            {"paper_id": "p0", "title": "T0", "year": 2023, "vector": _nim_vec(0.1)},
            {"paper_id": "p1", "title": "T1", "year": 2022, "vector": _nim_vec(0.5)},
            {"paper_id": "p2", "title": "T2", "year": 2024, "vector": _nim_vec(0.9)},
        ]

        with patch(
            "backend.agent.gap_detection.gap_nim_store.httpx.AsyncClient",
            return_value=_RecordingAsyncClient(_post_handler),
        ):
            count = await upsert_papers_nim(papers)

        assert count == 3
        assert called_urls
        assert all(url.endswith("upsert_gap_nim_embedding") for url in called_urls)

    @pytest.mark.asyncio
    async def test_query_by_vector_nim_returns_ids(self):
        from backend.agent.gap_detection.gap_nim_store import query_by_vector_nim

        rows = [
            {"paper_id": "p0", "distance": 0.1},
            {"paper_id": "p1", "distance": 0.2},
        ]
        with patch(
            "backend.agent.gap_detection.gap_nim_store._match",
            new=AsyncMock(return_value=rows),
        ):
            result = await query_by_vector_nim(_nim_vec(0.5), top_k=2)

        assert result == ["p0", "p1"]

    @pytest.mark.asyncio
    async def test_query_empty_collection_returns_empty_list(self):
        from backend.agent.gap_detection.gap_nim_store import query_by_vector_nim

        with patch(
            "backend.agent.gap_detection.gap_nim_store._match",
            new=AsyncMock(return_value=[]),
        ):
            result = await query_by_vector_nim(_nim_vec(0.1), top_k=5)

        assert result == []

    @pytest.mark.asyncio
    async def test_query_with_distances_nim_round_trip(self):
        from backend.agent.gap_detection.gap_nim_store import query_with_distances_nim

        rows = [
            {"paper_id": "pa", "distance": 0.0},
            {"paper_id": "pb", "distance": 0.6},
        ]
        with patch(
            "backend.agent.gap_detection.gap_nim_store._match",
            new=AsyncMock(return_value=rows),
        ):
            results = await query_with_distances_nim(_nim_vec(0.2), top_k=2)

        assert results == [("pa", 0.0), ("pb", 0.6)]

    @pytest.mark.asyncio
    async def test_upsert_empty_list_does_not_crash(self):
        from backend.agent.gap_detection.gap_nim_store import upsert_papers_nim

        assert await upsert_papers_nim([]) == 0

    @pytest.mark.asyncio
    async def test_upsert_skips_papers_without_vector(self):
        from backend.agent.gap_detection.gap_nim_store import upsert_papers_nim

        called_urls = []

        def _post_handler(url: str, payload: dict) -> _MockResponse:
            called_urls.append(url)
            return _MockResponse({})

        papers = [
            {"paper_id": "p_no_vec", "title": "T"},
            {"paper_id": "p_ok", "title": "T2", "vector": _nim_vec()},
        ]

        with patch(
            "backend.agent.gap_detection.gap_nim_store.httpx.AsyncClient",
            return_value=_RecordingAsyncClient(_post_handler),
        ):
            count = await upsert_papers_nim(papers)

        assert count == 1
        assert len(called_urls) == 1

    @pytest.mark.asyncio
    async def test_clear_nim_collection_calls_clear_rpc(self):
        from backend.agent.gap_detection.gap_nim_store import clear_nim_collection

        called_urls = []

        def _post_handler(url: str, payload: dict) -> _MockResponse:
            called_urls.append(url)
            return _MockResponse({})

        with patch(
            "backend.agent.gap_detection.gap_nim_store.httpx.AsyncClient",
            return_value=_RecordingAsyncClient(_post_handler),
        ):
            await clear_nim_collection()

        assert called_urls == [next(url for url in called_urls if url.endswith("clear_gap_nim_embeddings"))]


class TestHydeNimFunctions:
    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_uses_embed_text_not_batch(self):
        with (
            patch(
                "backend.agent.gap_detection.hyde.chat_completion",
                new=AsyncMock(return_value="This abstract discusses transformers."),
            ),
            patch("backend.agent.gap_detection.hyde.embed_text", new=AsyncMock(return_value=_nim_vec())) as mock_embed,
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=100),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim

            vec = await generate_hyde_vector_nim("transformer attention")

        assert vec is not None
        assert len(vec) == 4096
        mock_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_returns_4096_dim(self):
        with (
            patch(
                "backend.agent.gap_detection.hyde.chat_completion",
                new=AsyncMock(return_value="Hypothetical abstract here."),
            ),
            patch("backend.agent.gap_detection.hyde.embed_text", new=AsyncMock(return_value=_nim_vec())),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim

            vec = await generate_hyde_vector_nim("some query")

        assert isinstance(vec, list)
        assert len(vec) == 4096

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_backward_compat_alias(self):
        with (
            patch(
                "backend.agent.gap_detection.hyde.chat_completion", new=AsyncMock(return_value="Abstract text here.")
            ),
            patch("backend.agent.gap_detection.hyde.embed_text", new=AsyncMock(return_value=_nim_vec(0.7))),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector

            vec = await generate_hyde_vector("some query")

        assert vec is not None
        assert len(vec) == 4096

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_llm_failure_returns_none(self):
        with (
            patch(
                "backend.agent.gap_detection.hyde.chat_completion", new=AsyncMock(side_effect=RuntimeError("LLM down"))
            ),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim

            vec = await generate_hyde_vector_nim("query")

        assert vec is None

    @pytest.mark.asyncio
    async def test_generate_hyde_vector_nim_embed_failure_returns_none(self):
        with (
            patch("backend.agent.gap_detection.hyde.chat_completion", new=AsyncMock(return_value="Abstract text.")),
            patch("backend.agent.gap_detection.hyde.embed_text", new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.hyde.get_hyde_abstract_words", return_value=80),
        ):
            from backend.agent.gap_detection.hyde import generate_hyde_vector_nim

            vec = await generate_hyde_vector_nim("query")

        assert vec is None

    @pytest.mark.asyncio
    async def test_upsert_paper_to_nim_store_calls_embed_text(self):
        with (
            patch("backend.agent.gap_detection.hyde.embed_text", new=AsyncMock(return_value=_nim_vec())) as mock_embed,
            patch("backend.agent.gap_detection.hyde.upsert_papers_nim", new=AsyncMock(return_value=1)) as mock_upsert,
        ):
            from backend.agent.gap_detection.hyde import upsert_paper_to_nim_store

            await upsert_paper_to_nim_store("p123", "This paper discusses GANs.", "GAN paper", 2022)

        mock_embed.assert_called_once()
        mock_upsert.assert_awaited_once()
        call_args = mock_upsert.call_args[0][0]
        assert call_args[0]["paper_id"] == "p123"

    @pytest.mark.asyncio
    async def test_upsert_paper_to_nim_store_empty_abstract_noop(self):
        with patch("backend.agent.gap_detection.hyde.embed_text", new=AsyncMock(return_value=_nim_vec())) as mock_embed:
            from backend.agent.gap_detection.hyde import upsert_paper_to_nim_store

            await upsert_paper_to_nim_store("p_empty", "", "Title", 2023)

        mock_embed.assert_not_called()


class TestRetrievalRankNimStore:
    @pytest.mark.asyncio
    async def test_rank_calls_query_by_vector_nim_not_specter(self):
        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(5)]

        with (
            patch("backend.agent.gap_detection.retrieval.clear_collection"),
            patch("backend.agent.gap_detection.retrieval.get_embeddings_batch", new=AsyncMock(return_value={})),
            patch("backend.agent.gap_detection.retrieval.clear_nim_collection"),
            patch("backend.agent.gap_detection.retrieval.upsert_paper_to_nim_store", new=AsyncMock(return_value=None)),
            patch(
                "backend.agent.gap_detection.retrieval.generate_hyde_vector_nim", new=AsyncMock(return_value=_nim_vec())
            ) as mock_hyde,
            patch(
                "backend.agent.gap_detection.retrieval.query_by_vector_nim", return_value=["p0", "p1", "p2", "p3", "p4"]
            ) as mock_nim_query,
        ):
            from backend.agent.gap_detection.retrieval import rank

            result = await rank("transformer attention", papers, top_k=3)

        mock_hyde.assert_called_once()
        mock_nim_query.assert_called_once()
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rank_hyde_vec_none_fallback_bm25(self):
        papers = [_make_paper(f"p{i}", f"transformer paper {i}") for i in range(5)]

        with (
            patch("backend.agent.gap_detection.retrieval.clear_collection"),
            patch("backend.agent.gap_detection.retrieval.get_embeddings_batch", new=AsyncMock(return_value={})),
            patch("backend.agent.gap_detection.retrieval.clear_nim_collection"),
            patch("backend.agent.gap_detection.retrieval.upsert_paper_to_nim_store", new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.retrieval.generate_hyde_vector_nim", new=AsyncMock(return_value=None)),
            patch("backend.agent.gap_detection.retrieval.query_by_vector_nim", return_value=[]) as mock_nim,
        ):
            from backend.agent.gap_detection.retrieval import rank

            result = await rank("transformer attention", papers, top_k=3)

        mock_nim.assert_not_called()
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rank_specter_store_not_used_for_query(self):
        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(4)]

        with (
            patch("backend.agent.gap_detection.retrieval.clear_collection"),
            patch("backend.agent.gap_detection.retrieval.get_embeddings_batch", new=AsyncMock(return_value={})),
            patch("backend.agent.gap_detection.retrieval.clear_nim_collection"),
            patch("backend.agent.gap_detection.retrieval.upsert_paper_to_nim_store", new=AsyncMock(return_value=None)),
            patch(
                "backend.agent.gap_detection.retrieval.generate_hyde_vector_nim", new=AsyncMock(return_value=_nim_vec())
            ),
            patch("backend.agent.gap_detection.retrieval.query_by_vector_nim", return_value=["p0", "p1", "p2", "p3"]),
        ):
            import backend.agent.gap_detection.retrieval as retrieval_mod
            from backend.agent.gap_detection.retrieval import rank

            assert not hasattr(retrieval_mod, "query_by_vector")
            result = await rank("topic", papers, top_k=4)

        assert len(result) == 4
