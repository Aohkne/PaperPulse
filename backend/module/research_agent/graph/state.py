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

    # Personalization block rendered from the user's custom instructions
    # (shared.services.custom_instructions.build_persona_block). "" when unset;
    # injected into the greeting/clarify reply system prompt so replies can
    # address the user by name and honor their stated preferences.
    persona: str

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
    sub_queries: list[str]  # 4-6 angles for parallel_search, anchored on core_terms
    sources: list[str]  # LLM-selected subset of {semantic_scholar, openalex, pubmed}
    plan_description: str  # one-sentence plan summary shown for user approval
    # core_terms drive the Step ①bis relevance filter:
    #   {"required": [[syn, syn], ...], "context": [...]}
    core_terms: dict

    # ── Step 0c: Research plan approval (interrupt) ───────────────────
    plan_approved: bool

    # ── Step ①: Parallel multi-source search ─────────────────────────
    raw_papers: list[Paper]
    search_stats: dict[str, int]  # {"semantic_scholar": n, "openalex": n, "arxiv": n, "pubmed": n}

    # ── Step ①bis: Cross-source dedup + relevance filter ─────────────
    papers: list[Paper]  # deduplicated + relevance-filtered corpus
    low_relevance: bool  # True when the relevance filter left < relevance_min papers

    # ── Step ②: Embed → pgvector ─────────────────────────────────────
    embed_stats: dict[str, int]  # {"api_hit": n, "stored": n}

    # ── Step ③: Clustering + interrupt (cluster approval) ────────────
    themes: list[Theme]  # each Theme.paper_ids = the cluster's papers
    outline_approved: bool  # set True after the cluster-approval interrupt resumes

    # ── Step ④: Parallel writer agents ───────────────────────────────
    theme_contents: list[dict]  # [{"theme": str, "content": str, "paper_ids": list[str]}]

    # ── Step ⑤: Claim extraction + 3-tier verification ───────────────
    claims: list[Claim]
    verified_claims: list[Claim]

    # ── Step ⑥: Route + interrupt (claim review) ─────────────────────
    included_claims: list[Claim]
    review_claims: list[Claim]
    removed_claims: list[Claim]

    # ── Step ⑥bis: Knowledge Graph (knowledge-graph_SPEC_2.0.md) ──────
    knowledge_graph: dict  # {nodes, edges, stats} — paper/theme/claim layers

    # ── Step ⑦: Export ───────────────────────────────────────────────
    latex_doc: str  # full .tex document string
    bib_content: str  # BibTeX .bib content

    # ── Error handling ────────────────────────────────────────────────
    error: str | None
