"""Per-request token accounting (token.html §4 "Bắt token — không sửa từng node").

A ContextVar holds a mutable accumulator dict for the current request. Because
it's mutated in place (not re-``set``), every child task/coroutine spawned after
``start()`` — including the LangGraph node tasks — sees the same accumulator, so
token usage from deeply-nested LLM calls rolls up without threading a counter
through dozens of node signatures.

Two capture points feed it:
  - chat_completion() reads response.usage directly (gap-detection path).
  - get_llm()'s ChatOpenAI attaches TokenMeterCallback → on_llm_end (lr/pdf path).

Both are exact (from the provider's usage payload), never estimated.
"""

from __future__ import annotations

import contextvars
import logging

from backend.module.payment import pricing

log = logging.getLogger(__name__)

_usage: contextvars.ContextVar[dict | None] = contextvars.ContextVar("token_meter_usage", default=None)


def start() -> None:
    """Begin metering for the current request (fresh accumulator)."""
    _usage.set({"input": 0, "output": 0})


def record(input_tokens: int, output_tokens: int) -> None:
    """Add token usage to the current request's accumulator (in place)."""
    acc = _usage.get()
    if acc is None:
        return  # metering not started for this context — ignore
    acc["input"] += int(input_tokens or 0)
    acc["output"] += int(output_tokens or 0)


def credits_used() -> float:
    """Credits consumed so far in the current request (0 if metering not started)."""
    acc = _usage.get()
    if acc is None:
        return 0.0
    return pricing.credits_for_tokens(acc["input"], acc["output"])


def snapshot() -> dict:
    acc = _usage.get() or {"input": 0, "output": 0}
    return {"input": acc["input"], "output": acc["output"], "credits": credits_used()}


try:
    from langchain_core.callbacks import BaseCallbackHandler

    class TokenMeterCallback(BaseCallbackHandler):
        """Records ChatOpenAI usage into the token meter on every LLM completion."""

        def on_llm_end(self, response, **kwargs) -> None:  # noqa: ANN001
            try:
                usage = (response.llm_output or {}).get("token_usage") if response.llm_output else None
                if not usage:
                    # Streaming responses carry usage on the message instead.
                    for gen_list in response.generations:
                        for gen in gen_list:
                            meta = getattr(getattr(gen, "message", None), "usage_metadata", None)
                            if meta:
                                record(meta.get("input_tokens", 0), meta.get("output_tokens", 0))
                                return
                    return
                record(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            except Exception as exc:  # never let metering break an LLM call
                log.debug("TokenMeterCallback failed: %s", exc)

except Exception:  # langchain not importable in some contexts — degrade gracefully
    TokenMeterCallback = None  # type: ignore[assignment,misc]
