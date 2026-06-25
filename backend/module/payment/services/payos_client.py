"""Wrapper around the official `payos` PyPI SDK (v1.1.0+).

Using the official SDK rather than hand-rolling PayOS's HMAC-SHA256
alphabetical-sort request/webhook signing — that's exactly the kind of logic
where a subtle bug (wrong field order, wrong casing) silently breaks payment
integrity checks.
"""

from __future__ import annotations

from functools import lru_cache

from payos import AsyncPayOS, PayOSError, WebhookError
from payos.types.v2 import CreatePaymentLinkRequest, CreatePaymentLinkResponse, PaymentLink
from payos.types.webhooks import WebhookData

from backend.config import get_settings

__all__ = [
    "WebhookError", "PayOSError", "WebhookData", "get_payos_client",
    "create_checkout", "verify_webhook", "get_payment_link",
]


@lru_cache(maxsize=1)
def get_payos_client() -> AsyncPayOS:
    settings = get_settings()
    return AsyncPayOS(
        client_id=settings.payos_client_id,
        api_key=settings.payos_api_key,
        checksum_key=settings.payos_checksum_key,
    )


async def create_checkout(
    order_code: int,
    amount_vnd: int,
    description: str,
    return_url: str,
    cancel_url: str,
) -> CreatePaymentLinkResponse:
    client = get_payos_client()
    return await client.payment_requests.create(
        CreatePaymentLinkRequest(
            order_code=order_code,
            amount=amount_vnd,
            description=description,
            return_url=return_url,
            cancel_url=cancel_url,
        )
    )


async def verify_webhook(payload: dict) -> WebhookData:
    """Raises WebhookError if the signature doesn't match."""
    client = get_payos_client()
    return await client.webhooks.verify(payload)


async def get_payment_link(order_code: int) -> PaymentLink:
    """Live status check against PayOS — used as a fallback for local dev,
    where PayOS's webhook can never reach a localhost backend."""
    client = get_payos_client()
    return await client.payment_requests.get(order_code)
