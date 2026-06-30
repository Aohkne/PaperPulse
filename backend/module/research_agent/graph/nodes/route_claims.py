"""Step ⑨ — Claim routing + human-in-loop interrupt.

Routes verified claims into three buckets:
  - included: supported + high-confidence → go into final review
  - review:   partial / uncertain / low-confidence → human review queue
  - removed:  unsupported → excluded from final output

Interrupts after routing so the user can inspect the routing summary
before the final export step runs. Resume value is ignored (routing is
automatic); the interrupt is purely informational in this MVP.
"""

from __future__ import annotations

from langgraph.types import interrupt

from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState


async def route_claims_node(state: ResearchState) -> dict:
    verified = state.get("verified_claims", [])
    await narrate_step(f"routing {len(verified)} verified claims into included, needs-review, and removed buckets")

    included = [c for c in verified if c.status == "supported" and not c.low_confidence]
    removed = [c for c in verified if c.status == "unsupported"]
    review = [c for c in verified if c.status in ("partial", "uncertain") or c.low_confidence]

    routing_summary = {
        "included": len(included),
        "removed": len(removed),
        "review": len(review),
        "review_sample": [{"text": c.text[:120], "status": c.status, "paper_id": c.paper_id} for c in review[:5]],
    }

    # Pause: let user inspect routing before export
    interrupt(routing_summary)

    return {
        "included_claims": included,
        "removed_claims": removed,
        "review_claims": review,
    }
