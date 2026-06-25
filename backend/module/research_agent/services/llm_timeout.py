"""Shared timeout guard for LLM calls in the Research Agent.

Mirrors backend/module/pdf_agent/services/llm_timeout.py — see that module's
docstring for why this exists: `ChatOpenAI.ainvoke()` has no built-in
deadline, so a stalled upstream provider hangs the coroutine (and the whole
SSE stream) forever instead of raising. `asyncio.wait_for` only adds a
deadline around the coroutine — it doesn't touch the underlying streaming
callbacks, so token-level events still flow through LangGraph's
`astream_events()` exactly as before.
"""

from __future__ import annotations

import asyncio

from backend.config import get_settings


async def ainvoke_with_timeout(llm, messages):
    """Returns the LLM response, or raises asyncio.TimeoutError after the configured deadline."""
    settings = get_settings()
    return await asyncio.wait_for(llm.ainvoke(messages), timeout=settings.research_agent_llm_call_timeout_s)
