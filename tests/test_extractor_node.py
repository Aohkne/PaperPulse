"""Tests for TIP-G02a — ExtractorNode (abstract-based extraction).

All Semantic Scholar and LLM calls are mocked so tests run offline.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.nodes.extractor import (
    DEFAULT_CONCURRENCY,
    _parse_llm_json,
    extract_from_text,
    extractor_node,
)
from backend.agent.gap_detection.schemas import (
    ExtractedPaperData,
    GapDetectionState,
    PaperRef,
)

# ── Fixtures ─────────────────────────────────────────────────────────


def _make_ref(pid: str = "abc123", title: str = "Test Paper") -> PaperRef:
    return PaperRef(paper_id=pid, title=title, year=2024, url=f"https://s2/{pid}")


def _s2_detail(
    *,
    abstract: str | None = "This paper studies X.",
    tldr: str | None = "We study X.",
    pdf_url: str | None = "https://example.com/paper.pdf",
) -> dict:
    """Build a fake S2 API detail response."""
    result: dict = {
        "paperId": "abc123",
        "title": "Test Paper",
        "abstract": abstract,
        "year": 2024,
        "url": "https://s2/abc123",
        "authors": [{"name": "Alice"}],
        "fieldsOfStudy": ["Computer Science"],
        "publicationTypes": ["JournalArticle"],
        "venue": "NeurIPS",
    }
    if tldr is not None:
        result["tldr"] = {"text": tldr}
    else:
        result["tldr"] = None
    if pdf_url is not None:
        result["openAccessPdf"] = {"url": pdf_url}
    else:
        result["openAccessPdf"] = None
    return result


_GOOD_LLM_JSON = json.dumps(
    {
        "topics": ["machine learning", "NLP"],
        "keywords": ["transformer", "attention"],
        "methodology": "fine-tuning",
        "dataset": "GLUE",
        "population": None,
        "metrics": ["accuracy", "F1"],
        "key_claims": ["Model X outperforms baseline"],
        "limitation_statements": ["We did not test on low-resource languages"],
    }
)


# ── Unit: _parse_llm_json ────────────────────────────────────────────


def test_parse_llm_json_plain() -> None:
    raw = '{"topics": ["NLP"]}'
    assert _parse_llm_json(raw) == {"topics": ["NLP"]}


def test_parse_llm_json_fenced() -> None:
    raw = '```json\n{"topics": ["NLP"]}\n```'
    assert _parse_llm_json(raw) == {"topics": ["NLP"]}


# ── Unit: extract_from_text ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_from_text_success() -> None:
    ref = _make_ref()
    with patch(
        "backend.agent.gap_detection.nodes.extractor.chat_completion",
        new_callable=AsyncMock,
        return_value=_GOOD_LLM_JSON,
    ):
        result = await extract_from_text(ref, "Paper about ML", source="abstract", pdf_url="https://pdf.url")

    assert result is not None
    assert isinstance(result, ExtractedPaperData)
    assert result.topics == ["machine learning", "NLP"]
    assert result.limitation_statements == ["We did not test on low-resource languages"]
    assert result.extraction_source == "abstract"
    assert result.pdf_url == "https://pdf.url"
    assert result.paper_ref.paper_id == "abc123"


@pytest.mark.asyncio
async def test_extract_from_text_retry_on_malformed() -> None:
    """First LLM call returns garbage, second returns good JSON → success."""
    ref = _make_ref()
    with patch(
        "backend.agent.gap_detection.nodes.extractor.chat_completion",
        new_callable=AsyncMock,
        side_effect=["NOT JSON AT ALL", _GOOD_LLM_JSON],
    ):
        result = await extract_from_text(ref, "text")

    assert result is not None
    assert result.topics == ["machine learning", "NLP"]


@pytest.mark.asyncio
async def test_extract_from_text_both_fail_returns_fallback() -> None:
    """Both LLM attempts fail → returns minimal fallback, NOT None."""
    ref = _make_ref()
    with patch(
        "backend.agent.gap_detection.nodes.extractor.chat_completion",
        new_callable=AsyncMock,
        side_effect=Exception("LLM down"),
    ):
        result = await extract_from_text(ref, "text")

    assert result is not None
    assert result.limitation_statements == []
    assert result.paper_ref.paper_id == "abc123"


# ── Integration: extractor_node ──────────────────────────────────────


@pytest.mark.asyncio
async def test_extractor_node_3_papers_success() -> None:
    """AC: 3 papers with abstracts → 3 ExtractedPaperData."""
    refs = [_make_ref(f"p{i}", f"Paper {i}") for i in range(3)]
    state: GapDetectionState = {"session_papers": refs}

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            new_callable=AsyncMock,
            return_value=_s2_detail(),
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    assert len(result["extracted_data"]) == 3
    for epd in result["extracted_data"]:
        assert isinstance(epd, ExtractedPaperData)
        assert epd.extraction_source == "abstract"
        assert len(epd.topics) > 0
        assert len(epd.limitation_statements) > 0


@pytest.mark.asyncio
async def test_extractor_node_one_fetch_fail() -> None:
    """AC: 1/3 fetch fails → 2 results, no exception."""
    refs = [_make_ref(f"p{i}", f"Paper {i}") for i in range(3)]
    state: GapDetectionState = {"session_papers": refs}

    call_count = 0

    async def _mock_detail(paper_id: str) -> dict | None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return None  # simulate failure
        return _s2_detail()

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            side_effect=_mock_detail,
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    assert len(result["extracted_data"]) == 2


@pytest.mark.asyncio
async def test_extractor_node_no_abstract_no_tldr() -> None:
    """AC: paper with no abstract and no tldr → skip."""
    refs = [_make_ref()]
    state: GapDetectionState = {"session_papers": refs}

    with patch(
        "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
        new_callable=AsyncMock,
        return_value=_s2_detail(abstract=None, tldr=None),
    ):
        result = await extractor_node(state)

    assert len(result["extracted_data"]) == 0


@pytest.mark.asyncio
async def test_extractor_node_empty_papers() -> None:
    """Edge: empty session_papers → empty extracted_data."""
    state: GapDetectionState = {"session_papers": []}
    result = await extractor_node(state)
    assert result == {"extracted_data": []}


@pytest.mark.asyncio
async def test_extractor_node_pdf_url_preserved() -> None:
    """AC: pdf_url from openAccessPdf is passed through."""
    refs = [_make_ref()]
    state: GapDetectionState = {"session_papers": refs}

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            new_callable=AsyncMock,
            return_value=_s2_detail(pdf_url="https://arxiv.org/pdf/1234.pdf"),
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    assert result["extracted_data"][0].pdf_url == "https://arxiv.org/pdf/1234.pdf"


@pytest.mark.asyncio
async def test_extractor_node_arxiv_only_skips_s2_detail() -> None:
    """AC: arXiv-only paper uses local abstract and avoids S2 detail."""
    ref = PaperRef(
        paper_id="arxiv:2310.12345",
        title="ArXiv Paper",
        year=2023,
        abstract="Local arXiv abstract.",
        source="arxiv",
    )
    state: GapDetectionState = {"session_papers": [ref]}

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            new_callable=AsyncMock,
        ) as mock_detail,
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    mock_detail.assert_not_awaited()
    assert len(result["extracted_data"]) == 1
    assert result["extracted_data"][0].abstract == "Local arXiv abstract."


@pytest.mark.asyncio
async def test_extractor_node_s2_paper_still_calls_detail() -> None:
    """AC: paper with S2 id keeps the existing detail-fetch path."""
    ref = _make_ref(pid="s2:abc123")
    state: GapDetectionState = {"session_papers": [ref]}

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            new_callable=AsyncMock,
            return_value=_s2_detail(),
        ) as mock_detail,
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    mock_detail.assert_awaited_once_with("s2:abc123")
    assert len(result["extracted_data"]) == 1


@pytest.mark.asyncio
async def test_extractor_node_concurrency_respected() -> None:
    """AC: concurrency semaphore limits parallel execution."""
    refs = [_make_ref(f"p{i}", f"Paper {i}") for i in range(5)]
    state: GapDetectionState = {"session_papers": refs}

    max_concurrent = 0
    current = 0
    lock = asyncio.Lock()

    original_detail = _s2_detail()

    async def _tracking_detail(paper_id: str) -> dict | None:
        nonlocal max_concurrent, current
        async with lock:
            current += 1
            if current > max_concurrent:
                max_concurrent = current
        await asyncio.sleep(0.05)  # simulate I/O
        async with lock:
            current -= 1
        return original_detail

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            side_effect=_tracking_detail,
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        await extractor_node(state, concurrency=2)

    assert max_concurrent <= 2


def test_default_concurrency_is_3() -> None:
    assert DEFAULT_CONCURRENCY == 3
