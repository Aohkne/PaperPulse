"""CRUD endpoints for saved Literature Reviews — POST /api/reviews, GET, PATCH, DELETE, export, duplicate."""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.shared.services.latex_utils import unescape_latex
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
    """Slugify a title for use as a filename."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    return re.sub(r"[\s_-]+", "-", slug).strip("-")[:80]


# fpdf2's multi_cell raises FPDFException ("Not enough horizontal space to render
# a single character") when one unbroken run of non-space characters is wider than
# the page — common with bare DOI/arXiv URLs in citations. fpdf2 honors the
# soft-hyphen character (U+00AD) as a word-break hint, so sprinkle one into any
# long unbroken token to give it somewhere to wrap instead of crashing the export.
_LONG_TOKEN_RE = re.compile(r"\S{61,}")


def _break_long_token(match: re.Match) -> str:
    token = match.group(0)
    return "\u00ad".join(token[i : i + 60] for i in range(0, len(token), 60))


def _sanitize(text: str) -> str:
    """Replace common Unicode chars that Latin-1 fonts can't render, and break up
    unbroken long tokens (e.g. DOI/arXiv URLs) so fpdf2 can wrap them."""
    _MAP = {
        "–": "-", "—": "--", "‘": "'", "’": "'",
        "“": '"', "”": '"', "…": "...", "•": "-",
        "·": "*", "→": "->", "←": "<-", "≤": "<=",
        "≥": ">=", "×": "x", "÷": "/", "α": "alpha",
        "β": "beta", "γ": "gamma", "δ": "delta",
    }
    for src, dst in _MAP.items():
        text = text.replace(src, dst)
    text = _LONG_TOKEN_RE.sub(_break_long_token, text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ── LaTeX parsing (best-effort — not a full TeX engine) ──────────────────────

_INLINE_RE = re.compile(
    r"\\href\{(?P<href_url>[^{}]*)\}\{(?P<href_text>[^{}]*)\}"
    r"|\\cite[tp]?\{(?P<cite>[^{}]*)\}"
    r"|\\textbf\{(?P<bf>[^{}]*)\}"
    r"|\\textit\{(?P<it>[^{}]*)\}"
    r"|\\emph\{(?P<emph>[^{}]*)\}"
    r"|\$(?P<math1>[^$]+)\$"
    r"|\\\((?P<math2>.+?)\\\)"
    r"|\\\\"
    # Markdown fallback (legacy content saved before the LaTeX migration)
    r"|\*\*(?P<mdbf>[^*]+)\*\*"
    r"|\*(?P<mdit>[^*]+)\*"
    r"|__(?P<mdbf2>[^_]+)__"
    r"|`(?P<mdcode>[^`]+)`"
    r"|\[(?P<mdlinktext>[^\]]+)\]\((?P<mdlinkurl>[^)]+)\)"
)


def _inline_to_plain(text: str) -> str:
    """Render inline LaTeX markup as plain text (for the fpdf2 PDF renderer)."""
    def repl(m: re.Match) -> str:
        if m.lastgroup == "href_text":
            return f"{m.group('href_text')} ({m.group('href_url')})"
        if m.lastgroup == "mdlinktext":
            return f"{m.group('mdlinktext')} ({m.group('mdlinkurl')})"
        if m.lastgroup == "cite":
            return f"({m.group('cite')})"
        if m.lastgroup in ("bf", "it", "emph", "math1", "math2", "mdbf", "mdbf2", "mdit", "mdcode"):
            return m.group(m.lastgroup)
        return " "  # \\ line break

    return unescape_latex(_INLINE_RE.sub(repl, text))


def _inline_to_markdown(text: str) -> str:
    """Render inline LaTeX markup as Markdown."""
    def repl(m: re.Match) -> str:
        if m.lastgroup == "href_text":
            return f"[{m.group('href_text')}]({m.group('href_url')})"
        if m.lastgroup == "mdlinktext":
            return f"[{m.group('mdlinktext')}]({m.group('mdlinkurl')})"
        if m.lastgroup == "cite":
            return f"({m.group('cite')})"
        if m.lastgroup in ("bf", "mdbf", "mdbf2"):
            return f"**{m.group(m.lastgroup)}**"
        if m.lastgroup in ("it", "emph", "mdit"):
            return f"*{m.group(m.lastgroup)}*"
        if m.lastgroup == "mdcode":
            return f"`{m.group('mdcode')}`"
        if m.lastgroup in ("math1", "math2"):
            return f"${m.group(m.lastgroup)}$"
        return "  \n"  # \\ line break

    return unescape_latex(_INLINE_RE.sub(repl, text))


def _parse_latex_body(content: str) -> list[tuple[str, object]]:
    """Split .tex source into a sequence of (kind, data) blocks for rendering.

    kind is one of: h1, h2, h3, item, item_num, quote_start, quote_end,
    verbatim, hr, blank, para.
    """
    body_match = re.search(r"\\begin\{document\}(.*)\\end\{document\}", content, re.S)
    body = body_match.group(1) if body_match else content

    blocks: list[tuple[str, object]] = []
    list_stack: list[str] = []
    enum_counters: list[int] = []
    in_verbatim = False

    for raw_line in body.split("\n"):
        line = raw_line.strip()

        if in_verbatim:
            if line == r"\end{verbatim}":
                in_verbatim = False
            else:
                blocks.append(("verbatim", raw_line))
            continue

        if not line:
            blocks.append(("blank", ""))
            continue
        if line.startswith("%"):
            continue
        if line in (r"\maketitle",) or re.match(r"^\\(title|author|date)\{", line):
            continue
        if re.match(r"^\\(documentclass|usepackage)\b", line) or line in (r"\begin{document}", r"\end{document}"):
            continue
        if line == r"\begin{verbatim}":
            in_verbatim = True
            continue

        m = re.match(r"\\section\*?\{(.*)\}\s*$", line)
        if m:
            blocks.append(("h1", m.group(1)))
            continue
        m = re.match(r"\\subsection\*?\{(.*)\}\s*$", line)
        if m:
            blocks.append(("h2", m.group(1)))
            continue
        m = re.match(r"\\subsubsection\*?\{(.*)\}\s*$", line)
        if m:
            blocks.append(("h3", m.group(1)))
            continue

        # Markdown fallback (legacy content saved before the LaTeX migration)
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            kind = {1: "h1", 2: "h2"}.get(len(m.group(1)), "h3")
            blocks.append((kind, m.group(2)))
            continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            blocks.append(("mdquote", m.group(1)))
            continue

        if line == r"\begin{itemize}":
            list_stack.append("itemize")
            continue
        if line == r"\begin{enumerate}":
            list_stack.append("enumerate")
            enum_counters.append(0)
            continue
        if line == r"\end{itemize}":
            if list_stack and list_stack[-1] == "itemize":
                list_stack.pop()
            continue
        if line == r"\end{enumerate}":
            if list_stack and list_stack[-1] == "enumerate":
                list_stack.pop()
                enum_counters.pop()
            continue
        if line == r"\begin{quote}":
            blocks.append(("quote_start", ""))
            continue
        if line == r"\end{quote}":
            blocks.append(("quote_end", ""))
            continue

        m = re.match(r"\\item\s*(.*)$", line)
        if m:
            text = m.group(1)
            if list_stack and list_stack[-1] == "enumerate":
                enum_counters[-1] += 1
                blocks.append(("item_num", (enum_counters[-1], text)))
            else:
                blocks.append(("item", text))
            continue

        if re.match(r"^[-=]{3,}$", line) or line == r"\hrulefill":
            blocks.append(("hr", ""))
            continue

        m = re.match(r"^[-*+]\s+(.*)$", line)
        if m:
            blocks.append(("item", m.group(1)))
            continue
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m:
            blocks.append(("item_num", (int(m.group(1)), m.group(2))))
            continue

        blocks.append(("para", line))

    return blocks


def _latex_to_pdf(title: str, content: str) -> bytes:
    """Convert LaTeX content to PDF bytes using fpdf2 (best-effort, not a TeX engine)."""
    from fpdf import FPDF  # type: ignore[import]

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    NL = {"new_x": "LMARGIN", "new_y": "NEXT"}  # reset cursor to left margin after each cell

    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 10, _sanitize(title), align="L", **NL)
    pdf.ln(4)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    for kind, data in _parse_latex_body(content):
        if kind == "h1":
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(0, 9, _sanitize(_inline_to_plain(data)), align="L", **NL)
            pdf.ln(1)
        elif kind == "h2":
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 8, _sanitize(_inline_to_plain(data)), align="L", **NL)
            pdf.ln(1)
        elif kind == "h3":
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 7, _sanitize(_inline_to_plain(data)), align="L", **NL)
        elif kind == "hr":
            pdf.ln(2)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)
        elif kind in ("quote_start", "quote_end"):
            continue
        elif kind == "mdquote":
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, "  " + _sanitize(_inline_to_plain(data)), align="L", **NL)
            pdf.set_text_color(0, 0, 0)
        elif kind == "item":
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _sanitize("  * " + _inline_to_plain(data)), align="L", **NL)
        elif kind == "item_num":
            num, text = data
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _sanitize(f"  {num}. " + _inline_to_plain(text)), align="L", **NL)
        elif kind == "verbatim":
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 5, _sanitize(data) or " ", align="L", **NL)
            pdf.set_text_color(0, 0, 0)
        elif kind == "blank":
            pdf.ln(3)
        else:  # para
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _sanitize(_inline_to_plain(data)), align="L", **NL)

    return bytes(pdf.output())


def _latex_to_markdown(content: str) -> str:
    """Convert LaTeX content to Markdown (best-effort)."""
    lines: list[str] = []
    for kind, data in _parse_latex_body(content):
        if kind == "h1":
            lines.append(f"## {_inline_to_markdown(data)}")
        elif kind == "h2":
            lines.append(f"### {_inline_to_markdown(data)}")
        elif kind == "h3":
            lines.append(f"#### {_inline_to_markdown(data)}")
        elif kind == "hr":
            lines.append("---")
        elif kind == "quote_start":
            lines.append("> ")
        elif kind == "quote_end":
            continue
        elif kind == "mdquote":
            lines.append(f"> {_inline_to_markdown(data)}")
        elif kind == "item":
            lines.append(f"- {_inline_to_markdown(data)}")
        elif kind == "item_num":
            num, text = data
            lines.append(f"{num}. {_inline_to_markdown(text)}")
        elif kind == "verbatim":
            lines.append(f"    {data}")
        elif kind == "blank":
            lines.append("")
        else:  # para
            lines.append(_inline_to_markdown(data))

    return "\n".join(lines)


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
        .insert({
            "user_id": user_id,
            "title": title,
            "query": query,
            "markdown_content": markdown_content,
            "source_type": source_type,
            "content_format": content_format,
            "pending_annotations": pending_annotations,
        })
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
    res = (
        db.table("reviews")
        .select("*")
        .eq("id", review_id)
        .eq("user_id", str(user.id))
        .single()
        .execute()
    )
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

    res = (
        db.table("reviews")
        .update(patch)
        .eq("id", review_id)
        .eq("user_id", str(user.id))
        .execute()
    )
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
    res = (
        db.table("reviews")
        .delete()
        .eq("id", review_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Review not found")


@router.get("/{review_id}/export")
async def export_review(
    review_id: str,
    format: str = Query(default="tex", pattern="^(tex|markdown|pdf)$"),
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    """Export a review's LaTeX source as .tex, .md, or .pdf."""
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
            content=_latex_to_markdown(content).encode("utf-8"),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )

    # PDF via fpdf2
    try:
        pdf_bytes = _latex_to_pdf(title, content)
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
