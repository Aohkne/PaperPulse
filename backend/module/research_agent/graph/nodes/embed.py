"""Step ② — SPECTER v2 batch embed → pgvector upsert.

Fetches SPECTER v2 vectors via the S2 batch API (max 500 ids/call) and upserts
them into Supabase pgvector (single vector store, dev == production).

No embed_text() fallback (reseach-agent.html Step ②): the only fallback model
available is NVIDIA NIM (4096-dim), which is incompatible with the fixed
vector(768) column and not comparable to SPECTER v2 in the same space. Papers
without an S2 vector (OpenAlex/PubMed-only synthetic ids) are simply not
upserted → they don't participate in clustering. Accepted: OA/PubMed papers that
overlap S2 (same DOI) already merged onto the S2 paperId during dedup (Step ①),
so only papers genuinely absent from S2 are excluded.
"""

from __future__ import annotations

import logging

from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.services.vector_store import upsert_papers
from backend.shared.services.semantic_scholar import get_embeddings_batch

log = logging.getLogger(__name__)


async def embed_node(state: ResearchState) -> dict:
    papers = list(state.get("papers", []))
    await narrate_step(f"building SPECTER v2 semantic embeddings for {len(papers)} papers for clustering")
    if not papers:
        return {"embed_stats": {"api_hit": 0, "stored": 0}}

    api_hit = stored = 0

    try:
        # Only papers with a real S2 paperId can be batch-embedded. OpenAlex/
        # PubMed papers use synthetic ids ("OA_...", "pubmed_...") that S2's
        # /paper/batch endpoint rejects — they get no vector and are excluded
        # from clustering (see module docstring).
        s2_ids = [p.paper_id for p in papers if p.source == "semantic_scholar"]
        specter_map = await get_embeddings_batch(s2_ids) if s2_ids else {}
        for paper in papers:
            vec = specter_map.get(paper.paper_id)
            if vec:
                paper.embedding = vec
                api_hit += 1

        stored = await upsert_papers(papers)
    except Exception as exc:
        log.warning("Embed step failed: %s — pgvector may be empty for this session", exc)

    return {
        "papers": papers,
        "embed_stats": {"api_hit": api_hit, "stored": stored},
    }
