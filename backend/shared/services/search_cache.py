"""Postgres-backed cache for search/LLM results (optimize_Plan.html §2.1).

No Redis in this stack — Cloud Run instances are stateless and ephemeral
(scale-to-zero wipes in-memory caches), so the cache has to live in Supabase
like everything else. Not session/user-scoped on purpose: a cache hit should
be shared across every user querying the same source with the same params.

Uses raw httpx → PostgREST (same convention as vector_store.py / admin.py)
with the service-role key — this table has no RLS policy for anon/authenticated.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_TTL_S = 24 * 3600  # 1 day — search results don't change often enough to need shorter


def make_query_hash(source: str, **params) -> str:
    """Stable hash for a (source, params) pair — same params always hash the same."""
    canonical = json.dumps({"source": source, **params}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _rest_headers() -> dict:
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def get_cached(query_hash: str, ttl_s: float = _DEFAULT_TTL_S) -> dict | list | None:
    """Returns the cached payload, or None on miss/expired/any error (caller falls
    through to a live fetch — caching is a pure optimization, never a hard dependency)."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{settings.supabase_url}/rest/v1/search_cache",
                params={"query_hash": f"eq.{query_hash}", "select": "payload,created_at"},
                headers=_rest_headers(),
                timeout=5.0,
            )
        res.raise_for_status()
        rows = res.json()
    except Exception as exc:
        logger.warning("search_cache get_cached failed (treating as miss): %s", exc)
        return None

    if not rows:
        return None

    from datetime import datetime

    created_at = datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
    age_s = (datetime.now(UTC) - created_at).total_seconds()
    if age_s > ttl_s:
        return None
    return rows[0]["payload"]


async def set_cached(query_hash: str, source: str, payload: dict | list) -> None:
    """Best-effort write — a failed cache write should never break the caller's request."""
    from datetime import datetime

    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.supabase_url}/rest/v1/search_cache",
                params={"on_conflict": "query_hash"},
                # created_at must be sent explicitly — `merge-duplicates` only
                # refreshes the columns present in the body, and the column's
                # `DEFAULT now()` only fires on INSERT, not on this UPDATE path.
                # Without it, a refreshed row would keep its original
                # timestamp and the TTL in get_cached() would never reset.
                json={
                    "query_hash": query_hash,
                    "source": source,
                    "payload": payload,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                headers={**_rest_headers(), "Prefer": "resolution=merge-duplicates"},
                timeout=5.0,
            )
        res.raise_for_status()
    except Exception as exc:
        logger.warning("search_cache set_cached failed (non-fatal): %s", exc)
