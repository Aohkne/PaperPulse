"""Tests for TIP-G02b — PDF full-text fetch + section extraction.

Covers pdf_utils.py (unit) and the updated _process_one_paper flow
(integration).  All network and LLM calls are mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.nodes.extractor import (
    extractor_node,
)
from backend.agent.gap_detection.nodes.pdf_utils import (
    MAX_LLM_CHARS,
    MIN_TEXT_LENGTH,
    _find_sections,
    extract_relevant_sections,
    fetch_pdf_text,
)
from backend.agent.gap_detection.schemas import (
    GapDetectionState,
    PaperRef,
)

# ── Fixtures ─────────────────────────────────────────────────────────


def _make_ref(pid: str = "abc123", title: str = "Test Paper") -> PaperRef:
    return PaperRef(paper_id=pid, title=title, year=2024)


def _s2_detail(
    *,
    abstract: str | None = "This paper studies X.",
    tldr: str | None = "We study X.",
    pdf_url: str | None = "https://example.com/paper.pdf",
) -> dict:
    result: dict = {
        "paperId": "abc123",
        "title": "Test Paper",
        "abstract": abstract,
        "year": 2024,
        "url": "https://s2/abc123",
        "authors": [{"name": "Alice"}],
        "tldr": {"text": tldr} if tldr else None,
        "openAccessPdf": {"url": pdf_url} if pdf_url else None,
    }
    return result


_GOOD_LLM_JSON = json.dumps(
    {
        "topics": ["deep learning"],
        "keywords": ["transformer"],
        "methodology": "fine-tuning",
        "dataset": "GLUE",
        "population": None,
        "metrics": ["accuracy"],
        "key_claims": ["Model outperforms baseline"],
        "limitation_statements": ["We did not test on low-resource languages"],
    }
)


_FAKE_PAPER_TEXT = """\
1. Introduction

This paper presents a novel approach.

2. Methods

We used a transformer-based model fine-tuned on GLUE.
The architecture consists of 12 layers with attention heads.

3. Results

Our model achieves 95% accuracy.

4. Discussion

The results are promising but further research is needed.

5. Limitations

We did not evaluate on multilingual datasets.
Our sample size was limited to 1000 examples.
Future work should explore larger corpora.

6. Conclusion

We presented a novel approach that outperforms baselines.
"""


# ═══════════════════════════════════════════════════════════════════════
# Unit: pdf_utils
# ═══════════════════════════════════════════════════════════════════════


class TestExtractRelevantSections:
    """Tests for extract_relevant_sections()."""

    def test_finds_methods_and_limitations(self) -> None:
        result = extract_relevant_sections(_FAKE_PAPER_TEXT)
        assert "transformer-based model" in result
        assert "multilingual datasets" in result
        assert "further research is needed" in result

    def test_excludes_introduction(self) -> None:
        """Introduction should NOT be in extracted sections."""
        result = extract_relevant_sections(_FAKE_PAPER_TEXT)
        # "novel approach" appears in intro AND conclusion,
        # but "This paper presents" is only in intro
        assert "This paper presents" not in result

    def test_fallback_head_tail_when_no_headers(self) -> None:
        """Plain text without headers → head + tail trimming."""
        plain = "A " * 10000  # 20000 chars, no headings
        result = extract_relevant_sections(plain)
        assert len(result) > 0
        assert len(result) <= MAX_LLM_CHARS

    def test_short_text_returned_as_is(self) -> None:
        short = "Methods\n\nWe used X.\n\nLimitations\n\nNone."
        result = extract_relevant_sections(short)
        assert "We used X" in result

    def test_caps_at_max_llm_chars(self) -> None:
        huge = "Methods\n\n" + "x " * 100_000
        result = extract_relevant_sections(huge)
        assert len(result) <= MAX_LLM_CHARS

    def test_numbered_section_headers(self) -> None:
        text = "1. Introduction\n\nIntro text.\n\n2. Methodology\n\nWe did Y.\n\n3. Results\n\nGood.\n"
        result = extract_relevant_sections(text)
        assert "We did Y" in result


class TestFindSections:
    """Tests for the internal _find_sections helper."""

    def test_methods_section_found(self) -> None:
        sections = _find_sections(_FAKE_PAPER_TEXT)
        assert any("transformer" in s for s in sections)

    def test_limitations_section_found(self) -> None:
        sections = _find_sections(_FAKE_PAPER_TEXT)
        assert any("multilingual" in s for s in sections)

    def test_empty_text(self) -> None:
        assert _find_sections("") == []

    def test_no_headings(self) -> None:
        assert _find_sections("just some plain text without any headings") == []


class TestFetchPdfText:
    """Tests for fetch_pdf_text() with mocked downloads."""

    @pytest.mark.asyncio
    async def test_download_fail_returns_none(self) -> None:
        with patch(
            "backend.agent.gap_detection.nodes.pdf_utils._download_pdf",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await fetch_pdf_text("https://example.com/404.pdf")
        assert result is None

    @pytest.mark.asyncio
    async def test_scanned_image_pdf_returns_none(self) -> None:
        """Text shorter than MIN_TEXT_LENGTH → None (scanned image)."""
        with (
            patch(
                "backend.agent.gap_detection.nodes.pdf_utils._download_pdf",
                new_callable=AsyncMock,
                return_value=b"fake-pdf-bytes",
            ),
            patch(
                "backend.agent.gap_detection.nodes.pdf_utils._extract_text_from_bytes",
                return_value="short",  # < MIN_TEXT_LENGTH
            ),
        ):
            result = await fetch_pdf_text("https://example.com/scan.pdf")
        assert result is None

    @pytest.mark.asyncio
    async def test_good_pdf_returns_text(self) -> None:
        long_text = "A " * (MIN_TEXT_LENGTH + 100)
        with (
            patch(
                "backend.agent.gap_detection.nodes.pdf_utils._download_pdf",
                new_callable=AsyncMock,
                return_value=b"fake-pdf-bytes",
            ),
            patch(
                "backend.agent.gap_detection.nodes.pdf_utils._extract_text_from_bytes",
                return_value=long_text,
            ),
        ):
            result = await fetch_pdf_text("https://example.com/good.pdf")
        assert result == long_text

    @pytest.mark.asyncio
    async def test_exception_returns_none(self) -> None:
        with patch(
            "backend.agent.gap_detection.nodes.pdf_utils._download_pdf",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            result = await fetch_pdf_text("https://example.com/err.pdf")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Integration: _process_one_paper with PDF enrichment
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paper_with_pdf_uses_fulltext() -> None:
    """AC: paper with valid PDF → extraction_source='fulltext'."""
    refs = [_make_ref()]
    state: GapDetectionState = {"session_papers": refs}

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            new_callable=AsyncMock,
            return_value=_s2_detail(pdf_url="https://arxiv.org/pdf/1234.pdf"),
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.fetch_pdf_text",
            new_callable=AsyncMock,
            return_value=_FAKE_PAPER_TEXT,
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    assert len(result["extracted_data"]) == 1
    epd = result["extracted_data"][0]
    assert epd.extraction_source == "fulltext"
    assert epd.pdf_url == "https://arxiv.org/pdf/1234.pdf"


@pytest.mark.asyncio
async def test_pdf_fail_falls_back_to_abstract() -> None:
    """AC: PDF download fails → fallback to abstract, source='abstract'."""
    refs = [_make_ref()]
    state: GapDetectionState = {"session_papers": refs}

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            new_callable=AsyncMock,
            return_value=_s2_detail(
                abstract="Study of neural networks.",
                pdf_url="https://bad-url.com/404.pdf",
            ),
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.fetch_pdf_text",
            new_callable=AsyncMock,
            return_value=None,  # PDF fail
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    assert len(result["extracted_data"]) == 1
    assert result["extracted_data"][0].extraction_source == "abstract"


@pytest.mark.asyncio
async def test_no_pdf_url_uses_abstract() -> None:
    """AC: paper without openAccessPdf → abstract flow, source='abstract'."""
    refs = [_make_ref()]
    state: GapDetectionState = {"session_papers": refs}

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            new_callable=AsyncMock,
            return_value=_s2_detail(pdf_url=None),
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    assert len(result["extracted_data"]) == 1
    assert result["extracted_data"][0].extraction_source == "abstract"


@pytest.mark.asyncio
async def test_mixed_papers_pdf_and_abstract() -> None:
    """Two papers: one with PDF, one without → correct sources."""
    refs = [_make_ref("p1", "With PDF"), _make_ref("p2", "No PDF")]
    state: GapDetectionState = {"session_papers": refs}

    call_count = 0

    async def _mock_detail(paper_id: str) -> dict:
        nonlocal call_count
        call_count += 1
        if paper_id == "p1":
            return _s2_detail(pdf_url="https://pdf.com/p1.pdf")
        return _s2_detail(pdf_url=None)

    async def _mock_pdf(url: str) -> str | None:
        return _FAKE_PAPER_TEXT

    with (
        patch(
            "backend.agent.gap_detection.nodes.extractor.get_paper_detail",
            side_effect=_mock_detail,
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.fetch_pdf_text",
            side_effect=_mock_pdf,
        ),
        patch(
            "backend.agent.gap_detection.nodes.extractor.chat_completion",
            new_callable=AsyncMock,
            return_value=_GOOD_LLM_JSON,
        ),
    ):
        result = await extractor_node(state)

    {epd.paper_ref.paper_id: epd.extraction_source for epd in result["extracted_data"]}
    # p1 should have PDF, p2 should have abstract — but paper_ref comes from
    # input refs, not S2 detail. Both should succeed.
    assert len(result["extracted_data"]) == 2
    # p1 had pdf_url → fulltext
    assert any(e.extraction_source == "fulltext" for e in result["extracted_data"])
    # p2 had no pdf_url → abstract
    assert any(e.extraction_source == "abstract" for e in result["extracted_data"])
