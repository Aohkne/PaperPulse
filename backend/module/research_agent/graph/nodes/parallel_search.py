"""Step ① — Multi-agent parallel search: N sub-queries x M sources (SPEC 2.0).

Each sub-query from Step 0 is sent concurrently to every LLM-selected source
(semantic_scholar always included; openalex/arxiv/pubmed conditional on topic
domain — see intent_router.py). asyncio.gather runs all calls in parallel;
individual failures are caught and logged as empty lists so the pipeline
continues with partial results.

Guardrails (SPEC 2.0 §System Guardrails): max_search_calls caps the total
number of (sub_query x source) calls; max_papers_total caps the raw corpus
size (kept by citationCount) before it's passed on to dedup.
"""

from __future__ import annotations

import asyncio
import logging

from backend.config import get_settings
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.services.arxiv_search import search_arxiv
from backend.module.research_agent.services.openalex import search_openalex
from backend.module.research_agent.services.pubmed_search import search_pubmed
from backend.shared.models.paper import Paper
from backend.shared.services.semantic_scholar import search_papers as s2_search

log = logging.getLogger(__name__)

_SEARCH_FNS = {
    "semantic_scholar": s2_search,
    "openalex": search_openalex,
    "arxiv": search_arxiv,
    "pubmed": search_pubmed,
}


async def parallel_search_node(state: ResearchState) -> dict:
    settings = get_settings()
    base_query = state.get("refined_query") or state.get("query", "")
    sub_queries = (state.get("sub_queries") or [base_query])[: settings.max_sub_queries] or [base_query]
    sources = state.get("sources") or ["semantic_scholar", "arxiv"]
    per_source_limit = max(1, min(settings.max_papers_per_source, 100))

    await narrate_step(f"searching {len(sub_queries)} sub-queries across {', '.join(sources)} for {base_query}")

    # Build the (sub_query, source) call plan, capped at max_search_calls.
    # Iterate source-major so every source gets at least one call before any
    # source gets a second, even if max_search_calls < len(sub_queries) * len(sources).
    calls: list[tuple[str, str]] = []
    for sq in sub_queries:
        for src in sources:
            if src in _SEARCH_FNS:
                calls.append((sq, src))
    calls = calls[: settings.max_search_calls]

    tasks = [_SEARCH_FNS[src](sq, limit=per_source_limit) for sq, src in calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    raw_papers: list[Paper] = []
    stats: dict[str, int] = {src: 0 for src in sources}
    for (sq, src), result in zip(calls, results):
        if isinstance(result, Exception):
            log.warning("Search source '%s' (query=%r) failed: %s", src, sq, result)
            continue
        stats[src] = stats.get(src, 0) + len(result)
        raw_papers.extend(result)

    # Hard ceiling — keep the highest-cited papers if over budget
    if len(raw_papers) > settings.max_papers_total:
        raw_papers = sorted(raw_papers, key=lambda p: p.citation_count or 0, reverse=True)
        raw_papers = raw_papers[: settings.max_papers_total]

    return {"raw_papers": raw_papers, "search_stats": stats}
