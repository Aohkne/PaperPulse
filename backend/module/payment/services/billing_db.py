"""PostgREST access for billing — tables + RPC calls into the billing_* SQL
functions (supabase/schema.sql §14). Uses httpx + the service-role key, same
convention as backend/api/admin.py's `_pg`/`_pg_write` (supabase-py is avoided
here per the note in backend/auth/dependencies.py about sb_publishable_... key
incompatibility — stay consistent with the rest of the codebase).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import get_settings

log = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    pass


class BillingDBError(Exception):
    pass


def _headers() -> dict:
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def _rpc(fn_name: str, params: dict) -> Any:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{settings.supabase_url}/rest/v1/rpc/{fn_name}",
            json=params,
            headers=_headers(),
            timeout=10.0,
        )
    if res.status_code != 200:
        message = ""
        try:
            message = res.json().get("message", "")
        except Exception:
            message = res.text[:300]
        if "QUOTA_EXCEEDED" in message:
            raise QuotaExceededError(message)
        log.warning("billing rpc %s failed status=%s body=%s", fn_name, res.status_code, message)
        raise BillingDBError(f"{fn_name} failed: {message}")
    return res.json()


async def _pg(table: str, params: dict, count: bool = False) -> tuple[list[dict], int]:
    settings = get_settings()
    headers = _headers()
    if count:
        headers["Prefer"] = "count=exact"
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{settings.supabase_url}/rest/v1/{table}",
            params=params,
            headers=headers,
            timeout=10.0,
        )
    if res.status_code != 200:
        log.warning("billing _pg %s status=%s body=%s", table, res.status_code, res.text[:300])
        return [], 0
    rows = res.json() if isinstance(res.json(), list) else []
    total = len(rows)
    if count:
        cr = res.headers.get("content-range", "")
        if "/" in cr:
            try:
                total = int(cr.split("/")[1])
            except ValueError:
                pass
    return rows, total


async def _pg_write(table: str, method: str, params: dict, body: dict) -> list[dict]:
    settings = get_settings()
    headers = {**_headers(), "Prefer": "return=representation"}
    async with httpx.AsyncClient() as client:
        res = await client.request(
            method,
            f"{settings.supabase_url}/rest/v1/{table}",
            params=params,
            json=body,
            headers=headers,
            timeout=10.0,
        )
    if res.status_code not in (200, 201):
        log.warning("billing _pg_write %s %s status=%s body=%s", method, table, res.status_code, res.text[:300])
        raise BillingDBError(f"{method} {table} failed: {res.text[:300]}")
    return res.json()


# ── billing_* RPC wrappers ───────────────────────────────────────────────────

async def get_or_create_account(user_id: str) -> dict:
    return await _rpc("billing_get_or_create_account", {"p_user_id": user_id})


async def start_session(user_id: str, feature: str, session_id: str) -> dict:
    """Raises QuotaExceededError if both subscription quota and topup balance are exhausted."""
    return await _rpc(
        "billing_start_session",
        {"p_user_id": user_id, "p_feature": feature, "p_session_id": session_id},
    )


async def refund_session(user_id: str, feature: str, session_id: str) -> dict:
    """Idempotent — no-op if the session was never deducted or already refunded."""
    return await _rpc(
        "billing_refund_session",
        {"p_user_id": user_id, "p_feature": feature, "p_session_id": session_id},
    )


async def apply_payment(transaction_id: str) -> dict:
    """Idempotent — no-op if the transaction was already applied."""
    return await _rpc("billing_apply_payment", {"p_transaction_id": transaction_id})


async def request_downgrade(user_id: str, new_tier: str) -> dict:
    return await _rpc("billing_request_downgrade", {"p_user_id": user_id, "p_new_tier": new_tier})


# ── payment_transactions table access ───────────────────────────────────────

async def next_order_code() -> int:
    result = await _rpc("next_payos_order_code", {})
    return int(result)


async def create_transaction(
    user_id: str,
    type_: str,
    amount_vnd: int,
    payos_order_code: int,
    tier: str | None = None,
    topup_pack: str | None = None,
) -> dict:
    body = {
        "user_id": user_id,
        "type": type_,
        "amount_vnd": amount_vnd,
        "payos_order_code": payos_order_code,
        "tier": tier,
        "topup_pack": topup_pack,
    }
    rows = await _pg_write("payment_transactions", "POST", {}, body)
    return rows[0]


async def set_payment_link_id(transaction_id: str, payment_link_id: str) -> None:
    await _pg_write(
        "payment_transactions", "PATCH",
        {"id": f"eq.{transaction_id}"},
        {"payos_payment_link_id": payment_link_id},
    )


async def set_order_code(transaction_id: str, payos_order_code: int) -> None:
    await _pg_write(
        "payment_transactions", "PATCH",
        {"id": f"eq.{transaction_id}"},
        {"payos_order_code": payos_order_code},
    )


async def get_transaction(transaction_id: str) -> dict | None:
    rows, _ = await _pg("payment_transactions", {"id": f"eq.{transaction_id}", "select": "*"})
    return rows[0] if rows else None


async def get_transaction_by_order_code(order_code: int) -> dict | None:
    rows, _ = await _pg(
        "payment_transactions", {"payos_order_code": f"eq.{order_code}", "select": "*"}
    )
    return rows[0] if rows else None


async def mark_transaction_paid(transaction_id: str) -> bool:
    """Returns False if the transaction wasn't `pending` (already handled)."""
    rows = await _pg_write(
        "payment_transactions", "PATCH",
        {"id": f"eq.{transaction_id}", "status": "eq.pending"},
        {"status": "paid", "paid_at": "now"},
    )
    return bool(rows)
