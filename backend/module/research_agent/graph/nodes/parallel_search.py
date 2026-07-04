"""Step ① — Multi-agent parallel search: N sub-queries x M sources (SPEC 2.0).

Each sub-query from Step 0 is sent concurrently to every LLM-selected source
(semantic_scholar always included; openalex conditional/default; pubmed only for
biomedical domains — see intent_router.py). asyncio.gather runs all calls in
parallel; individual failures are caught and logged as empty lists so the
pipeline continues with partial results.

arXiv is no longer a search source: its real rate limit is ~1 req/3s (6
sub-queries ≈ 18s), and both S2 (SPECTER v2) and OpenAlex (ArXiv ID in
externalIds) already index arXiv content — so dropping it loses no coverage.

No max_search_calls cap: the calls are I/O-bound (asyncio.gather), so 18
concurrent calls are no slower than 15 — capping only dropped the last
sub-query's sources. Per-source proportional ceiling (quota = max_papers_total
// len(sources)) keeps each source's API relevance order instead of a global
citationCount sort (which wiped PubMed papers that have citationCount=None).
"""

from __future__ import annotations

import asyncio
import logging

from backend.config import get_settings
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.services.openalex import search_openalex
from backend.module.research_agent.services.pubmed_search import search_pubmed
from backend.shared.models.paper import Paper
from backend.shared.services.semantic_scholar import search_papers as s2_search

log = logging.getLogger(__name__)

_SEARCH_FNS = {
    "semantic_scholar": s2_search,
    "openalex": search_openalex,
    "pubmed": search_pubmed,
}


async def parallel_search_node(state: ResearchState) -> dict:
    settings = get_settings()
    base_query = state.get("refined_query") or state.get("query", "")
    sub_queries = (state.get("sub_queries") or [base_query])[: settings.max_sub_queries] or [base_query]
    sources = [s for s in (state.get("sources") or ["semantic_scholar", "openalex"]) if s in _SEARCH_FNS]
    if not sources:
        sources = ["semantic_scholar", "openalex"]
    per_source_limit = max(1, min(settings.max_papers_per_source, 100))

    await narrate_step(f"searching {len(sub_queries)} sub-queries across {', '.join(sources)} for {base_query}")

    # Full (sub_query, source) fan-out — no cap. I/O-bound gather, so every
    # sub-query reaches every source.
    calls: list[tuple[str, str]] = [(sq, src) for sq in sub_queries for src in sources]

    tasks = [_SEARCH_FNS[src](sq, limit=per_source_limit) for sq, src in calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    by_source: dict[str, list[Paper]] = {src: [] for src in sources}
    stats: dict[str, int] = {src: 0 for src in sources}
    for (sq, src), result in zip(calls, results):
        if isinstance(result, Exception):
            log.warning("Search source '%s' (query=%r) failed: %s", src, sq, result)
            continue
        stats[src] = stats.get(src, 0) + len(result)
        by_source[src].extend(result)

    # Per-source proportional ceiling — keep each source's API relevance order
    # (no global citationCount sort). Prevents one source dominating the corpus.
    per_source_quota = max(1, settings.max_papers_total // max(1, len(sources)))
    raw_papers: list[Paper] = []
    for src in sources:
        raw_papers.extend(by_source[src][:per_source_quota])

    return {"raw_papers": raw_papers, "search_stats": stats}
