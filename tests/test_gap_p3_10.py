"""Tests for Stage D coherence gate and orchestrator wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.shared.models.paper import Paper


def _make_paper(paper_id: str, title: str = "Paper") -> Paper:
    return Paper(paperId=paper_id, title=title, year=2023)


def _make_papers(n: int) -> list[Paper]:
    return [_make_paper(f"p{i}", f"Paper {i}") for i in range(n)]


def _make_vector(dim: int = 4, val: float = 1.0) -> list[float]:
    return [val] * dim


@pytest.mark.asyncio
async def test_coherence_fewer_than_min_papers_is_coherent():
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(4)
    result = await check_coherence(papers)
    assert result["coherent"] is True
    assert result["warning"] is None
    assert result["papers"] == papers


@pytest.mark.asyncio
async def test_coherence_specter_store_empty_returns_coherent():
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(6)
    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new=AsyncMock(return_value={}),
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True
    assert result["warning"] is None
    assert result["papers"] == papers


@pytest.mark.asyncio
async def test_coherence_too_few_vectors_returns_coherent():
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(8)
    sparse_vecs = {f"p{i}": _make_vector() for i in range(3)}
    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new=AsyncMock(return_value=sparse_vecs),
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True


@pytest.mark.asyncio
async def test_coherence_high_similarity_corpus_is_coherent():
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(6)
    high_sim = {f"p{i}": _make_vector(dim=4, val=1.0) for i in range(6)}
    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new=AsyncMock(return_value=high_sim),
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True
    assert result["warning"] is None


@pytest.mark.asyncio
async def test_coherence_grab_bag_detected():
    from backend.agent.gap_detection.nodes.coherence_check import COHERENCE_THRESHOLD, check_coherence

    papers = _make_papers(6)
    scattered = {
        "p0": [1, 0, 0, 0, 0, 0],
        "p1": [0, 1, 0, 0, 0, 0],
        "p2": [0, 0, 1, 0, 0, 0],
        "p3": [0, 0, 0, 1, 0, 0],
        "p4": [0, 0, 0, 0, 1, 0],
        "p5": [0, 0, 0, 0, 0, 1],
    }
    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new=AsyncMock(return_value=scattered),
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is False
    assert result["warning"] is not None
    assert "ph" in result["warning"].lower()
    assert f"{COHERENCE_THRESHOLD}" in result["warning"]


@pytest.mark.asyncio
async def test_coherence_grab_bag_reduces_paper_count():
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(6)
    scattered = {
        "p0": [1, 0, 0, 0, 0, 0],
        "p1": [0, 1, 0, 0, 0, 0],
        "p2": [0, 0, 1, 0, 0, 0],
        "p3": [0, 0, 0, 1, 0, 0],
        "p4": [0, 0, 0, 0, 1, 0],
        "p5": [0, 0, 0, 0, 0, 1],
    }
    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new=AsyncMock(return_value=scattered),
    ):
        result = await check_coherence(papers)

    assert len(result["papers"]) <= len(papers)


@pytest.mark.asyncio
async def test_coherence_never_raises_on_internal_exception():
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(6)
    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new=AsyncMock(side_effect=RuntimeError("store exploded")),
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True
    assert result["warning"] is None
    assert result["papers"] == papers


def test_cosine_sim_orthogonal_vectors():
    from backend.agent.gap_detection.nodes.coherence_check import _cosine_sim

    assert _cosine_sim([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]) == pytest.approx(0.0)


def test_cosine_sim_identical_vectors():
    from backend.agent.gap_detection.nodes.coherence_check import _cosine_sim

    a = [1.0, 2.0, 3.0]
    assert _cosine_sim(a, a) == pytest.approx(1.0)


def test_cosine_sim_zero_vector():
    from backend.agent.gap_detection.nodes.coherence_check import _cosine_sim

    assert _cosine_sim([0.0, 0.0], [1.0, 2.0]) == 0.0


_ORCH = "backend.agent.gap_detection.orchestrator"


@pytest.mark.asyncio
async def test_orchestrator_cold_start_logs_stage_a_and_bc(caplog):
    import logging

    from backend.agent.gap_detection import orchestrator
    from backend.agent.gap_detection.schemas import GapQuery, GapReport

    mock_gap_query = GapQuery(core_topic="transformer long-context", facets=["attention"])
    mock_papers = _make_papers(5)

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=True),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock, return_value=mock_gap_query),
        patch(f"{_ORCH}.run_relevance_gate", new_callable=AsyncMock, return_value=mock_papers),
        patch(
            f"{_ORCH}.check_coherence",
            new_callable=AsyncMock,
            return_value={"coherent": True, "warning": None, "papers": mock_papers},
        ),
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="transformer long-context"),
        patch(f"{_ORCH}.retrieval"),
        patch(
            f"{_ORCH}.run_gap_detection",
            new_callable=AsyncMock,
            return_value=GapReport(papers_analyzed=5, gaps=[], narrative="ok"),
        ),
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger="backend.agent.gap_detection.orchestrator"),
    ):
        await orchestrator.cold_start("transformer long-context")

    assert "Stage A GapQuery" in caplog.text
    assert "transformer long-context" in caplog.text
    assert "Stage B+C:" in caplog.text


@pytest.mark.asyncio
async def test_orchestrator_stage_a_failure_pipeline_still_runs(caplog):
    import logging

    from backend.agent.gap_detection import orchestrator
    from backend.agent.gap_detection.schemas import GapReport

    mock_papers = _make_papers(5)
    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=True),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock, side_effect=RuntimeError("LLM down")),
        patch(f"{_ORCH}.run_relevance_gate", new_callable=AsyncMock, return_value=mock_papers),
        patch(
            f"{_ORCH}.check_coherence",
            new_callable=AsyncMock,
            return_value={"coherent": True, "warning": None, "papers": mock_papers},
        ),
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="some topic"),
        patch(f"{_ORCH}.retrieval"),
        patch(
            f"{_ORCH}.run_gap_detection",
            new_callable=AsyncMock,
            return_value=GapReport(papers_analyzed=5, gaps=[], narrative="ok"),
        ),
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="backend.agent.gap_detection.orchestrator"),
    ):
        result = await orchestrator.cold_start("some topic")

    assert result is not None
    assert "Stage A failed" in caplog.text


@pytest.mark.asyncio
async def test_orchestrator_stage_bc_failure_fallback_to_default_search(caplog):
    import logging

    from backend.agent.gap_detection import orchestrator
    from backend.agent.gap_detection.schemas import GapQuery, GapReport

    mock_gap_query = GapQuery(core_topic="attention", facets=["attention"])
    mock_search_papers = _make_papers(5)
    mock_retrieval = MagicMock()
    mock_retrieval.search = AsyncMock(return_value=mock_search_papers)
    mock_retrieval.snowball = AsyncMock(return_value=mock_search_papers)
    mock_retrieval.rank = AsyncMock(return_value=mock_search_papers)

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=True),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock, return_value=mock_gap_query),
        patch(f"{_ORCH}.run_relevance_gate", new_callable=AsyncMock, side_effect=RuntimeError("gate broken")),
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="attention"),
        patch(f"{_ORCH}.retrieval", mock_retrieval),
        patch(
            f"{_ORCH}.run_gap_detection",
            new_callable=AsyncMock,
            return_value=GapReport(papers_analyzed=5, gaps=[], narrative="ok"),
        ),
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="backend.agent.gap_detection.orchestrator"),
    ):
        result = await orchestrator.cold_start("attention")

    assert result is not None
    assert "Stage B+C failed" in caplog.text
    mock_retrieval.search.assert_called()


@pytest.mark.asyncio
async def test_orchestrator_query_analyzer_disabled_skips_cold_start():
    from backend.agent.gap_detection import orchestrator
    from backend.agent.gap_detection.schemas import GapReport

    mock_retrieval = MagicMock()
    mock_retrieval.search = AsyncMock(return_value=_make_papers(5))
    mock_retrieval.snowball = AsyncMock(return_value=_make_papers(5))
    mock_retrieval.rank = AsyncMock(return_value=_make_papers(5))

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=False),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock) as mock_analyze,
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="topic"),
        patch(f"{_ORCH}.retrieval", mock_retrieval),
        patch(
            f"{_ORCH}.run_gap_detection",
            new_callable=AsyncMock,
            return_value=GapReport(papers_analyzed=5, gaps=[], narrative="ok"),
        ),
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
    ):
        await orchestrator.cold_start("topic")

    mock_analyze.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_coherence_warning_is_logged(caplog):
    import logging

    from backend.agent.gap_detection import orchestrator
    from backend.agent.gap_detection.schemas import GapQuery, GapReport

    mock_gap_query = GapQuery(core_topic="topic", facets=["topic"])
    original_papers = _make_papers(8)
    filtered_papers = _make_papers(3)

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=True),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock, return_value=mock_gap_query),
        patch(f"{_ORCH}.run_relevance_gate", new_callable=AsyncMock, return_value=original_papers),
        patch(
            f"{_ORCH}.check_coherence",
            new_callable=AsyncMock,
            return_value={
                "coherent": False,
                "warning": "Corpus phan tan (avg_similarity=0.10 < 0.3). Keep 3 core papers.",
                "papers": filtered_papers,
            },
        ),
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="topic"),
        patch(f"{_ORCH}.retrieval"),
        patch(
            f"{_ORCH}.run_gap_detection",
            new_callable=AsyncMock,
            return_value=GapReport(papers_analyzed=3, gaps=[], narrative="ok"),
        ),
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="backend.agent.gap_detection.orchestrator"),
    ):
        await orchestrator.cold_start("topic")

    assert "Stage D coherence" in caplog.text
    assert "phan tan" in caplog.text.lower()
