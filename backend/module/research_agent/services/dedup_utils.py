"""Cross-source paper deduplication.

Dedup priority (first match wins, first occurrence kept):
  1. DOI — canonical identifier across all sources
  2. ArXiv ID — for preprints without a DOI yet
  3. paperId — same-source exact ID match
  4. Title fuzzy — rapidfuzz ratio >= 90 catches minor formatting differences

Sources ordered S2 → OpenAlex → arXiv so S2 papers (richer metadata) win.
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


def dedup_papers(papers: list[Paper]) -> list[Paper]:
    """Return deduplicated list; first occurrence wins on each dedup key."""
    seen_doi: set[str] = set()
    seen_arxiv: set[str] = set()
    seen_paperid: set[str] = set()
    seen_titles: list[str] = []

    result: list[Paper] = []

    for paper in papers:
        ext = paper.external_ids or {}

        doi = (ext.get("DOI") or "").strip().lower()
        arxiv_id = (ext.get("ArXiv") or "").strip().lower()
        pid = (paper.paper_id or "").strip()

        # Priority 1: DOI
        if doi:
            if doi in seen_doi:
                continue
            seen_doi.add(doi)

        # Priority 2: ArXiv ID (only if no DOI)
        elif arxiv_id:
            if arxiv_id in seen_arxiv:
                continue
            seen_arxiv.add(arxiv_id)

        # Priority 3: paperId (only if no DOI/ArXiv)
        elif pid:
            if pid in seen_paperid:
                continue
            seen_paperid.add(pid)

        # Priority 4: title fuzzy (always check to catch cross-id duplicates)
        title = (paper.title or "").strip().lower()
        if title and _HAS_RAPIDFUZZ:
            if any(_fuzz.ratio(title, t) >= _TITLE_THRESHOLD for t in seen_titles):
                continue
            seen_titles.append(title)

        result.append(paper)

    return result
