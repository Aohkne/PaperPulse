"""Step ②bis — Dual-pool citation snowballing.

Wraps the existing snowball service: select ~7-9 seeds from two pools
(Pool A: top raw citations; Pool B: top citations/year), then expand
one hop of backward references + forward citations with quality filters.
"""

from __future__ import annotations

import logging

from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.services.snowball import run_snowball, select_seeds

log = logging.getLogger(__name__)


async def snowball_node(state: ResearchState) -> dict:
    papers = list(state.get("papers", []))
    await narrate_step(f"following citation trails from the top seed papers to expand the {len(papers)}-paper corpus")
    paper_map = {p.paper_id: p for p in papers}
    edges: list[dict] = []

    try:
        seed_ids = select_seeds(papers, pool_size=5)
        new_papers, edges = await run_snowball(seed_ids, depth=1)
        for p in new_papers:
            if p.paper_id not in paper_map:
                paper_map[p.paper_id] = p
    except Exception as exc:
        log.warning("Snowball failed: %s — proceeding with pre-snowball corpus", exc)

    return {"papers": list(paper_map.values()), "citation_edges": edges}
