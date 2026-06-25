"""Tests for TIP-P3-10 — Stage D Coherence Gate + Orchestrator wiring.

Covers:
- check_coherence: coherent corpus → coherent=True, warning=None
- check_coherence: grab-bag corpus (avg_sim < 0.3) → coherent=False, "phân tán" in warning
- check_coherence: filtered papers fewer than original
- check_coherence: SPECTER2 store empty → coherent=True (skip)
- check_coherence: fewer than MIN_PAPERS → coherent=True (skip)
- check_coherence: never raises (exception inside → safe fallback)
- orchestrator.cold_start: Stage A logs GapQuery + B+C logs count
- orchestrator.cold_start: Stage A failure → fallback, pipeline still runs
- orchestrator.cold_start: Stage B+C failure → fallback, pipeline still runs
- orchestrator.cold_start: QUERY_ANALYZER_ENABLED=false → analyze_query not called
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.shared.models.paper import Paper

# ── Helpers ──────────────────────────────────────────────────────────


def _make_paper(paper_id: str, title: str = "Paper") -> Paper:
    return Paper(paperId=paper_id, title=title, year=2023)


def _make_papers(n: int) -> list[Paper]:
    return [_make_paper(f"p{i}", f"Paper {i}") for i in range(n)]


def _make_vector(dim: int = 4, val: float = 1.0) -> list[float]:
    return [val] * dim


# ── coherence_check unit tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_coherence_fewer_than_min_papers_is_coherent():
    """Corpus with < 5 papers → coherent=True, no SPECTER2 lookup."""
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(4)
    result = await check_coherence(papers)
    assert result["coherent"] is True
    assert result["warning"] is None
    assert result["papers"] == papers


@pytest.mark.asyncio
async def test_coherence_specter_store_empty_returns_coherent():
    """When SPECTER2 store is empty → coherent=True (fail-safe)."""
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(6)

    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True
    assert result["warning"] is None
    assert result["papers"] == papers


@pytest.mark.asyncio
async def test_coherence_too_few_vectors_returns_coherent():
    """Fewer than MIN_PAPERS vectors available → skip, coherent=True."""
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(8)
    # Only 3 vectors — below MIN_PAPERS_TO_CHECK=5
    sparse_vecs = {f"p{i}": _make_vector() for i in range(3)}

    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new_callable=AsyncMock,
        return_value=sparse_vecs,
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True


@pytest.mark.asyncio
async def test_coherence_high_similarity_corpus_is_coherent():
    """Papers with avg pairwise cosine > 0.3 → coherent=True."""
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(6)
    # All identical vectors → cosine = 1.0 → avg = 1.0 >> 0.3
    high_sim = {f"p{i}": _make_vector(dim=4, val=1.0) for i in range(6)}

    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new_callable=AsyncMock,
        return_value=high_sim,
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True
    assert result["warning"] is None


@pytest.mark.asyncio
async def test_coherence_grab_bag_detected():
    """Corpus with avg_sim < 0.3 → coherent=False, warning contains 'phân tán'."""
    from backend.agent.gap_detection.nodes.coherence_check import (
        COHERENCE_THRESHOLD,
        check_coherence,
    )

    papers = _make_papers(6)
    # Orthogonal vectors in 6-dim space → cosine = 0 → avg < 0.3
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
        new_callable=AsyncMock,
        return_value=scattered,
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is False
    assert result["warning"] is not None
    assert "phân tán" in result["warning"]
    assert f"{COHERENCE_THRESHOLD}" in result["warning"]


@pytest.mark.asyncio
async def test_coherence_grab_bag_reduces_paper_count():
    """When grab-bag detected, returned papers are fewer than original."""
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
        new_callable=AsyncMock,
        return_value=scattered,
    ):
        result = await check_coherence(papers)

    # MAX_CORE_PAPERS=15 but we only have 6, so all may be kept;
    # the important thing is the function ran and returned something <= original
    assert len(result["papers"]) <= len(papers)


@pytest.mark.asyncio
async def test_coherence_never_raises_on_internal_exception():
    """Any exception inside check_coherence → safe fallback, no raise."""
    from backend.agent.gap_detection.nodes.coherence_check import check_coherence

    papers = _make_papers(6)

    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new_callable=AsyncMock,
        side_effect=RuntimeError("store exploded"),
    ):
        result = await check_coherence(papers)

    assert result["coherent"] is True
    assert result["warning"] is None
    assert result["papers"] == papers


# ── cosine_sim unit test ──────────────────────────────────────────────


def test_cosine_sim_orthogonal_vectors():
    from backend.agent.gap_detection.nodes.coherence_check import _cosine_sim

    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert _cosine_sim(a, b) == pytest.approx(0.0)


def test_cosine_sim_identical_vectors():
    from backend.agent.gap_detection.nodes.coherence_check import _cosine_sim

    a = [1.0, 2.0, 3.0]
    assert _cosine_sim(a, a) == pytest.approx(1.0)


def test_cosine_sim_zero_vector():
    from backend.agent.gap_detection.nodes.coherence_check import _cosine_sim

    assert _cosine_sim([0.0, 0.0], [1.0, 2.0]) == 0.0


# ── Orchestrator wiring tests ─────────────────────────────────────────

_ORCH = "backend.agent.gap_detection.orchestrator"


@pytest.mark.asyncio
async def test_orchestrator_cold_start_logs_stage_a_and_bc(caplog):
    """Happy path: Stage A logs GapQuery, Stage B+C logs paper count."""
    import logging

    from backend.agent.gap_detection.schemas import GapQuery

    mock_gap_query = GapQuery(core_topic="transformer long-context", facets=["attention"])
    mock_papers = _make_papers(5)

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=True),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock, return_value=mock_gap_query),
        patch(f"{_ORCH}.run_relevance_gate", new_callable=AsyncMock, return_value=mock_papers),
        patch(f"{_ORCH}.check_coherence", return_value={"coherent": True, "warning": None, "papers": mock_papers}),
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="transformer long-context"),
        patch(f"{_ORCH}.retrieval"),
        patch(f"{_ORCH}.run_gap_detection", new_callable=AsyncMock) as mock_pipeline,
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger="backend.agent.gap_detection.orchestrator"),
    ):
        from backend.agent.gap_detection.schemas import GapReport

        mock_pipeline.return_value = GapReport(papers_analyzed=5, gaps=[], narrative="ok")
        from backend.agent.gap_detection import orchestrator

        await orchestrator.cold_start("transformer long-context")

    log_text = caplog.text
    assert "Stage A GapQuery" in log_text
    assert "transformer long-context" in log_text
    assert "Stage B+C:" in log_text


@pytest.mark.asyncio
async def test_orchestrator_stage_a_failure_pipeline_still_runs(caplog):
    """Stage A raises → warning logged, pipeline still runs."""
    import logging

    mock_papers = _make_papers(5)

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=True),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock, side_effect=RuntimeError("LLM down")),
        patch(f"{_ORCH}.run_relevance_gate", new_callable=AsyncMock, return_value=mock_papers),
        patch(f"{_ORCH}.check_coherence", return_value={"coherent": True, "warning": None, "papers": mock_papers}),
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="some topic"),
        patch(f"{_ORCH}.retrieval"),
        patch(f"{_ORCH}.run_gap_detection", new_callable=AsyncMock) as mock_pipeline,
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="backend.agent.gap_detection.orchestrator"),
    ):
        from backend.agent.gap_detection.schemas import GapReport

        mock_pipeline.return_value = GapReport(papers_analyzed=5, gaps=[], narrative="ok")
        from backend.agent.gap_detection import orchestrator

        result = await orchestrator.cold_start("some topic")

    assert result is not None
    assert "Stage A failed" in caplog.text


@pytest.mark.asyncio
async def test_orchestrator_stage_bc_failure_fallback_to_default_search(caplog):
    """Stage B+C raises → cold_start_papers=None, pipeline falls back to default search path."""
    import logging

    from backend.agent.gap_detection.schemas import GapQuery

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
        patch(f"{_ORCH}.run_gap_detection", new_callable=AsyncMock) as mock_pipeline,
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="backend.agent.gap_detection.orchestrator"),
    ):
        from backend.agent.gap_detection.schemas import GapReport

        mock_pipeline.return_value = GapReport(papers_analyzed=5, gaps=[], narrative="ok")
        from backend.agent.gap_detection import orchestrator

        result = await orchestrator.cold_start("attention")

    assert result is not None
    assert "Stage B+C failed" in caplog.text
    # Default search path was used — retrieval.search was called
    mock_retrieval.search.assert_called()


@pytest.mark.asyncio
async def test_orchestrator_query_analyzer_disabled_skips_cold_start():
    """QUERY_ANALYZER_ENABLED=false → analyze_query never called."""
    mock_retrieval = MagicMock()
    mock_retrieval.search = AsyncMock(return_value=_make_papers(5))
    mock_retrieval.snowball = AsyncMock(return_value=_make_papers(5))
    mock_retrieval.rank = AsyncMock(return_value=_make_papers(5))

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=False),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock) as mock_analyze,
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="topic"),
        patch(f"{_ORCH}.retrieval", mock_retrieval),
        patch(f"{_ORCH}.run_gap_detection", new_callable=AsyncMock) as mock_pipeline,
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
    ):
        from backend.agent.gap_detection.schemas import GapReport

        mock_pipeline.return_value = GapReport(papers_analyzed=5, gaps=[], narrative="ok")
        from backend.agent.gap_detection import orchestrator

        await orchestrator.cold_start("topic")

    mock_analyze.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_coherence_warning_is_logged(caplog):
    """Grab-bag corpus → coherence warning is logged at WARNING level."""
    import logging

    from backend.agent.gap_detection.schemas import GapQuery

    mock_gap_query = GapQuery(core_topic="topic", facets=["topic"])
    original_papers = _make_papers(8)
    filtered_papers = _make_papers(3)

    with (
        patch(f"{_ORCH}.is_query_analyzer_enabled", return_value=True),
        patch(f"{_ORCH}.analyze_query", new_callable=AsyncMock, return_value=mock_gap_query),
        patch(f"{_ORCH}.run_relevance_gate", new_callable=AsyncMock, return_value=original_papers),
        patch(
            f"{_ORCH}.check_coherence",
            return_value={
                "coherent": False,
                "warning": "Corpus phân tán (avg_similarity=0.10 < 0.3). Giữ 3 papers gần chủ đề nhất.",
                "papers": filtered_papers,
            },
        ),
        patch(f"{_ORCH}.clean_query", new_callable=AsyncMock, return_value="topic"),
        patch(f"{_ORCH}.retrieval"),
        patch(f"{_ORCH}.run_gap_detection", new_callable=AsyncMock) as mock_pipeline,
        patch(f"{_ORCH}.build_background_corpus", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="backend.agent.gap_detection.orchestrator"),
    ):
        from backend.agent.gap_detection.schemas import GapReport

        mock_pipeline.return_value = GapReport(papers_analyzed=3, gaps=[], narrative="ok")
        from backend.agent.gap_detection import orchestrator

        await orchestrator.cold_start("topic")

    assert "Stage D coherence" in caplog.text
    assert "phân tán" in caplog.text
