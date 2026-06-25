"""Step 0b — Reply generator: produces the actual streaming response for
greeting and clarify intents (SPEC 2.0 §Step 0).

This node runs AFTER intent_router and generates:
  - greeting intent → a natural, helpful reply (streaming)
  - clarify intent  → 3-4 specific clarifying questions (streaming)

By placing reply generation in a SEPARATE node, its LLM token stream is
captured distinctly by graph.astream_events() and forwarded as "reply_token"
SSE events — separate from the "thinking_token" events from intent_router.

Frontend receives two distinct event streams:
  1. thinking_token  (intent_router reasoning — WHY this intent)
  2. reply_token     (reply_generator output  — the actual response)

This gives users real-time visibility into both reasoning AND response.
"""

from __future__ import annotations

import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.config import get_llm
from backend.module.research_agent.graph.state import ResearchState

log = logging.getLogger(__name__)

_GREETING_SYSTEM = """\
You are a helpful academic research assistant.
Reply naturally and helpfully to the user's message in the same language they used.
- If they greeted you, greet them warmly and briefly mention you can help with \
literature reviews and academic research.
- If they asked a conceptual question (e.g. "what is RAG?", "explain transformers"), \
give a clear, informative explanation in 3-5 sentences from your knowledge.
Be concise and conversational. Do not suggest searching papers for simple questions."""

_CLARIFY_SYSTEM = """\
You are a helpful academic research assistant.
The user's research query is too vague to search effectively.
Generate exactly 3-4 specific, numbered clarifying questions to understand:
- Which specific aspect or sub-problem they want to focus on
- What type of papers they need (foundational theory / recent advances / \
applications / benchmarks / comparisons)
- Any domain or constraint preferences (time period, specific methods, application areas)
Reply in the same language as the user.
Output only the numbered questions — nothing else."""


def _parse_questions(text: str) -> list[str]:
    """Extract numbered/bulleted questions from the LLM response."""
    questions = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r'^(\d+[\.\)]\s*|-\s*•\s*|\*\s*)', '', line).strip()
        if cleaned:
            questions.append(cleaned)
    return [q for q in questions if q][:5]


async def reply_generator_node(state: ResearchState) -> dict:
    intent = state.get("intent", "greeting")
    query = state.get("query", "")

    if intent == "clarify":
        llm = get_llm(temperature=0, streaming=True)
        response = await llm.ainvoke([
            SystemMessage(content=_CLARIFY_SYSTEM),
            HumanMessage(content=query),
        ])
        text = response.content.strip()
        questions = _parse_questions(text)
        if not questions:
            questions = [text]
        formatted = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
        return {
            "clarify_questions": questions,
            "reply": formatted,
            "messages": [AIMessage(content=formatted)],
        }

    else:  # greeting (or any non-search, non-clarify intent)
        llm = get_llm(temperature=0.7, streaming=True)
        response = await llm.ainvoke([
            SystemMessage(content=_GREETING_SYSTEM),
            HumanMessage(content=query),
        ])
        reply = response.content.strip()
        return {
            "reply": reply,
            "messages": [AIMessage(content=reply)],
        }
