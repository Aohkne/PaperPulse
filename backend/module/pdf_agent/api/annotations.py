"""GET/PATCH /api/pdf-agent/{doc_id}/annotations — Step P4 review actions (PLAN §6)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.module.pdf_agent.api._common import bearer, load_owned_state, pdf_agent_config
from backend.module.pdf_agent.graph.graph import get_pdf_agent_graph
from backend.module.pdf_agent.services import bundle_exporter
from backend.module.pdf_agent.services.text_quote_selector import refind_anchor

router = APIRouter(prefix="/pdf-agent", tags=["pdf-agent"])

_ACTION_TO_STATUS = {"accept": "accepted", "reject": "rejected", "dismiss": "dismissed"}


class AnnotationUpdate(BaseModel):
    action: Literal["accept", "reject", "dismiss"]


@router.get("/{doc_id}/annotations")
async def list_annotations(
    doc_id: str,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    state = await load_owned_state(doc_id, user)
    return {"annotations": state.get("annotations") or []}


@router.patch("/{doc_id}/annotations/{annotation_id}")
async def update_annotation(
    doc_id: str,
    annotation_id: str,
    body: AnnotationUpdate,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    user=Depends(get_current_user),
):
    state = await load_owned_state(doc_id, user)
    annotations = state.get("annotations") or []
    target = next((a for a in annotations if a["id"] == annotation_id), None)
    if target is None:
        raise HTTPException(404, "Annotation not found")

    if target["type"] == "warning" and body.action == "accept":
        # Hard invariant (Non-goals): warning never has an Accept affordance — there's
        # no "correct fix" for a fake/broken citation to silently apply.
        raise HTTPException(400, "Warnings have no Accept action — Dismiss only")

    main_tex_path = Path(state["main_tex_path"])
    tex_content = main_tex_path.read_text(encoding="utf-8")

    if body.action == "accept":
        offset = refind_anchor(tex_content, target["anchor"])
        if offset is None:
            raise HTTPException(409, "This passage was edited and its position couldn't be found — please dismiss and edit it manually")
        exact = target["anchor"]["exact"]
        tex_content = tex_content[:offset] + (target["suggested_fix"] or "") + tex_content[offset + len(exact):]
        main_tex_path.write_text(tex_content, encoding="utf-8")
        bundle_exporter.rezip_bundle(str(main_tex_path), str(main_tex_path.parent / "figures"), state["bundle_path"])

    new_status = _ACTION_TO_STATUS[body.action]
    new_annotations = [
        {**a, "status": new_status} if a["id"] == annotation_id else a for a in annotations
    ]
    graph = await get_pdf_agent_graph()
    await graph.aupdate_state(pdf_agent_config(doc_id), {"annotations": new_annotations})
    return {"id": annotation_id, "status": new_status, "tex_content": tex_content}
