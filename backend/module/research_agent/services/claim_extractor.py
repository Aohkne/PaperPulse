"""Step ⑦ — Service: thin orchestration wrapper around the claim extractor agent."""

from __future__ import annotations

from backend.module.research_agent.services import claim_extractor_agent as claim_agent
from backend.shared.models.claim import Claim


async def extract_claims(content: str, theme: str | None = None) -> list[Claim]:
    """Delegates to the claim_extractor agent (regex fast-path → LLM fallback)."""
    return await claim_agent.run(content)
