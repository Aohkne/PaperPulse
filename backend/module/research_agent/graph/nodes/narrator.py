"""
Shared helper: fire a brief LangChain LLM stream at the start of each node
so graph.astream_events() captures on_chat_model_stream tokens tagged with
the node's langgraph_node metadata. These are forwarded to the frontend as
"step_token" SSE events so each pipeline step shows real streaming LLM text.
"""

from __future__ import annotations

from backend.config import get_llm

_SYSTEM = (
    "You are narrating a research pipeline to the user. "
    "Respond with ONE sentence only (max 20 words), first-person present tense, "
    "describing what you are about to do. Be specific and concise. "
    "Do not use quotes around the query or topic."
)


async def narrate_step(context: str) -> None:
    """
    Streams a single contextual sentence so astream_events captures the tokens.
    The caller does not need the output — tokens flow through LangGraph's
    callback system and are captured by astream_events automatically.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    llm = get_llm(temperature=0.4, streaming=True)
    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=context),
    ]
    async for _ in llm.astream(messages):
        pass
