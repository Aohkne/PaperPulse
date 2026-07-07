"""CRUD endpoints for saved Literature Reviews — POST /api/reviews, GET, PATCH, DELETE, export, duplicate."""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.shared.services.latex_render import latex_to_markdown, latex_to_pdf
from supabase import Client, create_client

router = APIRouter(prefix="/reviews", tags=["reviews"])

_bearer = HTTPBearer(auto_error=True)


# ── Supabase client authenticated with user JWT (for RLS) ────────────────────


def _authed_client(token: str) -> Client:
    """Create a Supabase client for server-side DB access.

    Uses service role key when configured (bypasses RLS; safe because
    user identity is already verified by get_current_user and user_id is
    always pinned explicitly in every query). Falls back to anon key + user
    JWT so RLS policies apply if service key is absent.
    """
    settings = get_settings()
    if settings.supabase_service_key:
        return create_client(settings.supabase_url, settings.supabase_service_key)
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.auth(token)
    return client


# ── Pydantic models ───────────────────────────────────────────────────────────
# `markdown_content` holds LaTeX source (field/column kept as-is to avoid a DB migration).
# source_type/content_format/pending_annotations: added for PDF Agent Step P6 — 'uploaded'
# reviews (from PDF Agent) have no original research `query` and may carry unresolved
# annotations so the editor can resume where the user left off.


class ReviewCreate(BaseModel):
    title: str
    query: str | None = None
    markdown_content: str
    source_type: Literal["generated", "uploaded"] = "generated"
    content_format: Literal["markdown", "tex"] = "markdown"
    pending_annotations: list[dict] | None = None


class ReviewUpdate(BaseModel):
    title: str | None = None
    markdown_content: str | None = None


class ReviewSummary(BaseModel):
    id: str
    title: str
    query: str | None = None
    source_type: str = "generated"
    content_format: str = "markdown"
    created_at: str
    updated_at: str


class ReviewFull(ReviewSummary):
    markdown_content: str
    pending_annotations: list[dict] | None = None


class ReviewCreated(BaseModel):
    id: str
    title: str
    created_at: str


class Pagination(BaseModel):
    page: int
    limit: int
    total: int
    has_more: bool


class ReviewListResponse(BaseModel):
    data: list[ReviewSummary]
    pagination: Pagination


class DuplicateRequest(BaseModel):
    title: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slug(title: str) -> str:
    """Slugify a title for use as a filename.

    Transliterates to ASCII first since Content-Disposition headers are
    latin-1 only — accented titles (e.g. Vietnamese) would otherwise crash
    the response with a UnicodeEncodeError.
    """
    title = title.replace("Đ", "D").replace("đ", "d")
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")[:80]
    return slug or "review"


def _row_to_summary(row: dict) -> ReviewSummary:
    return ReviewSummary(
        id=row["id"],
        title=row["title"],
        query=row.get("query"),
        source_type=row.get("source_type", "generated"),
        content_format=row.get("content_format", "markdown"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_full(row: dict) -> ReviewFull:
    return ReviewFull(
        id=row["id"],
        title=row["title"],
        query=row.get("query"),
        source_type=row.get("source_type", "generated"),
        content_format=row.get("content_format", "markdown"),
        markdown_content=row["markdown_content"],
        pending_annotations=row.get("pending_annotations"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def insert_review_row(
    db: Client,
    user_id: str,
    title: str,
    markdown_content: str,
    query: str | None = None,
    source_type: str = "generated",
    content_format: str = "markdown",
    pending_annotations: list[dict] | None = None,
) -> dict:
    """Shared insert path for both POST /reviews and PDF Agent's save-to-review (Step P6).

    PDF Agent calls this directly with its own already-authed `db` client — no HTTP
    loopback to this router, just the same insert logic (PLAN §6 "gọi thẳng service
    layer của reviews").
    """
    res = (
        db.table("reviews")
        .insert(
            {
                "user_id": user_id,
                "title": title,
                "query": query,
                "markdown_content": markdown_content,
                "source_type": source_type,
                "content_format": content_format,
                "pending_annotations": pending_annotations,
            }
        )
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to save review")
    return res.data[0]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("", response_model=ReviewCreated, status_code=201)
async def create_review(
    body: ReviewCreate,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """Save a completed Literature Review from Step ⑩ (or, with source_type="uploaded", a
    PDF Agent document — Step P6)."""
    db = _authed_client(credentials.credentials)
    row = insert_review_row(
        db,
        user_id=str(user.id),
        title=body.title,
        markdown_content=body.markdown_content,
        query=body.query,
        source_type=body.source_type,
        content_format=body.content_format,
        pending_annotations=body.pending_annotations,
    )
    return ReviewCreated(id=row["id"], title=row["title"], created_at=row["created_at"])


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=5, ge=1, le=50),
    search: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """List saved reviews for the authenticated user (newest first). Supports pagination and title search."""
    db = _authed_client(credentials.credentials)
    offset = (page - 1) * limit

    query = (
        db.table("reviews")
        .select("id, title, query, source_type, content_format, created_at, updated_at", count="exact")
        .eq("user_id", str(user.id))
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if search:
        query = query.ilike("title", f"%{search}%")

    res = query.execute()
    total = res.count or 0
    rows = res.data or []

    return ReviewListResponse(
        data=[_row_to_summary(r) for r in rows],
        pagination=Pagination(
            page=page,
            limit=limit,
            total=total,
            has_more=(offset + limit) < total,
        ),
    )


@router.get("/{review_id}", response_model=ReviewFull)
async def get_review(
    review_id: str,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """Fetch a single review with full markdown content."""
    db = _authed_client(credentials.credentials)
    res = db.table("reviews").select("*").eq("id", review_id).eq("user_id", str(user.id)).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Review not found")
    return _row_to_full(res.data)


@router.patch("/{review_id}", response_model=ReviewFull)
async def update_review(
    review_id: str,
    body: ReviewUpdate,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """Edit title and/or markdown content of a saved review."""
    if body.title is None and body.markdown_content is None:
        raise HTTPException(status_code=422, detail="Provide at least one field to update")

    db = _authed_client(credentials.credentials)
    patch: dict = {}
    if body.title is not None:
        patch["title"] = body.title
    if body.markdown_content is not None:
        patch["markdown_content"] = body.markdown_content

    res = db.table("reviews").update(patch).eq("id", review_id).eq("user_id", str(user.id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Review not found")
    return _row_to_full(res.data[0])


@router.delete("/{review_id}", status_code=204)
async def delete_review(
    review_id: str,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """Delete a saved review."""
    db = _authed_client(credentials.credentials)
    res = db.table("reviews").delete().eq("id", review_id).eq("user_id", str(user.id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Review not found")


@router.get("/{review_id}/export")
async def export_review(
    review_id: str,
    format: str = Query(default="tex", pattern="^(tex|markdown|pdf|zip)$"),
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """Export a review's LaTeX source as .tex, .md, .pdf, or .zip (same format trio
    PDF Agent's /export offers, so both features download consistently)."""
    db = _authed_client(credentials.credentials)
    res = (
        db.table("reviews")
        .select("title, markdown_content")
        .eq("id", review_id)
        .eq("user_id", str(user.id))
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Review not found")

    title = res.data["title"]
    content = res.data["markdown_content"]
    filename = _slug(title)

    if format == "tex":
        return Response(
            content=content.encode("utf-8"),
            media_type="text/x-tex",
            headers={"Content-Disposition": f'attachment; filename="{filename}.tex"'},
        )

    if format == "markdown":
        return Response(
            content=latex_to_markdown(content).encode("utf-8"),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )

    if format == "zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{filename}.tex", content)
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}.zip"'},
        )

    # PDF via fpdf2
    try:
        pdf_bytes = latex_to_pdf(title, content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render PDF: {e}") from e
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )


@router.post("/{review_id}/duplicate", response_model=ReviewCreated, status_code=201)
async def duplicate_review(
    review_id: str,
    body: DuplicateRequest | None = None,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """Create a copy of a review with a new title."""
    db = _authed_client(credentials.credentials)
    src = (
        db.table("reviews")
        .select("title, query, markdown_content")
        .eq("id", review_id)
        .eq("user_id", str(user.id))
        .single()
        .execute()
    )
    if not src.data:
        raise HTTPException(status_code=404, detail="Review not found")

    new_title = (body.title if body and body.title else None) or f"{src.data['title']} (Copy)"
    res = (
        db.table("reviews")
        .insert(
            {
                "user_id": str(user.id),
                "title": new_title,
                "query": src.data["query"],
                "markdown_content": src.data["markdown_content"],
            }
        )
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=500, detail="Duplicate failed")
    row = res.data[0]
    return ReviewCreated(id=row["id"], title=row["title"], created_at=row["created_at"])
