"""Stage A — Query Analyzer.

Converts a raw topic string (Vietnamese or English) into a structured
``GapQuery`` object via a single LLM call.  Never raises: all exceptions
produce a minimal fallback ``GapQuery``.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.agent.gap_detection.nodes.extractor import _parse_llm_json
from backend.agent.gap_detection.retrieval import clean_query
from backend.agent.gap_detection.schemas import GapQuery
from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an academic research assistant. "
    "Convert a research-gap query into a structured JSON search specification. "
    "Respond with ONLY the JSON object — no extra text, no markdown fences."
)

_USER_TMPL = """\
INPUT QUERY: {query}

Return a JSON object with EXACTLY this schema:
{{
  "core_topic": "<core topic in English, 2-5 words, no meta-words like 'research gap', 'tìm', 'về', 'find', 'gap'>",
  "facets": ["<specific search term 1>", "<specific search term 2>", "<up to 5 terms>"],
  "year_range": [2019, 2026],
  "field_of_study": "Computer Science",
  "recency_bias": true,
  "seminal_bias": true,
  "user_intent": "<concise snake_case intent label, e.g. 'speed_optimization', 'privacy', 'accuracy', 'scalability', 'robustness', or null if unclear>"
}}

Rules:
- core_topic: English only, concise (2–5 words), strip ALL meta-words
- facets: 2–5 distinct search angles of core_topic (e.g. specific methods, datasets, subtasks)
- field_of_study: "Computer Science" for ML/AI/NLP; adjust only when clearly different
- If topic is unclear: default field_of_study to "Computer Science"
- user_intent: the user's primary research goal (what kind of improvement they care about most). Use snake_case. Set to null when intent is genuinely ambiguous.
"""


async def analyze_query(raw_query: str) -> GapQuery:
    """Convert raw topic string to a structured ``GapQuery`` in one LLM call.

    Fallback: any exception → ``GapQuery(core_topic=clean_query(raw), facets=[clean_query(raw)])``.
    """
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _USER_TMPL.format(query=raw_query)},
    ]

    try:
        raw = await chat_completion(messages, temperature=0.0)
        data: dict[str, Any] = _parse_llm_json(raw)

        # Coerce year_range list → tuple (LLM returns JSON array)
        yr = data.get("year_range")
        if isinstance(yr, list) and len(yr) >= 2:
            data["year_range"] = (int(yr[0]), int(yr[1]))
        else:
            data.pop("year_range", None)  # fall back to GapQuery default

        gap_query = GapQuery(**data)

        # Ensure at least 1 facet
        if not gap_query.facets:
            gap_query.facets = [gap_query.core_topic]

        logger.info(
            "query_analyzer: core_topic='%s' facets=%s field='%s'",
            gap_query.core_topic,
            gap_query.facets,
            gap_query.field_of_study,
        )
        return gap_query

    except Exception:
        logger.warning("query_analyzer: LLM call or parse failed — using clean_query fallback", exc_info=True)
        cleaned = clean_query(raw_query)
        return GapQuery(core_topic=cleaned, facets=[cleaned])
