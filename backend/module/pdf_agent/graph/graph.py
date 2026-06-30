"""PDF Agent — LangGraph `StateGraph` assembly (PLAN §3).

Graph riêng, KHÔNG chung `ResearchState`/checkpointer với research_agent —
Postgres schema riêng (`pdf_agent_checkpoints`) để tránh lẫn `thread_id` giữa
2 domain khác nhau (session nghiên cứu vs document upload).

KHÔNG có `interrupt_before`: P0→P4 chạy 1 lần xong hết, user tương tác
(accept/reject/dismiss/explain/rewrite) với *kết quả đã có* sau đó qua các
endpoint riêng dùng `graph.aupdate_state()` — không phải `resume()`.
"""

from __future__ import annotations

import asyncio

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.config import get_settings
from backend.module.pdf_agent.graph.nodes.batch_analysis import batch_analysis_node
from backend.module.pdf_agent.graph.nodes.build_annotations import build_annotations_node
from backend.module.pdf_agent.graph.nodes.format_detect import format_detect_node
from backend.module.pdf_agent.graph.nodes.parse_document import parse_document_node
from backend.module.pdf_agent.graph.nodes.render_bundle import render_bundle_node
from backend.module.pdf_agent.graph.state import PDFAgentState

_SEQUENCE = [
    ("format_detect", format_detect_node),  # Step P0
    ("parse_document", parse_document_node),  # Step P1
    ("render_bundle", render_bundle_node),  # Step P2
    ("batch_analysis", batch_analysis_node),  # Step P3
    ("build_annotations", build_annotations_node),  # Step P4
]


def build_pdf_agent_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    g = StateGraph(PDFAgentState)
    for name, node in _SEQUENCE:
        g.add_node(name, node)

    g.set_entry_point(_SEQUENCE[0][0])
    for (src, _), (dst, _) in zip(_SEQUENCE, _SEQUENCE[1:]):
        g.add_edge(src, dst)
    g.add_edge(_SEQUENCE[-1][0], END)

    return g.compile(checkpointer=checkpointer)


async def _open_checkpointer() -> BaseCheckpointSaver:
    """Postgres-backed checkpointer (Supabase) — own schema
    (`pdf_agent_checkpoints`) so its thread_id namespace can never collide
    with research_agent's checkpointer (same isolation intent as the old
    separate SQLite file, see module docstring above)."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

    settings = get_settings()
    pool = AsyncConnectionPool(
        conninfo=settings.supabase_db_url,
        max_size=10,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,  # Supavisor transaction-mode pooler doesn't support prepared statements
            "options": "-c search_path=pdf_agent_checkpoints,public",
        },
    )
    await pool.open()
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver


_graph_singleton: CompiledStateGraph | None = None
_graph_lock = asyncio.Lock()


async def get_pdf_agent_graph() -> CompiledStateGraph:
    global _graph_singleton
    if _graph_singleton is not None:
        return _graph_singleton
    async with _graph_lock:
        if _graph_singleton is None:
            checkpointer = await _open_checkpointer()
            _graph_singleton = build_pdf_agent_graph(checkpointer)
        return _graph_singleton
