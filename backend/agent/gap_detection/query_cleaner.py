"""query_cleaner.py — Normalise a user topic into a clean English search query.

Single public function: ``clean_query(topic: str) -> str``.

Responsibilities
----------------
* Translate Vietnamese input to English.
* Strip meta-words (VN: "tìm", "khoảng trống", "nghiên cứu về", etc.;
  EN: "research gap", "find papers on", "survey of", etc.).
* Return a concise keyword phrase (not a sentence) suitable for passing
  directly to Semantic Scholar ``/paper/search``.
* Graceful fallback: any LLM failure or empty result → return ``topic`` unchanged.
"""

from __future__ import annotations

import logging

from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a research query normaliser. "
    "Your only job is to convert a user's topic description into a concise "
    "English keyword search phrase for academic paper databases (like Semantic Scholar). "
    "Rules:\n"
    "1. Output ONLY the search phrase — no preamble, no explanation, no markdown.\n"
    "2. Translate to English if the input is in another language.\n"
    "3. Remove meta-words that are not part of the research topic itself, such as: "
    "\"tìm\", \"tìm kiếm\", \"research gap\", \"khoảng trống\", \"về\", "
    "\"nghiên cứu về\", \"find papers on\", \"survey of\", \"literature review on\", "
    "\"tổng quan về\", \"gap in\", \"explore\".\n"
    "4. Keep domain-specific terms intact (model names, acronyms, methods).\n"
    "5. Output a keyword phrase of 3–12 words, not a full sentence.\n"
    "6. Do NOT wrap the output in quotes or backticks."
)

_USER_TMPL = "Topic: {topic}\n\nSearch phrase:"

# Hard cap on returned query length (characters).
_MAX_LEN = 200


# ── Public API ────────────────────────────────────────────────────────────────


async def clean_query(topic: str) -> str:
    """Convert a raw user topic (VN or EN, may contain meta-words) to a clean
    English search phrase.

    Args:
        topic: Raw user input, e.g. "Tìm research gap về transformer efficiency
               cho long-context".

    Returns:
        A concise English keyword phrase (≤200 chars).
        Falls back to the original ``topic`` if the LLM call fails or returns
        an empty string — never raises.
    """
    if not topic or not topic.strip():
        return topic

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _USER_TMPL.format(topic=topic.strip())},
    ]

    try:
        raw: str = await chat_completion(messages)
        cleaned = _post_process(raw)
        if cleaned:
            logger.info("query_cleaner: '%s' → '%s'", topic[:60], cleaned[:60])
            return cleaned
        # LLM returned content that reduced to empty after cleanup → fallback
        logger.warning("query_cleaner: LLM returned empty after cleanup — using original topic")
        return topic

    except Exception:
        logger.warning("query_cleaner: LLM call failed — using original topic", exc_info=True)
        return topic


# ── Helpers ───────────────────────────────────────────────────────────────────


def _post_process(raw: str) -> str:
    """Strip formatting artefacts and enforce length cap.

    * Remove surrounding whitespace.
    * Strip leading/trailing quotation marks and backticks (LLM sometimes wraps output).
    * Collapse internal newlines to a single space (take only the first line).
    * Enforce ≤ _MAX_LEN characters.
    """
    if not raw:
        return ""

    # Take only the first non-empty line (guard against multi-line responses).
    for line in raw.splitlines():
        line = line.strip()
        if line:
            raw = line
            break
    else:
        return ""

    # Strip surrounding quotes / backticks.
    raw = raw.strip("\"'`")

    # Final whitespace normalisation.
    raw = " ".join(raw.split())

    # Length cap.
    if len(raw) > _MAX_LEN:
        raw = raw[:_MAX_LEN].rsplit(" ", 1)[0]  # cut at last word boundary

    return raw.strip()
