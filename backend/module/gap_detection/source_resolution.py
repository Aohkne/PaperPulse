"""source_resolution.py — Deterministic cross-source paper deduplication.

Merges raw paper records from multiple retrieval sources (S2, arXiv, …) into
canonical :class:`CanonicalPaper` objects using a three-level key hierarchy:

  1. DOI (lowercase, strip ``https://doi.org/`` prefix)
  2. Title-normalised (NFC + lowercase + strip punctuation)
  3. S2 paperId (fallback — reuses existing dedup key)

Public API
----------
``resolve_papers(records)`` — the only entry point callers need.

Input
-----
Each raw record is a :class:`RawRecord` dataclass that wraps a ``Paper``
object with its corpus role and the name of the source that produced it.

Merge rules
-----------
- ``sources``: sorted union of all source names in the group.
- ``corpus_role``: ``USER`` if *any* record in the group is ``USER``.
- ``fulltext``: taken from the first record that carries one.
- ``abstract``: preferred from the fulltext-bearing record; else longest.
- Other metadata: fulltext-bearing record wins; first record as tiebreaker.
- ``is_influential``: ``True`` if *any* record is influential.
- ``s2_paper_id``: first non-empty S2 paperId found in the group.

Error handling
--------------
Individual records that raise during key computation are skipped with a
warning (covers source-timeout scenarios where callers pass partial data).
Groups that raise during merge are also skipped with a warning.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from backend.module.gap_detection.schemas import CanonicalPaper, CorpusRole
from backend.shared.models.paper import Paper

logger = logging.getLogger(__name__)

TITLE_FUZZY_THRESHOLD = 90
_VERSION_TOKENS = {
    "2",
    "3",
    "4",
    "ii",
    "iii",
    "iv",
    "v",
    "part",
    "extended",
    "revisited",
    "v2",
    "v3",
}

try:
    from rapidfuzz import fuzz as _fuzz

    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    logger.warning("rapidfuzz not installed — fuzzy title fallback disabled; install with: uv add rapidfuzz")


# ── Input type ───────────────────────────────────────────────────────────────


@dataclass
class RawRecord:
    """One paper from one retrieval source, ready for resolution.

    Attributes:
        paper:       The raw :class:`Paper` object from the source API.
        corpus_role: Whether this paper came from a user-query search or the
                     background corpus.
        source_name: Short label for the originating source, e.g. ``"s2"``
                     or ``"arxiv"``.
        fulltext:    Full-text content if available (e.g. fetched from PDF).
    """

    paper: Paper
    corpus_role: CorpusRole
    source_name: str
    fulltext: str | None = field(default=None)


# ── Key normalisation helpers ─────────────────────────────────────────────────


def _normalize_doi(raw: str) -> str:
    """Return a normalised DOI string, or '' if *raw* is empty/None.

    Strips leading URL prefixes and lowercases the result so that
    ``https://doi.org/10.1234/ABC`` and ``10.1234/abc`` hash identically.
    """
    if not raw:
        return ""
    doi = raw.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi


def _normalize_title(raw: str) -> str:
    """Return a normalised title key for deduplication.

    Steps: NFC normalisation → lowercase → strip punctuation →
    collapse whitespace.  Two titles that are typographically identical
    (different hyphens, unicode variants, punctuation) map to the same key.
    """
    if not raw:
        return ""
    norm = unicodedata.normalize("NFC", raw)
    norm = norm.lower()
    norm = re.sub(r"[^\w\s]", "", norm)  # drop punctuation
    norm = re.sub(r"\s+", " ", norm).strip()  # collapse whitespace
    return norm


def _resolution_key(record: RawRecord) -> str:
    """Compute the canonical resolution key for *record*.

    Priority: DOI > normalised title > S2 paperId.  Returns an empty string
    for records that carry none of these identifiers.
    """
    ext = record.paper.external_ids or {}
    doi = _normalize_doi(ext.get("DOI") or "")
    if doi:
        return f"doi:{doi}"

    title_norm = _normalize_title(record.paper.title or "")
    if title_norm:
        return f"title:{title_norm}"

    pid = record.paper.paper_id or ""
    if pid:
        return f"s2:{pid}"

    return ""


def _title_norm_from_key(key: str) -> str:
    return key.removeprefix("title:")


def _title_similarity(a: str, b: str) -> float:
    if not a or not b or not _HAS_RAPIDFUZZ:
        return 0.0
    return _fuzz.ratio(a, b)


def _title_tokens(raw: str) -> set[str]:
    """Tokenize a normalised title into a stable comparison set."""
    return {tok for tok in re.split(r"\s+", raw.strip()) if tok}


def _has_version_suffix_guard(a: str, b: str) -> bool:
    """Return True when titles differ by a version/suffix token that should not merge.

    We only use this after fuzzy similarity is already high enough to be a
    candidate merge.  The guard blocks obvious versioned variants such as
    ``II``, ``Part 2``, ``v2``, ``Extended`` and similar suffixes.
    """
    tokens_a = _title_tokens(a)
    tokens_b = _title_tokens(b)
    if not tokens_a or not tokens_b:
        return False

    symdiff = tokens_a.symmetric_difference(tokens_b)
    if not symdiff:
        return False

    for tok in symdiff:
        norm = tok.lower()
        if norm in _VERSION_TOKENS:
            return True
        if re.fullmatch(r"v\d+", norm):
            return True
        if re.fullmatch(r"\d+", norm):
            return True
        if re.fullmatch(r"[ivxlcdm]+", norm):
            return True
    return False


# ── Merge logic ───────────────────────────────────────────────────────────────


def _merge_group(key: str, group: list[RawRecord]) -> CanonicalPaper:
    """Merge a non-empty list of records that share *key* into one paper.

    Records with fulltext are sorted first; within that tier, sorted by
    source_name for deterministic output regardless of call order.
    """
    sorted_group = sorted(
        group,
        key=lambda r: (0 if r.fulltext else 1, r.source_name),
    )
    primary = sorted_group[0]

    sources = sorted({r.source_name for r in group})

    corpus_role = CorpusRole.USER if any(r.corpus_role == CorpusRole.USER for r in group) else CorpusRole.BACKGROUND

    fulltext = next((r.fulltext for r in sorted_group if r.fulltext), None)

    # Abstract: prefer primary (fulltext bearer), else pick the longest.
    if primary.paper.abstract:
        abstract = primary.paper.abstract
    else:
        candidates = [r.paper.abstract for r in sorted_group if r.paper.abstract]
        abstract = max(candidates, key=len) if candidates else None

    s2_paper_id = next((r.paper.paper_id for r in group if r.paper.paper_id), None)

    return CanonicalPaper(
        id=key,
        sources=sources,
        corpus_role=corpus_role,
        fulltext_available=fulltext is not None,
        title=primary.paper.title,
        abstract=abstract,
        fulltext=fulltext,
        year=primary.paper.year,
        citation_count=primary.paper.citation_count,
        authors=list(primary.paper.authors or []),
        url=primary.paper.url,
        open_access_pdf=primary.paper.open_access_pdf,
        external_ids=dict(primary.paper.external_ids or {}),
        s2_paper_id=s2_paper_id,
        is_influential=any(r.paper.is_influential for r in group),
        venue=getattr(primary.paper, "venue", None),
    )


# ── Public entry point ────────────────────────────────────────────────────────


def resolve_papers(records: list[RawRecord]) -> list[CanonicalPaper]:
    """Resolve and deduplicate *records* into a list of :class:`CanonicalPaper`.

    Deterministic — no LLM, no I/O.  Safe to call in a hot path.

    Records that fail key computation (e.g. completely empty objects passed
    after a source timeout) are silently skipped.  Groups that fail during
    merge are also skipped with a warning so the rest of the output is intact.

    Args:
        records: Raw paper records from one or more retrieval sources.

    Returns:
        Deduplicated list of :class:`CanonicalPaper`, one per unique key.
        Order is deterministic: sorted by canonical key for reproducibility.
    """
    groups: dict[str, list[RawRecord]] = {}

    for rec in records:
        try:
            key = _resolution_key(rec)
        except Exception:
            logger.warning(
                "source_resolution: failed to compute key for record title=%r — skipping",
                getattr(getattr(rec, "paper", None), "title", None),
                exc_info=True,
            )
            continue

        if not key:
            logger.debug(
                "source_resolution: skipping record with no identifiable key (title=%r)",
                getattr(rec.paper, "title", None),
            )
            continue

        groups.setdefault(key, []).append(rec)

    title_groups: list[tuple[str, str, list[RawRecord]]] = []
    result: list[CanonicalPaper] = []
    for key, group in sorted(groups.items()):
        if key.startswith("title:"):
            title_groups.append((_title_norm_from_key(key), key, group))
            continue
        try:
            result.append(_merge_group(key, group))
        except Exception:
            logger.warning(
                "source_resolution: failed to merge group key=%r (%d records) — skipping",
                key,
                len(group),
                exc_info=True,
            )

    if not title_groups:
        return result

    parent = list(range(len(title_groups)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for i in range(len(title_groups)):
        norm_i, _, _ = title_groups[i]
        for j in range(i + 1, len(title_groups)):
            norm_j, _, _ = title_groups[j]
            if _title_similarity(norm_i, norm_j) >= TITLE_FUZZY_THRESHOLD and not _has_version_suffix_guard(
                norm_i, norm_j
            ):
                union(i, j)

    clusters: dict[int, list[tuple[str, list[RawRecord]]]] = defaultdict(list)
    for idx, (_norm, key, group) in enumerate(title_groups):
        clusters[find(idx)].append((key, group))

    for items in clusters.values():
        merged_group: list[RawRecord] = []
        for _, group in items:
            merged_group.extend(group)
        merged_key = items[0][0]
        try:
            result.append(_merge_group(merged_key, merged_group))
        except Exception:
            logger.warning(
                "source_resolution: failed to merge fuzzy title cluster key=%r (%d records) — skipping",
                merged_key,
                len(merged_group),
                exc_info=True,
            )

    return sorted(result, key=lambda cp: cp.id)
