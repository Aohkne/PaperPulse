from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Tier = Literal["free", "plus", "unlimited"]
Feature = Literal["lr", "pdf", "gap"]


class BillingAccountResponse(BaseModel):
    tier: Tier
    tier_period_end: datetime
    pending_downgrade_tier: Tier | None
    # Token-weighted billing: one shared credit pool. None = unlimited tier.
    subscription_credit_balance: float | None
    credit_used_this_period: float


class CheckoutSubscriptionRequest(BaseModel):
    tier: Literal["plus", "unlimited"]


class DowngradeRequest(BaseModel):
    tier: Literal["free", "plus"]


class CheckoutResponse(BaseModel):
    transaction_id: str
    checkout_url: str
    qr_code: str
    amount_vnd: int


class TransactionStatusResponse(BaseModel):
    id: str
    status: Literal["pending", "paid", "cancelled", "expired", "failed"]
    type: Literal["subscription_upgrade"]
    amount_vnd: int
