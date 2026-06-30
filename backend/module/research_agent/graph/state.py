"""LangGraph state for the research pipeline (SPEC 2.0).

total=False means every field is optional — nodes populate keys
incrementally and return only the keys they produce.

Step 0 adds conversation-aware fields so the intent router can
handle multi-turn clarification before the search pipeline runs.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages

from backend.shared.models.claim import Claim
from backend.shared.models.paper import Paper
from backend.shared.models.review import Theme


class ResearchState(TypedDict, total=False):
    # ── Input / conversation ──────────────────────────────────────────
    query: str  # original user query (latest turn)
    thread_id: str  # LangGraph thread ID for checkpoint lookup

    # Conversation history (Step 0 multi-turn); add_messages reducer appends
    messages: Annotated[list, add_messages]

    # ── Step 0: Intent router ─────────────────────────────────────────
    # intent: what the LLM decided to do
    intent: Literal["greeting", "clarify", "search"]

    # For intent="greeting": the natural reply to send back
    reply: str

    # For intent="clarify": list of clarifying questions
    clarify_questions: list[str]

    # For intent="search": rewritten query + sub-queries for parallel search
    refined_query: str
    sub_queries: list[str]  # 4-6 angles for parallel_search
    sources: list[str]  # LLM-selected subset of {semantic_scholar, openalex, arxiv, pubmed}
    plan_description: str  # one-sentence plan summary shown for user approval

    # ── Step 0c: Research plan approval (interrupt) ───────────────────
    plan_approved: bool

    # ── Step ①: Parallel multi-source search ─────────────────────────
    raw_papers: list[Paper]
    search_stats: dict[str, int]  # {"semantic_scholar": n, "openalex": n, "arxiv": n, "pubmed": n}

    # ── Step ①bis: Cross-source dedup ────────────────────────────────
    papers: list[Paper]  # deduplicated corpus

    # ── Step ②bis: Snowball also updates `papers` + records who-cites-whom ──
    citation_edges: list[dict]  # [{source, target, intent, isInfluential}] — source CITES target

    # ── Step ③: Embed + ChromaDB ─────────────────────────────────────
    embed_stats: dict[str, int]  # {"api_hit": n, "fallback_hit": n, "stored": n}

    # ── Step ④: Outline generation + interrupt ───────────────────────
    themes: list[Theme]
    outline_approved: bool

    # ── Steps ⑤⑥: Hybrid search + write ─────────────────────────────
    theme_contents: list[dict]  # [{"theme": str, "content": str, "paper_ids": list[str]}]

    # ── Step ⑦: Claim extraction ─────────────────────────────────────
    claims: list[Claim]

    # ── Step ⑧: 3-tier verification ──────────────────────────────────
    verified_claims: list[Claim]

    # ── Step ⑨: Route + interrupt ────────────────────────────────────
    included_claims: list[Claim]
    review_claims: list[Claim]
    removed_claims: list[Claim]

    # ── Step ⑨bis: Knowledge Graph (knowledge-graph_SPEC_2.0.md) ──────
    knowledge_graph: dict  # {nodes, edges, stats} — paper/theme/claim layers

    # ── Step ⑩: Export ───────────────────────────────────────────────
    latex_doc: str  # full .tex document string
    bib_content: str  # BibTeX .bib content

    # ── Error handling ────────────────────────────────────────────────
    error: str | None
