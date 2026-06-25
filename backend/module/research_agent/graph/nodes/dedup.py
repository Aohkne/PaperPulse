"""Step ①bis — Cross-source deduplication.

Delegates to dedup_utils.dedup_papers() which uses
DOI → ArXiv ID → paperId → title fuzzy (rapidfuzz ≥90) priority.
"""

from __future__ import annotations

from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.services.dedup_utils import dedup_papers


async def dedup_node(state: ResearchState) -> dict:
    raw_papers = state.get("raw_papers", [])
    await narrate_step(f"removing duplicate papers from {len(raw_papers)} raw results using DOI, ArXiv ID, and title matching")
    deduped = dedup_papers(raw_papers)
    return {"papers": deduped}
