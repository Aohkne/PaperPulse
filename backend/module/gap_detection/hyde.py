"""hyde.py — HyDE (Hypothetical Document Embeddings) for gap detection (TIP-P2-06/FIX).

Two public HyDE generators (architecture: Combined, TIP-P2-06-FIX):
──────────────────────────────────────────────────────────────────
``generate_hyde_vector_nim(clean_query)``   — PRIMARY (TIP-P2-06-FIX)
    LLM abstract → embed_text (NIM, 4096d) → query gap_nim_store.
    Used by ``retrieval.rank()`` for semantic reranking.

``generate_hyde_vector(clean_query)``       — ALIAS / backward-compat
    Identical to ``generate_hyde_vector_nim``.  Kept for callers that
    imported the original name.

Paper embedding helper:
──────────────────────
``upsert_paper_to_nim_store(paper_id, abstract, title, year)``
    embed_text(abstract) → upsert into gap_nim_store.
    Called from ``retrieval.rank()`` to populate the NIM store before querying.

Architectural note (TIP-P2-06 → FIX):
    The original TIP assumed get_embeddings_batch() could embed arbitrary text.
    In reality it only accepts real S2 paper IDs (768d SPECTER2).  We therefore
    use embed_text() from the configured NIM endpoint (EMBEDDING_BASE_URL).
    gap_specter_store (768d) is kept for future paper-paper cosine (P2-07/P2-08).
    gap_nim_store (4096d) is used for all text-based embedding queries.

Fallback hierarchy (all return None / no-op, never raise):
    1. LLM call fails → None
    2. LLM returns empty abstract → None
    3. embed_text not configured (EMBEDDING_BASE_URL unset) → None
    4. embed_text call fails → None
"""

from __future__ import annotations

import logging

from backend.module.gap_detection.gap_nim_store import upsert_papers_nim
from backend.module.gap_detection.services.embedding import embed_text
from backend.module.gap_detection.settings import get_hyde_abstract_words
from backend.shared.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

_HYDE_SYSTEM = "You are a scientific abstract writer. Write concise, information-dense research paper abstracts."

# ── Prompt builder ────────────────────────────────────────────────────────────


def _build_hyde_prompt(clean_query: str) -> str:
    words = get_hyde_abstract_words()
    return (
        f"Write a {words}-word abstract of a research paper that investigates: "
        f"{clean_query}\n"
        "Output ONLY the abstract text — no title, no preamble, no labels."
    )


# ── Core LLM call (shared) ────────────────────────────────────────────────────


async def _generate_abstract(clean_query: str) -> str | None:
    """Ask LLM for a hypothetical abstract. Returns None on any failure."""
    prompt = _build_hyde_prompt(clean_query)
    try:
        abstract = await chat_completion([{"role": "user", "content": prompt}])
    except Exception:
        logger.debug(
            "hyde._generate_abstract: LLM call failed for query %r",
            clean_query[:80],
            exc_info=True,
        )
        return None

    if not abstract or not abstract.strip():
        logger.debug(
            "hyde._generate_abstract: LLM returned empty abstract for query %r",
            clean_query[:80],
        )
        return None

    return abstract.strip()


# ── Primary: NIM 4096d (TIP-P2-06-FIX) ──────────────────────────────────────


async def generate_hyde_vector_nim(clean_query: str) -> list[float] | None:
    """Generate a HyDE query vector using NIM embedding (4096d).

    Steps:
    1. LLM writes a hypothetical research abstract.
    2. Embed via ``embed_text`` (NVIDIA NIM / nv-embed-v1, 4096d).
    3. Return vector or ``None`` on any failure.

    Args:
        clean_query: Cleaned English research topic string.

    Returns:
        ``list[float]`` of length 4096, or ``None`` when LLM or embed fails.
        Designed to query ``gap_nim_store`` — same embedding space.
    """
    abstract = await _generate_abstract(clean_query)
    if abstract is None:
        return None

    try:
        vector = await embed_text(abstract, input_type="query")
    except Exception:
        logger.debug("generate_hyde_vector_nim: embed_text failed", exc_info=True)
        return None

    if not vector:
        logger.debug(
            "generate_hyde_vector_nim: embed_text returned None (EMBEDDING_BASE_URL may be unset) — BM25 fallback"
        )
        return None

    logger.debug(
        "generate_hyde_vector_nim: HyDE vector dim=%d for query %r",
        len(vector),
        clean_query[:80],
    )
    return vector


# Backward-compat alias (previous name used by some callers / tests)
async def generate_hyde_vector(clean_query: str) -> list[float] | None:
    """Alias for ``generate_hyde_vector_nim``. Kept for backward compatibility."""
    return await generate_hyde_vector_nim(clean_query)


# ── Paper embedding helper ────────────────────────────────────────────────────


async def upsert_paper_to_nim_store(
    paper_id: str,
    abstract: str,
    title: str = "",
    year: int = 0,
) -> None:
    """Embed a paper's abstract via NIM and upsert into gap_nim_store.

    Fire-and-forget: failures are logged at DEBUG level and silently swallowed
    so that retrieval.rank() never crashes from store population errors.

    Args:
        paper_id: Semantic Scholar paper ID.
        abstract: Paper abstract text to embed.
        title: Paper title (stored as metadata).
        year: Publication year (stored as metadata).
    """
    if not paper_id or not abstract or not abstract.strip():
        return

    try:
        vector = await embed_text(abstract.strip(), input_type="passage")
        if vector:
            await upsert_papers_nim(
                [
                    {
                        "paper_id": paper_id,
                        "title": title,
                        "year": year,
                        "vector": vector,
                    }
                ]
            )
            logger.debug("upsert_paper_to_nim_store: upserted %s (dim=%d)", paper_id, len(vector))
    except Exception:
        logger.debug(
            "upsert_paper_to_nim_store: failed for paper %s — skipping",
            paper_id,
            exc_info=True,
        )
