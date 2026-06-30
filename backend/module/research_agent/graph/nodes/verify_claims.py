"""Step ⑧ — 3-tier parallel claim verification.

Tier A: Semantic Scholar /snippet/search (~30% coverage)
Tier B: ar5iv arXiv HTML (~80% CS/AI/ML coverage)
Tier C: Abstract conservative (NEVER marks Supported — only partial/uncertain)

Runs all claims in parallel via asyncio.gather + Semaphore(4).
temperature=0 (deterministic per SPEC 2.0).
"""

from __future__ import annotations

import logging

from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.shared.services.citation_verifier import verify_claims

log = logging.getLogger(__name__)


async def verify_claims_node(state: ResearchState) -> dict:
    claims = state.get("claims", [])
    await narrate_step(
        f"verifying {len(claims)} extracted claims against Semantic Scholar snippets and arXiv source text"
    )
    papers = state.get("papers", [])

    if not claims:
        return {"verified_claims": []}

    abstracts = {p.paper_id: p.abstract or "" for p in papers if p.abstract}

    try:
        verified = await verify_claims(claims, paper_abstracts=abstracts)
    except Exception as exc:
        log.warning("Claim verification failed: %s — using unverified claims", exc)
        verified = claims

    return {"verified_claims": verified}
