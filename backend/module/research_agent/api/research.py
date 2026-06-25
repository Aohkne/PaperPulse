"""POST /api/research/stream — SSE endpoint (SPEC 2.0 Step 0→⑩).

Uses graph.astream_events(version="v2") to capture three distinct LLM streams:
  intent_router   → "thinking_token" events  (reasoning: WHY this intent)
  reply_generator → "reply_token" events     (response: the actual reply / questions)
  pipeline nodes  → "step_token" events      (narrator text per pipeline step)

SSE event shapes emitted to the frontend:
  {"type": "thread_id",      "thread_id": "..."}
  {"type": "thinking_token", "content": "..."}     ← intent_router reasoning stream
  {"type": "reply_token",    "content": "..."}     ← reply_generator response stream
  {"type": "greeting",       "content": "..."}     ← intent=greeting (complete)
  {"type": "clarify",        "questions": [...]}   ← intent=clarify (complete)
  {"type": "step",           "stepNum": "N", ...}  ← pipeline step progress
  {"type": "step_token",     "stepNum": "N", ...}  ← pipeline narrator stream
  {"type": "interrupt",      "thread_id": "...", "data": {...}}
  {"type": "heartbeat"}                            ← keepalive during silent steps
  {"type": "done",           "content": "...", "bib": "..."}
  {"type": "error",          "message": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.module.payment.services import billing_db
from backend.module.payment.services.billing_db import QuotaExceededError
from backend.module.research_agent.graph.graph import get_research_graph
from backend.shared.models.graph import GraphResponse

router = APIRouter()
log = logging.getLogger(__name__)

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

# Emit a heartbeat if no graph event arrives within this many seconds — keeps
# the SSE connection alive through idle-timing-out proxies during long silent
# steps (parallel_search, snowball, embed) that make real network calls
# with no LLM token stream (PLAN_2.0 §SSE risk mitigation).
_HEARTBEAT_SECONDS = 15

# Nodes that belong to the search pipeline (Steps ① – ⑩)
_SEARCH_NODES = {
    "parallel_search", "dedup", "snowball", "embed",
    "outline_gen", "write_themes", "extract_claims",
    "verify_claims", "route_claims", "build_graph", "export",
}

_NODE_STEP_NUM: dict[str, str] = {
    "intent_router":  "0",
    "plan_review":    "0",
    "parallel_search":"1",
    "dedup":          "2",
    "snowball":       "3",
    "embed":          "4",
    "outline_gen":    "5",
    "write_themes":   "6",
    "extract_claims": "7",
    "verify_claims":  "8",
    "route_claims":   "9",
    "build_graph":    "10",
    "export":         "11",
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _node_to_step_event(node_name: str, state_update: dict) -> str:
    step_num = _NODE_STEP_NUM.get(node_name, node_name)

    if node_name == "parallel_search":
        s = state_update.get("search_stats", {})
        total = sum(s.values())
        stat = " ".join(f"{src}:{n}" for src, n in s.items()) + f" total:{total}"
        content = f"{total} papers fetched."
    elif node_name == "dedup":
        n = len(state_update.get("papers", []))
        stat = f"{n} unique"
        content = f"Corpus after dedup: {n} papers."
    elif node_name == "snowball":
        n = len(state_update.get("papers", []))
        stat = f"{n} corpus"
        content = f"Corpus after snowball: {n} papers."
    elif node_name == "embed":
        es = state_update.get("embed_stats", {})
        stat = f"api={es.get('api_hit',0)} fb={es.get('fallback_hit',0)} stored={es.get('stored',0)}"
        content = f"Embeddings ready. {stat}."
    elif node_name == "outline_gen":
        n = len(state_update.get("themes", []))
        stat = f"{n} themes"
        content = f"{n} themes generated."
    elif node_name == "write_themes":
        n = len(state_update.get("theme_contents", []))
        stat = f"{n} sections"
        content = f"{n} theme sections written."
    elif node_name == "extract_claims":
        n = len(state_update.get("claims", []))
        stat = f"{n} claims"
        content = f"{n} claims extracted."
    elif node_name == "verify_claims":
        vc = state_update.get("verified_claims", [])
        by_s: dict[str, int] = {}
        for c in vc:
            by_s[c.status] = by_s.get(c.status, 0) + 1
        stat = (f"S:{by_s.get('supported',0)} "
                f"P:{by_s.get('partial',0)} "
                f"U:{by_s.get('unsupported',0)}")
        content = f"{len(vc)} claims verified."
    elif node_name == "route_claims":
        stat = (
            f"included={len(state_update.get('included_claims',[]))} "
            f"review={len(state_update.get('review_claims',[]))} "
            f"removed={len(state_update.get('removed_claims',[]))}"
        )
        content = f"Claims routed. {stat}."
    elif node_name == "build_graph":
        kg = state_update.get("knowledge_graph", {}) or {}
        kg_stats = kg.get("stats", {})
        stat = (f"papers={kg_stats.get('papers',0)} "
                f"themes={kg_stats.get('themes',0)} "
                f"claims={kg_stats.get('claims',0)} "
                f"contradicts={kg_stats.get('contradicts_edges',0)}")
        content = "Knowledge graph built."
    elif node_name == "export":
        stat = f"tex={len(state_update.get('latex_doc',''))}chars"
        content = "Export complete."
    else:
        stat = ""
        content = f"{node_name} done."

    return _sse({"type": "step", "step_type": "observation",
                 "stepNum": step_num, "content": content, "stat": stat})


async def _stream_graph(graph, input_or_command, config: dict, thread_id: str):
    """
    Async generator that yields SSE strings.

    Uses astream_events(version="v2") to capture three distinct LLM streams:

      intent_router   → on_chat_model_stream → "thinking_token" events
                        (user sees the reasoning: WHY this intent)

      reply_generator → on_chat_model_stream → "reply_token" events
                        (user sees the response streaming: greeting or clarify questions)

      pipeline nodes  → on_chat_model_stream → "step_token" events
                        (narrator text per pipeline step)

    After the event loop ends, checks for pending interrupts.

    Heartbeats run on a *separate* background task that drains
    astream_events() into a queue; the main loop only ever times out on
    `queue.get()`, which is always safe to cancel. Previously the timeout
    wrapped `event_iter.__anext__()` directly — cancelling that future on
    timeout reached into astream_events()'s internals (mid node execution,
    e.g. a long-running embed() call) and could abort/retry the current
    node, causing its narrate_step() sentence to repeat over and over.
    """
    export_reached = False
    queue: asyncio.Queue = asyncio.Queue()
    _DONE = object()

    async def _produce() -> None:
        try:
            async for event in graph.astream_events(input_or_command, config, version="v2"):
                await queue.put(event)
        except Exception as exc:  # noqa: BLE001 — forwarded to the consumer below
            await queue.put(exc)
        finally:
            await queue.put(_DONE)

    producer_task = asyncio.create_task(_produce())

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                # No event for a while (real network calls in parallel_search /
                # snowball / embed) — keep the SSE connection alive and let the
                # frontend show a "still working" pulse instead of going silent.
                # Only the queue wait times out — the producer keeps running.
                yield _sse({"type": "heartbeat"})
                continue

            if item is _DONE:
                break
            if isinstance(item, Exception):
                raise item

            event = item
            await asyncio.sleep(0)
            kind = event["event"]
            name = event.get("name", "")
            node = event.get("metadata", {}).get("langgraph_node", "")

            # ── LLM token streams ────────────────────────────────────────────
            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                token = getattr(chunk, "content", "") or ""
                if not token:
                    continue

                if node == "intent_router":
                    # Reasoning tokens — user sees WHY the LLM chose this intent
                    yield _sse({"type": "thinking_token", "content": token})

                elif node == "reply_generator":
                    # Response tokens — user sees the reply streaming in real-time
                    yield _sse({"type": "reply_token", "content": token})

                elif node in _SEARCH_NODES:
                    # Narrator tokens — per-step description during pipeline
                    yield _sse({
                        "type": "step_token",
                        "stepNum": _NODE_STEP_NUM.get(node, ""),
                        "content": token,
                    })

            # ── Node completions ─────────────────────────────────────────────
            elif kind == "on_chain_end":
                raw_output = event["data"].get("output")
                if not isinstance(raw_output, dict):
                    continue
                output = raw_output

                if name == "intent_router":
                    intent = output.get("intent", "search")
                    if intent == "search":
                        # Emit step-0 event so frontend knows the research plan.
                        # `content` is the LLM's own "User wants to search about
                        # X, I will start from sources Y" sentence (plan_description)
                        # so the displayed text matches what it just reasoned about.
                        plan_description = output.get("plan_description", "")
                        yield _sse({
                            "type": "step",
                            "step_type": "observation",
                            "stepNum": "0",
                            "content": plan_description or "Research plan ready.",
                            "stat": f"{len(output.get('sub_queries', []))} sub-queries",
                            "refined_query": output.get("refined_query", ""),
                            "plan_description": plan_description,
                        })
                    # For greeting/clarify: graph continues to reply_generator

                elif name == "reply_generator":
                    # Reply generation complete — emit final greeting or clarify event
                    clarify_qs = output.get("clarify_questions") or []
                    if clarify_qs:
                        yield _sse({"type": "clarify", "questions": clarify_qs})
                    else:
                        yield _sse({"type": "greeting", "content": output.get("reply", "")})
                    return  # graph → END after reply_generator

                elif name in _SEARCH_NODES:
                    yield _node_to_step_event(name, output)
                    if name == "export":
                        export_reached = True
                        yield _sse({
                            "type": "done",
                            "content": output.get("latex_doc", ""),
                            "bib": output.get("bib_content", ""),
                        })

    except Exception as exc:
        log.exception("astream_events error: %s", exc)
        yield _sse({"type": "error", "message": str(exc)})
        return

    finally:
        if not producer_task.done():
            producer_task.cancel()

    # ── 3. Check for interrupt (stream ends silently when interrupt() fires) ──
    if not export_reached:
        try:
            state = await graph.aget_state(config)
            if state.next:  # graph is paused at a node
                interrupt_data: dict = {}
                for task in (state.tasks or []):
                    for ipt in getattr(task, "interrupts", []):
                        interrupt_data = getattr(ipt, "value", ipt) or {}
                        break
                    if interrupt_data:
                        break
                yield _sse({
                    "type": "interrupt",
                    "thread_id": thread_id,
                    "data": interrupt_data,
                })
        except Exception as exc:
            log.warning("Could not read interrupt state: %s", exc)


# Request / response models

class MessageDict(BaseModel):
    role: str
    content: str


class ResearchRequest(BaseModel):
    query: str
    thread_id: str | None = None
    # Optional prior-turn messages for multi-turn clarification flow
    messages: list[MessageDict] | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    resume_value: object = True


# Endpoints

@router.post("/research/stream")
async def research_stream(body: ResearchRequest, user: Any = Depends(get_current_user)):
    """
    SSE: Start (or continue) the pipeline.

    First call: body.query = user's initial message.
    Clarify follow-up: body.query = user's answer, body.messages = prior turns.
    The intent router uses the conversation history to determine whether to
    proceed to search or ask another question.
    """
    is_new_session = body.thread_id is None
    thread_id = body.thread_id or str(uuid.uuid4())

    # Deduct 1 Literature Review unit only on true session creation — a
    # clarify follow-up reuses the existing thread_id and is free (payment_SPEC_2.0.md
    # §Logic deduction: "chỉ session/document MỚI mới trừ unit").
    if is_new_session:
        try:
            await billing_db.start_session(str(user.id), "lr", thread_id)
        except QuotaExceededError as exc:
            raise HTTPException(402, "Hết quota Literature Review — vui lòng nâng cấp gói hoặc mua thêm.") from exc

    graph = await get_research_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # Build initial state, injecting conversation history if provided
    initial_state: dict = {"query": body.query, "thread_id": thread_id}
    if body.messages:
        initial_state["messages"] = [
            HumanMessage(content=m.content) if m.role == "user"
            else AIMessage(content=m.content)
            for m in body.messages
        ]

    async def generator():
        yield _sse({"type": "thread_id", "thread_id": thread_id})
        try:
            async for event in _stream_graph(graph, initial_state, config, thread_id):
                yield event
        except Exception as exc:
            log.exception("Pipeline error: %s", exc)
            # System error, not user abandonment — refund per spec's refund table.
            await billing_db.refund_session(str(user.id), "lr", thread_id)
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers=_SSE_HEADERS)


@router.post("/research/resume")
async def research_resume(body: ResumeRequest, user: Any = Depends(get_current_user)):
    """SSE: resume after interrupt (outline ④ or routing ⑨)."""
    from langgraph.types import Command

    graph = await get_research_graph()
    config = {"configurable": {"thread_id": body.thread_id}}

    async def generator():
        try:
            async for event in _stream_graph(
                graph, Command(resume=body.resume_value), config, body.thread_id
            ):
                yield event
        except Exception as exc:
            log.exception("Resume error: %s", exc)
            # Same session as the original /research/stream deduction —
            # billing_refund_session is idempotent on session_id, so this is
            # safe even if /research/stream's own error handler already refunded.
            await billing_db.refund_session(str(user.id), "lr", body.thread_id)
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers=_SSE_HEADERS)


@router.get("/research/graph", response_model=GraphResponse)
async def research_graph(thread_id: str):
    """Knowledge Graph (Step ⑨bis) — reads the already-built graph from the
    LangGraph checkpoint, same pattern as reading the .tex export: no
    rebuilding here, `build_graph_node` already assembled it during the run.
    """
    graph = await get_research_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    knowledge_graph = (state.values or {}).get("knowledge_graph")
    if not knowledge_graph:
        raise HTTPException(
            status_code=404,
            detail="Graph not built yet — session hasn't reached Step ⑨bis (build_graph).",
        )
    return knowledge_graph
