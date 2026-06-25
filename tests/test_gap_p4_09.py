"""Tests for TIP-409 — density_readiness + coverage_estimate (Stage D b,c).

Acceptance criteria (from TIP):
- AC1: method M in 2 papers (< 3) → cell containing M marked "not trusted"
- AC2: method M in 4 papers, domain D in 3 papers → cell (M,D) trusted (both ≥ 3)
- AC3: coverage_estimate → returns [0,1] saturation heuristic, fallback None safely
- AC4: density signal feeds state → co-occurrence (406) can read which cells are trusted

Also covers:
- density_readiness: empty corpus → empty result, no crash
- density_readiness: works with both Paper and ExtractedPaperData (duck-typed)
- density_readiness: cell_count / method_count / domain_count all correct
- density_readiness: deterministic (same input → same output, sorted)
- coverage_estimate: rounds=None → None (safe fallback)
- coverage_estimate: len/SATURATION_TARGET linear model, clamped to 1.0
- check_coherence: includes density_signal and coverage in return dict
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.nodes.coherence_check import (
    _SATURATION_TARGET,
    DENSITY_MIN_PAPERS,
    _paper_domain_key,
    _paper_method_key,
    check_coherence,
    coverage_estimate,
    density_readiness,
)
from backend.agent.gap_detection.schemas import ExtractedPaperData, PaperRef
from backend.shared.models.paper import Paper

# ── Helpers ───────────────────────────────────────────────────────────────────


def _paper(
    pid: str = "p1",
    title: str = "Test Paper",
    abstract: str | None = None,
    year: int | None = 2023,
) -> Paper:
    return Paper(paperId=pid, title=title, abstract=abstract or "", year=year)


def _extracted(
    methodology: str | None,
    topics: list[str],
    pid: str = "p1",
    year: int | None = 2023,
) -> ExtractedPaperData:
    return ExtractedPaperData(
        paper_ref=PaperRef(paper_id=pid, title="Test Paper", year=year),
        methodology=methodology,
        topics=topics,
    )


# ── AC1: method M in < 3 papers → cell not trusted ───────────────────────────


def test_density_method_below_threshold_not_trusted():
    """AC1: method M appears in only 2 papers → cell containing M is untrusted."""
    corpus = [
        _extracted("transformer", ["nlp"], pid="p1"),
        _extracted("transformer", ["nlp"], pid="p2"),
    ]
    result = density_readiness(corpus)

    assert "transformer|nlp" in result["untrusted_cells"]
    assert "transformer|nlp" not in result["trusted_cells"]
    assert result["cells"]["transformer|nlp"]["trusted"] is False
    assert result["cells"]["transformer|nlp"]["method_count"] == 2


def test_density_method_below_threshold_method_count_correct():
    """method_count reflects total papers for that method across all domains."""
    corpus = [
        _extracted("cnn", ["vision"], pid="p1"),
        _extracted("cnn", ["medical"], pid="p2"),
    ]
    result = density_readiness(corpus)

    for key, cell in result["cells"].items():
        if cell["method"] == "cnn":
            assert cell["method_count"] == 2
            assert cell["trusted"] is False


# ── AC2: method M ≥3, domain D ≥3 → cell (M,D) trusted ──────────────────────


def test_density_both_row_column_above_threshold_trusted():
    """AC2: method M in 4 papers, domain D in 3 papers → cell (M,D) trusted."""
    corpus = [
        _extracted("transformer", ["nlp"], pid="p1"),
        _extracted("transformer", ["nlp"], pid="p2"),
        _extracted("transformer", ["nlp"], pid="p3"),
        _extracted("transformer", ["vision"], pid="p4"),  # M count=4, D(nlp)=3
    ]
    result = density_readiness(corpus)

    key = "transformer|nlp"
    assert key in result["cells"]
    cell = result["cells"][key]
    assert cell["method_count"] == 4
    assert cell["domain_count"] == 3
    assert cell["trusted"] is True
    assert key in result["trusted_cells"]


def test_density_mixed_trusted_and_untrusted_cells():
    """corpus with one trusted and one untrusted cell → correctly partitioned."""
    # transformer: 4 papers across nlp(3) and vision(1)
    # cnn: 2 papers in vision
    corpus = [
        _extracted("transformer", ["nlp"], pid="p1"),
        _extracted("transformer", ["nlp"], pid="p2"),
        _extracted("transformer", ["nlp"], pid="p3"),
        _extracted("transformer", ["vision"], pid="p4"),
        _extracted("cnn", ["vision"], pid="p5"),
        _extracted("cnn", ["vision"], pid="p6"),
    ]
    result = density_readiness(corpus)

    # transformer|nlp: method_count=4, domain_count=3 → trusted
    assert result["cells"]["transformer|nlp"]["trusted"] is True
    # transformer|vision: method_count=4, domain_count=3 (vision has p4,p5,p6) → trusted
    assert result["cells"]["transformer|vision"]["trusted"] is True
    # cnn|vision: method_count=2 (< 3) → not trusted
    assert result["cells"]["cnn|vision"]["trusted"] is False


def test_density_domain_below_threshold_not_trusted():
    """If domain count < 3, cell is not trusted even if method count ≥ 3."""
    corpus = [
        _extracted("deep learning", ["rare_domain"], pid="p1"),
        _extracted("deep learning", ["rare_domain"], pid="p2"),
        _extracted("deep learning", ["other_domain"], pid="p3"),
        _extracted("deep learning", ["other_domain"], pid="p4"),
    ]
    result = density_readiness(corpus)

    # rare_domain: domain_count=2 → not trusted
    assert result["cells"]["deep learning|rare_domain"]["domain_count"] == 2
    assert result["cells"]["deep learning|rare_domain"]["trusted"] is False


# ── AC3: coverage_estimate → [0,1] or None ───────────────────────────────────


def test_coverage_estimate_rounds_none_returns_none():
    """AC3 fallback: rounds=None → returns None safely."""
    corpus = [_paper(pid=str(i)) for i in range(10)]
    assert coverage_estimate(corpus, rounds=None) is None


def test_coverage_estimate_empty_corpus_returns_none():
    """Empty corpus → returns None safely."""
    assert coverage_estimate([], rounds=1) is None


def test_coverage_estimate_in_range():
    """AC3: coverage_estimate returns float in [0.0, 1.0]."""
    corpus = [_paper(pid=str(i)) for i in range(10)]
    result = coverage_estimate(corpus, rounds=1)
    assert result is not None
    assert 0.0 <= result <= 1.0


def test_coverage_estimate_saturates_at_target():
    """corpus of SATURATION_TARGET papers → coverage == 1.0."""
    corpus = [_paper(pid=str(i)) for i in range(_SATURATION_TARGET)]
    result = coverage_estimate(corpus, rounds=1)
    assert result == 1.0


def test_coverage_estimate_linear_proxy():
    """Half of SATURATION_TARGET papers → coverage ≈ 0.5."""
    corpus = [_paper(pid=str(i)) for i in range(_SATURATION_TARGET // 2)]
    result = coverage_estimate(corpus, rounds=1)
    assert result == pytest.approx(0.5, abs=0.01)


def test_coverage_estimate_clamped_above_target():
    """More than SATURATION_TARGET papers → coverage still 1.0 (clamped)."""
    corpus = [_paper(pid=str(i)) for i in range(_SATURATION_TARGET * 3)]
    result = coverage_estimate(corpus, rounds=1)
    assert result == 1.0


# ── AC4: density signal in state ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_coherence_returns_density_signal_key():
    """AC4: check_coherence() result always includes 'density_signal' key."""
    papers = [_paper(pid=str(i), year=2023) for i in range(3)]
    result = await check_coherence(papers)
    assert "density_signal" in result
    assert isinstance(result["density_signal"], dict)


@pytest.mark.asyncio
async def test_check_coherence_returns_coverage_key():
    """check_coherence() result always includes 'coverage' key (None or float)."""
    papers = [_paper(pid=str(i), year=2023) for i in range(3)]
    result = await check_coherence(papers)
    assert "coverage" in result


@pytest.mark.asyncio
async def test_check_coherence_density_signal_has_expected_shape():
    """density_signal from check_coherence has cells / trusted / untrusted keys."""
    papers = [_paper(pid=str(i), year=2023) for i in range(6)]
    with patch(
        "backend.agent.gap_detection.nodes.coherence_check._get_specter_vectors",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await check_coherence(papers)
    ds = result["density_signal"]
    assert "cells" in ds
    assert "trusted_cells" in ds
    assert "untrusted_cells" in ds
    assert "min_papers" in ds
    assert ds["min_papers"] == DENSITY_MIN_PAPERS


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_density_readiness_empty_corpus():
    """Empty corpus → empty result, no crash."""
    result = density_readiness([])
    assert result["cells"] == {}
    assert result["trusted_cells"] == []
    assert result["untrusted_cells"] == []


def test_density_readiness_deterministic():
    """Same input produces identical output on repeated calls."""
    corpus = [
        _extracted("transformer", ["nlp"], pid="p1"),
        _extracted("cnn", ["vision"], pid="p2"),
        _extracted("transformer", ["nlp"], pid="p3"),
    ]
    r1 = density_readiness(corpus)
    r2 = density_readiness(corpus)
    assert r1["cells"] == r2["cells"]
    assert r1["trusted_cells"] == r2["trusted_cells"]
    assert r1["untrusted_cells"] == r2["untrusted_cells"]


def test_density_readiness_cell_count_correct():
    """cell_count reflects papers with BOTH that method AND domain."""
    corpus = [
        _extracted("transformer", ["nlp"], pid="p1"),
        _extracted("transformer", ["nlp"], pid="p2"),
        _extracted("transformer", ["vision"], pid="p3"),
    ]
    result = density_readiness(corpus)
    assert result["cells"]["transformer|nlp"]["cell_count"] == 2
    assert result["cells"]["transformer|vision"]["cell_count"] == 1


def test_density_readiness_works_with_paper_objects():
    """density_readiness accepts list[Paper] via heuristic fallback."""
    papers = [
        _paper(pid="p1", abstract="we use deep learning", year=2023),
        _paper(pid="p2", abstract="transformer approach", year=2023),
        _paper(pid="p3", abstract="deep learning method", year=2024),
    ]
    result = density_readiness(papers)
    assert isinstance(result["cells"], dict)
    assert isinstance(result["trusted_cells"], list)
    assert isinstance(result["untrusted_cells"], list)


def test_paper_method_key_extracted_data():
    """_paper_method_key uses methodology field on ExtractedPaperData."""
    item = _extracted("random forest", ["tabular"])
    assert _paper_method_key(item) == "random forest"


def test_paper_method_key_paper_abstract_fallback():
    """_paper_method_key falls back to abstract keyword matching for Paper."""
    p = _paper(abstract="We propose a transformer-based model for NLP tasks.")
    assert _paper_method_key(p) == "transformer"


def test_paper_method_key_unknown_fallback():
    """_paper_method_key returns 'other' when no keyword matches."""
    p = _paper(abstract="A study on ancient pottery techniques.")
    assert _paper_method_key(p) == "other"


def test_paper_domain_key_extracted_data():
    """_paper_domain_key uses first topic on ExtractedPaperData."""
    item = _extracted("transformer", ["computer vision"])
    assert _paper_domain_key(item) == "computer vision"


def test_paper_domain_key_year_buckets():
    """_paper_domain_key uses year buckets for Paper objects."""
    assert _paper_domain_key(_paper(year=2024)) == "recent"
    assert _paper_domain_key(_paper(year=2021)) == "post2020"
    assert _paper_domain_key(_paper(year=2018)) == "pre2020"
    assert _paper_domain_key(_paper(year=None)) == "unknown_domain"
