"""Waterfall citation verification — Step P3b (PLAN §7 Phase 4).

Reuses research_agent/shared search services in "lookup 1 paper" mode
(DOI/arXiv-id exact lookup, then keyword search) instead of the "discover
N papers" mode research_agent uses for corpus building. No new S2/OpenAlex/
arXiv client is created here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from rapidfuzz import fuzz

from backend.config import get_llm, get_settings
from backend.module.pdf_agent.graph.state import RawCitation
from backend.module.pdf_agent.services.llm_timeout import ainvoke_with_timeout
from backend.module.research_agent.services import arxiv_search, openalex
from backend.shared.models.paper import Paper
from backend.shared.services import semantic_scholar

logger = logging.getLogger(__name__)

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;)\]]+", re.IGNORECASE)
_ARXIV_RE = re.compile(r"(?:arxiv[:\s]*)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)

_JUDGE_PROMPT = """You are a conservative citation-match judge. Given a claimed citation and a \
candidate paper found via search, decide whether they refer to the SAME paper despite imperfect \
metadata (OCR noise, abbreviated author names, slightly different title wording).

Output ONLY JSON: {"same_paper": true|false, "reason": "<one short sentence>"}"""


def extract_doi(text: str) -> str | None:
    m = _DOI_RE.search(text or "")
    return m.group(0).rstrip(".") if m else None


def extract_arxiv_id(text: str) -> str | None:
    m = _ARXIV_RE.search(text or "")
    return m.group(1) if m else None


def _candidate_text(c: RawCitation) -> str:
    return c.get("guessed_title") or c.get("raw_text") or ""


def _score_match(citation: RawCitation, paper: Paper) -> float:
    """rapidfuzz title score, with year-mismatch / author-overlap as soft tie-breakers."""
    title_a = _candidate_text(citation)[:200]
    title_b = paper.title or ""
    if not title_a or not title_b:
        return 0.0
    score = fuzz.token_sort_ratio(title_a.lower(), title_b.lower()) / 100.0

    year_a = citation.get("guessed_year")
    if year_a and paper.year and abs(year_a - paper.year) > 1:
        score *= 0.7

    authors_a = {a.lower() for a in (citation.get("guessed_authors") or [])}
    authors_b_last = {n.split()[-1].lower() for n in (paper.authors or []) if n}
    if authors_a and authors_b_last and not (authors_a & authors_b_last):
        score *= 0.9

    return min(score, 1.0)


def _best_fuzzy_match(citation: RawCitation, candidates: list[Paper]) -> tuple[Paper | None, float]:
    if not candidates:
        return None, 0.0
    scored = [(p, _score_match(citation, p)) for p in candidates]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[0]


def _paper_to_evidence(paper: Paper) -> dict:
    return {
        "title": paper.title,
        "year": paper.year,
        "authors": (paper.authors or [])[:5],
        "url": paper.url,
        "source": paper.source,
    }


async def _llm_judge_citation_match(citation: RawCitation, paper: Paper) -> dict:
    """Gray-zone verdict (threshold_low <= score < threshold_high) — Step P3b."""
    settings = get_settings()
    llm = get_llm(temperature=settings.pdf_judge_temperature, streaming=False)
    user_content = (
        f"Claimed citation: {citation.get('raw_text', '')[:500]}\n"
        f"Candidate paper: title={paper.title!r}, year={paper.year}, authors={(paper.authors or [])[:5]!r}"
    )
    same = False
    try:
        response = await ainvoke_with_timeout(llm, [
            {"role": "system", "content": _JUDGE_PROMPT},
            {"role": "user", "content": user_content},
        ])
        content = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {}
        same = bool(parsed.get("same_paper"))
    except Exception:
        logger.warning("LLM judge failed for citation match — defaulting to Metadata Mismatch", exc_info=True)

    if same:
        return {"verdict": "Verified", "confidence": 0.7, "evidence": _paper_to_evidence(paper)}
    return {"verdict": "Metadata Mismatch", "confidence": 0.5, "evidence": _paper_to_evidence(paper)}


async def verify_citation(citation: RawCitation) -> dict:
    """Returns {"verdict": Verified|Metadata Mismatch|Not Found, "confidence": float, "evidence": dict|None}."""
    settings = get_settings()
    text = citation.get("raw_text") or ""
    doi_hint = citation.get("guessed_doi_or_url") or ""
    doi = extract_doi(doi_hint) or extract_doi(text)
    arxiv_id = extract_arxiv_id(doi_hint) or extract_arxiv_id(text)

    if doi:
        hit = await _safe_call(semantic_scholar.lookup_by_doi, doi)
        if hit:
            return _verdict_from_exact_hit(citation, hit)

    if arxiv_id:
        hit = await _safe_call(semantic_scholar.lookup_by_arxiv_id, arxiv_id)
        if not hit:
            hit = await _safe_call(arxiv_search.lookup_by_arxiv_id, arxiv_id)
        if hit:
            return _verdict_from_exact_hit(citation, hit)

    query = _candidate_text(citation)
    if not query:
        return {"verdict": "Not Found", "confidence": 0.0, "evidence": None}

    results = await asyncio.gather(
        _safe_call(semantic_scholar.search_papers, query, 5),
        _safe_call(openalex.search_openalex, query, 5),
        _safe_call(arxiv_search.search_arxiv, query, 5),
    )
    candidates: list[Paper] = [p for r in results if isinstance(r, list) for p in r]

    best, score = _best_fuzzy_match(citation, candidates)
    if best is None:
        return {"verdict": "Not Found", "confidence": 0.0, "evidence": None}
    if score >= settings.pdf_agent_match_threshold_high:
        return {"verdict": "Verified", "confidence": score, "evidence": _paper_to_evidence(best)}
    if score < settings.pdf_agent_match_threshold_low:
        return {"verdict": "Not Found", "confidence": score, "evidence": None}
    return await _llm_judge_citation_match(citation, best)


def _verdict_from_exact_hit(citation: RawCitation, hit: Paper) -> dict:
    """DOI/arXiv-id matched exactly — still sanity-check title if we have one (catches a
    wrong DOI typo'd into the right *format* but pointing at a different paper)."""
    if not _candidate_text(citation):
        return {"verdict": "Verified", "confidence": 0.95, "evidence": _paper_to_evidence(hit)}
    score = _score_match(citation, hit)
    verdict = "Verified" if score >= 0.5 else "Metadata Mismatch"
    return {"verdict": verdict, "confidence": max(score, 0.9), "evidence": _paper_to_evidence(hit)}


async def _safe_call(fn, *args):
    settings = get_settings()
    try:
        return await asyncio.wait_for(fn(*args), timeout=settings.pdf_agent_citation_lookup_timeout_s)
    except Exception:
        logger.warning("citation_lookup call failed: %s%r", fn.__name__, args, exc_info=True)
        return None


async def verify_citations_batch(citations: list[RawCitation]) -> list[dict]:
    """asyncio.gather all citations, capped by PDF_AGENT_MAX_CITATIONS_VERIFY guardrail."""
    settings = get_settings()
    capped = citations[: settings.pdf_agent_max_citations_verify]
    results = await asyncio.gather(*(verify_citation(c) for c in capped), return_exceptions=True)
    out: list[dict] = []
    for c, r in zip(capped, results):
        if isinstance(r, Exception):
            logger.warning("verify_citation crashed for %r: %s", c.get("key"), r)
            out.append({"verdict": "Not Found", "confidence": 0.0, "evidence": None})
        else:
            out.append(r)
    return out
