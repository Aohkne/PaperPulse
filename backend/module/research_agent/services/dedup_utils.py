"""Cross-source paper deduplication.

Dedup priority (first match wins, first occurrence kept as the "winner"):
  1. DOI — canonical identifier across all sources
  2. ArXiv ID — for preprints without a DOI yet
  3. paperId — same-source exact ID match
  4. Title fuzzy — rapidfuzz ratio >= 90 catches minor formatting differences

Sources ordered S2 → OpenAlex so S2 papers (richer metadata) win. Instead of
dropping the second copy outright, each source's strengths are MERGED into the
winner (S2 has the DOI, OpenAlex has the ArXiv ID, etc.). After dedup, papers
that can contribute to nothing downstream (no abstract to embed AND no
citationCount to rank) are filtered out.
"""

from __future__ import annotations

import logging

from backend.shared.models.paper import Paper

try:
    from rapidfuzz import fuzz as _fuzz

    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    logging.warning("rapidfuzz not installed — title fuzzy dedup disabled; install with: uv add rapidfuzz")

_TITLE_THRESHOLD = 90

# Scalar fields merged from a duplicate into the winner when the winner's value
# is None. paper_id and source are intentionally NOT merged — the winner keeps
# its own identity.
_MERGE_SCALARS = ("abstract", "citation_count", "year", "url")


def _merge_into(winner: Paper, dup: Paper) -> None:
    """Fill the winner's missing scalar fields + union externalIds from a dup."""
    for field in _MERGE_SCALARS:
        if getattr(winner, field, None) is None and getattr(dup, field, None) is not None:
            setattr(winner, field, getattr(dup, field))
    # externalIds: union both dicts, winner's own ids take precedence — picks up
    # e.g. DOI from S2 + ArXiv ID from OpenAlex.
    merged_ext = {**(dup.external_ids or {}), **(winner.external_ids or {})}
    if merged_ext:
        winner.external_ids = merged_ext


def dedup_papers(papers: list[Paper]) -> list[Paper]:
    """Return deduplicated list; first occurrence wins, later copies are merged in."""
    doi_winner: dict[str, Paper] = {}
    arxiv_winner: dict[str, Paper] = {}
    paperid_winner: dict[str, Paper] = {}
    title_winners: list[tuple[str, Paper]] = []

    result: list[Paper] = []

    for paper in papers:
        ext = paper.external_ids or {}

        doi = (ext.get("DOI") or "").strip().lower()
        arxiv_id = (ext.get("ArXiv") or "").strip().lower()
        pid = (paper.paper_id or "").strip()

        # Priority 1: DOI
        if doi:
            if doi in doi_winner:
                _merge_into(doi_winner[doi], paper)
                continue

        # Priority 2: ArXiv ID (only if no DOI)
        elif arxiv_id:
            if arxiv_id in arxiv_winner:
                _merge_into(arxiv_winner[arxiv_id], paper)
                continue

        # Priority 3: paperId (only if no DOI/ArXiv)
        elif pid:
            if pid in paperid_winner:
                _merge_into(paperid_winner[pid], paper)
                continue

        # Priority 4: title fuzzy (always check to catch cross-id duplicates)
        title = (paper.title or "").strip().lower()
        if title and _HAS_RAPIDFUZZ:
            match = next((w for t, w in title_winners if _fuzz.ratio(title, t) >= _TITLE_THRESHOLD), None)
            if match is not None:
                _merge_into(match, paper)
                continue

        # New unique paper — register it under every key it carries.
        if doi:
            doi_winner[doi] = paper
        if arxiv_id:
            arxiv_winner[arxiv_id] = paper
        if pid:
            paperid_winner[pid] = paper
        if title and _HAS_RAPIDFUZZ:
            title_winners.append((title, paper))
        result.append(paper)

    # Drop papers that contribute to nothing: no abstract to embed AND no
    # citationCount to rank/cluster on.
    return [p for p in result if not (p.abstract is None and p.citation_count is None)]
