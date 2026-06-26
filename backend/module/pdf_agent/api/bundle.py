"""GET /api/pdf-agent/{doc_id}/bundle — download current `.zip` (main.tex + figures/), PLAN §6."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.module.pdf_agent.api._common import bearer, load_owned_state
from backend.module.pdf_agent.services import bundle_exporter
from backend.shared.services.latex_render import latex_to_pdf

router = APIRouter(prefix="/pdf-agent", tags=["pdf-agent"])

_TITLE_RE = re.compile(r"\\title\{(.*?)\}", re.S)


class ContentSyncRequest(BaseModel):
    tex_content: str


@router.get("/{doc_id}/bundle")
async def get_bundle(
    doc_id: str,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    state = await load_owned_state(doc_id, user)
    figures_dir = str(Path(state["main_tex_path"]).parent / "figures")
    bundle_exporter.rezip_bundle(state["main_tex_path"], figures_dir, state["bundle_path"])
    return FileResponse(state["bundle_path"], media_type="application/zip", filename=f"{doc_id}.zip")


@router.get("/{doc_id}/export")
async def export_doc(
    doc_id: str,
    format: str = Query(default="zip", pattern="^(tex|pdf|zip)$"),
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    """Export the current document as .tex, .pdf, or .zip — same format trio as
    Reviews' /export, so My Reviews and PDF Agent download consistently."""
    state = await load_owned_state(doc_id, user)
    main_tex_path = Path(state["main_tex_path"])
    content = main_tex_path.read_text(encoding="utf-8")

    if format == "tex":
        return Response(
            content=content.encode("utf-8"),
            media_type="text/x-tex",
            headers={"Content-Disposition": f'attachment; filename="{doc_id}.tex"'},
        )

    if format == "pdf":
        title_match = _TITLE_RE.search(content)
        title = title_match.group(1).strip() if title_match else doc_id
        try:
            pdf_bytes = latex_to_pdf(title, content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to render PDF: {e}") from e
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{doc_id}.pdf"'},
        )

    figures_dir = str(main_tex_path.parent / "figures")
    bundle_exporter.rezip_bundle(str(main_tex_path), figures_dir, state["bundle_path"])
    return FileResponse(state["bundle_path"], media_type="application/zip", filename=f"{doc_id}.zip")


@router.get("/{doc_id}/content")
async def get_content(
    doc_id: str,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    state = await load_owned_state(doc_id, user)
    tex_content = Path(state["main_tex_path"]).read_text(encoding="utf-8")
    return {"tex_content": tex_content}


@router.put("/{doc_id}/content")
async def sync_content(
    doc_id: str,
    body: ContentSyncRequest,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    """Push the live editor buffer (free-form typing) to the server's main.tex.

    Not part of the original PLAN endpoint list — added because Accept/Apply/Save all
    mutate or read the server's copy of main.tex, and a real editable Monaco buffer
    needs a way to persist plain user edits before those operations run, otherwise
    free-typed changes would be silently lost on the next Accept/Apply/Save.
    """
    state = await load_owned_state(doc_id, user)
    main_tex_path = Path(state["main_tex_path"])
    main_tex_path.write_text(body.tex_content, encoding="utf-8")
    bundle_exporter.rezip_bundle(str(main_tex_path), str(main_tex_path.parent / "figures"), state["bundle_path"])
    return {"tex_content": body.tex_content}
