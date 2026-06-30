import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.background_corpus import build_background_corpus
from backend.agent.gap_detection.nodes.extractor import _process_one_paper
from backend.agent.gap_detection.schemas import ExtractedPaperData, PaperRef
from backend.shared.models.paper import Paper

# Feature: extractor persist SPECTER2


@pytest.mark.asyncio
async def test_extractor_persist_specter2_success():
    """Scenario: paper extract thành công → upserted vào store"""
    paper_ref = PaperRef(paper_id="test_1", title="T1", year=2023)
    semaphore = asyncio.Semaphore(1)

    with (
        patch("backend.agent.gap_detection.nodes.extractor.get_paper_detail", new_callable=AsyncMock) as mock_detail,
        patch("backend.agent.gap_detection.nodes.extractor.fetch_pdf_text", new_callable=AsyncMock) as mock_pdf,
        patch("backend.agent.gap_detection.nodes.extractor.extract_from_text", new_callable=AsyncMock) as mock_extract,
        patch("backend.agent.gap_detection.nodes.extractor.get_embeddings_batch", new_callable=AsyncMock) as mock_embed,
        patch("backend.agent.gap_detection.nodes.extractor.upsert_papers") as mock_upsert,
    ):
        mock_detail.return_value = {"abstract": "abs"}
        mock_pdf.return_value = None
        mock_extract.return_value = ExtractedPaperData(
            paper_ref=paper_ref, abstract="abs", key_claims=["C1"], extraction_source="abstract"
        )
        mock_embed.return_value = {"test_1": [0.1, 0.2]}

        res = await _process_one_paper(paper_ref, semaphore)

        assert res is not None
        mock_embed.assert_called_once_with(["test_1"])
        mock_upsert.assert_called_once()
        upsert_arg = mock_upsert.call_args[0][0]
        assert len(upsert_arg) == 1
        assert upsert_arg[0]["paper_id"] == "test_1"
        assert upsert_arg[0]["vector"] == [0.1, 0.2]


@pytest.mark.asyncio
async def test_extractor_persist_specter2_fail_safe():
    """Scenario: upsert fail không crash extraction"""
    paper_ref = PaperRef(paper_id="test_2", title="T2", year=2023)
    semaphore = asyncio.Semaphore(1)

    with (
        patch("backend.agent.gap_detection.nodes.extractor.get_paper_detail", new_callable=AsyncMock) as mock_detail,
        patch("backend.agent.gap_detection.nodes.extractor.extract_from_text", new_callable=AsyncMock) as mock_extract,
        patch("backend.agent.gap_detection.nodes.extractor.get_embeddings_batch", new_callable=AsyncMock) as mock_embed,
    ):
        mock_detail.return_value = {"abstract": "abs"}
        mock_extract.return_value = ExtractedPaperData(
            paper_ref=paper_ref, abstract="abs", extraction_source="abstract"
        )
        mock_embed.side_effect = Exception("Embedding API down")

        # Should not raise exception
        res = await _process_one_paper(paper_ref, semaphore)
        assert res is not None
        assert res.paper_ref.paper_id == "test_2"


# Feature: background corpus


@pytest.mark.asyncio
async def test_build_background_corpus_success():
    """Scenario: build_background_corpus() upsert papers"""
    papers = [
        Paper(paperId="p1", title="P1", abstract="A1", source="semantic_scholar"),
        Paper(paperId="p2", title="P2", abstract="A2", source="semantic_scholar"),
    ]
    with (
        patch("backend.agent.gap_detection.retrieval.search", new_callable=AsyncMock) as mock_search,
        patch("backend.agent.gap_detection.retrieval.snowball", new_callable=AsyncMock) as mock_snowball,
        patch(
            "backend.agent.gap_detection.background_corpus.get_embeddings_batch", new_callable=AsyncMock
        ) as mock_embed,
        patch("backend.agent.gap_detection.background_corpus.upsert_papers") as mock_upsert,
    ):
        mock_search.return_value = [papers[0]]
        mock_snowball.return_value = papers
        mock_embed.return_value = {"p1": [0.1], "p2": [0.2]}

        upserted = await build_background_corpus("test query")

        assert upserted == 2
        mock_search.assert_called_once()
        mock_snowball.assert_called_once()
        mock_embed.assert_called_once_with(["p1", "p2"])
        mock_upsert.assert_called_once()


@pytest.mark.asyncio
async def test_build_background_corpus_batch_fail_safe():
    """Scenario: batch fail → skip, tiếp tục"""
    papers = [Paper(paperId=f"p{i}", title=f"P{i}", abstract="A", source="semantic_scholar") for i in range(100)]

    with (
        patch("backend.agent.gap_detection.retrieval.search", new_callable=AsyncMock) as mock_search,
        patch("backend.agent.gap_detection.retrieval.snowball", new_callable=AsyncMock) as mock_snowball,
        patch(
            "backend.agent.gap_detection.background_corpus.get_embeddings_batch", new_callable=AsyncMock
        ) as mock_embed,
        patch("backend.agent.gap_detection.background_corpus.upsert_papers") as mock_upsert,
    ):
        mock_search.return_value = []
        mock_snowball.return_value = papers

        # Batch 1 fail, Batch 2 success
        def embed_side_effect(ids):
            if "p0" in ids:
                raise Exception("Batch 1 error")
            return {pid: [0.5] for pid in ids}

        mock_embed.side_effect = embed_side_effect

        upserted = await build_background_corpus("test query")

        # batch_size=25: 4 batches (p0-24, p25-49, p50-74, p75-99)
        # Batch 0 (contains p0) fails → skip; batches 1,2,3 succeed → 75 upserted
        assert upserted == 75
        assert mock_upsert.call_count == 3


@pytest.mark.asyncio
async def test_build_background_corpus_no_llm():
    """Scenario: không có LLM call"""
    papers = [Paper(paperId="p1", title="P1", abstract="A1", source="semantic_scholar")]
    with (
        patch("backend.agent.gap_detection.retrieval.search", new_callable=AsyncMock) as mock_search,
        patch("backend.agent.gap_detection.retrieval.snowball", new_callable=AsyncMock) as mock_snowball,
        patch(
            "backend.agent.gap_detection.background_corpus.get_embeddings_batch", new_callable=AsyncMock
        ) as mock_embed,
        patch("backend.agent.gap_detection.background_corpus.upsert_papers"),
        patch("backend.shared.services.llm_client.chat_completion", new_callable=AsyncMock) as mock_chat,
    ):
        mock_search.return_value = papers
        mock_snowball.return_value = papers
        mock_embed.return_value = {"p1": [0.1]}

        await build_background_corpus("test")

        mock_chat.assert_not_called()


# Feature: orchestrator fire-and-forget


@pytest.mark.asyncio
async def test_orchestrator_fire_and_forget():
    """Scenario: background corpus không block detection"""
    from backend.agent.gap_detection.orchestrator import cold_start

    with (
        patch("backend.agent.gap_detection.orchestrator.is_query_analyzer_enabled", return_value=False),
        patch("backend.agent.gap_detection.orchestrator.clean_query", new_callable=AsyncMock) as mock_clean,
        patch("backend.agent.gap_detection.retrieval.search", new_callable=AsyncMock) as mock_search,
        patch("backend.agent.gap_detection.retrieval.snowball", new_callable=AsyncMock) as mock_snowball,
        patch("backend.agent.gap_detection.retrieval.rank", new_callable=AsyncMock) as mock_rank,
        patch("backend.agent.gap_detection.orchestrator.run_gap_detection", new_callable=AsyncMock) as mock_run_gap,
        patch(
            "backend.agent.gap_detection.orchestrator.build_background_corpus", new_callable=AsyncMock
        ) as mock_build_bg,
    ):
        mock_clean.return_value = "clean"
        mock_search.return_value = [Paper(paperId="p1", title="P1", source="semantic_scholar")] * 10
        mock_snowball.return_value = [Paper(paperId="p1", title="P1", source="semantic_scholar")] * 10
        mock_rank.return_value = [Paper(paperId="p1", title="P1", source="semantic_scholar")] * 10
        mock_run_gap.return_value = "report"

        async def slow_bg(q):
            await asyncio.sleep(2.0)

        mock_build_bg.side_effect = slow_bg

        # Should return immediately, not after 2.0s
        import time

        start = time.time()
        res = await cold_start("topic")
        duration = time.time() - start

        assert res == "report"
        assert duration < 1.0  # Proves it didn't block
        mock_build_bg.assert_called_once()
