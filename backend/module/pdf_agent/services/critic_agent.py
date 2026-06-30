"""Critic Agent — Step P3a (PLAN §7 Phase 5).

1 LLM call/section, `temperature=CRITIC_TEMPERATURE` (default 0), conservative
prompt (PLAN §9 + SPEC Landscape B "LLM-REVal" warning: LLM reviewers tend to
over-criticize and self-bias — keep it deterministic, no overall scoring, only
specific issues with a verbatim quote so the anchor is guaranteed valid).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from backend.config import get_llm, get_settings
from backend.module.pdf_agent.graph.state import Section
from backend.module.pdf_agent.services.llm_timeout import ainvoke_with_timeout

logger = logging.getLogger(__name__)

_REFERENCES_TITLE_RE = re.compile(r"^(references?|bibliography)$", re.IGNORECASE)

_CRITIC_SYSTEM_PROMPT = """You are a careful, conservative academic writing critic. Review the given \
section of an academic paper for SPECIFIC, ACTIONABLE issues only. Do not invent issues, do not nitpick \
subjective style preferences, and do not summarize what the section says.

Classify each issue under exactly one aspect: "clarity", "terminology", "flow", or "redundancy".

For each issue you MUST quote an EXACT, VERBATIM substring copied character-for-character from the \
section text (including punctuation) — this anchors the comment in the editor. If you cannot quote an \
exact substring, do not report that issue.

Output ONLY a JSON array. Each item:
{"aspect": "clarity|terminology|flow|redundancy", "quote": "<exact verbatim substring>",
 "comment": "<specific, actionable feedback, 1-2 sentences>",
 "suggested_fix": "<replacement text for the quoted substring, or null if you have no concrete fix>"}

If there are no significant issues, output an empty array []. Do not pad the list with minor nitpicks."""


async def critique_section(section: Section) -> list[dict]:
    """Returns [{"aspect", "quote", "comment", "suggested_fix"}] — quote is guaranteed to be a
    verbatim substring of section['raw_latex'] (entries that fail this check are dropped, since
    build_annotations needs an exact match to anchor the comment).
    """
    settings = get_settings()
    llm = get_llm(temperature=settings.critic_temperature, streaming=False)
    try:
        response = await ainvoke_with_timeout(
            llm,
            [
                {"role": "system", "content": _CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": f"Section: {section['title']}\n\n{section['raw_latex']}"},
            ],
        )
        content = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\[.*\]", content, re.DOTALL)
        issues = json.loads(match.group(0)) if match else []
    except Exception:
        logger.warning("critique_section failed for section %r", section.get("title"), exc_info=True)
        return []

    valid: list[dict] = []
    for issue in issues if isinstance(issues, list) else []:
        quote = issue.get("quote") if isinstance(issue, dict) else None
        if quote and quote in section["raw_latex"]:
            valid.append(issue)
    return valid


async def critique_sections_batch(sections: list[Section]) -> list[tuple[Section, list[dict]]]:
    """asyncio.gather 1 critic call/section (capped by PDF_AGENT_MAX_SECTIONS_CRITIC).

    Reference/bibliography sections are skipped — there's no prose to critique.
    """
    settings = get_settings()
    candidates = [s for s in sections if not _REFERENCES_TITLE_RE.match(s["title"].strip())]
    capped = candidates[: settings.pdf_agent_max_sections_critic]

    results = await asyncio.gather(*(critique_section(s) for s in capped), return_exceptions=True)
    out: list[tuple[Section, list[dict]]] = []
    for s, r in zip(capped, results):
        if isinstance(r, Exception):
            logger.warning("critique_section crashed for %r: %s", s["title"], r)
            out.append((s, []))
        else:
            out.append((s, r))
    return out
