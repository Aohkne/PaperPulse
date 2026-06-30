import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.false_gap import check_false_gap
from backend.agent.gap_detection.novelty import compute_novelty_score
from backend.agent.gap_detection.schemas import GapItem


def test_gapitem_backward_compat():
    data = {
        "statement": "Test gap",
        "gap_type": "topical",
        "origin": "limitation",
    }
    gap = GapItem(**data)
    assert gap.novelty_score is None
    assert gap.false_gap_flag is False


@pytest.mark.asyncio
async def test_check_false_gap_flagged():
    with (
        patch("backend.agent.gap_detection.false_gap.embed_text", new_callable=AsyncMock) as mock_embed,
        patch("backend.agent.gap_detection.false_gap.query_with_distances_nim") as mock_query,
        patch("backend.agent.gap_detection.false_gap.get_false_gap_threshold") as mock_threshold,
    ):
        mock_embed.return_value = [0.1] * 4096
        mock_query.return_value = [("p1", 0.10)]
        mock_threshold.return_value = 0.15

        res = await check_false_gap("Test")
        assert res is True


@pytest.mark.asyncio
async def test_check_false_gap_not_flagged():
    with (
        patch("backend.agent.gap_detection.false_gap.embed_text", new_callable=AsyncMock) as mock_embed,
        patch("backend.agent.gap_detection.false_gap.query_with_distances_nim") as mock_query,
        patch("backend.agent.gap_detection.false_gap.get_false_gap_threshold") as mock_threshold,
    ):
        mock_embed.return_value = [0.1] * 4096
        mock_query.return_value = [("p1", 0.80)]
        mock_threshold.return_value = 0.15

        res = await check_false_gap("Test")
        assert res is False


@pytest.mark.asyncio
async def test_check_false_gap_empty_or_fail():
    with patch("backend.agent.gap_detection.false_gap.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.side_effect = Exception("API fail")
        res = await check_false_gap("Test")
        assert res is False


@pytest.mark.asyncio
async def test_compute_novelty_score_success():
    with (
        patch("backend.agent.gap_detection.novelty.embed_text", new_callable=AsyncMock) as mock_embed,
        patch("backend.agent.gap_detection.novelty.query_with_distances_nim", new_callable=AsyncMock) as mock_query,
    ):
        mock_embed.return_value = [0.1] * 4096
        mock_query.return_value = [("p1", 1.2), ("p2", 1.3), ("p3", 1.4)]

        score = await compute_novelty_score("Test")
        assert score == 1.3


@pytest.mark.asyncio
async def test_compute_novelty_score_empty():
    with (
        patch("backend.agent.gap_detection.novelty.embed_text", new_callable=AsyncMock) as mock_embed,
        patch("backend.agent.gap_detection.novelty.query_with_distances_nim", new_callable=AsyncMock) as mock_query,
    ):
        mock_embed.return_value = [0.1] * 4096
        mock_query.return_value = []
        score = await compute_novelty_score("Test")
        assert score is None


@pytest.mark.asyncio
async def test_background_corpus_dual_upsert():
    from backend.agent.gap_detection.background_corpus import build_background_corpus
    from backend.shared.models.paper import Paper

    papers = [Paper(paperId="p1", title="P1", abstract="A1", source="semantic_scholar")]
    with (
        patch("backend.agent.gap_detection.retrieval.search", new_callable=AsyncMock) as mock_search,
        patch("backend.agent.gap_detection.retrieval.snowball", new_callable=AsyncMock) as mock_snowball,
        patch(
            "backend.agent.gap_detection.background_corpus.get_embeddings_batch", new_callable=AsyncMock
        ) as mock_s2_embed,
        patch("backend.agent.gap_detection.background_corpus.upsert_papers") as mock_s2_upsert,
        patch("backend.agent.gap_detection.background_corpus.embed_text", new_callable=AsyncMock) as mock_nim_embed,
        patch("backend.agent.gap_detection.background_corpus.upsert_papers_nim") as mock_nim_upsert,
    ):
        mock_search.return_value = papers
        mock_snowball.return_value = papers
        mock_s2_embed.return_value = {"p1": [0.1]}
        mock_nim_embed.return_value = [0.5]

        await build_background_corpus("test")

        mock_s2_upsert.assert_called_once()
        mock_nim_embed.assert_called_once_with("A1")
        mock_nim_upsert.assert_called_once()
        assert mock_nim_upsert.call_args[0][0][0]["paper_id"] == "p1"
        assert mock_nim_upsert.call_args[0][0][0]["vector"] == [0.5]


@pytest.mark.asyncio
async def test_extractor_dual_upsert():
    from backend.agent.gap_detection.nodes.extractor import _process_one_paper
    from backend.agent.gap_detection.schemas import ExtractedPaperData, PaperRef

    paper_ref = PaperRef(paper_id="test_1", title="T1", year=2023)
    semaphore = asyncio.Semaphore(1)

    with (
        patch("backend.agent.gap_detection.nodes.extractor.get_paper_detail", new_callable=AsyncMock) as mock_detail,
        patch("backend.agent.gap_detection.nodes.extractor.fetch_pdf_text", new_callable=AsyncMock) as mock_pdf,
        patch("backend.agent.gap_detection.nodes.extractor.extract_from_text", new_callable=AsyncMock) as mock_extract,
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_embeddings_batch", new_callable=AsyncMock
        ) as mock_s2_embed,
        patch("backend.agent.gap_detection.nodes.extractor.upsert_papers") as mock_s2_upsert,
        patch(
            "backend.agent.gap_detection.nodes.extractor.upsert_paper_to_nim_store", new_callable=AsyncMock
        ) as mock_nim_upsert,
    ):
        mock_detail.return_value = {"abstract": "abs"}
        mock_pdf.return_value = None
        mock_extract.return_value = ExtractedPaperData(
            paper_ref=paper_ref, abstract="abs", extraction_source="abstract"
        )
        mock_s2_embed.return_value = {"test_1": [0.1]}

        await _process_one_paper(paper_ref, semaphore)

        mock_s2_upsert.assert_called_once()
        mock_nim_upsert.assert_called_once_with("test_1", "abs", "T1", 2023)
