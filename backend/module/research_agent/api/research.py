"""POST /api/research/stream - SSE endpoint for the research pipeline."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid

import httpx

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.module.payment.services import billing_db
from backend.module.payment.services.billing_db import QuotaExceededError
from backend.module.research_agent.graph.graph import get_research_graph
from backend.shared.models.graph import GraphResponse
from backend.shared.services import chat_persistence, topic_monitoring

router = APIRouter()
log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=True)

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
_HEARTBEAT_SECONDS = 15

_SEARCH_NODES = {
    "parallel_search",
    "dedup",
    "snowball",
    "embed",
    "outline_gen",
    "write_themes",
    "extract_claims",
    "verify_claims",
    "route_claims",
    "build_graph",
    "export",
}

_NODE_STEP_NUM: dict[str, str] = {
    "intent_router": "0",
    "plan_review": "0",
    "parallel_search": "1",
    "dedup": "2",
    "snowball": "3",
    "embed": "4",
    "outline_gen": "5",
    "write_themes": "6",
    "extract_claims": "7",
    "verify_claims": "8",
    "route_claims": "9",
    "build_graph": "10",
    "export": "11",
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _parse_sse(raw_event: str) -> dict[str, Any] | None:
    if not raw_event.startswith("data: "):
        return None
    try:
        return json.loads(raw_event[6:].strip())
    except json.JSONDecodeError:
        return None


def _format_clarify_content(questions: list[str]) -> str:
    if not questions:
        return "I need a bit more context."
    formatted = "\n".join(f"{idx + 1}. {question}" for idx, question in enumerate(questions))
    return f"I need a bit more context:\n\n{formatted}"


def _deleted_chat_sse(chat_id: str) -> str:
    return _sse({
        "type": "error",
        "code": "chat_deleted",
        "chat_id": chat_id,
        "message": "Chat deleted while research was running.",
    })


_DELETED_POLL_INTERVAL_SECONDS = 0.5


class _DeletedChatTermination(Exception):
    pass


def _build_deleted_chat_poller(*, poll_deleted, chat_id: str, interval_seconds: float = _DELETED_POLL_INTERVAL_SECONDS):
    last_checked_at: float | None = None
    last_deleted = False

    async def _poll() -> bool:
        nonlocal last_checked_at, last_deleted

        now = time.monotonic()
        if last_checked_at is not None and (now - last_checked_at) < interval_seconds:
            return last_deleted

        last_checked_at = now
        try:
            last_deleted = bool(await poll_deleted())
        except httpx.TransportError as exc:
            log.warning("deleted-chat poll failed for chat_id=%s: %s", chat_id, exc)
        return last_deleted

    return _poll


async def _record_assistant_state(
    token: str,
    user_id: str,
    chat_id: str,
    assistant_message_id: str,
    content: str,
    status: str,
    thread_id: str,
    request_kind: str,
    steps: list[dict[str, Any]],
    pending_plan: dict[str, Any] | None = None,
    bib: str | None = None,
    events: dict[str, Any] | None = None,
) -> None:
    metadata: dict[str, Any] = {
        "source": "research_stream",
        "thread_id": thread_id,
        "request_kind": request_kind,
        "steps": steps,
    }
    if pending_plan is not None:
        metadata["pending_plan"] = pending_plan
    if bib is not None:
        metadata["bib"] = bib
    if events is not None:
        metadata["events"] = events
    await chat_persistence.update_assistant_message(
        token,
        assistant_message_id,
        content=content,
        status=status,
        metadata=metadata,
        user_id=user_id,
        chat_id=chat_id,
    )


async def _node_to_step_event(node_name: str, state_update: dict) -> str:
    step_num = _NODE_STEP_NUM.get(node_name, node_name)

    if node_name == "parallel_search":
        search_stats = state_update.get("search_stats", {})
        total = sum(search_stats.values())
        stat = " ".join(f"{src}:{count}" for src, count in search_stats.items()) + f" total:{total}"
        content = f"{total} papers fetched."
    elif node_name == "dedup":
        count = len(state_update.get("papers", []))
        stat = f"{count} unique"
        content = f"Corpus after dedup: {count} papers."
    elif node_name == "snowball":
        count = len(state_update.get("papers", []))
        stat = f"{count} corpus"
        content = f"Corpus after snowball: {count} papers."
    elif node_name == "embed":
        embed_stats = state_update.get("embed_stats", {})
        stat = (
            f"api={embed_stats.get('api_hit', 0)} "
            f"fb={embed_stats.get('fallback_hit', 0)} "
            f"stored={embed_stats.get('stored', 0)}"
        )
        content = f"Embeddings ready. {stat}."
    elif node_name == "outline_gen":
        count = len(state_update.get("themes", []))
        stat = f"{count} themes"
        content = f"{count} themes generated."
    elif node_name == "write_themes":
        count = len(state_update.get("theme_contents", []))
        stat = f"{count} sections"
        content = f"{count} theme sections written."
    elif node_name == "extract_claims":
        count = len(state_update.get("claims", []))
        stat = f"{count} claims"
        content = f"{count} claims extracted."
    elif node_name == "verify_claims":
        verified_claims = state_update.get("verified_claims", [])
        by_status: dict[str, int] = {}
        for claim in verified_claims:
            by_status[claim.status] = by_status.get(claim.status, 0) + 1
        stat = (
            f"S:{by_status.get('supported', 0)} "
            f"P:{by_status.get('partial', 0)} "
            f"U:{by_status.get('unsupported', 0)}"
        )
        content = f"{len(verified_claims)} claims verified."
    elif node_name == "route_claims":
        stat = (
            f"included={len(state_update.get('included_claims', []))} "
            f"review={len(state_update.get('review_claims', []))} "
            f"removed={len(state_update.get('removed_claims', []))}"
        )
        content = f"Claims routed. {stat}."
    elif node_name == "build_graph":
        graph_stats = (state_update.get("knowledge_graph", {}) or {}).get("stats", {})
        stat = (
            f"papers={graph_stats.get('papers', 0)} "
            f"themes={graph_stats.get('themes', 0)} "
            f"claims={graph_stats.get('claims', 0)} "
            f"contradicts={graph_stats.get('contradicts_edges', 0)}"
        )
        content = "Knowledge graph built."
    elif node_name == "export":
        stat = f"tex={len(state_update.get('latex_doc', ''))}chars"
        content = "Export complete."
    else:
        stat = ""
        content = f"{node_name} done."

    return _sse({
        "type": "step",
        "step_type": "observation",
        "stepNum": step_num,
        "content": content,
        "stat": stat,
    })


async def _iterate_stream_graph(graph, input_or_command, config: dict, thread_id: str, stop_requested=None):
    params = inspect.signature(_stream_graph).parameters
    if "stop_requested" in params:
        async for item in _stream_graph(
            graph,
            input_or_command,
            config,
            thread_id,
            stop_requested=stop_requested,
        ):
            yield item
        return

    async for item in _stream_graph(graph, input_or_command, config, thread_id):
        yield item


async def _stream_graph(graph, input_or_command, config: dict, thread_id: str, stop_requested=None):
    export_reached = False
    queue: asyncio.Queue = asyncio.Queue()
    done_marker = object()

    async def _produce() -> None:
        try:
            async for event in graph.astream_events(input_or_command, config, version="v2"):
                await queue.put(event)
        except Exception as exc:
            await queue.put(exc)
        finally:
            await queue.put(done_marker)

    async def _should_stop() -> bool:
        if stop_requested is None:
            return False
        return bool(await stop_requested())

    async def _raise_if_stop_requested() -> None:
        if await _should_stop():
            raise _DeletedChatTermination

    producer_task = asyncio.create_task(_produce())

    try:
        while True:
            await _raise_if_stop_requested()
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                await _raise_if_stop_requested()
                yield _sse({"type": "heartbeat"})
                continue

            if item is done_marker:
                break
            if isinstance(item, Exception):
                raise item

            await _raise_if_stop_requested()

            event = item
            await asyncio.sleep(0)
            kind = event["event"]
            name = event.get("name", "")
            node = event.get("metadata", {}).get("langgraph_node", "")

            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                token = getattr(chunk, "content", "") or ""
                if not token:
                    continue

                if node == "intent_router":
                    await _raise_if_stop_requested()
                    yield _sse({"type": "thinking_token", "content": token})
                elif node == "reply_generator":
                    await _raise_if_stop_requested()
                    yield _sse({"type": "reply_token", "content": token})
                elif node in _SEARCH_NODES:
                    await _raise_if_stop_requested()
                    yield _sse({
                        "type": "step_token",
                        "stepNum": _NODE_STEP_NUM.get(node, ""),
                        "content": token,
                    })
                continue

            if kind != "on_chain_end":
                continue

            raw_output = event["data"].get("output")
            if not isinstance(raw_output, dict):
                continue
            output = raw_output

            if name == "intent_router":
                intent = output.get("intent", "search")
                if intent == "search":
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
                continue

            if name == "reply_generator":
                clarify_questions = output.get("clarify_questions") or []
                if clarify_questions:
                    yield _sse({"type": "clarify", "questions": clarify_questions})
                else:
                    yield _sse({"type": "greeting", "content": output.get("reply", "")})
                return

            if name in _SEARCH_NODES:
                yield await _node_to_step_event(name, output)
                if name == "export":
                    export_reached = True
                    yield _sse({
                        "type": "done",
                        "content": output.get("latex_doc", ""),
                        "bib": output.get("bib_content", ""),
                    })
    except _DeletedChatTermination:
        raise
    except Exception as exc:
        log.exception("astream_events error: %s", exc)
        yield _sse({"type": "error", "message": str(exc)})
        return
    finally:
        if not producer_task.done():
            producer_task.cancel()

    if export_reached:
        return

    try:
        state = await graph.aget_state(config)
        if not state.next:
            return
        interrupt_data: dict[str, Any] = {}
        for task in state.tasks or []:
            for interrupt in getattr(task, "interrupts", []):
                interrupt_data = getattr(interrupt, "value", interrupt) or {}
                break
            if interrupt_data:
                break
        yield _sse({"type": "interrupt", "thread_id": thread_id, "data": interrupt_data})
    except Exception as exc:
        log.warning("Could not read interrupt state: %s", exc)


class MessageDict(BaseModel):
    role: str
    content: str


class ResearchRequest(BaseModel):
    query: str
    thread_id: str | None = None
    chat_id: str | None = None
    client_message_id: str | None = None
    messages: list[MessageDict] | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    chat_id: str | None = None
    resume_value: object = True


@router.post("/research/stream")
async def research_stream(
    body: ResearchRequest,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    is_new_session = body.thread_id is None
    request_kind = "initial" if is_new_session else "followup"
    thread_id = body.thread_id or str(uuid.uuid4())
    token = credentials.credentials
    quota_started = False

    if is_new_session:
        try:
            await billing_db.start_session(str(user.id), "lr", thread_id)
            quota_started = True
        except QuotaExceededError as exc:
            raise HTTPException(402, "Het quota Literature Review - vui long nang cap goi hoac mua them.") from exc

    try:
        turn = await chat_persistence.start_stream_turn(
            token=token,
            user_id=str(user.id),
            query=body.query,
            thread_id=thread_id,
            chat_id=body.chat_id,
            client_message_id=body.client_message_id,
            request_kind=request_kind,
        )
    except HTTPException:
        if quota_started:
            await billing_db.refund_session(str(user.id), "lr", thread_id)
        raise
    except Exception as exc:
        if quota_started:
            await billing_db.refund_session(str(user.id), "lr", thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    graph = await get_research_graph()
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: dict[str, Any] = {"query": body.query, "thread_id": thread_id}
    if body.messages:
        initial_state["messages"] = [
            HumanMessage(content=message.content) if message.role == "user" else AIMessage(content=message.content)
            for message in body.messages
        ]

    chat_id = turn["chat"]["id"]
    assistant_message_id = turn["assistant_message"]["id"]

    try:
        await topic_monitoring.score_topic_signal(
            str(user.id),
            signal="new_session" if is_new_session else "followup",
            query=body.query,
            chat_id=chat_id,
            token=token,
        )
    except HTTPException as exc:
        if exc.status_code >= 500:
            log.warning("topic scoring failed for research stream chat_id=%s user_id=%s: %s", chat_id, user.id, exc.detail)
    except Exception as exc:
        log.warning("topic scoring failed for research stream chat_id=%s user_id=%s: %s", chat_id, user.id, exc)

    async def generator():
        steps: list[dict[str, Any]] = []
        pending_plan: dict[str, Any] | None = None
        final_content = ""
        final_bib: str | None = None
        event_counts: dict[str, int] = {}

        yield _sse({
            "type": "thread_id",
            "thread_id": thread_id,
            "chat_id": chat_id,
            "assistant_message_id": assistant_message_id,
        })

        async def _chat_deleted() -> bool:
            return await chat_persistence.is_chat_deleted(token, str(user.id), chat_id)

        deleted_poller = _build_deleted_chat_poller(poll_deleted=_chat_deleted, chat_id=chat_id)

        try:
            async for raw_event in _iterate_stream_graph(graph, initial_state, config, thread_id, stop_requested=deleted_poller):
                payload = _parse_sse(raw_event) or {}
                event_type = payload.get("type")
                if event_type:
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1

                try:
                    if event_type != "thread_id" and await deleted_poller():
                        yield _deleted_chat_sse(chat_id)
                        return

                    if event_type == "thread_id":
                        await chat_persistence.update_chat(token, str(user.id), chat_id, thread_id=thread_id, status="running")
                    elif event_type == "step":
                        steps.append({
                            "stepNum": payload.get("stepNum"),
                            "type": payload.get("step_type"),
                            "content": payload.get("content"),
                            "stat": payload.get("stat"),
                        })
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "streaming",
                            thread_id,
                            request_kind,
                            steps,
                            pending_plan=pending_plan,
                            events=event_counts,
                        )
                    elif event_type == "interrupt":
                        pending_plan = payload.get("data") or {}
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "awaiting_plan",
                            thread_id,
                            request_kind,
                            steps,
                            pending_plan=pending_plan,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=thread_id,
                            status="awaiting_plan",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "done":
                        final_content = payload.get("content") or final_content or "*(Pipeline complete - no content returned)*"
                        final_bib = payload.get("bib")
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "done",
                            thread_id,
                            request_kind,
                            steps,
                            pending_plan=pending_plan,
                            bib=final_bib,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=thread_id,
                            status="complete",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "greeting":
                        final_content = payload.get("content") or "Hello!"
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "done",
                            thread_id,
                            request_kind,
                            steps,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=thread_id,
                            status="idle",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "clarify":
                        final_content = _format_clarify_content(payload.get("questions") or [])
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "done",
                            thread_id,
                            request_kind,
                            steps,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=thread_id,
                            status="idle",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "error":
                        final_content = final_content or payload.get("message") or "Research pipeline failed."
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "error",
                            thread_id,
                            request_kind,
                            steps,
                            pending_plan=pending_plan,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=thread_id,
                            status="error",
                            last_message_at=chat_persistence._now_iso(),
                        )
                except chat_persistence.ChatDeletedError:
                    yield _deleted_chat_sse(chat_id)
                    return

                yield raw_event
        except _DeletedChatTermination:
            yield _deleted_chat_sse(chat_id)
            return

    return StreamingResponse(generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/research/resume")
async def research_resume(
    body: ResumeRequest,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
):
    from langgraph.types import Command

    token = credentials.credentials
    turn = await chat_persistence.start_resume_turn(
        token=token,
        user_id=str(user.id),
        thread_id=body.thread_id,
        chat_id=body.chat_id,
    )

    try:
        await topic_monitoring.score_topic_signal(
            str(user.id),
            signal="plan_approval",
            chat_id=turn["chat"]["id"],
            token=token,
        )
    except HTTPException as exc:
        if exc.status_code >= 500:
            log.warning("topic scoring failed for research resume chat_id=%s user_id=%s: %s", turn["chat"]["id"], user.id, exc.detail)
    except Exception as exc:
        log.warning("topic scoring failed for research resume chat_id=%s user_id=%s: %s", turn["chat"]["id"], user.id, exc)

    graph = await get_research_graph()
    config = {"configurable": {"thread_id": body.thread_id}}
    chat_id = turn["chat"]["id"]
    assistant_message_id = turn["assistant_message"]["id"]

    async def generator():
        steps = ((turn["assistant_message"].get("metadata") or {}).get("steps")) or []
        pending_plan = ((turn["assistant_message"].get("metadata") or {}).get("pending_plan"))
        resume_from_pending_plan = pending_plan is not None
        final_content = "" if resume_from_pending_plan else (turn["assistant_message"].get("content") or "")
        final_bib = ((turn["assistant_message"].get("metadata") or {}).get("bib"))
        event_counts: dict[str, int] = {}

        if resume_from_pending_plan:
            pending_plan = None
            await _record_assistant_state(
                token,
                str(user.id),
                chat_id,
                assistant_message_id,
                final_content,
                "streaming",
                body.thread_id,
                "resume",
                steps,
                pending_plan=pending_plan,
                bib=final_bib,
                events=event_counts,
            )
            await chat_persistence.update_chat(
                token,
                str(user.id),
                chat_id,
                thread_id=body.thread_id,
                status="running",
                last_message_at=chat_persistence._now_iso(),
            )
            resume_from_pending_plan = False

        yield _sse({
            "type": "thread_id",
            "thread_id": body.thread_id,
            "chat_id": chat_id,
            "assistant_message_id": assistant_message_id,
        })

        async def _chat_deleted() -> bool:
            return await chat_persistence.is_chat_deleted(token, str(user.id), chat_id)

        deleted_poller = _build_deleted_chat_poller(poll_deleted=_chat_deleted, chat_id=chat_id)

        try:
            async for raw_event in _iterate_stream_graph(
                graph,
                Command(resume=body.resume_value),
                config,
                body.thread_id,
                stop_requested=deleted_poller,
            ):
                payload = _parse_sse(raw_event) or {}
                event_type = payload.get("type")
                if event_type:
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1

                try:
                    if event_type != "thread_id" and await deleted_poller():
                        yield _deleted_chat_sse(chat_id)
                        return

                    if event_type == "step":
                        steps.append({
                            "stepNum": payload.get("stepNum"),
                            "type": payload.get("step_type"),
                            "content": payload.get("content"),
                            "stat": payload.get("stat"),
                        })
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "streaming",
                            body.thread_id,
                            "resume",
                            steps,
                            pending_plan=pending_plan,
                            bib=final_bib,
                            events=event_counts,
                        )
                    elif event_type == "interrupt":
                        pending_plan = payload.get("data") or {}
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "awaiting_plan",
                            body.thread_id,
                            "resume",
                            steps,
                            pending_plan=pending_plan,
                            bib=final_bib,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=body.thread_id,
                            status="awaiting_plan",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "done":
                        final_content = payload.get("content") or final_content or "*(Pipeline complete - no content returned)*"
                        final_bib = payload.get("bib")
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "done",
                            body.thread_id,
                            "resume",
                            steps,
                            pending_plan=pending_plan,
                            bib=final_bib,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=body.thread_id,
                            status="complete",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "greeting":
                        final_content = payload.get("content") or "Hello!"
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "done",
                            body.thread_id,
                            "resume",
                            steps,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=body.thread_id,
                            status="idle",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "clarify":
                        final_content = _format_clarify_content(payload.get("questions") or [])
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "done",
                            body.thread_id,
                            "resume",
                            steps,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=body.thread_id,
                            status="idle",
                            last_message_at=chat_persistence._now_iso(),
                        )
                    elif event_type == "error":
                        final_content = final_content or payload.get("message") or "Research pipeline failed."
                        await _record_assistant_state(
                            token,
                            str(user.id),
                            chat_id,
                            assistant_message_id,
                            final_content,
                            "error",
                            body.thread_id,
                            "resume",
                            steps,
                            pending_plan=pending_plan,
                            bib=final_bib,
                            events=event_counts,
                        )
                        await chat_persistence.update_chat(
                            token,
                            str(user.id),
                            chat_id,
                            thread_id=body.thread_id,
                            status="error",
                            last_message_at=chat_persistence._now_iso(),
                        )
                except chat_persistence.ChatDeletedError:
                    yield _deleted_chat_sse(chat_id)
                    return

                yield raw_event
        except _DeletedChatTermination:
            yield _deleted_chat_sse(chat_id)
            return

    return StreamingResponse(generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/research/graph", response_model=GraphResponse)
async def research_graph(thread_id: str):
    graph = await get_research_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    knowledge_graph = (state.values or {}).get("knowledge_graph")
    if not knowledge_graph:
        raise HTTPException(status_code=404, detail="Graph not built yet - session has not reached build_graph.")
    return knowledge_graph
