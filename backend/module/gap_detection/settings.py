"""Gap-detection module settings — reads from env directly.

Keeps gap config self-contained so the module is rebaseable without
touching backend/config.py (that file is baseline-owned).
"""

from __future__ import annotations

import os

_DEFAULT_NIM_UPSERT_CONCURRENCY = 3  # max concurrent NIM abstract upserts (TIP-410)

_DEFAULT_MAX_PAPERS = 20  # cap-final (G11.1 — Chu thau duyet 2026-06-20):
# E2E@20 ~4.8min validated from G10.4 data:
# pipeline@N=10=175s, extractor dom. ~100s, fixed~75s;
# budget 300s-13s(retrieval)-75s(fixed)=212s extractor
# @20 papers=4 batches@conc5: 4/2*100=200s < 212s ok.
# Phase 2: raise EXTRACTOR_CONCURRENCY 5->8-10 to lift to 30.
_DEFAULT_CONCURRENCY = 3  # S2 + LLM concurrent requests per extractor batch (TIP-410: 5→3)
_DEFAULT_MIN_COLD_START = 5  # minimum papers required to trigger cold-start gap run
_DEFAULT_CO_OCCURRENCE_THRESHOLD = 2  # gap if < 2 papers cover (method, domain) pair
_DEFAULT_HYDE_ABSTRACT_WORDS = 80  # target word count for HyDE abstract generation
_DEFAULT_SPECTER2_WEIGHT = 0.4  # semantic arm weight in hybrid rank (0.4 sem + 0.6 BM25)
_DEFAULT_BACKGROUND_POOL_SIZE = 100  # default pool size for background corpus (reduced from 200)
_DEFAULT_BACKGROUND_BATCH_SIZE = 25  # default SPECTER2 batch size (smaller to reduce S2 rate-limit pressure)
_DEFAULT_SPECTER_RETRY_MAX = 3  # max retries on 429 from SPECTER2 API
_DEFAULT_SPECTER_BACKOFF_BASE = 2.0  # exponential backoff base (seconds)
_DEFAULT_FALSE_GAP_THRESHOLD = 0.15  # cosine distance < 0.15 → probable existing research
_DEFAULT_TOP_K_GAPS = 7  # default number of top gaps returned after quality ranking
_DEFAULT_INTENT_OFF_PENALTY = 0.7  # quality_score multiplier for gaps whose topic diverges from user_intent
_DEFAULT_GAP_DEDUP_JACCARD = 0.6  # supporting-paper overlap threshold for gap dedup clusters
_DEFAULT_DENSITY_MIN_PAPERS = 3  # row/column paper-count threshold for trusted density cells
_DEFAULT_GAP_DIVERSITY_THRESHOLD = 0.85  # cosine similarity threshold for grouping near-duplicate gaps
_DEFAULT_GAP_DIVERSITY_ENABLED = True  # enable semantic cluster diversity selection in synthesizer top-k
_DEFAULT_GAP_DIVERSITY_POOL = 20  # max number of quality-ranked gaps sent to the LLM grouping step
_DEFAULT_GAP_DIVERSITY_LLM_TEMPERATURE = 0.2  # low-temperature grouping for stable research-direction clusters
_DEFAULT_SELF_CONSISTENCY_ENABLED = True  # enable post-selection re-judging of top-N gaps
_DEFAULT_SELF_CONSISTENCY_PENALTY = 0.3  # quality_score/confidence multiplier for unstable (low-vote) top-N gaps
_DEFAULT_SELF_CONSISTENCY_K = 3  # number of independent self-consistency samples for final top-N gaps
_DEFAULT_SELF_CONSISTENCY_MIN_VOTES = 2  # minimum yes votes required to avoid low-confidence downgrade
_DEFAULT_DETECTOR_SAMPLE_TEMPERATURE = 0.6  # moderate sampling temperature for detector/self-consistency re-judging
_DEFAULT_COUNTER_CRITIQUE_ENABLED = True  # enable lightweight critic review of the final top-3 gaps
_DEFAULT_COUNTER_CRITIQUE_MODERATE_PENALTY = 0.6  # downgrade factor for moderately-criticized top gaps
_DEFAULT_COUNTER_CRITIQUE_BACKFILL = False  # refill dropped critique gaps from later candidates (disabled by default)
_DEFAULT_FIELDS_OF_STUDY = "Computer Science"
_DEFAULT_UNPAYWALL_ENABLED = True
_DEFAULT_UNPAYWALL_EMAIL = "duybao04042004@gmail.com"
_DEFAULT_OPENALEX_ENABLED = True
_DEFAULT_OPENALEX_SEARCH_LIMIT = 20  # OpenAlex papers per query (replaces arXiv supplement)
_DEFAULT_OPENALEX_MAILTO = "duybao04042004@gmail.com"  # polite pool: 10 req/s


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


def get_gap_dedup_jaccard() -> float:
    """Return supporting-paper Jaccard threshold for gap dedup. Configurable via GAP_DEDUP_JACCARD env var."""
    val = os.environ.get("GAP_DEDUP_JACCARD")
    if val is None:
        return _DEFAULT_GAP_DEDUP_JACCARD
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_GAP_DEDUP_JACCARD


def get_density_min_papers() -> int:
    """Return the trusted-cell row/column threshold. Configurable via DENSITY_MIN_PAPERS env var."""
    val = os.environ.get("DENSITY_MIN_PAPERS")
    if val is None:
        return _DEFAULT_DENSITY_MIN_PAPERS
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_DENSITY_MIN_PAPERS


def get_gap_diversity_threshold() -> float:
    """Return cosine threshold for grouping semantically similar gaps. Configurable via GAP_DIVERSITY_THRESHOLD env var."""
    val = os.environ.get("GAP_DIVERSITY_THRESHOLD")
    if val is None:
        return _DEFAULT_GAP_DIVERSITY_THRESHOLD
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_GAP_DIVERSITY_THRESHOLD


def is_gap_diversity_enabled() -> bool:
    """Return True when semantic diversity selection is active in synthesizer top-k."""
    return os.getenv("GAP_DIVERSITY_ENABLED", "true").lower() not in ("false", "0", "no")


def get_gap_diversity_pool() -> int:
    """Return max candidate pool size for LLM diversity grouping. Configurable via GAP_DIVERSITY_POOL env var."""
    val = os.environ.get("GAP_DIVERSITY_POOL")
    if val is None:
        return _DEFAULT_GAP_DIVERSITY_POOL
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_GAP_DIVERSITY_POOL


def get_gap_diversity_llm_temperature() -> float:
    """Return temperature for LLM diversity grouping. Configurable via GAP_DIVERSITY_LLM_TEMPERATURE env var."""
    val = os.environ.get("GAP_DIVERSITY_LLM_TEMPERATURE")
    if val is None:
        return _DEFAULT_GAP_DIVERSITY_LLM_TEMPERATURE
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_GAP_DIVERSITY_LLM_TEMPERATURE


def is_self_consistency_enabled() -> bool:
    """Return True when post-selection self-consistency confirmation is active."""
    return os.getenv("SELF_CONSISTENCY_ENABLED", "true").lower() not in ("false", "0", "no")


def get_self_consistency_penalty() -> float:
    """Return quality_score/confidence multiplier applied to unstable (low-vote) top-N gaps. Configurable via SELF_CONSISTENCY_PENALTY env var."""
    val = os.environ.get("SELF_CONSISTENCY_PENALTY")
    if val is None:
        return _DEFAULT_SELF_CONSISTENCY_PENALTY
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_SELF_CONSISTENCY_PENALTY


def get_self_consistency_k() -> int:
    """Return number of self-consistency samples. Configurable via SELF_CONSISTENCY_K env var."""
    val = os.environ.get("SELF_CONSISTENCY_K")
    if val is None:
        return _DEFAULT_SELF_CONSISTENCY_K
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_SELF_CONSISTENCY_K


def get_self_consistency_min_votes() -> int:
    """Return minimum yes votes needed to avoid downgrade. Configurable via SELF_CONSISTENCY_MIN_VOTES env var."""
    val = os.environ.get("SELF_CONSISTENCY_MIN_VOTES")
    if val is None:
        return _DEFAULT_SELF_CONSISTENCY_MIN_VOTES
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_SELF_CONSISTENCY_MIN_VOTES


def get_detector_sample_temperature() -> float:
    """Return sampling temperature for detector/self-consistency re-judging. Configurable via DETECTOR_SAMPLE_TEMPERATURE env var."""
    val = os.environ.get("DETECTOR_SAMPLE_TEMPERATURE")
    if val is None:
        return _DEFAULT_DETECTOR_SAMPLE_TEMPERATURE
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_DETECTOR_SAMPLE_TEMPERATURE


def is_counter_critique_enabled() -> bool:
    """Return True when the top-3 counter-critique gate is active."""
    return os.getenv("COUNTER_CRITIQUE_ENABLED", "true").lower() not in ("false", "0", "no")


def get_counter_critique_moderate_penalty() -> float:
    """Return downgrade factor for moderate critique verdicts. Configurable via COUNTER_CRITIQUE_MODERATE_PENALTY env var."""
    val = os.environ.get("COUNTER_CRITIQUE_MODERATE_PENALTY")
    if val is None:
        return _DEFAULT_COUNTER_CRITIQUE_MODERATE_PENALTY
    try:
        return max(0.0, min(1.0, float(val)))
    except ValueError:
        return _DEFAULT_COUNTER_CRITIQUE_MODERATE_PENALTY


def is_counter_critique_backfill_enabled() -> bool:
    """Return True when dropped critique gaps should be backfilled from later candidates."""
    return os.getenv("COUNTER_CRITIQUE_BACKFILL", "false").lower() not in ("false", "0", "no")


def is_query_analyzer_enabled() -> bool:
    """Return True when the Stage A LLM query analyzer is active. Configurable via QUERY_ANALYZER_ENABLED env var."""
    return os.getenv("QUERY_ANALYZER_ENABLED", "true").lower() not in ("false", "0", "no")


def is_unpaywall_enabled() -> bool:
    """Return True when the extractor may query Unpaywall after the primary PDF path fails."""
    return os.getenv("UNPAYWALL_ENABLED", str(_DEFAULT_UNPAYWALL_ENABLED).lower()).lower() not in ("false", "0", "no")


def get_unpaywall_email() -> str:
    """Return the email used for Unpaywall API requests. Configurable via UNPAYWALL_EMAIL env var."""
    return os.getenv("UNPAYWALL_EMAIL", _DEFAULT_UNPAYWALL_EMAIL).strip()


def is_openalex_enabled() -> bool:
    """Return True when OpenAlex retrieval is active. Configurable via OPENALEX_ENABLED env var."""
    return os.getenv("OPENALEX_ENABLED", "true").lower() not in ("false", "0", "no")


def get_openalex_search_limit() -> int:
    """Return max OpenAlex papers fetched per query. Configurable via OPENALEX_SEARCH_LIMIT env var."""
    val = os.environ.get("OPENALEX_SEARCH_LIMIT")
    if val is None:
        return _DEFAULT_OPENALEX_SEARCH_LIMIT
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_OPENALEX_SEARCH_LIMIT


def get_openalex_mailto() -> str:
    """Return the email for OpenAlex polite pool requests. Configurable via OPENALEX_MAILTO env var."""
    return os.getenv("OPENALEX_MAILTO", _DEFAULT_OPENALEX_MAILTO).strip()


def get_nim_upsert_concurrency() -> int:
    """Return max concurrent NIM abstract upsert tasks. Configurable via NIM_UPSERT_CONCURRENCY env var."""
    val = os.environ.get("NIM_UPSERT_CONCURRENCY")
    if val is None:
        return _DEFAULT_NIM_UPSERT_CONCURRENCY
    try:
        return max(1, int(val))
    except ValueError:
        return _DEFAULT_NIM_UPSERT_CONCURRENCY
