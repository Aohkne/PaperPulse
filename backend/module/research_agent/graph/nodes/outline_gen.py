"""Step ④ — Outline generation + human-in-loop interrupt.

Generates 5-8 research themes via MMR selection → LLM, then pauses with
interrupt() to let the user approve or edit the outline before continuing.

On resume: the user may send back a list of (possibly modified) theme dicts.
If so, those replace the LLM-generated themes. A plain True/bool signals
acceptance with no changes.

temperature=0.7 (creative outline generation per SPEC 2.0).
"""

from __future__ import annotations

import logging

from langgraph.types import interrupt

from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.shared.models.review import Theme
from backend.module.research_agent.services.outline_generator import generate_outline

log = logging.getLogger(__name__)


async def outline_gen_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state.get("query", "")
    papers = state.get("papers", [])
    await narrate_step(f"analyzing {len(papers)} papers to identify the main research themes for {query}")

    try:
        themes = await generate_outline(query, top_k=20, papers=papers)
    except Exception as exc:
        log.error("Outline generation failed: %s", exc)
        themes = []

    themes_payload = [
        {"title": t.title, "description": t.description, "paper_ids": t.paper_ids}
        for t in themes
    ]

    # Pause: send outline to frontend for user approval/editing
    resume_value = interrupt({"themes": themes_payload})

    # After resume: accept user-modified themes if they sent back a list
    if isinstance(resume_value, list):
        try:
            themes = [Theme(**t) if isinstance(t, dict) else t for t in resume_value]
        except Exception as exc:
            log.warning("Could not parse user-modified themes (%s) — using LLM themes", exc)

    return {"themes": themes, "outline_approved": True}
