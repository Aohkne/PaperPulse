"""Tests for TIP-P2-04 — co_occurrence.py + method_detector wire.

Verifies:
- build_co_occurrence() correctly counts (method, domain) pairs
- find_underexplored_pairs() returns pairs below threshold
- collect_corpus_vocab() returns deduplicated sorted lists
- get_co_occurrence_threshold() returns 2 by default
- method_detector_node still works after wiring (regression)
- test_gap_* regression suite still passes
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_epd(methodology: str | None, topics: list[str], paper_id: str = "p0"):
    """Create a minimal ExtractedPaperData for testing."""
    from backend.agent.gap_detection.schemas import ExtractedPaperData, PaperRef

    return ExtractedPaperData(
        paper_ref=PaperRef(paper_id=paper_id, title=f"Paper {paper_id}"),
        methodology=methodology,
        topics=topics,
    )


def _make_canonical(methodology: str | None, topics: list[str], paper_id: str = "p0"):
    """Create a minimal CanonicalPaper-shaped object for testing dedupe."""
    from types import SimpleNamespace

    return SimpleNamespace(
        paper_ref=SimpleNamespace(paper_id=paper_id, title=f"Paper {paper_id}"),
        methodology=methodology,
        topics=topics,
    )


# ── Part 1: co_occurrence.py unit tests ──────────────────────────────────────


def test_build_co_occurrence_counts_pairs() -> None:
    """AC: 3 papers with method=transformer + domain=NLP → count=3."""
    from backend.agent.gap_detection.co_occurrence import build_co_occurrence

    papers = [_make_epd("transformer", ["NLP"], f"p{i}") for i in range(3)]
    matrix = build_co_occurrence(papers)
    assert matrix[("transformer", "nlp")] == 3


def test_build_co_occurrence_empty_methodology() -> None:
    """Papers with no methodology contribute 0 to matrix."""
    from backend.agent.gap_detection.co_occurrence import build_co_occurrence

    papers = [_make_epd(None, ["vision"], "p0")]
    matrix = build_co_occurrence(papers)
    assert len(matrix) == 0


def test_build_co_occurrence_compound_methodology() -> None:
    """Compound methodology 'BERT, fine-tuning' is split into 2 method tokens."""
    from backend.agent.gap_detection.co_occurrence import build_co_occurrence

    papers = [_make_epd("BERT, fine-tuning", ["NLP"], "p0")]
    matrix = build_co_occurrence(papers)
    assert matrix[("bert", "nlp")] == 1
    assert matrix[("fine-tuning", "nlp")] == 1


def test_build_co_occurrence_multiple_domains() -> None:
    """A paper with 2 topics generates 2 pairs per method."""
    from backend.agent.gap_detection.co_occurrence import build_co_occurrence

    papers = [_make_epd("CNN", ["vision", "medical"], "p0")]
    matrix = build_co_occurrence(papers)
    assert matrix[("cnn", "vision")] == 1
    assert matrix[("cnn", "medical")] == 1


def test_build_co_occurrence_deduplicates_canonical_paper_sources() -> None:
    """Same CanonicalPaper seen from multiple sources is counted once."""
    from backend.agent.gap_detection.co_occurrence import build_co_occurrence

    papers = [
        _make_canonical("transformer", ["NLP"], "paper-1"),
        _make_canonical("transformer", ["NLP"], "paper-1"),
    ]
    matrix = build_co_occurrence(papers)
    assert matrix[("transformer", "nlp")] == 1


def test_find_underexplored_pairs_below_threshold() -> None:
    """AC: pair (transformer, vision)=0 with threshold=2 → in results."""
    from backend.agent.gap_detection.co_occurrence import find_underexplored_pairs

    matrix = {("transformer", "nlp"): 3}  # covered
    result = find_underexplored_pairs(matrix, ["transformer"], ["nlp", "vision"], threshold=2)
    assert ("transformer", "vision") in result
    assert ("transformer", "nlp") not in result  # count=3 >= threshold=2


def test_find_underexplored_pairs_at_threshold_is_covered() -> None:
    """AC: pair count=2, threshold=2 → NOT in results (exactly at threshold)."""
    from backend.agent.gap_detection.co_occurrence import find_underexplored_pairs

    matrix = {("transformer", "nlp"): 2}
    result = find_underexplored_pairs(matrix, ["transformer"], ["nlp"], threshold=2)
    assert ("transformer", "nlp") not in result


def test_find_underexplored_pairs_uses_default_threshold() -> None:
    """Default threshold=2 is applied when threshold=None."""
    from backend.agent.gap_detection.co_occurrence import find_underexplored_pairs

    matrix = {("cnn", "vision"): 1}  # 1 < 2 → underexplored
    result = find_underexplored_pairs(matrix, ["cnn"], ["vision"], threshold=None)
    assert ("cnn", "vision") in result


def test_find_underexplored_pairs_empty_matrix() -> None:
    """Empty matrix → all pairs are underexplored (count defaults to 0)."""
    from backend.agent.gap_detection.co_occurrence import find_underexplored_pairs

    result = find_underexplored_pairs({}, ["cnn"], ["vision"], threshold=2)
    assert ("cnn", "vision") in result


def test_collect_corpus_vocab_deduplication() -> None:
    """collect_corpus_vocab returns deduplicated sorted method + domain lists."""
    from backend.agent.gap_detection.co_occurrence import collect_corpus_vocab

    papers = [
        _make_epd("transformer", ["NLP", "vision"], "p0"),
        _make_epd("transformer", ["NLP"], "p1"),  # transformer + NLP repeated
        _make_epd("CNN", ["vision"], "p2"),
    ]
    methods, domains = collect_corpus_vocab(papers)
    assert methods == ["cnn", "transformer"]  # sorted, deduped
    assert domains == ["nlp", "vision"]  # sorted, deduped


def test_collect_corpus_vocab_no_methodology() -> None:
    """Papers with no methodology don't contribute to method vocab."""
    from backend.agent.gap_detection.co_occurrence import collect_corpus_vocab

    papers = [_make_epd(None, ["NLP"], "p0")]
    methods, domains = collect_corpus_vocab(papers)
    assert methods == []
    assert domains == ["nlp"]


# ── Part 2: settings.py threshold ────────────────────────────────────────────


def test_co_occurrence_threshold_default() -> None:
    """CO_OCCURRENCE_THRESHOLD default=2 when env not set."""
    from backend.agent.gap_detection.settings import get_co_occurrence_threshold

    os.environ.pop("CO_OCCURRENCE_THRESHOLD", None)
    assert get_co_occurrence_threshold() == 2


def test_co_occurrence_threshold_env_override() -> None:
    """CO_OCCURRENCE_THRESHOLD env var overrides default."""
    from backend.agent.gap_detection.settings import get_co_occurrence_threshold

    os.environ["CO_OCCURRENCE_THRESHOLD"] = "5"
    try:
        assert get_co_occurrence_threshold() == 5
    finally:
        os.environ.pop("CO_OCCURRENCE_THRESHOLD", None)


def test_co_occurrence_threshold_invalid_env_falls_back() -> None:
    """Invalid env value falls back to default 2."""
    from backend.agent.gap_detection.settings import get_co_occurrence_threshold

    os.environ["CO_OCCURRENCE_THRESHOLD"] = "not-a-number"
    try:
        assert get_co_occurrence_threshold() == 2
    finally:
        os.environ.pop("CO_OCCURRENCE_THRESHOLD", None)


# ── Part 3: method_detector wiring regression ─────────────────────────────────


@pytest.mark.asyncio
async def test_method_detector_no_gap_for_covered_pairs() -> None:
    """AC: method_detector does not suggest a gap for well-covered (transformer, NLP) pairs."""
    from backend.agent.gap_detection.nodes.method_detector import method_detector_node

    # 3 papers all cover (transformer, NLP) → count=3 ≥ threshold=2 → COVERED
    papers = [_make_epd("transformer", ["NLP"], f"p{i}") for i in range(3)]

    # LLM returns empty gaps (mocked) — test is about the wire path, not LLM output
    with patch(
        "backend.agent.gap_detection.nodes.method_detector.chat_completion",
        new=AsyncMock(return_value='{"gaps": []}'),
    ):
        result = await method_detector_node({"extracted_data": papers, "candidate_gaps": []})

    assert result["candidate_gaps"] == []


@pytest.mark.asyncio
async def test_method_detector_prompt_contains_covered_annotation() -> None:
    """The prompt sent to LLM includes [COVERED] annotation for covered pairs."""
    from backend.agent.gap_detection.nodes.method_detector import method_detector_node

    # 3 papers: transformer + NLP (covered, count=3)
    papers = [_make_epd("transformer", ["NLP"], f"p{i}") for i in range(3)]

    captured_messages: list = []

    async def _capture_chat(messages, **kwargs):
        captured_messages.extend(messages)
        return '{"gaps": []}'

    with patch(
        "backend.agent.gap_detection.nodes.method_detector.chat_completion",
        new=_capture_chat,
    ):
        await method_detector_node({"extracted_data": papers, "candidate_gaps": []})

    user_content = next(m["content"] for m in captured_messages if m["role"] == "user")
    # Covered pair annotated [COVERED]
    assert "[COVERED]" in user_content


@pytest.mark.asyncio
async def test_method_detector_prompt_contains_underexplored_annotation() -> None:
    """Underexplored pairs annotated [UNDEREXPLORED domains exist] in prompt."""
    from backend.agent.gap_detection.nodes.method_detector import method_detector_node

    # 2 papers but only 1 covers (transformer, NLP) → count=1 < threshold=2 → UNDEREXPLORED
    # (Need ≥2 papers to bypass the "need ≥2 to compare" guard in method_detector_node.)
    papers = [
        _make_epd("transformer", ["NLP"], "p0"),
        _make_epd("CNN", ["vision"], "p1"),  # different method/domain — doesn't cover transformer+NLP
    ]

    captured_messages: list = []

    async def _capture_chat(messages, **kwargs):
        captured_messages.extend(messages)
        return '{"gaps": []}'

    with patch(
        "backend.agent.gap_detection.nodes.method_detector.chat_completion",
        new=_capture_chat,
    ):
        await method_detector_node({"extracted_data": papers, "candidate_gaps": []})

    user_msgs = [m["content"] for m in captured_messages if m["role"] == "user"]
    assert user_msgs, "No user message was captured"
    user_content = user_msgs[0]
    assert "[UNDEREXPLORED domains exist]" in user_content


@pytest.mark.asyncio
async def test_method_detector_skips_untrusted_density_cells() -> None:
    """Cells below the density gate are filtered out before prompt generation."""
    from backend.agent.gap_detection.nodes.method_detector import method_detector_node

    papers = [
        _make_epd("transformer", ["NLP"], "p0"),
        _make_epd("transformer", ["NLP"], "p1"),
    ]

    captured_messages: list = []

    async def _capture_chat(messages, **kwargs):
        captured_messages.extend(messages)
        return '{"gaps": []}'

    density_signal = {
        "trusted_cells": [],
        "untrusted_cells": ["transformer|nlp"],
        "cells": {
            "transformer|nlp": {
                "method": "transformer",
                "domain": "nlp",
                "cell_count": 2,
                "method_count": 2,
                "domain_count": 2,
                "trusted": False,
            }
        },
        "min_papers": 3,
    }

    with patch(
        "backend.agent.gap_detection.nodes.method_detector.chat_completion",
        new=_capture_chat,
    ):
        await method_detector_node({"extracted_data": papers, "candidate_gaps": [], "density_signal": density_signal})

    user_content = next(m["content"] for m in captured_messages if m["role"] == "user")
    assert "[UNDEREXPLORED domains exist]" not in user_content
    assert "[COVERED]" in user_content
