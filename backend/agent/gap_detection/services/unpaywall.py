from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx

_API_BASE = "https://api.unpaywall.org/v2"
_TIMEOUT_SECONDS = 5.0
_MIN_INTERVAL_SECONDS = 0.1
_CACHE: dict[str, str | None] = {}
_IN_FLIGHT: dict[str, asyncio.Task[str | None]] = {}
_CACHE_LOCK = asyncio.Lock()
_RATE_LIMIT_LOCK = asyncio.Lock()
_LAST_CALL_AT = 0.0


async def get_oa_pdf_url(doi: str, email: str) -> str | None:
    normalized = _normalize_doi(doi)
    if not normalized or not email.strip():
        return None

    async with _CACHE_LOCK:
        if normalized in _CACHE:
            return _CACHE[normalized]
        task = _IN_FLIGHT.get(normalized)
        if task is None:
            task = asyncio.create_task(_fetch_and_cache(normalized, email.strip()))
            _IN_FLIGHT[normalized] = task

    return await task


async def _fetch_and_cache(normalized_doi: str, email: str) -> str | None:
    try:
        result = await _fetch_oa_pdf_url(normalized_doi, email)
        async with _CACHE_LOCK:
            _CACHE[normalized_doi] = result
            _IN_FLIGHT.pop(normalized_doi, None)
        return result
    except Exception:
        async with _CACHE_LOCK:
            _CACHE[normalized_doi] = None
            _IN_FLIGHT.pop(normalized_doi, None)
        return None


async def _fetch_oa_pdf_url(normalized_doi: str, email: str) -> str | None:
    await _respect_rate_limit()
    encoded_doi = quote(normalized_doi, safe="")
    url = f"{_API_BASE}/{encoded_doi}"

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, params={"email": email}, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    return _extract_best_oa_url(payload)


async def _respect_rate_limit() -> None:
    global _LAST_CALL_AT

    async with _RATE_LIMIT_LOCK:
        now = asyncio.get_running_loop().time()
        wait_seconds = _MIN_INTERVAL_SECONDS - (now - _LAST_CALL_AT)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
            now = asyncio.get_running_loop().time()
        _LAST_CALL_AT = now


def _extract_best_oa_url(payload: dict[str, Any]) -> str | None:
    best_location = payload.get("best_oa_location")
    if not isinstance(best_location, dict):
        return None

    pdf_url = best_location.get("url_for_pdf")
    if isinstance(pdf_url, str) and pdf_url.strip():
        return pdf_url.strip()

    landing_url = best_location.get("url")
    if isinstance(landing_url, str) and landing_url.strip():
        return landing_url.strip()

    return None


def _normalize_doi(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.strip()


def _reset_cache_for_tests() -> None:
    global _LAST_CALL_AT
    _CACHE.clear()
    _IN_FLIGHT.clear()
    _LAST_CALL_AT = 0.0
