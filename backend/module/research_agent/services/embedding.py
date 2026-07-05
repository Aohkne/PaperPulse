"""Fetch SPECTER v2 embeddings from Semantic Scholar; fallback to custom embedding model."""

import asyncio
import logging

import httpx

from backend.agent.gap_detection.settings import get_nim_backoff_base, get_nim_retry_max
from backend.config import get_settings


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


async def embed_texts_batch(
    texts: list[str], input_type: str = "passage", batch_size: int = 32
) -> list[list[float] | None]:
    """Embed many texts via batched NIM calls (few round-trips instead of one per text).

    Used by Step ①bis relevance filter, where the semantic side previously issued
    one HTTP call per paper (up to ~1500) even under a concurrency cap — each
    round-trip was a separate chance to hit NIM 429/502. Batching `batch_size`
    texts per call cuts that to len(texts)/batch_size calls.

    Returns a list aligned 1:1 with `texts`; entries are None where that text's
    batch failed after retries. Never raises.
    """
    settings = get_settings()
    result: list[list[float] | None] = [None] * len(texts)
    if not settings.embedding_base_url or not texts:
        return result

    max_retries = get_nim_retry_max()
    backoff_base = get_nim_backoff_base()
    is_nv_embed = bool(settings.embedding_model and "nv-embed" in settings.embedding_model)
    sem = asyncio.Semaphore(4)  # cap concurrent batch calls to NIM

    async def _one_chunk(client: httpx.AsyncClient, start: int, chunk: list[str]) -> None:
        body: dict = {"model": settings.embedding_model, "input": chunk}
        if is_nv_embed:
            body["input_type"] = input_type
            body["truncate"] = "END"

        async with sem:
            for attempt in range(max_retries):
                try:
                    r = await client.post(
                        f"{settings.embedding_base_url}/embeddings",
                        json=body,
                        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                        timeout=60,
                    )
                    r.raise_for_status()
                    for item in r.json()["data"]:
                        idx = item.get("index")
                        vec = item.get("embedding")
                        if idx is not None and vec is not None and 0 <= idx < len(chunk):
                            result[start + idx] = vec
                    return
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429 and attempt < max_retries - 1:
                        delay = backoff_base ** (attempt + 1)
                        logging.warning(
                            "NIM batch 429 (chunk %d), retry %d/%d sau %.0fs",
                            start,
                            attempt + 1,
                            max_retries - 1,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logging.warning("embed_texts_batch failed (chunk %d): %s", start, exc)
                    return
                except Exception as exc:
                    logging.warning("embed_texts_batch failed (chunk %d): %s", start, exc)
                    return

    async with httpx.AsyncClient() as client:
        chunks = [(i, texts[i : i + batch_size]) for i in range(0, len(texts), batch_size)]
        await asyncio.gather(*[_one_chunk(client, start, chunk) for start, chunk in chunks])

    return result
