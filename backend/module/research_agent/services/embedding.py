"""Fetch SPECTER v2 embeddings from Semantic Scholar; fallback to custom embedding model."""

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.shared.models.paper import EmbedResponse
from backend.shared.services.semantic_scholar import get_embeddings_batch
from backend.module.research_agent.services.vector_store import upsert_papers
from backend.agent.gap_detection.settings import get_nim_backoff_base, get_nim_retry_max


async def embed_text(text: str, input_type: str = "query") -> list[float] | None:
    """Embed text via configured embedding endpoint. Returns None on any failure.

    Never raises — callers treat None as 'no vector available, use keyword fallback'.
    `input_type` is "query" for search queries, "passage" for paper abstracts (nv-embed-v1 requirement).
    Retries up to NIM_RETRY_MAX times on HTTP 429 with exponential backoff (NIM_BACKOFF_BASE seconds).
    """
    settings = get_settings()
    if not settings.embedding_base_url:
        return None

    max_retries = get_nim_retry_max()
    backoff_base = get_nim_backoff_base()

    for attempt in range(max_retries):
        try:
            # NVIDIA NIM (and most OpenAI-compatible embedding servers) expect
            # `input` as a list of strings, not a bare string.
            body: dict = {"model": settings.embedding_model, "input": [text]}
            # nv-embed-v1 requires input_type; other providers ignore unknown fields
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
                    logging.warning("NIM 429, retry %d/%d sau %.0fs", attempt + 1, max_retries - 1, delay)
                    await asyncio.sleep(delay)
                else:
                    logging.error("NIM 429: đã retry đủ lần, trả None")
                    return None
            else:
                logging.warning("embed_text failed (returning None): %s", exc)
                return None
        except Exception as exc:
            logging.warning("embed_text failed (returning None): %s", exc)
            return None

    return None  # fail-safe: max_retries exhausted via 429 loop


async def fetch_and_store_embeddings(paper_ids: list[str]) -> EmbedResponse:
    """③ Fetch SPECTER v2 for all paper_ids, fallback to abstract embed, store in ChromaDB."""
    from backend.module.research_agent.services.vector_store import get_papers_by_ids

    specter_map = await get_embeddings_batch(paper_ids)

    papers = await get_papers_by_ids(paper_ids)
    embedded = 0

    for paper in papers:
        if paper.paper_id in specter_map:
            paper.embedding = specter_map[paper.paper_id]
            embedded += 1
        elif paper.abstract:
            fallback = await embed_text(paper.abstract, input_type="passage")
            if fallback:
                paper.embedding = fallback
                embedded += 1
                logging.warning("SPECTER v2 missing for %s — used fallback embedding", paper.paper_id)

    stored = await upsert_papers(papers)
    return EmbedResponse(embedded=embedded, stored=stored)
