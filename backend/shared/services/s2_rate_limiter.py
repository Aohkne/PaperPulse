"""Global Semantic Scholar rate limiter — token bucket, all callers share one instance.

Rate is auto-detected once (lazy) from environment:
  S2_RATE_LIMIT_RPS  — explicit override (float, req/s)
  semantic_scholar_api_key present → 1.0 req/s  (introductory tier default)
  No key             → 1.0 req/s  (free tier default)

The current key is on S2's introductory tier (1 req/s). Setting a higher rate
than the key actually allows only causes 429s → tenacity retries → net slower.
Upgrade the key at semanticscholar.org/product/api to raise this safely.

All S2 HTTP callers (semantic_scholar._get, s2_client._s2_get, and
get_embeddings_batch POST) must call ``await s2_acquire()`` before
issuing the request.  This serialises them through the bucket so the
pipeline never exceeds the detected rate regardless of how many
coroutines are running concurrently.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)

_DEFAULT_RPS_FREE = 1.0  # S2 free tier
_DEFAULT_RPS_KEY = 1.0  # S2 introductory-tier key (upgrade tier to raise)


class _TokenBucket:
    """Async token bucket rate limiter (thread-safe via asyncio.Lock)."""

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._tokens: float = rate  # start full so first requests aren't delayed
        self._last: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
                self._last = time.monotonic()
            else:
                self._tokens -= 1.0


_bucket: _TokenBucket | None = None


def _build_bucket() -> _TokenBucket:
    rps_env = os.getenv("S2_RATE_LIMIT_RPS")
    if rps_env:
        try:
            rate = max(0.1, float(rps_env))
            logger.info("S2 rate limiter: %.1f req/s (S2_RATE_LIMIT_RPS override)", rate)
            return _TokenBucket(rate)
        except ValueError:
            logger.warning("S2_RATE_LIMIT_RPS=%r invalid — using default", rps_env)

    try:
        from backend.config import get_settings

        if get_settings().semantic_scholar_api_key:
            logger.info("S2 rate limiter: %.1f req/s (API key detected)", _DEFAULT_RPS_KEY)
            return _TokenBucket(_DEFAULT_RPS_KEY)
    except Exception:
        pass

    logger.info("S2 rate limiter: %.1f req/s (free tier / no key)", _DEFAULT_RPS_FREE)
    return _TokenBucket(_DEFAULT_RPS_FREE)


async def s2_acquire() -> None:
    """Acquire one token from the global S2 rate limiter.

    Must be called before every S2 HTTP request (GET or POST).
    Blocks until a token is available; never raises.
    """
    global _bucket
    if _bucket is None:
        _bucket = _build_bucket()
    await _bucket.acquire()
