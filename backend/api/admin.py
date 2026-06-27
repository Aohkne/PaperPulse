"""Admin-only endpoints — dashboard stats, user list, activity log."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth.dependencies import require_admin
from backend.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


# ── PostgREST helper ─────────────────────────────────────────────────────────

async def _pg(
    table: str,
    params: dict | None = None,
    count: bool = False,
) -> tuple[list[dict], int]:
    """Query PostgREST via service-role key (bypasses RLS). Returns (rows, total_count)."""
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    headers: dict = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if count:
        headers["Prefer"] = "count=exact"

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{settings.supabase_url}/rest/v1/{table}",
            params=params or {},
            headers=headers,
            timeout=10.0,
        )

    if res.status_code != 200:
        import logging
        logging.getLogger(__name__).warning("_pg %s status=%s body=%s", table, res.status_code, res.text[:300])
        return [], 0

    rows = res.json() if isinstance(res.json(), list) else []
    total = 0
    if count:
        cr = res.headers.get("content-range", "")
        if "/" in cr:
            try:
                total = int(cr.split("/")[1])
            except ValueError:
                total = len(rows)
        else:
            total = len(rows)
    return rows, total


async def _pg_write(table: str, method: str, params: dict, body: dict) -> list[dict]:
    """POST/PATCH/DELETE a row via PostgREST using the service-role key (bypasses RLS).
    Returns the affected rows (Prefer: return=representation)."""
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
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
        import logging
        logging.getLogger(__name__).warning("_pg_write %s %s status=%s body=%s", method, table, res.status_code, res.text[:300])
        raise HTTPException(status_code=502, detail=f"PostgREST {method} {table} failed")
    return res.json()


# ── Pydantic models ───────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    total_users: int
    new_users_today: int
    new_users_this_week: int
    total_logins_today: int
    total_logins_this_week: int
    total_registers_this_week: int
    active_users_7d: int


class UserRow(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    is_banned: bool = False
    created_at: str
    last_login: str | None
    total_logins: int


class UserListResponse(BaseModel):
    data: list[UserRow]
    total: int
    page: int
    limit: int
    has_more: bool


class BanRequest(BaseModel):
    reason: str


class BillingAccountRow(BaseModel):
    user_id: str
    email: str
    full_name: str | None
    tier: str
    tier_period_end: str
    subscription_lr_quota: int | None
    subscription_pdf_quota: int | None
    subscription_gap_quota: int | None
    topup_lr_balance: int
    topup_pdf_balance: int
    topup_gap_balance: int
    lr_used_this_period: int
    pdf_used_this_period: int
    gap_used_this_period: int


class BillingAccountListResponse(BaseModel):
    data: list[BillingAccountRow]
    total: int
    page: int
    limit: int
    has_more: bool


class UsageTopupRequest(BaseModel):
    lr: int = 0
    pdf: int = 0
    gap: int = 0


# Mirrors the tier defaults in billing_get_or_create_account() (schema.sql §13d)
# — kept in sync manually since this is an admin override path, not the lazy
# period-rollover path the SQL function handles for normal users.
_TIER_DEFAULTS: dict[str, dict[str, int | None]] = {
    "free": {"lr": 3, "pdf": 5, "gap": 3},
    "plus": {"lr": 5, "pdf": 10, "gap": 5},
    "unlimited": {"lr": None, "pdf": None, "gap": None},
}


class ActivityRow(BaseModel):
    id: int
    user_id: str
    email: str
    event_type: str
    logged_in_at: str
    ip_address: str | None


class ActivityResponse(BaseModel):
    data: list[ActivityRow]
    total: int
    page: int
    limit: int
    has_more: bool


class DailyRevenue(BaseModel):
    date: str
    revenue_vnd: int
    count: int


class RecentTransaction(BaseModel):
    id: str
    email: str | None
    type: str
    tier: str | None
    topup_pack: str | None
    amount_vnd: int
    paid_at: str | None


class RevenueResponse(BaseModel):
    total_revenue_vnd: int
    revenue_this_month_vnd: int
    total_paid_transactions: int
    avg_transaction_vnd: int
    daily: list[DailyRevenue]
    recent: list[RecentTransaction]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    _admin: Any = Depends(require_admin),
):
    """Aggregate dashboard statistics (admin only)."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    _, total_users = await _pg("profiles", {"select": "id"}, count=True)

    _, new_today = await _pg("profiles", {"select": "id", "created_at": f"gte.{today}"}, count=True)
    _, new_week  = await _pg("profiles", {"select": "id", "created_at": f"gte.{week_ago}"}, count=True)

    _, logins_today = await _pg("login_logs", {"select": "id", "event_type": "eq.login", "logged_in_at": f"gte.{today}"}, count=True)
    _, logins_week  = await _pg("login_logs", {"select": "id", "event_type": "eq.login", "logged_in_at": f"gte.{week_ago}"}, count=True)

    _, registers_week = await _pg("login_logs", {"select": "id", "event_type": "eq.register", "logged_in_at": f"gte.{week_ago}"}, count=True)

    active_rows, _ = await _pg("login_logs", {"select": "user_id", "logged_in_at": f"gte.{week_ago}"})
    active_users_7d = len({r["user_id"] for r in active_rows})

    return StatsResponse(
        total_users=total_users,
        new_users_today=new_today,
        new_users_this_week=new_week,
        total_logins_today=logins_today,
        total_logins_this_week=logins_week,
        total_registers_this_week=registers_week,
        active_users_7d=active_users_7d,
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_banned: bool | None = Query(default=None),
    _admin: Any = Depends(require_admin),
):
    """List all users with last login and login count (admin only)."""
    offset = (page - 1) * limit

    params: dict = {
        "select": "id,email,full_name,role,is_banned,created_at",
        "order": "created_at.desc",
        "offset": offset,
        "limit": limit,
    }
    if search:
        params["email"] = f"ilike.*{search}*"
    if role:
        params["role"] = f"eq.{role}"
    if is_banned is not None:
        params["is_banned"] = f"eq.{str(is_banned).lower()}"

    profiles, total = await _pg("profiles", params, count=True)
    user_ids = [p["id"] for p in profiles]

    from collections import defaultdict
    counts: dict[str, int] = defaultdict(int)
    last_login: dict[str, str] = {}

    if user_ids:
        id_filter = ",".join(user_ids)
        logs, _ = await _pg("login_logs", {
            "select": "user_id,logged_in_at",
            "event_type": "eq.login",
            "user_id": f"in.({id_filter})",
        })
        for log in logs:
            uid = log["user_id"]
            counts[uid] += 1
            ts = log["logged_in_at"]
            if uid not in last_login or ts > last_login[uid]:
                last_login[uid] = ts

    rows = [
        UserRow(
            id=p["id"],
            email=p["email"],
            full_name=p.get("full_name"),
            role=p["role"],
            is_banned=p.get("is_banned", False),
            created_at=p["created_at"],
            last_login=last_login.get(p["id"]),
            total_logins=counts[p["id"]],
        )
        for p in profiles
    ]

    return UserListResponse(
        data=rows,
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + limit) < total,
    )


@router.post("/users/{user_id}/ban", response_model=UserRow)
async def ban_user(
    user_id: str,
    body: BanRequest,
    _admin: Any = Depends(require_admin),
):
    """Ban a user — they can no longer submit/vote on community contributions."""
    rows = await _pg_write(
        "profiles",
        "PATCH",
        {"id": f"eq.{user_id}"},
        {
            "is_banned": True,
            "banned_at": datetime.now(timezone.utc).isoformat(),
            "ban_reason": body.reason,
        },
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    p = rows[0]
    return UserRow(
        id=p["id"], email=p["email"], full_name=p.get("full_name"), role=p["role"],
        is_banned=p.get("is_banned", False), created_at=p["created_at"], last_login=None, total_logins=0,
    )


@router.post("/users/{user_id}/unban", response_model=UserRow)
async def unban_user(
    user_id: str,
    _admin: Any = Depends(require_admin),
):
    """Lift a ban."""
    rows = await _pg_write(
        "profiles",
        "PATCH",
        {"id": f"eq.{user_id}"},
        {"is_banned": False, "banned_at": None, "ban_reason": None},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    p = rows[0]
    return UserRow(
        id=p["id"], email=p["email"], full_name=p.get("full_name"), role=p["role"],
        is_banned=p.get("is_banned", False), created_at=p["created_at"], last_login=None, total_logins=0,
    )


def _billing_row(user_id: str, profile: dict, acct: dict) -> BillingAccountRow:
    return BillingAccountRow(
        user_id=user_id,
        email=profile.get("email", ""),
        full_name=profile.get("full_name"),
        tier=acct.get("tier", "free"),
        tier_period_end=acct.get("tier_period_end") or datetime.now(timezone.utc).isoformat(),
        subscription_lr_quota=acct.get("subscription_lr_quota"),
        subscription_pdf_quota=acct.get("subscription_pdf_quota"),
        subscription_gap_quota=acct.get("subscription_gap_quota"),
        topup_lr_balance=acct.get("topup_lr_balance", 0),
        topup_pdf_balance=acct.get("topup_pdf_balance", 0),
        topup_gap_balance=acct.get("topup_gap_balance", 0),
        lr_used_this_period=acct.get("lr_used_this_period", 0),
        pdf_used_this_period=acct.get("pdf_used_this_period", 0),
        gap_used_this_period=acct.get("gap_used_this_period", 0),
    )


_BILLING_ACCOUNT_DEFAULTS: dict = {
    "tier": "free",
    "subscription_lr_quota": 3, "subscription_pdf_quota": 5, "subscription_gap_quota": 3,
    "topup_lr_balance": 0, "topup_pdf_balance": 0, "topup_gap_balance": 0,
    "lr_used_this_period": 0, "pdf_used_this_period": 0, "gap_used_this_period": 0,
}


@router.get("/billing-accounts", response_model=BillingAccountListResponse)
async def list_billing_accounts(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    _admin: Any = Depends(require_admin),
):
    """List users with their usage/quota state (admin only).

    Accounts are lazily created on first use (billing_get_or_create_account),
    so a profile with no billing_accounts row yet is shown with the Free
    tier's defaults rather than a 404/empty row.
    """
    offset = (page - 1) * limit

    params: dict = {
        "select": "id,email,full_name",
        "order": "created_at.desc",
        "offset": offset,
        "limit": limit,
    }
    if search:
        params["email"] = f"ilike.*{search}*"

    profiles, total = await _pg("profiles", params, count=True)
    user_ids = [p["id"] for p in profiles]

    accounts_by_id: dict[str, dict] = {}
    if user_ids:
        id_filter = ",".join(user_ids)
        accounts, _ = await _pg("billing_accounts", {
            "select": (
                "user_id,tier,tier_period_end,subscription_lr_quota,subscription_pdf_quota,"
                "subscription_gap_quota,topup_lr_balance,topup_pdf_balance,topup_gap_balance,"
                "lr_used_this_period,pdf_used_this_period,gap_used_this_period"
            ),
            "user_id": f"in.({id_filter})",
        })
        accounts_by_id = {a["user_id"]: a for a in accounts}

    rows = [
        _billing_row(p["id"], p, accounts_by_id.get(p["id"], _BILLING_ACCOUNT_DEFAULTS))
        for p in profiles
    ]

    return BillingAccountListResponse(
        data=rows, total=total, page=page, limit=limit, has_more=(offset + limit) < total,
    )


@router.post("/users/{user_id}/usage/reset", response_model=BillingAccountRow)
async def reset_usage(
    user_id: str,
    admin: Any = Depends(require_admin),
):
    """Reset a user's subscription quota + usage counters back to their
    tier's default allowance for a fresh 30-day period — an admin override
    independent of the normal lazy rollover in billing_get_or_create_account.
    """
    existing, _ = await _pg("billing_accounts", {"select": "tier", "user_id": f"eq.{user_id}"})
    tier = existing[0]["tier"] if existing else "free"
    defaults = _TIER_DEFAULTS.get(tier, _TIER_DEFAULTS["free"])

    patch = {
        "subscription_lr_quota": defaults["lr"],
        "subscription_pdf_quota": defaults["pdf"],
        "subscription_gap_quota": defaults["gap"],
        "lr_used_this_period": 0,
        "pdf_used_this_period": 0,
        "gap_used_this_period": 0,
        "tier_period_end": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }

    if existing:
        rows = await _pg_write("billing_accounts", "PATCH", {"user_id": f"eq.{user_id}"}, patch)
    else:
        rows = await _pg_write("billing_accounts", "POST", {}, {"user_id": user_id, **patch})

    if not rows:
        raise HTTPException(status_code=404, detail="Billing account not found")

    await _pg_write(
        "quota_ledger", "POST", {},
        {
            "user_id": user_id, "feature": "lr", "delta": 0, "source": "subscription",
            "session_id": f"admin-reset:{admin.id}:{datetime.now(timezone.utc).isoformat()}",
            "reason": "subscription_reset",
        },
    )

    profile, _ = await _pg("profiles", {"select": "email,full_name", "id": f"eq.{user_id}"})
    return _billing_row(user_id, profile[0] if profile else {}, rows[0])


@router.post("/users/{user_id}/usage/topup", response_model=BillingAccountRow)
async def topup_usage(
    user_id: str,
    body: UsageTopupRequest,
    admin: Any = Depends(require_admin),
):
    """Add prepaid top-up balance to a user's account, customized per feature
    — lands in the same topup_*_balance columns a real purchase would credit.
    """
    if body.lr == 0 and body.pdf == 0 and body.gap == 0:
        raise HTTPException(status_code=400, detail="Provide at least one non-zero amount")

    existing, _ = await _pg("billing_accounts", {
        "select": "topup_lr_balance,topup_pdf_balance,topup_gap_balance",
        "user_id": f"eq.{user_id}",
    })

    if existing:
        current = existing[0]
        patch = {
            "topup_lr_balance": current["topup_lr_balance"] + body.lr,
            "topup_pdf_balance": current["topup_pdf_balance"] + body.pdf,
            "topup_gap_balance": current["topup_gap_balance"] + body.gap,
        }
        rows = await _pg_write("billing_accounts", "PATCH", {"user_id": f"eq.{user_id}"}, patch)
    else:
        rows = await _pg_write("billing_accounts", "POST", {}, {
            "user_id": user_id,
            "topup_lr_balance": max(body.lr, 0),
            "topup_pdf_balance": max(body.pdf, 0),
            "topup_gap_balance": max(body.gap, 0),
        })

    if not rows:
        raise HTTPException(status_code=404, detail="Billing account not found")

    for feature, delta in (("lr", body.lr), ("pdf", body.pdf), ("gap", body.gap)):
        if delta:
            await _pg_write(
                "quota_ledger", "POST", {},
                {
                    "user_id": user_id, "feature": feature, "delta": delta, "source": "topup",
                    "session_id": f"admin-topup:{admin.id}:{datetime.now(timezone.utc).isoformat()}",
                    "reason": "topup_purchase",
                },
            )

    profile, _ = await _pg("profiles", {"select": "email,full_name", "id": f"eq.{user_id}"})
    return _billing_row(user_id, profile[0] if profile else {}, rows[0])


@router.get("/activity", response_model=ActivityResponse)
async def list_activity(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=500),
    event_type: str | None = Query(default=None),
    since: str | None = Query(default=None),
    _admin: Any = Depends(require_admin),
):
    """Paginated login/register activity log (admin only).

    `since` (ISO timestamp) lets callers like the dashboard chart pull every
    event within a date range instead of just the most recent N rows overall
    — without it, low-frequency event types (e.g. "register") get crowded
    out of a small top-N window by high-frequency ones (login/logout).
    """
    offset = (page - 1) * limit

    params: dict = {
        "select": "id,user_id,email,event_type,logged_in_at,ip_address",
        "order": "logged_in_at.desc",
        "offset": offset,
        "limit": limit,
    }
    if event_type:
        params["event_type"] = f"eq.{event_type}"
    if since:
        params["logged_in_at"] = f"gte.{since}"

    rows, total = await _pg("login_logs", params, count=True)

    return ActivityResponse(
        data=[ActivityRow(**r) for r in rows],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + limit) < total,
    )


@router.get("/revenue", response_model=RevenueResponse)
async def get_revenue(
    _admin: Any = Depends(require_admin),
):
    """Aggregate revenue from paid PayOS transactions (admin only)."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    paid, total_paid = await _pg(
        "payment_transactions",
        {"select": "id,user_id,type,tier,topup_pack,amount_vnd,paid_at", "status": "eq.paid"},
        count=True,
    )

    total_revenue = sum(p["amount_vnd"] for p in paid)
    revenue_this_month = sum(p["amount_vnd"] for p in paid if p["paid_at"] and p["paid_at"] >= month_start)
    avg_transaction = total_revenue // total_paid if total_paid else 0

    # Zero-filled daily series for the last 30 days (same convention as
    # DashboardPage.jsx's buildChartData on the frontend).
    days = [(now - timedelta(days=i)).date().isoformat() for i in range(29, -1, -1)]
    daily_map = {d: {"date": d, "revenue_vnd": 0, "count": 0} for d in days}
    for p in paid:
        if not p["paid_at"] or p["paid_at"] < thirty_days_ago:
            continue
        day = p["paid_at"][:10]
        if day in daily_map:
            daily_map[day]["revenue_vnd"] += p["amount_vnd"]
            daily_map[day]["count"] += 1

    # Recent 20 paid transactions, with the paying user's email joined in
    # (same pattern as list_users' login_logs join above).
    recent_sorted = sorted(paid, key=lambda p: p["paid_at"] or "", reverse=True)[:20]
    user_ids = list({p["user_id"] for p in recent_sorted})
    emails: dict[str, str] = {}
    if user_ids:
        id_filter = ",".join(user_ids)
        profiles, _ = await _pg("profiles", {"select": "id,email", "id": f"in.({id_filter})"})
        emails = {pr["id"]: pr["email"] for pr in profiles}

    return RevenueResponse(
        total_revenue_vnd=total_revenue,
        revenue_this_month_vnd=revenue_this_month,
        total_paid_transactions=total_paid,
        avg_transaction_vnd=avg_transaction,
        daily=[DailyRevenue(**daily_map[d]) for d in days],
        recent=[
            RecentTransaction(
                id=p["id"],
                email=emails.get(p["user_id"]),
                type=p["type"],
                tier=p.get("tier"),
                topup_pack=p.get("topup_pack"),
                amount_vnd=p["amount_vnd"],
                paid_at=p["paid_at"],
            )
            for p in recent_sorted
        ],
    )
