"""Fixed VND price catalog + token→credit economics (token.html Draft v4).

Not env-configurable on purpose — the spec is explicit that subscription
pricing must not move with daily FX rates. Review manually on a quarterly
cadence or when the USD/VND rate drifts >10%, per the spec.

Billing model (token-weighted): all three features (lr / pdf / gap) draw from a
single per-tier monthly credit pool. 1 credit = $0.001 of model spend. There is
no top-up — when the pool is exhausted the user upgrades or waits for renewal.
"""

from __future__ import annotations

TIER_PRICES_VND: dict[str, int] = {
    "plus": 19_000,
    "unlimited": 299_000,
}

# ── Token economics ──────────────────────────────────────────────────────────
# openai/gpt-oss-120b via OpenRouter (fetched, not copied from internal spec):
#   $0.03 / 1M input tokens, $0.15 / 1M output tokens.
USD_PER_1M_INPUT = 0.03
USD_PER_1M_OUTPUT = 0.15
USD_PER_CREDIT = 0.001  # 1 credit = $0.001 of spend


def credits_for_tokens(input_tokens: int, output_tokens: int) -> float:
    """Convert token usage into credits (rounded to 3 dp, matching NUMERIC(10,3))."""
    usd = (input_tokens * USD_PER_1M_INPUT + output_tokens * USD_PER_1M_OUTPUT) / 1_000_000
    return round(usd / USD_PER_CREDIT, 3)


# tier -> monthly credit budget; None = unlimited (soft cap only). Rounded values
# (token.html §3): Free ≈ 3 lr + 5 pdf + 3 gap, Plus ≈ 2×.
TIER_CREDIT_BUDGET: dict[str, int | None] = {
    "free": 50,
    "plus": 100,
    "unlimited": None,
}

# Unlimited tier isn't hard-capped; past this many credits/period we log+alert
# only (MVP — no auto-throttle), same as the old per-feature soft caps.
SOFT_CAP_CREDIT = 1500
