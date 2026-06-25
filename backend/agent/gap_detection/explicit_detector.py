"""Detect EXPLICIT/LIMITATION/INFERRED origin from gap statement + paper text.

Pure function — no async, no LLM, no embedding calls.
Used by verifier_node to annotate INFERRED gaps before NLI routing.
"""

from __future__ import annotations

import re

from backend.agent.gap_detection.schemas import GapOrigin

# Patterns that signal a gap was explicitly stated by the author as future work
# or an open problem — these take precedence over limitation patterns.
_EXPLICIT_PATTERNS: list[str] = [
    r"future\s+work\s+(?:should|could|will|may|might|includes?|involves?|can)",
    r"(?:we|this\s+(?:paper|work|study))\s+(?:leave[s]?|defer[s]?|do\s+not\s+address|does\s+not\s+address)",
    r"(?:direction[s]?\s+for\s+)?future\s+research",
    r"remains?\s+an\s+open\s+(?:problem|question|challenge|issue)",
    r"(?:not\s+yet\s+|yet\s+to\s+be\s+)?(?:fully\s+)?explored",
    r"open\s+(?:research\s+)?(?:question|problem|challenge)",
    r"(?:warrant[s]?|require[s]?|deserve[s]?)\s+further\s+(?:investigation|study|research|exploration)",
    # Vietnamese
    r"(?:chúng\s+tôi|bài\s+báo\s+này|nghiên\s+cứu\s+này)\s+chưa\s+(?:giải\s+quyết|xem\s+xét)",
    r"hướng\s+nghiên\s+cứu\s+(?:tương\s+lai|tiếp\s+theo)",
]

# Patterns that signal an author-stated limitation (lower confidence than EXPLICIT).
_LIMITATION_PATTERNS: list[str] = [
    r"limitation[s]?\s+(?:of|include[s]?|are)",
    r"(?:our\s+)?(?:approach|method|model|study|work|paper)\s+is\s+limited\s+to",
    r"(?:a\s+)?(?:key\s+)?limitation",
    r"limited\s+to",
    r"constrained\s+to",
    r"only\s+(?:applies?|works?)\s+(?:to|for|when)",
    r"we\s+(?:acknowledge|note)\s+that",
    r"(?:hạn\s+chế|giới\s+hạn)\s+(?:của|là)",
]

# Compiled once at import time for speed.
_COMPILED_EXPLICIT = [re.compile(p, re.IGNORECASE) for p in _EXPLICIT_PATTERNS]
_COMPILED_LIMITATION = [re.compile(p, re.IGNORECASE) for p in _LIMITATION_PATTERNS]


def detect_origin(
    gap_statement: str,
    paper_text: str = "",
) -> tuple[GapOrigin, float]:
    """Determine the origin of a gap from its statement and optional paper text.

    Checks the combined text against EXPLICIT patterns first (future work /
    open questions), then LIMITATION patterns.  Returns INFERRED with
    confidence 0.0 when nothing matches — caller should derive confidence
    from NLI score instead.

    Args:
        gap_statement: The gap statement string to classify.
        paper_text: Optional surrounding paper text (abstract etc.) for
            additional signal.  Combined with gap_statement for pattern check.

    Returns:
        (GapOrigin, confidence) where:
        - EXPLICIT, 1.0  — author explicitly flagged as future work / open problem
        - LIMITATION, 0.9 — author explicitly stated a limitation
        - INFERRED, 0.0  — no pattern match; confidence set by NLI downstream
    """
    combined = f"{gap_statement} {paper_text}"

    # Check EXPLICIT patterns first (higher confidence, takes precedence).
    for pat in _COMPILED_EXPLICIT:
        if pat.search(combined):
            # If the *statement itself* (not paper_text) also matches a
            # limitation pattern, treat as LIMITATION — e.g. "our method is
            # limited; future work should address this" → statement-level limit
            # wins over the future-work signal in paper_text.
            for lpat in _COMPILED_LIMITATION:
                if lpat.search(gap_statement):
                    return GapOrigin.LIMITATION, 0.9
            return GapOrigin.EXPLICIT, 1.0

    # Check LIMITATION patterns.
    for pat in _COMPILED_LIMITATION:
        if pat.search(combined):
            return GapOrigin.LIMITATION, 0.9

    return GapOrigin.INFERRED, 0.0
