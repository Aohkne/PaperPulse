"""Step ⑥ — LLM agent: synthesize themed content with inline citations.

Input : theme title + description + top-k papers
Output: str  (300-500 word synthesis with (Source: PAPER_ID) citations)
"""

from __future__ import annotations

from backend.shared.services.llm_client import chat_completion

_SYSTEM = (
    "You are an academic writer. "
    "Write a literature review section with inline citations in the format (Source: PAPER_ID). "
    "Base your writing ONLY on the provided abstracts — do not invent facts. "
    "Output plain prose paragraphs only — no Markdown (#, *, **, -, etc.), no LaTeX commands, "
    "no headings, and no document title. The caller wraps your text in its own section heading."
)

_USER_TMPL = """Theme: {theme_title}
Description: {theme_desc}

Relevant papers (paperId — title — abstract):
{papers_text}

Write a 300-500 word synthesis of this theme as plain prose paragraphs (no headings, no Markdown or LaTeX markup).
After every factual claim, add a citation like (Source: PAPER_ID)."""


async def run(theme_title: str, theme_desc: str, papers: list[dict]) -> str:
    """
    Args:
        theme_title : display name of the theme
        theme_desc  : 1-2 sentence description (used as context for the LLM)
        papers      : [{"paper_id": str, "title": str, "abstract": str | None}]
    Returns:
        generated content string with inline (Source: PAPER_ID) citations
    """
    papers_text = "\n\n".join(f"{p['paper_id']} — {p['title']}\n{p.get('abstract') or '(no abstract)'}" for p in papers)

    return await chat_completion(
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _USER_TMPL.format(
                    theme_title=theme_title,
                    theme_desc=theme_desc,
                    papers_text=papers_text,
                ),
            },
        ]
    )
