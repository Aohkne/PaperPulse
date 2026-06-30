"""②bis Citation snowballing — dual-pool seed selection + isInfluential filter (SPEC_1.0.1).

Also persists the citation relationships discovered while expanding (who
cites whom, with what intent) as `citation_edges` — needed by the Step ⑨bis
Knowledge Graph's Paper layer (knowledge-graph_SPEC_2.0.md). Previously this
module only kept the papers and discarded the edges from the S2
references/citations response.
"""

import asyncio
import logging
from datetime import datetime

from backend.shared.models.paper import Paper
from backend.shared.services.semantic_scholar import get_citations, get_references

_CURRENT_YEAR = datetime.now().year


# ── Seed selection: dual-pool (SPEC Fix 1) ────────────────────────────────────


def select_seeds(papers: list[Paper], pool_size: int = 5) -> list[str]:
    """Dual-pool seed selection per SPEC_1.0.1:
    Pool A: top-N by raw citationCount (foundational papers)
    Pool B: top-N by citationCount/(current_year - year) (recent impactful)
    Returns deduplicated paperId list (~7-9 seeds).
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


# ── Backward filter: time-decayed + isInfluential bypass (SPEC Fix 2) ─────────


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


# ── Main snowball ──────────────────────────────────────────────────────────────


async def run_snowball(seed_ids: list[str], depth: int = 1) -> tuple[list[Paper], list[dict]]:
    """Expand seed papers via backward (references) + forward (citations) snowballing.

    Applies SPEC_1.0.1 filters: time-decayed backward + isInfluential bypass.
    Runs seeds sequentially with a small delay to avoid S2 rate limits.

    Returns:
        (new_papers, citation_edges) — edges are {source, target, intent,
        isInfluential} with `source` CITING `target`. An edge is recorded
        whenever its paper passes the keep-filter OR is already a known
        paper (an original seed, or one kept earlier in this same call) —
        the edge itself is valid corpus-to-corpus information even when the
        paper on the other end isn't "new".
    """
    seen: set[str] = set(seed_ids)
    new_papers: list[Paper] = []
    edges: list[dict] = []
    current_seed_ids = list(seed_ids)

    for _ in range(depth):
        # Sequential with tiny delay — avoids hitting S2 rate limit (1 req/s no-key, 100/10s with key)
        raw_results = []
        for pid in current_seed_ids:
            try:
                result = await _expand_one(pid)
            except Exception as exc:
                logging.warning("Snowball expand error for %s: %s", pid, exc)
                result = ([], [])
            raw_results.append(result)
            await asyncio.sleep(0.15)  # ~6 seeds × 2 calls = 12 reqs in ~1.8s

        next_ids: list[str] = []

        for seed_pid, (backward, forward) in zip(current_seed_ids, raw_results):
            # Backward (/references): seed_pid CITES the older paper.
            for entry in backward:
                paper = entry["paper"]
                if not paper.paper_id:
                    continue
                is_inf = entry.get("isInfluential", False)
                intents = entry.get("intents", [])
                already_known = paper.paper_id in seen
                if not already_known and not _backward_keep(paper, is_inf):
                    continue
                if not already_known:
                    paper.is_influential = is_inf
                    paper.intents = intents
                    seen.add(paper.paper_id)
                    new_papers.append(paper)
                    next_ids.append(paper.paper_id)
                edges.append(
                    {
                        "source": seed_pid,
                        "target": paper.paper_id,
                        "intent": intents[0] if intents else "background",
                        "isInfluential": is_inf,
                    }
                )

            # Forward (/citations): the newer paper CITES seed_pid.
            for entry in forward:
                paper = entry["paper"]
                if not paper.paper_id:
                    continue
                is_inf = entry.get("isInfluential", False)
                intents = entry.get("intents", [])
                already_known = paper.paper_id in seen
                if not already_known and not _forward_keep(paper, is_inf):
                    continue
                if not already_known:
                    paper.is_influential = is_inf
                    paper.intents = intents
                    seen.add(paper.paper_id)
                    new_papers.append(paper)
                    next_ids.append(paper.paper_id)
                edges.append(
                    {
                        "source": paper.paper_id,
                        "target": seed_pid,
                        "intent": intents[0] if intents else "background",
                        "isInfluential": is_inf,
                    }
                )

        current_seed_ids = next_ids[:10]
        if not current_seed_ids:
            break

    logging.info("Snowball: %d new papers, %d citation edges from dual-pool seeds", len(new_papers), len(edges))
    return new_papers, edges


async def _expand_one(paper_id: str) -> tuple[list[dict], list[dict]]:
    refs, cites = await asyncio.gather(
        get_references(paper_id, limit=100),
        get_citations(paper_id, limit=100),
    )
    return refs, cites
