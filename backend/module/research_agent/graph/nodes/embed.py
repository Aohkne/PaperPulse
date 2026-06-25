"""Step ③ — SPECTER v2 batch embed + ChromaDB upsert.

Fetches SPECTER v2 vectors via S2 batch API (max 500 ids/call).
Papers with no API vector fall back to local SPECTER2 via embed_text().
All papers with vectors are upserted into ChromaDB for later hybrid search.
"""

from __future__ import annotations

import logging

from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.services.embedding import embed_text
from backend.shared.services.semantic_scholar import get_embeddings_batch
from backend.module.research_agent.services.vector_store import upsert_papers

log = logging.getLogger(__name__)


async def embed_node(state: ResearchState) -> dict:
    papers = list(state.get("papers", []))
    await narrate_step(f"building SPECTER v2 semantic embeddings for {len(papers)} papers for ranking and search")
    if not papers:
        return {"embed_stats": {"api_hit": 0, "fallback_hit": 0, "stored": 0}}

    api_hit = fallback_hit = stored = 0

    try:
        # Only papers that actually came from Semantic Scholar (direct search
        # or snowball) have a real S2 paperId. OpenAlex/arXiv/PubMed papers use
        # synthetic ids ("OA_...", "arxiv_...", "pubmed_...") that S2's batch
        # endpoint rejects with 400 — and since /paper/batch validates the
        # whole chunk at once, a handful of bad ids would fail embedding
        # lookup for every paper in that chunk. Those papers go straight to
        # the local SPECTER2 fallback below instead.
        s2_ids = [p.paper_id for p in papers if p.source == "semantic_scholar"]
        specter_map = await get_embeddings_batch(s2_ids) if s2_ids else {}
        for paper in papers:
            vec = specter_map.get(paper.paper_id)
            if vec:
                paper.embedding = vec
                api_hit += 1
            elif paper.abstract:
                fb = await embed_text(paper.abstract)
                if fb:
                    paper.embedding = fb
                    fallback_hit += 1

        stored = await upsert_papers(papers)
    except Exception as exc:
        log.warning("Embed step failed: %s — ChromaDB may be empty for this session", exc)

    return {
        "papers": papers,
        "embed_stats": {"api_hit": api_hit, "fallback_hit": fallback_hit, "stored": stored},
    }
