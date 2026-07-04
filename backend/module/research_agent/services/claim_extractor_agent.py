"""Step ⑤ — LLM agent: extract factual claims with source paper IDs.

Strategy:
  1. Regex fast-path: parse "[[PAPER_ID]]" citations inline  → O(n), no LLM call
  2. LLM fallback   : used when content has no inline citations

Input : raw content string from content agent
Output: list[Claim]
"""

from __future__ import annotations

import json
import re

from backend.shared.models.claim import Claim
from backend.shared.services.llm_client import chat_completion

# Matches the hard [[PAPER_ID]] citation token emitted by content_agent. The
# char class includes '_' to cover OpenAlex synthetic ids (OA_...).
_INLINE_RE = re.compile(r"\[\[([A-Za-z0-9_]+)\]\]")

_SYSTEM = "You are a claim extractor. Extract every factual claim from the text and its source paper ID."

_USER_TMPL = """Extract all factual claims from the text below. Each claim must have a paperId.

Text:
{content}

Return a JSON array:
[{{"text": "<claim sentence>", "paperId": "<PAPER_ID>"}}]

Respond ONLY with the JSON array, no extra text."""


def _regex_fast_path(content: str) -> list[Claim]:
    """Parse [[ID]] inline citations without an LLM call."""
    claims: list[Claim] = []
    for sentence in re.split(r"(?<=[.!?])\s+", content):
        m = _INLINE_RE.search(sentence)
        if m:
            text = _INLINE_RE.sub("", sentence).strip()
            if text:
                claims.append(Claim(text=text, paperId=m.group(1)))
    return claims


async def run(content: str) -> list[Claim]:
    """Try regex first; fall back to LLM if no inline citations are found."""
    claims = _regex_fast_path(content)
    if claims:
        return claims

    response = await chat_completion(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER_TMPL.format(content=content)},
        ]
    )
    raw = json.loads(response)
    return [Claim(text=r["text"], paperId=r["paperId"]) for r in raw]
