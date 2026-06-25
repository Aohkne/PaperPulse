from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Tier = Literal["free", "plus", "unlimited"]
TopupPack = Literal["pdf_5", "lr_5", "gap_5", "combo"]
Feature = Literal["lr", "pdf", "gap"]


class BillingAccountResponse(BaseModel):
    tier: Tier
    tier_period_end: datetime
    pending_downgrade_tier: Tier | None
    subscription_lr_quota: int | None  # None = unlimited
    subscription_pdf_quota: int | None
    subscription_gap_quota: int | None
    topup_lr_balance: int
    topup_pdf_balance: int
    topup_gap_balance: int
    lr_used_this_period: int
    pdf_used_this_period: int
    gap_used_this_period: int


class CheckoutSubscriptionRequest(BaseModel):
    tier: Literal["plus", "unlimited"]


class CheckoutTopupRequest(BaseModel):
    pack: TopupPack


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
    type: Literal["subscription_upgrade", "topup"]
    amount_vnd: int
