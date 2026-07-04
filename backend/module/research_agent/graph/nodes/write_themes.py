"""Step ④ — Parallel writer agents (one per cluster/theme).

Each theme is written concurrently via asyncio.gather. The writer receives the
theme's clustered papers directly (Step ③) — no per-theme hybrid search.

Papers without an abstract are filtered out BEFORE the writer runs: the LLM has
no content to write from or cite, and a citation to a no-abstract paper can't be
verified in Step ⑤. Those papers still shaped the cluster centroid in Step ③;
they're only excluded from the writing step.

temperature=0.7 for the writer (applied inside content_agent via llm_client).
"""

from __future__ import annotations

import asyncio
import logging

from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.services import content_agent

log = logging.getLogger(__name__)


async def write_themes_node(state: ResearchState) -> dict:
    themes = state.get("themes", [])
    papers = state.get("papers", [])
    paper_map = {p.paper_id: p for p in papers}
    theme_names = ", ".join(t.title for t in themes[:4]) + ("…" if len(themes) > 4 else "")
    await narrate_step(f"writing literature review sections for {len(themes)} themes: {theme_names}")

    async def _process(theme):
        # Filter no-abstract papers before writing (see module docstring).
        cluster_papers = [paper_map[pid] for pid in theme.paper_ids if pid in paper_map]
        with_abstract = [p for p in cluster_papers if p.abstract]
        if not with_abstract:
            return None
        papers_payload = [
            {"paper_id": p.paper_id, "title": p.title, "abstract": p.abstract} for p in with_abstract
        ]
        try:
            content = await content_agent.run(theme.title, theme.description or "", papers_payload)
            return {
                "theme": theme.title,
                "content": content,
                "paper_ids": [p.paper_id for p in with_abstract],
            }
        except Exception as exc:
            log.warning("Theme '%s' write failed: %s", theme.title, exc)
            return None

    results = await asyncio.gather(*[_process(t) for t in themes])
    theme_contents = [r for r in results if r is not None]

    return {"theme_contents": theme_contents}
