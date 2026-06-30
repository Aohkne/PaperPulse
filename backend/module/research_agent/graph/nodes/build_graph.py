"""Step ⑨bis — Knowledge Graph construction (knowledge-graph_SPEC_2.0.md).

Runs after Step ⑨ (route_claims) so the claim layer only includes claims
already verified + routed (never claims that were filtered out as
unsupported). No LLM call — pure reassembly via networkx, so this step is
not parallelised with export (negligible cost, see SPEC "Chi phí Step ⑨bis").
"""

from __future__ import annotations

import logging

from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.services.graph_builder import build_knowledge_graph

log = logging.getLogger(__name__)


async def build_graph_node(state: ResearchState) -> dict:
    papers = state.get("papers", [])
    included = state.get("included_claims", [])
    review = state.get("review_claims", [])
    query = state.get("refined_query") or state.get("query", "")
    await narrate_step(
        f"assembling the knowledge graph from {len(papers)} papers, "
        f"{len(state.get('theme_contents', []))} themes, and {len(included) + len(review)} claims"
    )

    try:
        knowledge_graph = build_knowledge_graph(
            query=query,
            papers=papers,
            citation_edges=state.get("citation_edges", []),
            theme_contents=state.get("theme_contents", []),
            included_claims=included,
            review_claims=review,
        )
    except Exception as exc:
        log.warning("Knowledge graph build failed: %s — proceeding without it", exc)
        knowledge_graph = {"nodes": [], "edges": [], "stats": {}}

    return {"knowledge_graph": knowledge_graph}
