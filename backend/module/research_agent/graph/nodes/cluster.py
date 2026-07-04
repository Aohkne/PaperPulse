"""Step ③ — Clustering + user approval (AutoSurvey, arXiv:2406.10252).

Replaces the old MMR outline + per-theme hybrid search. Themes are discovered
directly from the corpus by k-means over SPECTER v2 vectors — the natural
structure of the data, not a query projection:

  Phase 1 — Optimal k: try k = k_min..k_max, keep the k with the best cosine
            silhouette score. (< 30 embedded papers → fixed k = k_min, the
            silhouette is unstable on tiny corpora.)
  Phase 2 — K-means (k-means++). Clusters with < cluster_min_papers are
            discarded as outliers.
  Phase 3 — Rank each cluster's papers by cosine similarity to its centroid,
            cap at cluster_max_papers_per_theme (context-rot guard), then have
            the LLM name the cluster (title + description).
  Phase 4 — interrupt() so the user can rename / merge / keep themes before the
            writer runs.
"""

from __future__ import annotations

import asyncio
import json
import logging

import numpy as np
from langgraph.types import interrupt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from backend.config import get_settings
from backend.module.research_agent.graph.nodes.narrator import narrate_step
from backend.module.research_agent.graph.state import ResearchState
from backend.shared.models.paper import Paper
from backend.shared.models.review import Theme
from backend.shared.services.llm_client import chat_completion

log = logging.getLogger(__name__)

_SILHOUETTE_MIN_PAPERS = 30  # below this the silhouette score is too noisy → fixed k

_NAME_SYSTEM = (
    "You name a cluster of related academic papers. Given a list of paper titles "
    "(and short abstract snippets), return a concise, specific theme title (<= 8 words) "
    "and a 1-2 sentence description of what the cluster is about. "
    'Respond ONLY with JSON: {"title": "...", "description": "..."}'
)


def _find_optimal_k(vectors: np.ndarray, k_min: int, k_max: int) -> int:
    """Pick the k in [k_min, k_max] with the best cosine silhouette score."""
    n = len(vectors)
    hi = min(k_max, n - 1)
    if n < _SILHOUETTE_MIN_PAPERS or hi < k_min:
        return min(k_min, max(1, n))

    best_k, best_score = k_min, -1.0
    for k in range(k_min, hi + 1):
        labels = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=42).fit_predict(vectors)
        try:
            score = silhouette_score(vectors, labels, metric="cosine")
        except ValueError:
            continue
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def _rank_by_centroid(vectors: np.ndarray, papers: list[Paper]) -> list[Paper]:
    """Sort a cluster's papers by cosine similarity to the cluster centroid (closest first)."""
    centroid = vectors.mean(axis=0)
    norm = np.linalg.norm(vectors, axis=1) * np.linalg.norm(centroid) + 1e-12
    sims = vectors @ centroid / norm
    order = np.argsort(-sims)
    return [papers[i] for i in order]


async def _name_cluster(papers: list[Paper], fallback_idx: int) -> tuple[str, str]:
    lines = "\n".join(f"- {p.title or '(untitled)'}: {(p.abstract or '')[:160]}" for p in papers[:10])
    try:
        raw = await chat_completion(
            [
                {"role": "system", "content": _NAME_SYSTEM},
                {"role": "user", "content": f"Papers:\n{lines}"},
            ],
            temperature=get_settings().cluster_temperature,
        )
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        title = str(data.get("title") or "").strip()
        desc = str(data.get("description") or "").strip()
        if title:
            return title, desc
    except Exception as exc:
        log.warning("cluster naming failed (%s) — using fallback title", exc)
    return f"Theme {fallback_idx + 1}", ""


async def cluster_node(state: ResearchState) -> dict:
    settings = get_settings()
    papers = state.get("papers", [])
    embedded = [p for p in papers if p.embedding]
    await narrate_step(f"clustering {len(embedded)} embedded papers into research themes")

    themes: list[Theme] = []
    if len(embedded) < settings.cluster_min_papers:
        # Not enough embedded papers to cluster — one catch-all theme of whatever
        # papers DID get a vector (reseach-agent.html: papers without a SPECTER
        # vector are excluded from clustering).
        if embedded:
            themes = [Theme(title="Overview", description="", paper_ids=[p.paper_id for p in embedded])]
    else:
        vectors = np.asarray([p.embedding for p in embedded], dtype=float)
        k = _find_optimal_k(vectors, settings.cluster_k_min, settings.cluster_k_max)
        labels = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=42).fit_predict(vectors)

        grouped: dict[int, list[int]] = {}
        for idx, lbl in enumerate(labels):
            grouped.setdefault(int(lbl), []).append(idx)

        # Rank + cap each surviving cluster, then name them in parallel.
        candidates: list[list[Paper]] = []
        for idxs in grouped.values():
            if len(idxs) < settings.cluster_min_papers:
                continue  # outlier cluster — discard
            ranked = _rank_by_centroid(vectors[idxs], [embedded[i] for i in idxs])
            candidates.append(ranked[: settings.cluster_max_papers_per_theme])

        names = await asyncio.gather(*[_name_cluster(c, i) for i, c in enumerate(candidates)])
        for (title, desc), cluster_papers in zip(names, candidates):
            themes.append(Theme(title=title, description=desc, paper_ids=[p.paper_id for p in cluster_papers]))

    themes_payload = [{"title": t.title, "description": t.description, "paper_ids": t.paper_ids} for t in themes]

    # Phase 4 — user approve / rename / merge before writing.
    resume_value = interrupt({"type": "cluster_approval", "themes": themes_payload})
    if isinstance(resume_value, list):
        try:
            themes = [Theme(**t) if isinstance(t, dict) else t for t in resume_value]
        except Exception as exc:
            log.warning("Could not parse user-modified themes (%s) — using generated themes", exc)

    return {"themes": themes, "outline_approved": True}
