"""Step ④ — Service: MMR-select top-k papers from the corpus -> outline agent.

Priority:
  1. If `papers` arg provided (in-memory list from pipeline): MMR-select over
     their SPECTER embeddings — pre-filter `fetch_k` by cosine vs query, then
     greedy MMR for diversity (SPEC 2.0 lambda=0.5, fetch_k=150, k=20).
  2. Else try vector search via ChromaDB (no embeddings client-side -> plain top-k).
  3. Else fall back to all ChromaDB metadata.
"""

from __future__ import annotations

import logging

from backend.config import get_settings
from backend.module.research_agent.services import outline_agent
from backend.module.research_agent.services.embedding import embed_text
from backend.module.research_agent.services.mmr import mmr_select
from backend.module.research_agent.services.vector_store import get_all_papers_metadata, get_papers_by_ids, query_by_vector
from backend.shared.models.paper import Paper
from backend.shared.models.review import Theme


async def generate_outline(query: str, top_k: int = 20, papers: list[Paper] | None = None) -> list[Theme]:
    settings = get_settings()
    papers_data: list[dict] = []

    if papers is not None:
        embedded = [p for p in papers if p.embedding]
        sampled: list[Paper]

        if embedded:
            query_vec = await embed_text(query)
            if query_vec:
                candidates = [(p.paper_id, p.embedding) for p in embedded]
                selected_ids = mmr_select(
                    query_vec,
                    candidates,
                    k=top_k,
                    lambda_mult=settings.mmr_lambda,
                    fetch_k=settings.mmr_prefetch_outline,
                )
                by_id = {p.paper_id: p for p in embedded}
                sampled = [by_id[pid] for pid in selected_ids if pid in by_id]
            else:
                logging.warning("generate_outline: query embedding failed — falling back to first %d papers", top_k)
                sampled = embedded[:top_k]
        else:
            logging.warning("generate_outline: no papers have embeddings — falling back to first %d papers", top_k)
            sampled = papers[:top_k]

        papers_data = [{"paper_id": p.paper_id, "title": p.title or "", "abstract": p.abstract} for p in sampled]
    else:
        query_vec = await embed_text(query)
        if query_vec:
            results = await query_by_vector(query_vec, top_k=top_k)
            paper_ids = [r["metadata"]["paperId"] for r in results]
            fetched = await get_papers_by_ids(paper_ids)
            papers_data = [{"paper_id": p.paper_id, "title": p.title or "", "abstract": p.abstract} for p in fetched]
        else:
            logging.warning("generate_outline: embedding unavailable — using keyword sample from ChromaDB")
            all_meta = await get_all_papers_metadata()
            papers_data = [
                {"paper_id": m["paperId"], "title": m.get("title", ""), "abstract": m.get("abstract")}
                for m in all_meta[:top_k]
            ]

    if not papers_data:
        logging.warning("generate_outline: no papers available — generating outline from query only")

    return await outline_agent.run(query, papers_data)
