"""Fixed VND price catalog (payment_SPEC_2.0.md §Identified Gaps #4).

Not env-configurable on purpose — the spec is explicit that subscription
pricing must not move with daily FX rates. Review manually on a quarterly
cadence or when the USD/VND rate drifts >10%, per the spec.
"""

from __future__ import annotations

TIER_PRICES_VND: dict[str, int] = {
    "plus": 19_000,
    "unlimited": 299_000,
}

# name -> (price_vnd, {feature: units})
TOPUP_PACKS: dict[str, dict] = {
    "pdf_5": {"price_vnd": 10_000, "units": {"pdf": 5}},
    "lr_5": {"price_vnd": 10_000, "units": {"lr": 5}},
    "gap_5": {"price_vnd": 10_000, "units": {"gap": 5}},
    "combo": {"price_vnd": 18_000, "units": {"pdf": 5, "lr": 5}},
}

# tier -> {feature: monthly allowance}; None = unlimited (soft cap only)
TIER_ALLOWANCE: dict[str, dict[str, int | None]] = {
    "free": {"lr": 3, "pdf": 5, "gap": 3},
    "plus": {"lr": 5, "pdf": 10, "gap": 5},
    "unlimited": {"lr": None, "pdf": None, "gap": None},
}

SOFT_CAP: dict[str, int] = {"lr": 80, "pdf": 150, "gap": 80}

# PayOS caps the payment-link `description` at ~9 chars for merchant accounts
# that haven't linked their own bank channel — keep these short on purpose.
TOPUP_DESCRIPTIONS: dict[str, str] = {
    "pdf_5": "PDF5",
    "lr_5": "LR5",
    "gap_5": "Gap5",
    "combo": "Combo",
}
