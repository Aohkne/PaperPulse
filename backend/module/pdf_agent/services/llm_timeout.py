"""Shared timeout guard for LLM calls in the PDF Agent.

`langchain_openai.ChatOpenAI.ainvoke()` has no built-in deadline — if the
upstream API (NVIDIA NIM) stalls mid-request, the coroutine hangs forever
with nothing to except (it never raises, it just never resolves). Every
LLM call in this module goes through here so one stalled call degrades
gracefully (caller falls back) instead of hanging the request indefinitely.
"""

from __future__ import annotations

import asyncio

from backend.config import get_settings


async def ainvoke_with_timeout(llm, messages: list[dict]):
    """Returns the LLM response, or raises asyncio.TimeoutError after the configured deadline."""
    settings = get_settings()
    return await asyncio.wait_for(llm.ainvoke(messages), timeout=settings.pdf_agent_llm_call_timeout_s)
