"""Tests for TIP-404 — source_resolution.py + CanonicalPaper schema.

Covers acceptance criteria:
- AC1: Same DOI from two sources → 1 CanonicalPaper, sources includes both
- AC2: Same title (no DOI) → merged via title-normalize
- AC3: One fulltext + one abstract → fulltext != None, fulltext_available=True
- AC4: background_corpus paper → corpus_role=BACKGROUND
- AC5: One bad/empty record → resolve continues without crash

Also covers:
- _normalize_doi: strips URL prefix, lowercases
- _normalize_title: NFC + lowercase + punctuation strip
- _resolution_key: DOI > title > s2_paper_id priority
- corpus_role: USER wins over BACKGROUND when mixed
- sources: sorted union of source names
- is_influential: True if any record is influential
- abstract: longest abstract preferred when no fulltext record
- s2_paper_id: carried through from S2 record
- deterministic sort: output order is by canonical key
"""

from __future__ import annotations

from backend.agent.gap_detection.schemas import CorpusRole
from backend.agent.gap_detection.source_resolution import (
    RawRecord,
    _normalize_doi,
    _normalize_title,
    _resolution_key,
    resolve_papers,
)
from backend.shared.models.paper import Paper

# ── Helpers ───────────────────────────────────────────────────────────────────


def _paper(
    paper_id: str = "p1",
    title: str = "A Study on X",
    doi: str | None = None,
    abstract: str | None = None,
    year: int | None = 2023,
    is_influential: bool = False,
    authors: list[str] | None = None,
) -> Paper:
    ext = {"DOI": doi} if doi else {}
    return Paper(
        paperId=paper_id,
        title=title,
        abstract=abstract,
        year=year,
        externalIds=ext,
        isInfluential=is_influential,
        authors=authors or [],
    )


def _rec(
    paper: Paper,
    corpus_role: CorpusRole = CorpusRole.USER,
    source_name: str = "s2",
    fulltext: str | None = None,
) -> RawRecord:
    return RawRecord(
        paper=paper,
        corpus_role=corpus_role,
        source_name=source_name,
        fulltext=fulltext,
    )


# ── _normalize_doi ────────────────────────────────────────────────────────────


def test_normalize_doi_strips_https_prefix():
    assert _normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"


def test_normalize_doi_strips_http_prefix():
    assert _normalize_doi("http://doi.org/10.1234/ABC") == "10.1234/abc"


def test_normalize_doi_strips_doi_colon_prefix():
    assert _normalize_doi("doi:10.5678/XYZ") == "10.5678/xyz"


def test_normalize_doi_lowercases_bare():
    assert _normalize_doi("10.1234/ABC") == "10.1234/abc"


def test_normalize_doi_empty_string():
    assert _normalize_doi("") == ""


def test_normalize_doi_none_like():
    assert _normalize_doi(None) == ""  # type: ignore[arg-type]


# ── _normalize_title ──────────────────────────────────────────────────────────


def test_normalize_title_lowercases_and_strips_punctuation():
    result = _normalize_title("Learning, Reasoning & Planning!")
    assert result == "learning reasoning planning"


def test_normalize_title_collapses_whitespace():
    result = _normalize_title("A   Study   on   X")
    assert result == "a study on x"


def test_normalize_title_nfc():
    """Precomposed and decomposed forms of the same character → same key."""
    composed = _normalize_title("café")  # é precomposed
    decomposed = _normalize_title("café")  # é decomposed
    assert composed == decomposed


def test_normalize_title_empty():
    assert _normalize_title("") == ""


# ── _resolution_key ───────────────────────────────────────────────────────────


def test_resolution_key_prefers_doi():
    rec = _rec(_paper(paper_id="s2abc", title="Some Paper", doi="10.1/x"))
    key = _resolution_key(rec)
    assert key == "doi:10.1/x"


def test_resolution_key_falls_back_to_title():
    rec = _rec(_paper(paper_id="s2abc", title="A Study on X", doi=None))
    key = _resolution_key(rec)
    assert key.startswith("title:")
    assert "a study on x" in key


def test_resolution_key_falls_back_to_s2_paper_id():
    p = Paper(paperId="abc123", title="", externalIds={})
    rec = _rec(p)
    key = _resolution_key(rec)
    assert key == "s2:abc123"


def test_resolution_key_empty_returns_empty():
    p = Paper(paperId="", title="", externalIds={})
    rec = _rec(p)
    assert _resolution_key(rec) == ""


# ── AC1: same DOI from two sources → 1 CanonicalPaper ───────────────────────


def test_resolve_same_doi_two_sources():
    """AC1: two records with same DOI → single CanonicalPaper, sources merged."""
    p_s2 = _paper(paper_id="s2abc", title="Paper A", doi="10.1234/abc")
    p_ax = _paper(paper_id="", title="Paper A (arXiv)", doi="10.1234/abc")

    records = [
        _rec(p_s2, source_name="s2"),
        _rec(p_ax, source_name="arxiv"),
    ]
    result = resolve_papers(records)

    assert len(result) == 1
    cp = result[0]
    assert cp.id == "doi:10.1234/abc"
    assert "s2" in cp.sources
    assert "arxiv" in cp.sources
    assert len(cp.sources) == 2


# ── AC2: same title, no DOI → merged via title-normalize ─────────────────────


def test_resolve_same_title_no_doi():
    """AC2: two records with same normalised title, no DOI → 1 CanonicalPaper."""
    p1 = _paper(paper_id="p1", title="Learning Representations of Text!", doi=None)
    p2 = _paper(paper_id="p2", title="Learning Representations of Text", doi=None)

    records = [_rec(p1, source_name="s2"), _rec(p2, source_name="arxiv")]
    result = resolve_papers(records)

    assert len(result) == 1
    cp = result[0]
    assert cp.id.startswith("title:")
    assert set(cp.sources) == {"s2", "arxiv"}


# ── AC3: fulltext + abstract → fulltext wins ──────────────────────────────────


def test_resolve_fulltext_preferred_over_abstract():
    """AC3: one record with fulltext, one with abstract only → fulltext propagated."""
    p_abstract = _paper(paper_id="p1", title="Paper B", doi="10.5/b", abstract="Short abstract")
    p_fulltext = _paper(paper_id="p2", title="Paper B", doi="10.5/b", abstract="Abstract from fulltext source")

    records = [
        _rec(p_abstract, source_name="s2", fulltext=None),
        _rec(p_fulltext, source_name="arxiv", fulltext="Full paper text here..."),
    ]
    result = resolve_papers(records)

    assert len(result) == 1
    cp = result[0]
    assert cp.fulltext == "Full paper text here..."
    assert cp.fulltext_available is True
    assert cp.abstract == "Abstract from fulltext source"


# ── AC4: background paper → corpus_role=BACKGROUND ───────────────────────────


def test_resolve_background_paper():
    """AC4: record with BACKGROUND role → corpus_role=BACKGROUND."""
    p = _paper(paper_id="bg1", title="Background Paper", doi="10.9/bg")
    records = [_rec(p, corpus_role=CorpusRole.BACKGROUND, source_name="s2")]
    result = resolve_papers(records)

    assert len(result) == 1
    assert result[0].corpus_role == CorpusRole.BACKGROUND


def test_resolve_user_wins_over_background():
    """USER record in group overrides BACKGROUND → corpus_role=USER."""
    doi = "10.9/mixed"
    p_bg = _paper(paper_id="p1", title="Paper", doi=doi)
    p_user = _paper(paper_id="p2", title="Paper", doi=doi)

    records = [
        _rec(p_bg, corpus_role=CorpusRole.BACKGROUND, source_name="s2"),
        _rec(p_user, corpus_role=CorpusRole.USER, source_name="arxiv"),
    ]
    result = resolve_papers(records)

    assert len(result) == 1
    assert result[0].corpus_role == CorpusRole.USER


# ── AC5: bad/empty record → resolve continues without crash ──────────────────


def test_resolve_skips_empty_record():
    """AC5: record with no title, no doi, no paper_id → skipped, rest resolves."""
    p_good = _paper(paper_id="p1", title="Good Paper", doi="10.1/good")
    p_bad = Paper(paperId="", title="", externalIds={})

    records = [
        _rec(p_good, source_name="s2"),
        _rec(p_bad, source_name="s2"),
    ]
    result = resolve_papers(records)

    assert len(result) == 1
    assert result[0].id == "doi:10.1/good"


def test_resolve_empty_list():
    """Empty input → empty output, no crash."""
    assert resolve_papers([]) == []


# ── Additional: sources, s2_paper_id, is_influential ─────────────────────────


def test_resolve_sources_sorted():
    """sources list is always sorted for determinism."""
    doi = "10.1/sort"
    records = [
        _rec(_paper(paper_id="p1", title="X", doi=doi), source_name="s2"),
        _rec(_paper(paper_id="p2", title="X", doi=doi), source_name="arxiv"),
        _rec(_paper(paper_id="p3", title="X", doi=doi), source_name="pubmed"),
    ]
    result = resolve_papers(records)

    assert result[0].sources == ["arxiv", "pubmed", "s2"]


def test_resolve_s2_paper_id_carried_through():
    """s2_paper_id from S2 record is preserved in CanonicalPaper."""
    doi = "10.1/s2id"
    records = [
        _rec(_paper(paper_id="S2ID123", title="X", doi=doi), source_name="s2"),
    ]
    result = resolve_papers(records)
    assert result[0].s2_paper_id == "S2ID123"


def test_resolve_is_influential_propagates():
    """is_influential=True on any record → CanonicalPaper.is_influential=True."""
    doi = "10.1/inf"
    records = [
        _rec(_paper(paper_id="p1", title="X", doi=doi, is_influential=False), source_name="s2"),
        _rec(_paper(paper_id="p2", title="X", doi=doi, is_influential=True), source_name="arxiv"),
    ]
    result = resolve_papers(records)
    assert result[0].is_influential is True


def test_resolve_abstract_longest_when_no_fulltext():
    """When no fulltext, pick the longest abstract."""
    doi = "10.1/abs"
    records = [
        _rec(_paper(paper_id="p1", title="X", doi=doi, abstract="Short"), source_name="s2"),
        _rec(
            _paper(paper_id="p2", title="X", doi=doi, abstract="Much longer abstract with more content"),
            source_name="arxiv",
        ),
    ]
    result = resolve_papers(records)
    assert result[0].abstract == "Much longer abstract with more content"


def test_resolve_distinct_papers_not_merged():
    """Papers with different DOIs produce separate CanonicalPaper objects."""
    records = [
        _rec(_paper(paper_id="p1", title="Paper A", doi="10.1/a"), source_name="s2"),
        _rec(_paper(paper_id="p2", title="Paper B", doi="10.1/b"), source_name="s2"),
    ]
    result = resolve_papers(records)
    assert len(result) == 2


def test_resolve_output_sorted_by_key():
    """Output is sorted by canonical key (deterministic)."""
    records = [
        _rec(_paper(paper_id="p2", title="Zebra Study", doi="10.9/z"), source_name="s2"),
        _rec(_paper(paper_id="p1", title="Alpha Study", doi="10.1/a"), source_name="s2"),
    ]
    result = resolve_papers(records)
    assert result[0].id == "doi:10.1/a"
    assert result[1].id == "doi:10.9/z"


def test_resolve_single_record_no_doi_uses_title_key():
    """Single record without DOI uses title key."""
    p = _paper(paper_id="p1", title="Unique Study Title", doi=None)
    records = [_rec(p, source_name="s2")]
    result = resolve_papers(records)

    assert len(result) == 1
    assert result[0].id.startswith("title:unique study title")


def test_resolve_fuzzy_title_fallback_merges_punctuation_variants():
    """AC: punctuated title variants merge via fuzzy fallback when exact normalize misses."""
    records = [
        _rec(_paper(paper_id="p1", title="Speculative Decoding: Efficient X", doi=None), source_name="s2"),
        _rec(_paper(paper_id="p2", title="Speculative Decoding-- Efficient X", doi=None), source_name="arxiv"),
    ]
    result = resolve_papers(records)

    assert len(result) == 1
    assert result[0].id.startswith("title:speculative decoding efficient x")
    assert set(result[0].sources) == {"s2", "arxiv"}


def test_resolve_fuzzy_title_fallback_does_not_merge_distinct_titles():
    """AC: clearly different titles remain separate when ratio is below threshold."""
    records = [
        _rec(_paper(paper_id="p1", title="A Study on Federated Learning", doi=None), source_name="s2"),
        _rec(_paper(paper_id="p2", title="A Study on Federated Learning II", doi=None), source_name="arxiv"),
    ]
    result = resolve_papers(records)

    assert len(result) == 2


def test_resolve_doi_match_preempts_fuzzy_title_fallback():
    """AC: records already merged by DOI should not rely on fuzzy title matching."""
    records = [
        _rec(_paper(paper_id="p1", title="Paper A: Version 1", doi="10.1/doi-match"), source_name="s2"),
        _rec(_paper(paper_id="p2", title="Paper A -- Version 2", doi="10.1/doi-match"), source_name="arxiv"),
    ]
    result = resolve_papers(records)

    assert len(result) == 1
    assert result[0].id == "doi:10.1/doi-match"


def test_resolve_near_match_below_threshold_does_not_false_merge():
    """AC: near matches that do not clear the fuzzy threshold must stay separate."""
    records = [
        _rec(_paper(paper_id="p1", title="A Study on Federated Learning", doi=None), source_name="s2"),
        _rec(_paper(paper_id="p2", title="A Study on Graph Learning", doi=None), source_name="arxiv"),
    ]
    result = resolve_papers(records)

    assert len(result) == 2
