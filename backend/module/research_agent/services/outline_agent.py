"""Step ④ — LLM agent: generate thematic outline from paper abstracts.

Input : query string + list of papers (paper_id, title, abstract)
Output: list[Theme]
"""

from __future__ import annotations

import json
import re

from backend.shared.models.review import Theme
from backend.shared.services.llm_client import chat_completion

_SYSTEM = (
    "You are a research assistant. "
    "Given a list of academic paper abstracts, identify the main themes for a literature review."
)

_USER_TMPL = """Research topic: {query}

Papers (paperId — title — abstract):
{papers_text}

Return a JSON array of themes. Each theme must have:
- "title": short theme name (≤ 8 words)
- "description": 1-2 sentence description used for downstream semantic search
- "paper_ids": list of relevant paperId strings

Respond ONLY with the JSON array, no extra text."""


async def run(query: str, papers: list[dict]) -> list[Theme]:
    """
    Args:
        query    : research topic entered by the user
        papers   : [{"paper_id": str, "title": str, "abstract": str | None}]
    Returns:
        list of Theme objects
    """
    papers_text = "\n\n".join(f"[{p['paper_id']}] {p['title']}\n{p.get('abstract') or '(no abstract)'}" for p in papers)

    response = await chat_completion(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER_TMPL.format(query=query, papers_text=papers_text)},
        ]
    )

    # Strip markdown fences if LLM wraps JSON in ```json ... ```
    text = response.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()

    raw = json.loads(text)
    return [Theme(**t) for t in raw]
