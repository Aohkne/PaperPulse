"""Research Pipeline v2 — LangGraph StateGraph assembly (SPEC 2.0).

Two-node Step 0 for full LLM event streaming:
  intent_router   → classifies intent, thinking tokens stream as "thinking_token"
  reply_generator → generates reply/questions, tokens stream as "reply_token"

Routing after Step 0:
  greeting → reply_generator → END   (natural reply)
  clarify  → reply_generator → END   (clarifying questions; user replies on next POST)
  search   → parallel_search → … → export

Interrupt points:
  plan_review  (Step 0c) — user approves/edits the research plan before search
  outline_gen  (Step ④) — user approves/edits research outline
  route_claims (Step ⑨) — user reviews claim routing before export
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.config import get_settings
from backend.module.research_agent.graph.nodes.build_graph import build_graph_node
from backend.module.research_agent.graph.nodes.dedup import dedup_node
from backend.module.research_agent.graph.nodes.embed import embed_node
from backend.module.research_agent.graph.nodes.export import export_node
from backend.module.research_agent.graph.nodes.extract_claims import extract_claims_node
from backend.module.research_agent.graph.nodes.intent_router import intent_router_node
from backend.module.research_agent.graph.nodes.reply_generator import reply_generator_node
from backend.module.research_agent.graph.nodes.outline_gen import outline_gen_node
from backend.module.research_agent.graph.nodes.parallel_search import parallel_search_node
from backend.module.research_agent.graph.nodes.plan_review import plan_review_node
from backend.module.research_agent.graph.nodes.route_claims import route_claims_node
from backend.module.research_agent.graph.nodes.snowball import snowball_node
from backend.module.research_agent.graph.nodes.verify_claims import verify_claims_node
from backend.module.research_agent.graph.nodes.write_themes import write_themes_node
from backend.module.research_agent.graph.state import ResearchState

# Linear sequence after the routing branch
_SEARCH_SEQUENCE = [
    ("plan_review",      plan_review_node),       # Step 0c ← interrupt
    ("parallel_search", parallel_search_node),  # Step ①
    ("dedup",           dedup_node),             # Step ①bis
    ("snowball",        snowball_node),           # Step ②bis
    ("embed",           embed_node),              # Step ③
    ("outline_gen",     outline_gen_node),        # Step ④ ← interrupt
    ("write_themes",    write_themes_node),       # Steps ⑤⑥
    ("extract_claims",  extract_claims_node),     # Step ⑦
    ("verify_claims",   verify_claims_node),      # Step ⑧
    ("route_claims",    route_claims_node),       # Step ⑨ ← interrupt
    ("build_graph",     build_graph_node),         # Step ⑨bis — knowledge graph
    ("export",          export_node),             # Step ⑩
]


def _route_after_intent(
    state: ResearchState,
) -> Literal["reply_generator", "plan_review"]:
    """Conditional edge: greeting/clarify → reply_generator, search → plan review."""
    intent = state.get("intent", "search")
    if intent in ("greeting", "clarify"):
        return "reply_generator"
    return "plan_review"


def build_research_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    graph = StateGraph(ResearchState)

    # Step 0a: intent classification
    graph.add_node("intent_router", intent_router_node)
    # Step 0b: reply generation for greeting/clarify (streams reply_token events)
    graph.add_node("reply_generator", reply_generator_node)

    # Step 0c – Step ⑩
    for name, node in _SEARCH_SEQUENCE:
        graph.add_node(name, node)

    # Entry point
    graph.set_entry_point("intent_router")

    # Conditional branch after Step 0a
    graph.add_conditional_edges(
        "intent_router",
        _route_after_intent,
        {"reply_generator": "reply_generator", "plan_review": "plan_review"},
    )

    # Step 0b always ends after generating reply
    graph.add_edge("reply_generator", END)

    # Linear chain for the search pipeline
    for (src, _), (dst, _) in zip(_SEARCH_SEQUENCE, _SEARCH_SEQUENCE[1:]):
        graph.add_edge(src, dst)
    graph.add_edge(_SEARCH_SEQUENCE[-1][0], END)

    return graph.compile(checkpointer=checkpointer)


async def _open_checkpointer() -> BaseCheckpointSaver:
    """SQLite-backed checkpointer — survives server restarts so an interrupted
    session (plan / outline / claim review) can be resumed via thread_id later.

    Connection is opened once and kept alive for the process lifetime (never
    closed) — same lifecycle as the cached graph singleton below.
    """
    import aiosqlite
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    settings = get_settings()
    db_path = settings.langgraph_checkpoint_db
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # ResearchState stores these Pydantic models directly (Paper, Claim, Theme) —
    # allow-list them so checkpointing doesn't warn/eventually fail to
    # deserialize them (LangGraph is moving to a strict allow-list by default).
    serde = JsonPlusSerializer(allowed_msgpack_modules=[
        ("backend.shared.models.paper", "Paper"),
        ("backend.shared.models.claim", "Claim"),
        ("backend.shared.models.review", "Theme"),
    ])

    conn = await aiosqlite.connect(db_path)
    saver = AsyncSqliteSaver(conn, serde=serde)
    await saver.setup()
    return saver


_graph_singleton: CompiledStateGraph | None = None
_graph_lock = asyncio.Lock()


async def get_research_graph() -> CompiledStateGraph:
    """Return the singleton compiled graph, built (and its SQLite checkpointer
    connection opened) once per process.
    """
    global _graph_singleton
    if _graph_singleton is not None:
        return _graph_singleton
    async with _graph_lock:
        if _graph_singleton is None:
            checkpointer = await _open_checkpointer()
            _graph_singleton = build_research_graph(checkpointer)
        return _graph_singleton
