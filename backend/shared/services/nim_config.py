"""NIM API retry/backoff config — shared by any module calling a NIM embedding endpoint.

Used by module/gap_detection/services/embedding.py and
module/research_agent/services/embedding.py so neither module depends
on the other's settings.
"""

from __future__ import annotations

import os

_DEFAULT_NIM_RETRY_MAX = 3  # max retry attempts for NIM API HTTP 429
_DEFAULT_NIM_BACKOFF_BASE = 2.0  # exponential backoff base seconds (attempt N → base^N s)


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
