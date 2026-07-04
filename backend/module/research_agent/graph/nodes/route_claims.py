"""Step ⑥ — Claim routing + human-in-loop review interrupt.

Automatic routing (not shown to the user):
  - supported → included   (verified)
  - partial   → included   (partial verification is enough for the review)
  - unsupported → removed

Human review: claims that are `uncertain` OR `low_confidence` (abstract-only)
can't be auto-decided — they're surfaced via interrupt() with enough context
(text, theme, paper url) for the user to approve (→ included) or drop
(→ removed). Contrasting-intent claims are listed first.

Resume value contract:
  {"approved": [...claim_ids], "removed": [...claim_ids]}
Claim ids not present in either list stay in the review bucket (still surfaced
but neither promoted nor dropped) so nothing is silently lost.
"""

from __future__ import annotations

from langgraph.types import interrupt

from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState


async def route_claims_node(state: ResearchState) -> dict:
    verified = state.get("verified_claims", [])
    papers = state.get("papers", [])
    paper_map = {p.paper_id: p for p in papers}
    await narrate_step(f"routing {len(verified)} verified claims and surfacing uncertain ones for review")

    included = [c for c in verified if c.status in ("supported", "partial") and not c.low_confidence]
    removed = [c for c in verified if c.status == "unsupported"]
    review = [c for c in verified if c.status == "uncertain" or c.low_confidence]
    # Contrasting claims first — the most decision-relevant for the reviewer.
    review.sort(key=lambda c: c.intent != "Contrasting")

    def _theme_of(claim) -> str:
        for tc in state.get("theme_contents", []):
            if claim.paper_id in tc.get("paper_ids", []):
                return tc.get("theme", "")
        return ""

    payload_claims = [
        {
            "id": c.id,
            "text": c.text,
            "status": c.status,
            "intent": c.intent,
            "theme": _theme_of(c),
            "paper_id": c.paper_id,
            "paper_url": getattr(paper_map.get(c.paper_id), "url", None),
        }
        for c in review
    ]

    resume_value = interrupt({"type": "claim_review", "claims": payload_claims})

    approved_ids: set[str] = set()
    removed_ids: set[str] = set()
    if isinstance(resume_value, dict):
        approved_ids = {str(i) for i in (resume_value.get("approved") or [])}
        removed_ids = {str(i) for i in (resume_value.get("removed") or [])}

    still_review = []
    for c in review:
        if c.id in approved_ids:
            included.append(c)
        elif c.id in removed_ids:
            removed.append(c)
        else:
            still_review.append(c)

    return {
        "included_claims": included,
        "removed_claims": removed,
        "review_claims": still_review,
    }
