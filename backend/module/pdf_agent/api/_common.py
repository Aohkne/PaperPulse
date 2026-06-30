"""Shared auth/ownership helpers for PDF Agent endpoints.

PDFAgentState carries `user_id` (set at upload time) so every other endpoint
can verify the requesting user owns `doc_id` before reading/mutating its
checkpoint — the SPEC/PLAN docs treat PDF Agent as a single-user local module
with no auth model at all, but this app requires a Supabase JWT on every
other endpoint, so the same is enforced here.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.security import HTTPBearer

from backend.module.pdf_agent.graph.graph import get_pdf_agent_graph
from backend.module.pdf_agent.graph.state import PDFAgentState

bearer = HTTPBearer(auto_error=True)


def pdf_agent_config(doc_id: str) -> dict:
    return {"configurable": {"thread_id": doc_id}}


async def load_owned_state(doc_id: str, user) -> PDFAgentState:
    """Fetch the checkpointed PDFAgentState for doc_id — 404 if missing or not owned by user,
    409 if the P0→P4 pipeline hasn't reached render_bundle yet (e.g. still running, or it
    errored out partway through parse_document/batch_analysis) — every endpoint that calls
    this needs `main_tex_path` to exist, so fail clearly here instead of a bare KeyError 500
    downstream.
    """
    graph = await get_pdf_agent_graph()
    state = await graph.aget_state(pdf_agent_config(doc_id))
    if not state.values or state.values.get("user_id") != str(user.id):
        raise HTTPException(status_code=404, detail="Document not found")
    if "main_tex_path" not in state.values:
        raise HTTPException(
            status_code=409, detail="Document is still processing or failed to parse — please re-upload"
        )
    return state.values
