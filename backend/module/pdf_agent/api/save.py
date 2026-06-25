"""POST /api/pdf-agent/{doc_id}/save — Step P6, and /resume/{review_id} (PLAN §6, §9 gap #8).

Save calls the reviews insert logic directly (service layer, no HTTP loopback —
PLAN §6: "Gọi thẳng service layer của reviews"). Resume is the read path back:
load a previously-saved 'uploaded' review and rehydrate a fresh PDFAgentState
checkpoint so the editor can reopen exactly where the user left off.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from backend.api.reviews import _authed_client, insert_review_row
from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.module.pdf_agent.api._common import bearer, load_owned_state, pdf_agent_config
from backend.module.pdf_agent.graph.graph import get_pdf_agent_graph
from backend.module.pdf_agent.services import bundle_exporter
from backend.module.pdf_agent.services.text_quote_selector import refind_anchor

router = APIRouter(prefix="/pdf-agent", tags=["pdf-agent"])


class SaveRequest(BaseModel):
    title: str
    tex_content: str | None = None  # live editor buffer — overrides the server's copy if given


@router.post("/{doc_id}/save")
async def save_to_review(
    doc_id: str,
    body: SaveRequest,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    state = await load_owned_state(doc_id, user)
    main_tex_path = Path(state["main_tex_path"])
    if body.tex_content is not None:
        main_tex_path.write_text(body.tex_content, encoding="utf-8")
    tex_content = main_tex_path.read_text(encoding="utf-8")
    pending = [a for a in (state.get("annotations") or []) if a["status"] == "pending"]

    db = _authed_client(credentials.credentials)
    row = insert_review_row(
        db,
        user_id=str(user.id),
        title=body.title,
        markdown_content=tex_content,
        query=None,
        source_type="uploaded",
        content_format="tex",
        pending_annotations=pending,
    )

    graph = await get_pdf_agent_graph()
    await graph.aupdate_state(pdf_agent_config(doc_id), {"review_id": row["id"]})
    return {"id": row["id"], "title": row["title"], "created_at": row["created_at"]}


@router.post("/resume/{review_id}")
async def resume_from_review(
    review_id: str,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    """Rehydrate a fresh doc_id from a saved 'uploaded' review so the Monaco editor can
    reopen it. Annotations are re-anchored against the saved content via refind_anchor() —
    any that no longer match (the user edited that spot, or saved before this endpoint
    existed) are dropped rather than shown at a wrong position.

    Known limitation (not solved here): figure image files aren't stored in `reviews`
    (only the .tex text is), so re-opened documents lose any embedded figures unless the
    original doc_id's output directory still happens to exist on disk.
    """
    db = _authed_client(credentials.credentials)
    res = (
        db.table("reviews")
        .select("title, markdown_content, content_format, source_type, pending_annotations")
        .eq("id", review_id)
        .eq("user_id", str(user.id))
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(404, "Review không tồn tại")
    row = res.data
    if row["source_type"] != "uploaded" or row["content_format"] != "tex":
        raise HTTPException(400, "Review này không phải document upload từ PDF Agent")

    settings = get_settings()
    doc_id = str(uuid4())
    doc_dir = Path(settings.pdf_agent_output_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    main_tex_path = doc_dir / "main.tex"
    main_tex_path.write_text(row["markdown_content"], encoding="utf-8")

    annotations = []
    for a in row.get("pending_annotations") or []:
        if refind_anchor(row["markdown_content"], a["anchor"]) is not None:
            annotations.append(a)

    figures_dir = doc_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    bundle_path = doc_dir / "bundle.zip"
    bundle_exporter.rezip_bundle(str(main_tex_path), str(figures_dir), str(bundle_path))

    graph = await get_pdf_agent_graph()
    config = pdf_agent_config(doc_id)
    await graph.aupdate_state(config, {
        "doc_id": doc_id,
        "user_id": str(user.id),
        "input_format": "tex",
        "raw_file_path": str(main_tex_path),
        "sections": [],
        "raw_citations": [],
        "figures": [],
        "bundle_path": str(bundle_path),
        "main_tex_path": str(main_tex_path),
        "annotations": annotations,
        "review_id": review_id,
    })
    return {"doc_id": doc_id, "title": row["title"], "annotations": annotations}
