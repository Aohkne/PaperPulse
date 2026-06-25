"""Knowledge Graph response models — knowledge-graph_SPEC_2.0.md §Node/Edge JSON Schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    type: Literal["topic", "theme", "paper", "claim"]
    label: str
    # Paper-only
    year: int | None = None
    citation_count: int | None = None
    source: str | None = None
    url: str | None = None
    # Claim-only
    verdict: str | None = None
    confidence: float | None = None
    low_confidence: bool | None = None
    source_paper_id: str | None = None
    snippet: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["covers", "belongs_to", "cites", "evidenced_by", "supports", "contradicts", "mentions"]
    is_influential: bool | None = None
    intent: str | None = None


class GraphStats(BaseModel):
    papers: int = 0
    themes: int = 0
    claims: int = 0
    contradicts_edges: int = 0


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: GraphStats
