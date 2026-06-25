"""Step ⑤⑥ — Service: hybrid search for a theme → content agent."""

from __future__ import annotations

from backend.module.research_agent.services import content_agent
from backend.shared.models.paper import Paper
from backend.shared.models.review import Theme, ThemeContentResponse
from backend.module.research_agent.services.hybrid_search import hybrid_search
from backend.module.research_agent.services.vector_store import get_all_papers_metadata, get_papers_by_ids


async def generate_theme_content(theme: Theme, top_k: int = 10, papers: list[Paper] | None = None) -> ThemeContentResponse:
    """
    1. Build corpus: from in-memory `papers` list (fast path) or ChromaDB (fallback).
    2. Run hybrid search (semantic + BM25 + RRF) for the theme description.
    3. Fetch top-k Paper objects and pass to the content LLM agent.
    """
    if papers is not None:
        corpus = [
            {"paperId": p.paper_id, "title": p.title or "", "abstract": p.abstract or ""}
            for p in papers
        ]
        paper_map = {p.paper_id: p for p in papers}
    else:
        all_meta = await get_all_papers_metadata()
        corpus = [
            {"paperId": m["paperId"], "title": m.get("title", ""), "abstract": m.get("abstract", "")}
            for m in all_meta
        ]
        paper_map = {}

    paper_ids = await hybrid_search(theme.description, corpus, top_k=top_k, papers=papers)

    if paper_map:
        fetched = [paper_map[pid] for pid in paper_ids if pid in paper_map]
    else:
        fetched = await get_papers_by_ids(paper_ids)

    papers_data = [{"paper_id": p.paper_id, "title": p.title or "", "abstract": p.abstract} for p in fetched]

    content = await content_agent.run(theme.title, theme.description, papers_data)
    return ThemeContentResponse(theme=theme.title, content=content, paper_ids=paper_ids)
