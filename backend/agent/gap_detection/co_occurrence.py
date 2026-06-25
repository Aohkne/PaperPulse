"""co_occurrence.py — Method × domain co-occurrence matrix for gap detection (TIP-P2-04).

Counts how many papers in the corpus cover each (method, domain) pair.
Pairs that are under-explored (count < CO_OCCURRENCE_THRESHOLD) are surfaced
as candidate methodological gaps by ``method_detector_node``.

Field mapping from ``ExtractedPaperData`` (schemas.py):
  - method  → ``methodology: str | None``  (single string; split on comma/slash
              for compound methods, e.g. "BERT, fine-tuning")
  - domain  → ``topics: list[str]``         (multi-valued)

Note: ``ExtractedPaperData`` does NOT have ``methodology_tags`` or
``domain_tags`` as the TIP initially assumed.  This module adapts to the
actual schema: ``methodology`` is normalised and tokenised; ``topics`` are
used as-is (lowercased).  This was reported as a finding in the Completion
Report (TIP-P2-04).

This module is pure: no I/O, no LLM calls, no side effects.
"""

from __future__ import annotations

from collections import defaultdict

from backend.agent.gap_detection.settings import get_co_occurrence_threshold


def _normalise_method(methodology: str | None) -> list[str]:
    """Split a compound methodology string into individual method tokens.

    Examples:
        "BERT, fine-tuning" → ["bert", "fine-tuning"]
        "CNN/RNN"           → ["cnn", "rnn"]
        None                → []
    """
    if not methodology:
        return []
    # Split on comma or slash; strip and lowercase each token.
    import re
    tokens = re.split(r"[,/]", methodology)
    return [t.strip().lower() for t in tokens if t.strip()]


def build_co_occurrence(extracted_data: list) -> dict[tuple[str, str], int]:
    """Count how many papers cover each (method, domain) pair.

    Args:
        extracted_data: ``list[ExtractedPaperData]`` — the pipeline state value.

    Returns:
        ``{(method_token, domain_token): count}`` mapping.
        Both keys are lowercase-normalised.

    Field mapping:
        - method tokens ← ``paper.methodology`` (string, split on ``[,/]``)
        - domain tokens ← ``paper.topics``      (list[str])
    """
    matrix: dict[tuple[str, str], int] = defaultdict(int)
    seen_papers: set[str] = set()

    for paper in extracted_data:
        paper_ref = getattr(paper, "paper_ref", None)
        paper_id = getattr(paper_ref, "paper_id", None)
        if paper_id and paper_id in seen_papers:
            continue
        if paper_id:
            seen_papers.add(paper_id)

        methods = _normalise_method(getattr(paper, "methodology", None))
        domains = [t.strip().lower() for t in (getattr(paper, "topics", None) or []) if t.strip()]

        for m in methods:
            for d in domains:
                matrix[(m, d)] += 1

    return dict(matrix)


def find_underexplored_pairs(
    matrix: dict[tuple[str, str], int],
    all_methods: list[str],
    all_domains: list[str],
    threshold: int | None = None,
) -> list[tuple[str, str]]:
    """Return (method, domain) pairs whose coverage count is below *threshold*.

    A pair below the threshold has been studied by too few papers to be
    considered "covered" — it is a candidate methodological gap.

    Args:
        matrix:      Output of :func:`build_co_occurrence`.
        all_methods: Distinct method tokens to check (lowercase).
        all_domains: Distinct domain tokens to check (lowercase).
        threshold:   Minimum paper-count to consider a pair "covered".
                     Defaults to ``get_co_occurrence_threshold()`` (env
                     ``CO_OCCURRENCE_THRESHOLD``, default 2).

    Returns:
        ``list[(method, domain)]`` of under-explored pairs, in the order
        ``all_methods × all_domains`` (deterministic for tests).
    """
    t = threshold if threshold is not None else get_co_occurrence_threshold()
    return [
        (m.lower(), d.lower())
        for m in all_methods
        for d in all_domains
        if matrix.get((m.lower(), d.lower()), 0) < t
    ]


def collect_corpus_vocab(extracted_data: list) -> tuple[list[str], list[str]]:
    """Collect distinct (method, domain) tokens across all papers.

    Helper for ``method_detector_node`` so it can pass consistent
    ``all_methods`` / ``all_domains`` lists to :func:`find_underexplored_pairs`.

    Returns:
        ``(sorted_methods, sorted_domains)`` — both deduped and sorted for
        deterministic output.
    """
    methods: set[str] = set()
    domains: set[str] = set()

    for paper in extracted_data:
        for m in _normalise_method(getattr(paper, "methodology", None)):
            methods.add(m)
        for t in (getattr(paper, "topics", None) or []):
            d = t.strip().lower()
            if d:
                domains.add(d)

    return sorted(methods), sorted(domains)
