"""Step ⑦ — Claim extraction from all theme sections.

Parses (Source: PAPER_ID) tags produced by the content writer and attaches
Citation Intent (Supporting/Contrasting/Mentioning) from S2 snowball metadata.

temperature=0 (deterministic extraction per SPEC 2.0).
"""

from __future__ import annotations

import logging

from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.services.claim_extractor import extract_claims

log = logging.getLogger(__name__)


async def extract_claims_node(state: ResearchState) -> dict:
    theme_contents = state.get("theme_contents", [])
    await narrate_step(f"extracting factual claims from {len(theme_contents)} written sections to verify against sources")
    papers = state.get("papers", [])
    paper_map = {p.paper_id: p for p in papers}

    all_claims = []
    for tc in theme_contents:
        content = tc.get("content", "")
        theme = tc.get("theme", "")
        try:
            claims = await extract_claims(content, theme=theme)
            for claim in claims:
                paper = paper_map.get(claim.paper_id)
                if paper:
                    # Attach intent from S2 snowball metadata
                    if paper.intents:
                        intent_raw = paper.intents[0]
                        if intent_raw in ("Supporting", "Contrasting", "Mentioning"):
                            claim.intent = intent_raw  # type: ignore[assignment]
                    # Attach ArXiv ID for Case B verification
                    arxiv_id = paper.external_ids.get("ArXiv")
                    if arxiv_id:
                        claim.__dict__["arxiv_id"] = arxiv_id  # type: ignore[attr-defined]
            all_claims.extend(claims)
        except Exception as exc:
            log.warning("Claim extraction failed for theme '%s': %s", theme, exc)

    return {"claims": all_claims}
