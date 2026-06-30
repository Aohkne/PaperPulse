"""Step ⑨bis — Knowledge Graph assembly (knowledge-graph_SPEC_2.0.md v1.1).

Builds a 4-layer "solar system" graph (Topic / Theme / Paper / Claim-discourse)
purely by reassembling data the pipeline already produced in Steps
②bis/④/⑤/⑦/⑧/⑨ — no new LLM call. Uses `networkx` in-memory.

Layer scope (SPEC v1.1 — corrected from v1.0):
  - Topic: exactly one root node, label = the query, `covers` edge to each theme.
  - Theme + Paper: ONLY papers that actually appear in `theme_contents`
    (i.e. papers cited in the written review), NOT the full post-snowball
    corpus (`state["papers"]`, ~600-900 papers). This keeps the graph at
    review-scope (~60-150 papers) instead of corpus-scope.
  - Claim: two distinct edges per claim — `evidenced_by` (claim→paper,
    neutral, just traces the source) and an intent-typed edge (claim→theme,
    supports/contradicts/mentions) used for the "contradicts only" filter.
    A claim can never logically "contradict" the very paper it was quoted
    from, so the intent edge must point at the theme, not the paper.
"""

from __future__ import annotations

import logging

import networkx as nx
from slugify import slugify

from backend.config import get_settings
from backend.shared.models.claim import Claim
from backend.shared.models.paper import Paper

log = logging.getLogger(__name__)

# Claim.intent (Supporting/Contrasting/Mentioning, from S2 citation-intent
# classification) mapped onto the SPEC's discourse edge-type vocabulary.
# Claim.intent has no "Extends" value, so "Mentioning" stands in for it.
_INTENT_EDGE_TYPE = {
    "Supporting": "supports",
    "Contrasting": "contradicts",
    "Mentioning": "mentions",
}

# Claim.status doesn't carry a numeric probability — this is a coarse,
# documented heuristic for node sizing/coloring in the viewer, not a model
# output. snippet/arXiv-verified "supported" claims rank highest confidence;
# abstract-only ("low_confidence") and non-"supported" verdicts rank lower.
_STATUS_CONFIDENCE = {
    "supported": 0.9,
    "partial": 0.6,
    "uncertain": 0.4,
    "unsupported": 0.1,
    "pending": 0.3,
}


def _claim_confidence(claim: Claim) -> float:
    base = _STATUS_CONFIDENCE.get(claim.status, 0.3)
    return min(base, 0.5) if claim.low_confidence else base


def build_knowledge_graph(
    query: str,
    papers: list[Paper],
    citation_edges: list[dict],
    theme_contents: list[dict],
    included_claims: list[Claim],
    review_claims: list[Claim],
) -> dict:
    """Assemble the 4-layer knowledge graph and return it as plain JSON (node_link format).

    Claims considered are `included_claims + review_claims` — i.e. everything
    NOT explicitly removed as unsupported (`removed_claims` excluded). This
    mirrors export_node's own citation set so the graph and the .tex agree on
    which claims "made it" into the final review.
    """
    g = nx.MultiDiGraph()
    paper_by_id = {p.paper_id: p for p in papers}

    # ── Topic layer — single root node, the anchor for the radial layout ────
    topic_id = "topic:root"
    g.add_node(topic_id, type="topic", label=query or "Research Topic")

    # ── Theme + Paper layer — ONLY papers actually cited in the review ──────
    # (i.e. papers referenced from `theme_contents`, not the full snowballed
    # corpus). A paper can belong to >1 theme (interdisciplinary paper).
    paper_to_themes: dict[str, list[str]] = {}
    for tc in theme_contents:
        theme_title = tc.get("theme", "")
        if not theme_title:
            continue
        theme_id = f"theme:{slugify(theme_title)}"
        if not g.has_node(theme_id):
            g.add_node(theme_id, type="theme", label=theme_title)
            g.add_edge(topic_id, theme_id, type="covers")

        for pid in tc.get("paper_ids", []):
            paper = paper_by_id.get(pid)
            if paper is None:
                continue
            paper_node_id = f"paper:{pid}"
            if not g.has_node(paper_node_id):
                g.add_node(
                    paper_node_id,
                    type="paper",
                    label=paper.title or pid,
                    year=paper.year,
                    citation_count=paper.citation_count or 0,
                    source=paper.source,
                    url=paper.url,
                )
            g.add_edge(paper_node_id, theme_id, type="belongs_to")
            paper_to_themes.setdefault(paper_node_id, []).append(theme_id)

    # ── cites edge — only if BOTH ends are already in scope (in-review papers) ──
    for edge in citation_edges:
        src, tgt = f"paper:{edge.get('source')}", f"paper:{edge.get('target')}"
        if g.has_node(src) and g.has_node(tgt):
            g.add_edge(
                src,
                tgt,
                type="cites",
                is_influential=bool(edge.get("isInfluential")),
                intent=edge.get("intent") or "background",
            )

    # ── Claim / discourse layer — 2 distinct edges per claim ─────────────────
    for claim in [*included_claims, *review_claims]:
        paper_node_id = f"paper:{claim.paper_id}"
        themes_for_paper = paper_to_themes.get(paper_node_id)
        if not themes_for_paper:
            continue  # claim's source paper is outside review scope — skip (no orphan node)

        claim_id = f"claim:{claim.id}"
        g.add_node(
            claim_id,
            type="claim",
            label=(claim.text or "")[:160],
            verdict=claim.status,
            confidence=_claim_confidence(claim),
            low_confidence=claim.low_confidence,
            source_paper_id=paper_node_id,
            snippet=claim.snippet,
        )

        # Neutral — just traces where the evidence came from.
        g.add_edge(claim_id, paper_node_id, type="evidenced_by")

        # Meaningful — stance against the theme(s) the source paper belongs to.
        edge_type = _INTENT_EDGE_TYPE.get(claim.intent or "", "mentions")
        for theme_id in themes_for_paper:
            g.add_edge(claim_id, theme_id, type=edge_type)

    _enforce_guardrails(g)

    try:
        data = nx.node_link_data(g, edges="links")
    except TypeError:
        # Older networkx without the `edges=` kwarg (default already "links")
        data = nx.node_link_data(g)

    nodes = data["nodes"]
    edges_out = [{k: v for k, v in e.items() if k != "key"} for e in data.get("links", data.get("edges", []))]

    stats = {
        "papers": sum(1 for n in nodes if n.get("type") == "paper"),
        "themes": sum(1 for n in nodes if n.get("type") == "theme"),
        "claims": sum(1 for n in nodes if n.get("type") == "claim"),
        "contradicts_edges": sum(1 for e in edges_out if e.get("type") == "contradicts"),
    }
    log.info("Knowledge graph built: %s", stats)

    return {"nodes": nodes, "edges": edges_out, "stats": stats}


def _enforce_guardrails(g: nx.MultiDiGraph) -> None:
    """KG_MAX_NODES_RENDERED / KG_MAX_EDGES_RENDERED — drop the lowest-value
    claim nodes first (least essential layer) if the graph somehow still
    exceeds the render ceiling, rather than crashing or shipping a laggy graph.
    """
    settings = get_settings()
    max_nodes = settings.kg_max_nodes_rendered
    max_edges = settings.kg_max_edges_rendered

    if g.number_of_nodes() > max_nodes:
        claim_nodes = [n for n, d in g.nodes(data=True) if d.get("type") == "claim"]
        # Drop lowest-confidence claims first — keep the most decision-relevant ones.
        claim_nodes.sort(key=lambda n: g.nodes[n].get("confidence", 0))
        overflow = g.number_of_nodes() - max_nodes
        for n in claim_nodes[:overflow]:
            g.remove_node(n)
        log.warning(
            "Knowledge graph exceeded %d nodes — dropped %d lowest-confidence claim nodes",
            max_nodes,
            min(overflow, len(claim_nodes)),
        )

    if g.number_of_edges() > max_edges:
        log.warning(
            "Knowledge graph has %d edges (> %d guardrail) — rendering may be slow",
            g.number_of_edges(),
            max_edges,
        )
