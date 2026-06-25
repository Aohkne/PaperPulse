"""Gap-detection module settings — reads from env directly.

Keeps gap config self-contained so the module is rebaseable without
touching backend/config.py (that file is baseline-owned).
"""

from __future__ import annotations

import os

_DEFAULT_NIM_RETRY_MAX = 3            # max retry attempts for NIM API HTTP 429
_DEFAULT_NIM_BACKOFF_BASE = 2.0       # exponential backoff base seconds (attempt N → base^N s)
_DEFAULT_NIM_UPSERT_CONCURRENCY = 3  # max concurrent NIM abstract upserts (TIP-410)

_DEFAULT_MAX_PAPERS = 20          # cap-final (G11.1 — Chu thau duyet 2026-06-20):
                                   # E2E@20 ~4.8min validated from G10.4 data:
                                   # pipeline@N=10=175s, extractor dom. ~100s, fixed~75s;
                                   # budget 300s-13s(retrieval)-75s(fixed)=212s extractor
                                   # @20 papers=4 batches@conc5: 4/2*100=200s < 212s ok.
                                   # Phase 2: raise EXTRACTOR_CONCURRENCY 5->8-10 to lift to 30.
_DEFAULT_CONCURRENCY = 3          # S2 + LLM concurrent requests per extractor batch (TIP-410: 5→3)
_DEFAULT_MIN_COLD_START = 5       # minimum papers required to trigger cold-start gap run
_DEFAULT_CO_OCCURRENCE_THRESHOLD = 2  # gap if < 2 papers cover (method, domain) pair
_DEFAULT_HYDE_ABSTRACT_WORDS = 80     # target word count for HyDE abstract generation
_DEFAULT_SPECTER2_WEIGHT = 0.4        # semantic arm weight in hybrid rank (0.4 sem + 0.6 BM25)
_DEFAULT_BACKGROUND_POOL_SIZE = 100   # default pool size for background corpus (reduced from 200)
_DEFAULT_BACKGROUND_BATCH_SIZE = 25   # default SPECTER2 batch size (smaller to reduce S2 rate-limit pressure)
_DEFAULT_SPECTER_RETRY_MAX = 3        # max retries on 429 from SPECTER2 API
_DEFAULT_SPECTER_BACKOFF_BASE = 2.0   # exponential backoff base (seconds)
_DEFAULT_FALSE_GAP_THRESHOLD = 0.15  # cosine distance < 0.15 → probable existing research
_DEFAULT_TOP_K_GAPS = 7              # default number of top gaps returned after quality ranking
_DEFAULT_INTENT_OFF_PENALTY = 0.7   # quality_score multiplier for gaps whose topic diverges from user_intent
_DEFAULT_FIELDS_OF_STUDY = "Computer Science"
_DEFAULT_ARXIV_ENABLED = True
_DEFAULT_ARXIV_SEARCH_LIMIT = 20     # arXiv papers per query (supplement to S2)


def get_default_fields_of_study() -> list[str] | None:
    """Return fieldsOfStudy filter list for S2 search. Configurable via DEFAULT_FIELDS_OF_STUDY env var.

    Comma-separated list (e.g. "Computer Science,Mathematics").
    Set to "None" or "" to disable filtering.
    """
    val = os.getenv("DEFAULT_FIELDS_OF_STUDY", _DEFAULT_FIELDS_OF_STUDY).strip()
    if val.lower() in ("none", ""):
        return None
    return [v.strip() for v in val.split(",")]


def get_max_papers_for_gap() -> int:
    """Return the paper-cap for gap detection. Configurable via MAX_PAPERS_FOR_GAP env var."""
    val = os.environ.get("MAX_PAPERS_FOR_GAP")
    if val is None:
        return _DEFAULT_MAX_PAPERS
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_MAX_PAPERS


def get_extractor_concurrency() -> int:
    """Return max concurrent paper-extraction tasks. Configurable via EXTRACTOR_CONCURRENCY env var.

    Bounded by S2 rate-limit tolerance (default 5). Lower to 2-3 if hitting 429s.
    """
    val = os.environ.get("EXTRACTOR_CONCURRENCY")
    if val is None:
        return _DEFAULT_CONCURRENCY
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_CONCURRENCY


def get_min_papers_cold_start() -> int:
    """Return minimum papers needed to run gap detection via cold-start. Configurable via MIN_PAPERS_COLD_START env var."""
    val = os.environ.get("MIN_PAPERS_COLD_START")
    if val is None:
        return _DEFAULT_MIN_COLD_START
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_MIN_COLD_START


def get_co_occurrence_threshold() -> int:
    """Return the minimum paper-count for a (method, domain) pair to be considered 'covered'.

    Pairs with count < threshold are flagged as candidate methodological gaps.
    Configurable via CO_OCCURRENCE_THRESHOLD env var (default 2).
    """
    val = os.environ.get("CO_OCCURRENCE_THRESHOLD")
    if val is None:
        return _DEFAULT_CO_OCCURRENCE_THRESHOLD
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_CO_OCCURRENCE_THRESHOLD


def get_hyde_abstract_words() -> int:
    """Return target word count for HyDE abstract generation. Configurable via HYDE_ABSTRACT_WORDS env var."""
    val = os.environ.get("HYDE_ABSTRACT_WORDS")
    if val is None:
        return _DEFAULT_HYDE_ABSTRACT_WORDS
    try:
        return max(10, int(val))
    except ValueError:
        return _DEFAULT_HYDE_ABSTRACT_WORDS


def get_specter2_weight() -> float:
    """Return semantic arm weight in hybrid rank (0.0–1.0). Configurable via SPECTER2_WEIGHT env var.

    SPECTER2_WEIGHT controls how much of the final score comes from the semantic
    (HyDE + SPECTER2) arm.  The BM25 composite arm receives weight (1 - SPECTER2_WEIGHT).
    Default 0.4: 40% semantic, 60% BM25/citation/recency.
    """
    val = os.environ.get("SPECTER2_WEIGHT")
    if val is None:
        return _DEFAULT_SPECTER2_WEIGHT
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_SPECTER2_WEIGHT


def get_background_pool_size() -> int:
    """Return max number of papers to fetch for the background corpus. Configurable via BACKGROUND_POOL_SIZE env var."""
    val = os.environ.get("BACKGROUND_POOL_SIZE")
    if val is None:
        return _DEFAULT_BACKGROUND_POOL_SIZE
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_BACKGROUND_POOL_SIZE


def get_background_batch_size() -> int:
    """Return SPECTER2 batch size. Configurable via BACKGROUND_BATCH_SIZE env var."""
    val = os.environ.get("BACKGROUND_BATCH_SIZE")
    if val is None:
        return _DEFAULT_BACKGROUND_BATCH_SIZE
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_BACKGROUND_BATCH_SIZE


def get_specter_retry_max() -> int:
    """Return max retry attempts for SPECTER2 API 429. Configurable via SPECTER_RETRY_MAX env var."""
    val = os.environ.get("SPECTER_RETRY_MAX")
    if val is None:
        return _DEFAULT_SPECTER_RETRY_MAX
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_SPECTER_RETRY_MAX


def get_specter_backoff_base() -> float:
    """Return exponential backoff base seconds for SPECTER2 429 retries. Configurable via SPECTER_BACKOFF_BASE env var."""
    val = os.environ.get("SPECTER_BACKOFF_BASE")
    if val is None:
        return _DEFAULT_SPECTER_BACKOFF_BASE
    try:
        return max(0.1, float(val))
    except ValueError:
        return _DEFAULT_SPECTER_BACKOFF_BASE


def get_top_k_gaps() -> int:
    """Return number of top gaps to return after quality ranking. Configurable via TOP_K_GAPS env var."""
    val = os.environ.get("TOP_K_GAPS")
    if val is None:
        return _DEFAULT_TOP_K_GAPS
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_TOP_K_GAPS


def get_intent_off_penalty() -> float:
    """Return quality_score multiplier for off-intent gaps. Configurable via INTENT_OFF_PENALTY env var."""
    val = os.environ.get("INTENT_OFF_PENALTY")
    if val is None:
        return _DEFAULT_INTENT_OFF_PENALTY
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_INTENT_OFF_PENALTY


def get_false_gap_threshold() -> float:
    """Return false gap threshold. Configurable via FALSE_GAP_THRESHOLD env var."""
    val = os.environ.get("FALSE_GAP_THRESHOLD")
    if val is None:
        return _DEFAULT_FALSE_GAP_THRESHOLD
    try:
        return float(val)
    except ValueError:
        return _DEFAULT_FALSE_GAP_THRESHOLD


def get_nim_retry_max() -> int:
    """Return max retry attempts for NIM API 429. Configurable via NIM_RETRY_MAX env var."""
    val = os.environ.get("NIM_RETRY_MAX")
    if val is None:
        return _DEFAULT_NIM_RETRY_MAX
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_NIM_RETRY_MAX


def get_nim_backoff_base() -> float:
    """Return exponential backoff base seconds for NIM 429 retries. Configurable via NIM_BACKOFF_BASE env var."""
    val = os.environ.get("NIM_BACKOFF_BASE")
    if val is None:
        return _DEFAULT_NIM_BACKOFF_BASE
    try:
        return max(0.1, float(val))
    except ValueError:
        return _DEFAULT_NIM_BACKOFF_BASE


def is_query_analyzer_enabled() -> bool:
    """Return True when the Stage A LLM query analyzer is active. Configurable via QUERY_ANALYZER_ENABLED env var."""
    return os.getenv("QUERY_ANALYZER_ENABLED", "true").lower() not in ("false", "0", "no")


def is_arxiv_enabled() -> bool:
    """Return True when arXiv supplement retrieval is active. Configurable via ARXIV_ENABLED env var."""
    return os.getenv("ARXIV_ENABLED", "true").lower() not in ("false", "0", "no")


def get_arxiv_search_limit() -> int:
    """Return max arXiv papers fetched per query. Configurable via ARXIV_SEARCH_LIMIT env var."""
    val = os.environ.get("ARXIV_SEARCH_LIMIT")
    if val is None:
        return _DEFAULT_ARXIV_SEARCH_LIMIT
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_ARXIV_SEARCH_LIMIT


def get_nim_upsert_concurrency() -> int:
    """Return max concurrent NIM abstract upsert tasks. Configurable via NIM_UPSERT_CONCURRENCY env var."""
    val = os.environ.get("NIM_UPSERT_CONCURRENCY")
    if val is None:
        return _DEFAULT_NIM_UPSERT_CONCURRENCY
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_NIM_UPSERT_CONCURRENCY
