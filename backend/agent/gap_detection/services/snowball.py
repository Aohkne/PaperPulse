"""Citation snowballing for gap detection — gap-owned copy, independent of research_agent.

Gap module MUST NOT import from research_agent.services (Chủ nhà constraint, TIP-413).
This file owns run_snowball() + select_seeds() used by retrieval.py.

Key difference from research_agent/services/snowball.py:
  - run_snowball() returns list[Paper] only (NOT tuple[list[Paper], list[dict]]).
    Gap doesn't need citation_edges (used by research_agent Knowledge Graph only).
    This avoids the tuple-mismatch bug that crashed retrieval.py after the KG merge.
  - Uses named logger (not module-level logging).
  - research_agent/services/snowball.py is NOT touched (it still serves the KG pipeline).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from backend.shared.models.paper import Paper
from backend.shared.services.semantic_scholar import get_citations, get_references

logger = logging.getLogger(__name__)

_CURRENT_YEAR = datetime.now().year


# ── Seed selection: dual-pool (SPEC_1.0.1) ───────────────────────────────────

def select_seeds(papers: list[Paper], pool_size: int = 5) -> list[str]:
    """Dual-pool seed selection per SPEC_1.0.1:
    Pool A: top-N by raw citationCount (foundational papers)
    Pool B: top-N by citationCount/(current_year - year) (recent impactful)
    Returns deduplicated paperId list (~7–9 seeds).
    """
    valid = [p for p in papers if p.paper_id and p.citation_count is not None]

    pool_a = sorted(valid, key=lambda p: p.citation_count or 0, reverse=True)[:pool_size]

    def per_year_rate(p: Paper) -> float:
        age = max(_CURRENT_YEAR - (p.year or _CURRENT_YEAR), 1)
        return (p.citation_count or 0) / age

    pool_b = sorted(valid, key=per_year_rate, reverse=True)[:pool_size]

    seen: set[str] = set()
    seeds: list[str] = []
    for p in pool_a + pool_b:
        if p.paper_id not in seen:
            seen.add(p.paper_id)
            seeds.append(p.paper_id)
    return seeds


# ── Backward/forward filters (SPEC_1.0.1) ────────────────────────────────────

def _backward_keep(paper: Paper, is_influential: bool) -> bool:
    if is_influential:
        return True
    year = paper.year or 2000
    citations = paper.citation_count or 0
    if year >= _CURRENT_YEAR - 2:
        return citations >= 0
    if year >= _CURRENT_YEAR - 5:
        return citations >= 3
    return citations >= 5


def _forward_keep(paper: Paper, is_influential: bool) -> bool:
    citations = paper.citation_count or 0
    year = paper.year or 0
    if is_influential and citations >= 1:
        return True
    return year >= _CURRENT_YEAR - 4 and citations >= 1


# ── Main snowball ─────────────────────────────────────────────────────────────

async def run_snowball(seed_ids: list[str], depth: int = 1) -> list[Paper]:
    """Expand seed papers via backward (references) + forward (citations) snowballing.

    Gap-specific version: returns list[Paper] only.
    Citation edges are NOT returned (gap doesn't need them — that's research_agent KG concern).
    This avoids the tuple-unpack bug introduced when research_agent added edge return values.

    Applies SPEC_1.0.1 filters: time-decayed backward + isInfluential bypass.
    Seeds are expanded sequentially with a small delay as belt-and-suspenders alongside
    the global S2 rate limiter (TIP-410).
    """
    seen: set[str] = set(seed_ids)
    new_papers: list[Paper] = []
    current_seed_ids = list(seed_ids)

    for _ in range(depth):
        raw_results: list[tuple[list[dict], list[dict]]] = []
        for pid in current_seed_ids:
            try:
                result = await _expand_one(pid)
            except Exception as exc:
                logger.warning("snowball expand error for %s: %s", pid, exc)
                result = ([], [])
            raw_results.append(result)
            await asyncio.sleep(0.15)  # belt-and-suspenders alongside TIP-410 rate limiter

        next_ids: list[str] = []

        for seed_pid, (backward, forward) in zip(current_seed_ids, raw_results):
            for entry in backward:
                paper = entry["paper"]
                if not paper.paper_id:
                    continue
                is_inf = entry.get("isInfluential", False)
                intents = entry.get("intents", [])
                if paper.paper_id in seen:
                    continue
                if not _backward_keep(paper, is_inf):
                    continue
                paper.is_influential = is_inf
                paper.intents = intents
                seen.add(paper.paper_id)
                new_papers.append(paper)
                next_ids.append(paper.paper_id)

            for entry in forward:
                paper = entry["paper"]
                if not paper.paper_id:
                    continue
                is_inf = entry.get("isInfluential", False)
                intents = entry.get("intents", [])
                if paper.paper_id in seen:
                    continue
                if not _forward_keep(paper, is_inf):
                    continue
                paper.is_influential = is_inf
                paper.intents = intents
                seen.add(paper.paper_id)
                new_papers.append(paper)
                next_ids.append(paper.paper_id)

        current_seed_ids = next_ids[:10]
        if not current_seed_ids:
            break

    logger.info("gap snowball: %d new papers from %d seeds", len(new_papers), len(seed_ids))
    return new_papers


async def _expand_one(paper_id: str) -> tuple[list[dict], list[dict]]:
    refs, cites = await asyncio.gather(
        get_references(paper_id, limit=100),
        get_citations(paper_id, limit=100),
    )
    return refs, cites
