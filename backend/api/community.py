"""Community Feedback ("Đồng kiến tạo") — contributions, voting, leaderboard, moderation.

Per normal_feature_SPEC_2.0.md: users submit a markdown `contribution` (optionally
linked to one of their saved reviews); an admin approves/rejects it; approved
contributions are votable (toggle, one vote per user); a `leaderboard` view ranks
users by total votes received. Banned users (`profiles.is_banned`) can't submit or
vote. No comment threads — vote-only, per the spec's own non-goals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client, create_client

from backend.api.reviews import Pagination
from backend.auth.dependencies import get_current_user, optional_user, require_admin
from backend.config import get_settings

router = APIRouter(tags=["community"])
admin_router = APIRouter(prefix="/admin/contributions", tags=["admin", "community"])


# ── DB client ─────────────────────────────────────────────────────────────────

def _db_client(token: str | None = None) -> Client:
    """Supabase client for server-side access.

    Uses the service-role key when configured (bypasses RLS — every query below
    pins user_id/ownership explicitly in Python, mirroring reviews.py's pattern).
    Falls back to anon key (+ user JWT if present) so RLS still protects access
    when no service key is configured.
    """
    settings = get_settings()
    if settings.supabase_service_key:
        return create_client(settings.supabase_url, settings.supabase_service_key)
    client = create_client(settings.supabase_url, settings.supabase_key)
    if token:
        client.postgrest.auth(token)
    return client


def _get_role(db: Client, user_id: str) -> str:
    res = db.table("profiles").select("role").eq("id", user_id).limit(1).execute()
    return res.data[0]["role"] if res.data else "user"


def _is_banned(db: Client, user_id: str) -> bool:
    res = db.table("profiles").select("is_banned").eq("id", user_id).limit(1).execute()
    return bool(res.data and res.data[0].get("is_banned"))


# ── Pydantic models ───────────────────────────────────────────────────────────

class ContributionCreate(BaseModel):
    title: str
    content: str
    review_id: str | None = None


class ContributionUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class ContributionOut(BaseModel):
    id: str
    user_id: str
    author_name: str | None = None
    title: str
    content: str
    review_id: str | None = None
    status: str
    rejection_reason: str | None = None
    total_votes: int = 0
    voted_by_me: bool = False
    created_at: str
    updated_at: str


class ContributionListResponse(BaseModel):
    data: list[ContributionOut]
    pagination: Pagination


class VoteResponse(BaseModel):
    voted: bool
    total_votes: int


class LeaderboardRow(BaseModel):
    user_id: str
    full_name: str | None = None
    avatar_url: str | None = None
    contributions_count: int
    total_votes: int


class RejectRequest(BaseModel):
    reason: str


# ── Shared row-hydration helper ───────────────────────────────────────────────

def _hydrate(db: Client, rows: list[dict], caller_id: str | None) -> list[ContributionOut]:
    """Attach author_name + total_votes + voted_by_me to raw contribution rows."""
    if not rows:
        return []

    ids = [r["id"] for r in rows]
    user_ids = list({r["user_id"] for r in rows})

    profiles = db.table("profiles").select("id,full_name").in_("id", user_ids).execute().data or []
    names = {p["id"]: p.get("full_name") for p in profiles}

    votes = db.table("contribution_votes").select("contribution_id,user_id").in_("contribution_id", ids).execute().data or []
    counts: dict[str, int] = {}
    my_votes: set[str] = set()
    for v in votes:
        cid = v["contribution_id"]
        counts[cid] = counts.get(cid, 0) + 1
        if caller_id and v["user_id"] == caller_id:
            my_votes.add(cid)

    return [
        ContributionOut(
            id=r["id"],
            user_id=r["user_id"],
            author_name=names.get(r["user_id"]),
            title=r["title"],
            content=r["content"],
            review_id=r.get("review_id"),
            status=r["status"],
            rejection_reason=r.get("rejection_reason"),
            total_votes=counts.get(r["id"], 0),
            voted_by_me=r["id"] in my_votes,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/contributions", response_model=ContributionListResponse)
async def list_contributions(
    sort: Literal["new", "top"] = Query(default="new"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    user: Any | None = Depends(optional_user),
):
    """List approved contributions, sorted by newest or by total votes."""
    db = _db_client()
    rows = db.table("contributions").select("*").eq("status", "approved").execute().data or []

    out = _hydrate(db, rows, str(user.id) if user else None)
    out.sort(key=lambda c: c.total_votes if sort == "top" else c.created_at, reverse=True)

    total = len(out)
    offset = (page - 1) * limit
    page_items = out[offset : offset + limit]

    return ContributionListResponse(
        data=page_items,
        pagination=Pagination(page=page, limit=limit, total=total, has_more=(offset + limit) < total),
    )


@router.post("/contributions", response_model=ContributionOut, status_code=201)
async def create_contribution(
    body: ContributionCreate,
    user: Any = Depends(get_current_user),
):
    """Submit a new contribution — always created with status=pending."""
    db = _db_client()
    if _is_banned(db, str(user.id)):
        raise HTTPException(status_code=403, detail="Your account has been banned from contributing.")

    res = (
        db.table("contributions")
        .insert({
            "user_id": str(user.id),
            "title": body.title,
            "content": body.content,
            "review_id": body.review_id,
        })
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to submit contribution")
    return _hydrate(db, [res.data[0]], str(user.id))[0]


@router.get("/contributions/{contribution_id}", response_model=ContributionOut)
async def get_contribution(
    contribution_id: str,
    user: Any | None = Depends(optional_user),
):
    """Fetch a single contribution — public if approved, owner/admin otherwise."""
    db = _db_client()
    res = db.table("contributions").select("*").eq("id", contribution_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Contribution not found")

    row = res.data[0]
    if row["status"] != "approved":
        is_owner = user and str(user.id) == row["user_id"]
        is_admin = user and _get_role(db, str(user.id)) == "admin"
        if not (is_owner or is_admin):
            raise HTTPException(status_code=404, detail="Contribution not found")

    return _hydrate(db, [row], str(user.id) if user else None)[0]


@router.patch("/contributions/{contribution_id}", response_model=ContributionOut)
async def update_contribution(
    contribution_id: str,
    body: ContributionUpdate,
    user: Any = Depends(get_current_user),
):
    """Edit title/content — owner only, and only while still pending."""
    if body.title is None and body.content is None:
        raise HTTPException(status_code=422, detail="Provide at least one field to update")

    db = _db_client()
    patch: dict = {}
    if body.title is not None:
        patch["title"] = body.title
    if body.content is not None:
        patch["content"] = body.content

    res = (
        db.table("contributions")
        .update(patch)
        .eq("id", contribution_id)
        .eq("user_id", str(user.id))
        .eq("status", "pending")
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Contribution not found, not owned by you, or no longer pending")
    return _hydrate(db, [res.data[0]], str(user.id))[0]


@router.delete("/contributions/{contribution_id}", status_code=204)
async def delete_contribution(
    contribution_id: str,
    user: Any = Depends(get_current_user),
):
    """Delete a contribution — owner or admin."""
    db = _db_client()
    is_admin = _get_role(db, str(user.id)) == "admin"

    query = db.table("contributions").delete().eq("id", contribution_id)
    if not is_admin:
        query = query.eq("user_id", str(user.id))
    res = query.execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Contribution not found")


@router.post("/contributions/{contribution_id}/vote", response_model=VoteResponse)
async def toggle_vote(
    contribution_id: str,
    user: Any = Depends(get_current_user),
):
    """Toggle vote: not yet voted -> insert; already voted -> delete."""
    db = _db_client()
    if _is_banned(db, str(user.id)):
        raise HTTPException(status_code=403, detail="Your account has been banned from voting.")

    contrib = db.table("contributions").select("user_id,status").eq("id", contribution_id).limit(1).execute()
    if not contrib.data:
        raise HTTPException(status_code=404, detail="Contribution not found")
    row = contrib.data[0]
    if row["status"] != "approved":
        raise HTTPException(status_code=403, detail="This contribution is not open for voting")
    if row["user_id"] == str(user.id):
        raise HTTPException(status_code=403, detail="You can't vote on your own contribution")

    existing = (
        db.table("contribution_votes")
        .select("id")
        .eq("contribution_id", contribution_id)
        .eq("user_id", str(user.id))
        .execute()
    )

    if existing.data:
        db.table("contribution_votes").delete().eq("id", existing.data[0]["id"]).execute()
        voted = False
    else:
        db.table("contribution_votes").insert({"contribution_id": contribution_id, "user_id": str(user.id)}).execute()
        voted = True

    count_res = (
        db.table("contribution_votes")
        .select("id", count="exact")
        .eq("contribution_id", contribution_id)
        .execute()
    )
    return VoteResponse(voted=voted, total_votes=count_res.count or 0)


@router.get("/leaderboard", response_model=list[LeaderboardRow])
async def get_leaderboard(limit: int = Query(default=20, ge=1, le=100)):
    """Top contributors ranked by total votes received (all-time)."""
    db = _db_client()
    rows = (
        db.table("leaderboard")
        .select("*")
        .order("total_votes", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    return [LeaderboardRow(**r) for r in rows]


# ── Admin moderation endpoints ────────────────────────────────────────────────

@admin_router.get("", response_model=ContributionListResponse)
async def admin_list_contributions(
    status: Literal["pending", "approved", "rejected"] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: Any = Depends(require_admin),
):
    """Moderation queue — all statuses by default, or filtered."""
    db = _db_client()
    query = db.table("contributions").select("*")
    if status:
        query = query.eq("status", status)
    rows = query.order("created_at", desc=True).execute().data or []

    out = _hydrate(db, rows, None)
    total = len(out)
    offset = (page - 1) * limit
    page_items = out[offset : offset + limit]

    return ContributionListResponse(
        data=page_items,
        pagination=Pagination(page=page, limit=limit, total=total, has_more=(offset + limit) < total),
    )


@admin_router.post("/{contribution_id}/approve", response_model=ContributionOut)
async def approve_contribution(
    contribution_id: str,
    admin: Any = Depends(require_admin),
):
    db = _db_client()
    res = (
        db.table("contributions")
        .update({
            "status": "approved",
            "reviewed_by": str(admin.id),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", contribution_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return _hydrate(db, [res.data[0]], None)[0]


@admin_router.post("/{contribution_id}/reject", response_model=ContributionOut)
async def reject_contribution(
    contribution_id: str,
    body: RejectRequest,
    admin: Any = Depends(require_admin),
):
    db = _db_client()
    res = (
        db.table("contributions")
        .update({
            "status": "rejected",
            "rejection_reason": body.reason,
            "reviewed_by": str(admin.id),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", contribution_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return _hydrate(db, [res.data[0]], None)[0]
