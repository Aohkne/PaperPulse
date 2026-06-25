"""PDF full-text utilities for the gap-detection pipeline.

Provides helpers for downloading open-access PDFs via httpx,
extracting raw text via PyMuPDF (``fitz``), and isolating the
Methods / Limitations / Discussion sections that are most valuable
for research-gap detection.

This module is consumed by ``extractor.py`` (TIP-G02b extension).
"""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

#: Minimum character count to accept extracted text.
#: Anything shorter is likely a scanned-image PDF → skip.
MIN_TEXT_LENGTH = 500

#: Hard cap on text sent to the LLM to stay within context limits.
MAX_LLM_CHARS = 12_000

#: When sections can't be identified, take this many chars from the
#: beginning and end of the document respectively.
_HEAD_CHARS = 8_000
_TAIL_CHARS = 4_000

# ── Section heading patterns ────────────────────────────────────────

#: Regex alternatives for section headings we want to keep.
#: Matches numbered ("3. Methods") and unnumbered ("METHODS") forms.
_SECTION_RE = re.compile(
    r"^"
    r"(?:\d+[\.\)]\s*)?"            # optional leading number
    r"("
    r"method(?:ology|s)?"
    r"|materials?\s+and\s+methods?"
    r"|experimental\s+(?:setup|design|procedure)"
    r"|limitation(?:s)?"
    r"|discussion"
    r"|future\s+(?:work|directions?|research)"
    r"|conclusion(?:s)?"
    r")"
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)

#: Pattern that matches *any* section-level heading (used to find
#: where a matched section ends).
_ANY_HEADING_RE = re.compile(
    r"^(?:\d+[\.\)]\s*)?[A-Z][A-Za-z\s&,]{2,50}\s*$",
    re.MULTILINE,
)


# ── Public API ───────────────────────────────────────────────────────


async def fetch_pdf_text(pdf_url: str) -> str | None:
    """Download a PDF from *pdf_url* and return its full text.

    Returns ``None`` (never raises) when:
    * the download fails (network error, non-200, timeout),
    * the response is not a PDF (wrong content-type, parse error),
    * the extracted text is too short (< ``MIN_TEXT_LENGTH`` chars),
      which typically means a scanned-image PDF.
    """
    try:
        raw_bytes = await _download_pdf(pdf_url)
        if raw_bytes is None:
            return None
        text = _extract_text_from_bytes(raw_bytes)
        if text is None or len(text) < MIN_TEXT_LENGTH:
            logger.warning(
                "PDF text too short (%d chars) — likely scanned image: %s",
                len(text) if text else 0,
                pdf_url,
            )
            return None
        return text
    except Exception:
        logger.warning("fetch_pdf_text failed for %s", pdf_url, exc_info=True)
        return None


def extract_relevant_sections(full_text: str) -> str:
    """Return the subset of *full_text* most useful for gap detection.

    Tries to locate Methods and Limitations/Discussion/Conclusion
    sections via heading-pattern heuristics.  When no recognisable
    headings are found, falls back to head + tail trimming (because
    limitations usually appear near the end of a paper).

    The result is capped at ``MAX_LLM_CHARS`` characters.
    """
    sections = _find_sections(full_text)

    if sections:
        combined = "\n\n".join(sections)
    else:
        # Fallback: head + tail
        if len(full_text) <= MAX_LLM_CHARS:
            combined = full_text
        else:
            head = full_text[:_HEAD_CHARS]
            tail = full_text[-_TAIL_CHARS:]
            combined = head + "\n\n[...]\n\n" + tail

    # Hard cap for LLM context safety
    return combined[:MAX_LLM_CHARS]


# ── Internal helpers ─────────────────────────────────────────────────


async def _download_pdf(url: str) -> bytes | None:
    """Download PDF bytes with a 8-second timeout."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=8.0)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "pdf" not in content_type and not resp.content[:5] == b"%PDF-":
                logger.warning(
                    "Response is not a PDF (content-type=%s): %s",
                    content_type,
                    url,
                )
                return None
            return resp.content
    except Exception:
        logger.warning("PDF download failed: %s", url, exc_info=True)
        return None


def _extract_text_from_bytes(data: bytes) -> str | None:
    """Parse PDF bytes via PyMuPDF and return concatenated page text."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("pymupdf (fitz) is not installed — cannot parse PDF")
        return None

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)
    except Exception:
        logger.warning("PyMuPDF failed to parse PDF bytes", exc_info=True)
        return None


def _find_sections(text: str) -> list[str]:
    """Extract sections matching ``_SECTION_RE`` from *text*.

    Returns a list of section bodies (without the heading line itself).
    Each body runs from the matched heading until the next heading or
    end-of-text.
    """
    # Collect positions of all generic headings
    all_headings = [m.start() for m in _ANY_HEADING_RE.finditer(text)]
    if not all_headings:
        return []

    # Find our target headings
    matched: list[str] = []
    for m in _SECTION_RE.finditer(text):
        start = m.end()
        # Find the next heading after this one
        end = len(text)
        for h_pos in all_headings:
            if h_pos > start:
                end = h_pos
                break
        body = text[start:end].strip()
        if body:
            matched.append(body)

    return matched
