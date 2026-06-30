"""3-tier citation verification pipeline (SPEC_1.0.1).

Case A (~30% papers): Semantic Scholar /snippet/search -> direct full-text snippet
Case B (~80% CS/AI): arXiv full text via ar5iv HTML
Case C (fallback): Abstract conservative -> NEVER return Supported

Contrasting-intent claims are prioritised (returned first) for human review.
"""

import asyncio
import logging
import re
from typing import Literal

from backend.shared.models.claim import Claim
from backend.shared.services.arxiv_fetcher import fetch_arxiv_text
from backend.shared.services.llm_client import chat_completion
from backend.shared.services.semantic_scholar import search_snippet

# Limit concurrent LLM calls to avoid 429 from the NVIDIA/OpenAI API
_VERIFY_SEM = asyncio.Semaphore(4)
_VERIFY_SYSTEM = (
    "You are a fact-checker for academic citations. "
    "Given a source text and a claim, classify strictly as one of: "
    "Supported | Partially Supported | Unsupported | Uncertain."
)

_VERIFY_TMPL = """Given the following source text from paper {paper_id}:
---
{source_text}
---
Does this source text support the following claim?
Claim: {claim_text}

Classify as one of:
- Supported: source explicitly and directly confirms the claim
- Partially Supported: source is related but claim oversimplifies or omits conditions
- Unsupported: source contradicts or does not mention the claim
- Uncertain: source is ambiguous or insufficient to determine

{conservative_note}

Return ONLY one classification label."""

_ABSTRACT_CONSERVATIVE_NOTE = (
    "[ABSTRACT-ONLY MODE: You are reading an abstract, not the full paper. "
    "If not explicitly confirmed by the abstract -> classify as Uncertain, NEVER Supported.]"
)

_STATUS_MAP: dict[str, Literal["supported", "partial", "unsupported", "uncertain"]] = {
    "supported": "supported",
    "partially supported": "partial",
    "partially": "partial",
    "unsupported": "unsupported",
    "uncertain": "uncertain",
}


async def _llm_classify(
    source_text: str, claim_text: str, paper_id: str, conservative: bool = False
) -> tuple[str, str | None]:
    """Call LLM to classify the claim. Returns (status, quote_or_None)."""
    note = _ABSTRACT_CONSERVATIVE_NOTE if conservative else ""
    prompt = _VERIFY_TMPL.format(
        paper_id=paper_id,
        source_text=source_text[:4000],
        claim_text=claim_text,
        conservative_note=note,
    )
    verdict = await chat_completion(
        [
            {"role": "system", "content": _VERIFY_SYSTEM},
            {"role": "user", "content": prompt},
        ]
    )
    normalized = verdict.strip().lower()
    status = _STATUS_MAP.get(normalized, "uncertain")
    # Extract a short quote from the first 200 chars of source if supported
    quote = source_text[:200].strip() if status in ("supported", "partial") else None
    return status, quote


async def _verify_one(claim: Claim, paper_abstracts: dict[str, str]) -> Claim:
    """Run 3-tier verification for a single claim (rate-limited via semaphore)."""
    async with _VERIFY_SEM:
        # -- Case A: Semantic Scholar /snippet/search --------------------------
        # Strip markdown formatting before sending to S2 API to avoid 400 errors
        clean_query = re.sub(r"\*+|_+|#+|`+", "", claim.text).strip()[:200]
        try:
            snippet = await search_snippet(clean_query, paper_id=claim.paper_id)
        except Exception as exc:
            logging.debug("Case A snippet search failed for %s: %s", claim.paper_id, exc)
            snippet = None
        if snippet:
            status, quote = await _llm_classify(snippet, claim.text, claim.paper_id)
            claim.status = status
            claim.source = "snippet"
            claim.snippet = quote
            if status in ("partial", "uncertain"):
                claim.human_review = True
            logging.debug("Claim %s: Case A -> %s", claim.id[:8], status)
            return claim

        # -- Case B: arXiv full text via ar5iv ---------------------------------
        arxiv_id = None
        if hasattr(claim, "arxiv_id") and claim.arxiv_id:  # type: ignore[attr-defined]
            arxiv_id = claim.arxiv_id  # type: ignore[attr-defined]

        if arxiv_id:
            full_text = await fetch_arxiv_text(arxiv_id)
            if full_text:
                status, quote = await _llm_classify(full_text, claim.text, claim.paper_id)
                claim.status = status
                claim.source = "arxiv"
                claim.snippet = quote
                if status in ("partial", "uncertain"):
                    claim.human_review = True
                logging.debug("Claim %s: Case B -> %s", claim.id[:8], status)
                return claim

        # -- Case C: Abstract conservative (NEVER return Supported) ------------
        abstract = paper_abstracts.get(claim.paper_id)
        if abstract:
            status, quote = await _llm_classify(abstract, claim.text, claim.paper_id, conservative=True)
            if status == "supported":
                status = "uncertain"
            claim.status = status
            claim.source = "abstract"
            claim.low_confidence = True
            claim.human_review = True
            claim.snippet = quote
            logging.debug("Claim %s: Case C (abstract conservative) -> %s", claim.id[:8], status)
            return claim

    # No source at all
    claim.status = "uncertain"
    claim.source = None
    claim.low_confidence = True
    claim.human_review = True
    return claim


async def verify_claims(claims: list[Claim], paper_abstracts: dict[str, str] | None = None) -> list[Claim]:
    """Verify all claims concurrently using the 3-tier pipeline.

    Args:
        claims: Claims to verify.
        paper_abstracts: dict[paperId -> abstract] used as Case C fallback.
    """
    abstracts = paper_abstracts or {}

    # Prioritise Contrasting-intent claims (run first, appear first in result)
    contrasting = [c for c in claims if c.intent == "Contrasting"]
    others = [c for c in claims if c.intent != "Contrasting"]

    raw_contrasting = await asyncio.gather(*[_verify_one(c, abstracts) for c in contrasting], return_exceptions=True)
    raw_others = await asyncio.gather(*[_verify_one(c, abstracts) for c in others], return_exceptions=True)

    verified_contrasting = [r for r in raw_contrasting if isinstance(r, Claim)]
    verified_others = [r for r in raw_others if isinstance(r, Claim)]

    # Log any per-claim failures silently
    for r in raw_contrasting + raw_others:
        if isinstance(r, Exception):
            logging.warning("verify_claims: per-claim error: %s", r)

    return verified_contrasting + verified_others
