"""POST/GET /api/billing/* — subscription checkout via PayOS, credit-pool
status, and the PayOS webhook (token-weighted billing — no top-up).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.module.payment import pricing
from backend.module.payment.schemas import (
    BillingAccountResponse,
    CheckoutResponse,
    CheckoutSubscriptionRequest,
    DowngradeRequest,
    TransactionStatusResponse,
)
from backend.module.payment.services import billing_db
from backend.module.payment.services.payos_client import (
    PayOSError,
    WebhookError,
    create_checkout,
    get_payment_link,
    verify_webhook,
)

router = APIRouter(prefix="/billing", tags=["billing"])
log = logging.getLogger(__name__)


@router.get("/me", response_model=BillingAccountResponse)
async def get_my_account(user: Any = Depends(get_current_user)):
    acct = await billing_db.get_or_create_account(str(user.id))
    return BillingAccountResponse(**acct)


@router.post("/checkout/subscription", response_model=CheckoutResponse)
async def checkout_subscription(body: CheckoutSubscriptionRequest, user: Any = Depends(get_current_user)):
    amount = pricing.TIER_PRICES_VND[body.tier]
    return await _checkout(
        user_id=str(user.id),
        type_="subscription_upgrade",
        amount_vnd=amount,
        # PayOS caps `description` at ~9 chars for non-bank-linked merchant
        # accounts — "Unlimited" is exactly 9, "Plus" is 4.
        description=body.tier.capitalize(),
        tier=body.tier,
    )


async def _checkout(
    user_id: str,
    type_: str,
    amount_vnd: int,
    description: str,
    tier: str | None = None,
) -> CheckoutResponse:
    settings = get_settings()
    order_code = await billing_db.next_order_code()
    txn = await billing_db.create_transaction(
        user_id=user_id,
        type_=type_,
        amount_vnd=amount_vnd,
        payos_order_code=order_code,
        tier=tier,
    )

    return_url = f"{settings.frontend_base_url}/app/billing?status=success"
    cancel_url = f"{settings.frontend_base_url}/app/billing?status=cancelled"

    try:
        link = await create_checkout(order_code, amount_vnd, description, return_url, cancel_url)
    except PayOSError as exc:
        # PayOS remembers every orderCode it has ever issued, even ones our
        # local DB no longer has a record of (e.g. after a dev DB reset) — so
        # a freshly-allocated code can still collide. Retry once with a new
        # one instead of failing the whole checkout.
        if "tồn tại" not in str(exc):
            log.exception("PayOS create_checkout failed: %s", exc)
            raise HTTPException(502, "Không tạo được giao dịch PayOS") from exc
        log.warning("PayOS orderCode=%s already exists, retrying with a fresh code", order_code)
        order_code = await billing_db.next_order_code()
        await billing_db.set_order_code(txn["id"], order_code)
        try:
            link = await create_checkout(order_code, amount_vnd, description, return_url, cancel_url)
        except Exception as exc2:
            log.exception("PayOS create_checkout retry failed: %s", exc2)
            raise HTTPException(502, "Không tạo được giao dịch PayOS") from exc2
    except Exception as exc:
        log.exception("PayOS create_checkout failed: %s", exc)
        raise HTTPException(502, "Không tạo được giao dịch PayOS") from exc

    await billing_db.set_payment_link_id(txn["id"], link.payment_link_id)

    return CheckoutResponse(
        transaction_id=txn["id"],
        checkout_url=link.checkout_url,
        qr_code=link.qr_code,
        amount_vnd=amount_vnd,
    )


@router.post("/downgrade")
async def downgrade(body: DowngradeRequest, user: Any = Depends(get_current_user)):
    return await billing_db.request_downgrade(str(user.id), body.tier)


async def _settle_paid(txn: dict) -> bool:
    """Marks a still-pending transaction paid and applies its effect.
    Idempotent — both callers (webhook + the direct-check fallback below) may
    race to call this for the same transaction; mark_transaction_paid's
    `status=eq.pending` filter means only one of them actually flips it."""
    marked = await billing_db.mark_transaction_paid(txn["id"])
    if marked:
        try:
            await billing_db.apply_payment(txn["id"])
        except Exception as exc:
            log.exception("billing_apply_payment failed for txn=%s: %s", txn["id"], exc)
    return marked


@router.get("/transactions/{transaction_id}", response_model=TransactionStatusResponse)
async def get_transaction(transaction_id: str, user: Any = Depends(get_current_user)):
    txn = await billing_db.get_transaction(transaction_id)
    if not txn or txn["user_id"] != str(user.id):
        raise HTTPException(404, "Transaction not found")

    # Fallback for environments where PayOS's webhook can never arrive (e.g.
    # localhost backends with no public URL) — check PayOS directly instead
    # of waiting on a webhook that will never fire.
    if txn["status"] == "pending":
        try:
            link = await get_payment_link(txn["payos_order_code"])
        except Exception as exc:
            log.warning("PayOS get_payment_link failed for txn=%s: %s", txn["id"], exc)
        else:
            if link.status == "PAID":
                await _settle_paid(txn)
                txn = await billing_db.get_transaction(transaction_id)

    return TransactionStatusResponse(**txn)


@router.post("/webhook/payos")
async def payos_webhook(request: Request):
    """Public endpoint — integrity comes from PayOS's HMAC signature, not auth.
    Always returns 2xx so PayOS doesn't retry-storm; unknown/duplicate
    transactions are safe no-ops (this also covers PayOS's webhook-confirmation
    test ping, which has no matching orderCode)."""
    body = await request.json()
    try:
        data = await verify_webhook(body)
    except WebhookError as exc:
        log.warning("PayOS webhook signature verification failed: %s", exc)
        return {"received": True}

    txn = await billing_db.get_transaction_by_order_code(data.order_code)
    if not txn:
        log.info("PayOS webhook for unknown orderCode=%s (likely a confirm-webhook test ping)", data.order_code)
        return {"received": True}

    if txn["status"] == "pending" and data.code == "00":
        await _settle_paid(txn)

    return {"received": True}
