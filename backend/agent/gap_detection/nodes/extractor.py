"""ExtractorNode — Phase 1 of the gap-detection pipeline.

Fetches paper metadata via Semantic Scholar.  When an open-access PDF
is available the node downloads it, extracts text with PyMuPDF, and
isolates the Methods / Limitations / Discussion sections for richer
LLM extraction.  Otherwise falls back to abstract + tldr.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.agent.gap_detection.gap_specter_store import upsert_papers
from backend.agent.gap_detection.hyde import upsert_paper_to_nim_store
from backend.agent.gap_detection.nodes.pdf_utils import (
    extract_relevant_sections,
    fetch_pdf_text,
)
from backend.agent.gap_detection.s2_client import get_paper_detail
from backend.agent.gap_detection.schemas import (
    ExtractedPaperData,
    GapDetectionState,
    PaperRef,
)
from backend.agent.gap_detection.settings import get_extractor_concurrency
from backend.shared.services.llm_client import chat_completion
from backend.shared.services.semantic_scholar import get_embeddings_batch

logger = logging.getLogger(__name__)
_ARXIV_SOURCE = "arxiv"

# ── Default concurrency (kept for backward compat; runtime value from settings) ──

DEFAULT_CONCURRENCY = 3  # legacy constant; actual default now via get_extractor_concurrency()

# ── LLM prompt ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a research paper analysis assistant. "
    "Extract structured information from the provided paper text. "
    "Pay special attention to limitation statements — sentences that "
    "indicate gaps, unknowns, or areas for future work."
)

_USER_PROMPT_TMPL = """\
Analyze the following paper text and extract structured information.

Paper Title: {title}

Paper Text:
{text}

Return a JSON object with EXACTLY these keys:
{{
  "topics": ["<main research topics>"],
  "keywords": ["<important keywords>"],
  "methodology": "<methodology used, or null>",
  "dataset": "<dataset used, or null>",
  "population": "<study population, or null>",
  "metrics": ["<evaluation metrics used>"],
  "key_claims": ["<main findings / claims>"],
  "limitation_statements": ["<explicit limitation sentences>"]
}}

For limitation_statements, look for sentences containing phrases like:
- "remains unknown", "future work", "limitation", "we did not",
  "further research needed", "not investigated", "beyond the scope",
  "could not", "remains to be", "has not been explored"

If a field has no data, use an empty list [] or null as appropriate.
Respond with ONLY the JSON object, no extra text."""


# ── LLM extraction helper ───────────────────────────────────────────


async def extract_from_text(
    paper_ref: PaperRef,
    text: str,
    source: str = "abstract",
    *,
    pdf_url: str | None = None,
    raw_abstract: str | None = None,
) -> ExtractedPaperData | None:
    """Run LLM structured extraction on *text* and return an
    ``ExtractedPaperData`` instance, or ``None`` on failure.

    Retries once on malformed LLM output before giving up.

    Args:
        raw_abstract: Raw abstract text from Semantic Scholar, persisted
            independently of LLM extraction so ``verifier.py`` Case C can
            verify against a source that is not circularly derived from
            the extracted ``limitation_statements``.
    """
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_PROMPT_TMPL.format(title=paper_ref.title, text=text)},
    ]

    for attempt in range(2):  # try + 1 retry
        try:
            raw = await chat_completion(messages)
            parsed = _parse_llm_json(raw)
            return ExtractedPaperData(
                paper_ref=paper_ref,
                topics=_ensure_list(parsed.get("topics")),
                keywords=_ensure_list(parsed.get("keywords")),
                methodology=_coerce_text(parsed.get("methodology")),
                dataset=_coerce_text(parsed.get("dataset")),
                population=_coerce_text(parsed.get("population")),
                metrics=_ensure_list(parsed.get("metrics")),
                key_claims=_ensure_list(parsed.get("key_claims")),
                limitation_statements=_ensure_list(parsed.get("limitation_statements")),
                pdf_url=pdf_url,
                extraction_source=source,
                abstract=raw_abstract or None,
            )
        except Exception:
            if attempt == 0:
                logger.warning(
                    "LLM extraction attempt %d failed for %s, retrying…",
                    attempt + 1,
                    paper_ref.paper_id,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "LLM extraction failed after retry for %s — returning fallback",
                    paper_ref.paper_id,
                    exc_info=True,
                )
                # Return a minimal valid result rather than None
                return ExtractedPaperData(
                    paper_ref=paper_ref,
                    pdf_url=pdf_url,
                    extraction_source=source,
                    abstract=raw_abstract or None,
                )
    return None  # unreachable, but keeps mypy happy


# ── Single-paper pipeline ────────────────────────────────────────────


async def _process_one_paper(
    paper_ref: PaperRef,
    semaphore: asyncio.Semaphore,
) -> ExtractedPaperData | None:
    """Fetch detail → try PDF full-text → fallback abstract → LLM extract."""
    async with semaphore:
        is_arxiv_only = _is_arxiv_only(paper_ref)
        detail: dict[str, Any] | None = None
        raw_abstract: str | None = paper_ref.abstract or None
        pdf_url: str | None = None

        # 1. Fetch metadata from Semantic Scholar unless this is an arXiv-only paper.
        if not is_arxiv_only:
            detail = await get_paper_detail(paper_ref.paper_id)
            if detail is None:
                logger.warning("Fetch failed for paper %s — skipping", paper_ref.paper_id)
                return None

            # 1b. Capture raw abstract NOW, before any processing, so it can be
            #     persisted independently of what the LLM extracts (TIP-G06-R).
            raw_abstract = detail.get("abstract") or raw_abstract

            # 2. Resolve pdf_url
            open_access = detail.get("openAccessPdf")
            if isinstance(open_access, dict):
                pdf_url = open_access.get("url")
        elif not raw_abstract:
            logger.warning(
                "ArXiv-only paper %s has no abstract — skipping safely",
                paper_ref.paper_id,
            )
            return None

        # 3. Try PDF full-text first
        text: str = ""
        source: str = "abstract"

        if pdf_url:
            pdf_text = await fetch_pdf_text(pdf_url)
            if pdf_text:
                text = extract_relevant_sections(pdf_text)
                source = "fulltext"
                logger.info(
                    "PDF full-text extracted for %s (%d chars)",
                    paper_ref.paper_id,
                    len(text),
                )

        # 4. Fallback to abstract + tldr
        if not text:
            abstract = raw_abstract or ""
            tldr_text = ""
            tldr = detail.get("tldr") if detail else None
            if isinstance(tldr, dict):
                tldr_text = tldr.get("text", "")

            parts = [p for p in (abstract, tldr_text) if p]
            text = "\n".join(parts).strip()
            source = "abstract"

        if not text:
            logger.warning(
                "Paper %s has no PDF, abstract, or tldr — skipping",
                paper_ref.paper_id,
            )
            return None

        # 5. Run LLM extraction (pass raw_abstract through for Case C)
        extracted = await extract_from_text(
            paper_ref,
            text,
            source=source,
            pdf_url=pdf_url,
            raw_abstract=raw_abstract,
        )

        if extracted:
            try:
                vectors = await get_embeddings_batch([paper_ref.paper_id])
                vec = vectors.get(paper_ref.paper_id)
                if vec:
                    await upsert_papers([{
                        "paper_id": paper_ref.paper_id,
                        "title": paper_ref.title,
                        "year": paper_ref.year,
                        "vector": vec,
                    }])
            except Exception:
                pass   # fire-and-forget, do not block extraction

            try:
                await upsert_paper_to_nim_store(
                    paper_ref.paper_id,
                    extracted.abstract or "",
                    paper_ref.title or "",
                    paper_ref.year or 0,
                )
            except Exception:
                pass  # fire-and-forget

        return extracted


# ── Node entry point ────────────────────────────────────────────────


async def extractor_node(
    state: GapDetectionState,
    *,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """LangGraph node: extract structured data from each session paper.

    Reads ``state["session_papers"]``, fetches metadata via S2 API,
    runs **concurrent** LLM extraction (bounded by Semaphore), and returns
    ``{"extracted_data": list[ExtractedPaperData]}``.

    Args:
        concurrency: Maximum concurrent extraction tasks.  Defaults to
            ``get_extractor_concurrency()`` (env ``EXTRACTOR_CONCURRENCY``,
            default 5).  Pass an explicit value only in tests.
    """
    papers: list[PaperRef] = state.get("session_papers", [])
    if not papers:
        logger.info("extractor_node: no session_papers — returning empty list")
        return {"extracted_data": []}

    effective_concurrency = concurrency if concurrency is not None else get_extractor_concurrency()
    semaphore = asyncio.Semaphore(effective_concurrency)
    tasks = [_process_one_paper(p, semaphore) for p in papers]
    # asyncio.gather preserves input order → extracted[i] corresponds to papers[i]
    # return_exceptions=False: individual paper failures are caught inside _process_one_paper
    # and return None (isolated), so gather never sees raw exceptions from paper tasks.
    results = await asyncio.gather(*tasks)

    # Filter out None (failed papers)
    extracted: list[ExtractedPaperData] = [r for r in results if r is not None]

    logger.info(
        "extractor_node: extracted %d / %d papers",
        len(extracted),
        len(papers),
    )
    return {"extracted_data": extracted}


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_llm_json(raw: str) -> dict:
    """Parse LLM response, stripping markdown fences if present."""
    text = raw.strip()
    # Strip ```json ... ``` wrapping
    if text.startswith("```"):
        first_nl = text.index("\n")
        text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


def _ensure_list(value: Any) -> list[str]:
    """Coerce a value to a list of strings."""
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _coerce_text(value: Any) -> str | None:
    """Coerce scalar-or-list LLM fields into a single string."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if v is not None and str(v).strip()]
        if not parts:
            return None
        return ", ".join(parts)
    text = str(value).strip()
    return text or None


def _is_arxiv_only(paper_ref: PaperRef) -> bool:
    """Detect arXiv-only papers so we can avoid the S2 detail fetch."""
    source = (paper_ref.source or "").lower()
    paper_id = (paper_ref.paper_id or "").lower()
    return source == _ARXIV_SOURCE or paper_id.startswith("arxiv:")
