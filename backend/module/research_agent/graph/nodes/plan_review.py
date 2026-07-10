"""Step 0c — Research plan approval (human-in-loop interrupt, SPEC 2.0 §Step 0).

After intent_router classifies intent="search" and drafts a research plan
(sub_queries + sources), this node pauses so the user can review/edit the
plan before any search API calls are made — SPEC 2.0's "User alignment" goal:
"User confirm research scope trước khi search".

Resume value contract:
  - omitted / not a dict → accept the LLM-drafted plan unchanged
  - {"sub_queries": [...]} and/or {"sources": [...]} → override those fields
"""

from __future__ import annotations

import logging

from langgraph.types import interrupt

from backend.module.research_agent.graph.state import ResearchState

log = logging.getLogger(__name__)

_VALID_SOURCES = {"semantic_scholar", "openalex", "pubmed"}


async def plan_review_node(state: ResearchState) -> dict:
    sub_queries = state.get("sub_queries", [])
    sources = state.get("sources", ["semantic_scholar"])
    plan_description = state.get("plan_description", "")

    resume_value = interrupt(
        {
            "sub_queries": sub_queries,
            "sources": sources,
            "plan_description": plan_description,
        }
    )

    update: dict = {"plan_approved": True}

    if isinstance(resume_value, dict):
        if "sub_queries" in resume_value:
            edited_queries = resume_value.get("sub_queries")
            if isinstance(edited_queries, list):
                update["sub_queries"] = [str(q) for q in edited_queries if str(q).strip()]

        edited_sources = resume_value.get("sources")
        if isinstance(edited_sources, list):
            valid = [s for s in edited_sources if s in _VALID_SOURCES]
            if "semantic_scholar" not in valid:
                valid.insert(0, "semantic_scholar")
            if valid:
                update["sources"] = valid

    return update
