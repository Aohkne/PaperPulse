"""NIM embedding client for gap detection — gap-owned copy, independent of research_agent.

Gap module MUST NOT import from research_agent.services (Chủ nhà constraint, TIP-412).
This file owns the NIM embed_text() used by: hyde.py, false_gap.py, novelty.py,
background_corpus.py.

Differences from research_agent/services/embedding.py:
  - NIM 429 logged at DEBUG (not WARNING) — avoids log spam from fire-and-forget upserts.
  - Uses gap-local settings (NIM_RETRY_MAX, NIM_BACKOFF_BASE from gap_detection.settings).
  - fetch_and_store_embeddings() is NOT included (research_agent concern only).
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.agent.gap_detection.settings import get_nim_backoff_base, get_nim_retry_max

logger = logging.getLogger(__name__)


async def embed_text(text: str, input_type: str = "query") -> list[float] | None:
    """Embed text via configured NIM endpoint. Returns None on any failure.

    Never raises — callers treat None as 'no vector available, use BM25 fallback'.
    `input_type` is "query" for search queries, "passage" for paper abstracts
    (nv-embed-v1 requirement).
    Retries up to NIM_RETRY_MAX times on HTTP 429 with exponential backoff.
    NIM 429 is logged at DEBUG to avoid log spam from concurrent fire-and-forget upserts.
    """
    settings = get_settings()
    if not settings.embedding_base_url:
        return None

    max_retries = get_nim_retry_max()
    backoff_base = get_nim_backoff_base()

    for attempt in range(max_retries):
        try:
            body: dict = {"model": settings.embedding_model, "input": [text]}
            if settings.embedding_model and "nv-embed" in settings.embedding_model:
                body["input_type"] = input_type
                body["truncate"] = "END"
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{settings.embedding_base_url}/embeddings",
                    json=body,
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    timeout=30,
                )
                r.raise_for_status()
                data = r.json()
                return data["data"][0]["embedding"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = backoff_base ** (attempt + 1)
                    logger.debug("NIM 429, retry %d/%d in %.0fs", attempt + 1, max_retries - 1, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.debug("NIM 429: retries exhausted — returning None")
                    return None
            else:
                logger.warning("gap embed_text failed (returning None): %s", exc)
                return None
        except Exception as exc:
            logger.warning("gap embed_text failed (returning None): %s", exc)
            return None

    return None
