"""Steps ⑤⑥ — Per-theme hybrid search + content generation (parallel).

Runs all themes concurrently via asyncio.gather. Each theme goes through:
  ⑤ Hybrid search (semantic MMR + BM25 + RRF, top-10 per theme)
  ⑥ LLM writer → structured LaTeX section body

temperature=0.7 for the writer (applied inside content_generator via llm_client).
"""

from __future__ import annotations

import asyncio
import logging

from backend.module.research_agent.graph.state import ResearchState
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.services.content_generator import generate_theme_content

log = logging.getLogger(__name__)


async def write_themes_node(state: ResearchState) -> dict:
    themes = state.get("themes", [])
    papers = state.get("papers", [])
    theme_names = ", ".join(t.title for t in themes[:4]) + ("…" if len(themes) > 4 else "")
    await narrate_step(f"writing literature review sections for {len(themes)} themes: {theme_names}")

    async def _process(theme):
        try:
            result = await generate_theme_content(theme, top_k=10, papers=papers)
            return {
                "theme": result.theme,
                "content": result.content,
                "paper_ids": result.paper_ids,
            }
        except Exception as exc:
            log.warning("Theme '%s' write failed: %s", theme.title, exc)
            return None

    results = await asyncio.gather(*[_process(t) for t in themes])
    theme_contents = [r for r in results if r is not None]

    return {"theme_contents": theme_contents}
