"""Step P3 — Critic Agents ∥ Reference Verification ∥ Link Liveness Check (PLAN §7 Phase 5).

All 3 sub-steps run concurrently via `asyncio.gather` — they're independent of
each other (P3a reads sections, P3b reads raw_citations, P3c reads sections).
"""

from __future__ import annotations

import asyncio

from backend.module.pdf_agent.graph.state import PDFAgentState
from backend.module.pdf_agent.services import citation_lookup, critic_agent, link_checker


async def batch_analysis_node(state: PDFAgentState) -> dict:
    critic_task = critic_agent.critique_sections_batch(state["sections"])
    citation_task = citation_lookup.verify_citations_batch(state["raw_citations"])
    link_task = link_checker.check_links_batch(state["sections"])

    critic_pairs, citation_verdicts, link_results = await asyncio.gather(
        critic_task, citation_task, link_task
    )

    critic_results = [
        {"section_title": section["title"], "issues": issues} for section, issues in critic_pairs
    ]
    return {
        "critic_results": critic_results,
        "citation_verdicts": citation_verdicts,
        "link_results": link_results,
    }
