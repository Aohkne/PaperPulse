"""arXiv services for PaperPulse gap detection.

① fetch_arxiv_text  — Fetch full text from ar5iv (arXiv HTML mirror).
   Coverage: ~80%+ for CS/AI/ML papers.
   ArXiv ID taken from paper.externalIds.ArXiv (collected at Step ②/②bis).
   Graceful degradation: falls back to plain-text if beautifulsoup4 absent.

② arxiv_search — Search arXiv REST API for papers matching a query (TIP-405).
   Returns list[Paper] (same model as Semantic Scholar) with source="arxiv".
   Called by retrieval.search() in parallel with S2.
"""

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from backend.shared.models.paper import Paper

_AR5IV_BASE = "https://ar5iv.labs.arxiv.org/html"
_MAX_CHARS = 10_000  # truncate to avoid overwhelming LLM context

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False
    logging.warning("beautifulsoup4 not installed — arXiv fetcher will use plain-text fallback")


def _strip_html(html: str) -> str:
    """Minimal HTML → text without bs4: strip tags, collapse whitespace."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def fetch_arxiv_text(arxiv_id: str) -> str | None:
    """Fetch ar5iv HTML and return plain text (truncated to 10k chars).

    Returns None if the paper is not available on ar5iv.
    """
    url = f"{_AR5IV_BASE}/{arxiv_id}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            logging.debug("ar5iv %s: HTTP %d", arxiv_id, resp.status_code)
            return None

        html = resp.text
        if _HAS_BS4:
            soup = BeautifulSoup(html, "lxml" if _has_lxml() else "html.parser")
            # Remove nav/header/footer/script/style nodes
            for tag in soup(["nav", "header", "footer", "script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        else:
            text = _strip_html(html)

        return text[:_MAX_CHARS] if text else None
    except Exception as exc:
        logging.warning("ar5iv fetch failed for %s: %s", arxiv_id, exc)
        return None


def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False


# ── arXiv search (TIP-405) ────────────────────────────────────────────────────

_ARXIV_API_BASE = "https://export.arxiv.org/api/query"
_ARXIV_SEARCH_TIMEOUT = 15  # seconds — short to avoid blocking retrieval pipeline

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"
_NS_MAP = {"atom": _ATOM_NS, "arxiv": _ARXIV_NS}

_VERSION_SUFFIX_RE = re.compile(r"v\d+$")


def _parse_arxiv_id(entry_id_url: str) -> str:
    """Extract bare arXiv ID from a full URL like http://arxiv.org/abs/2310.12345v2.

    Handles both modern format (2310.12345) and old format (cs/0601001).
    Strips trailing version suffix vN.
    """
    parts = entry_id_url.split("/abs/", 1)
    base = parts[1] if len(parts) == 2 else entry_id_url.rstrip("/").rsplit("/", 1)[-1]
    return _VERSION_SUFFIX_RE.sub("", base)


def _parse_arxiv_feed(xml_text: str) -> list[Paper]:
    """Parse arXiv Atom feed XML into Paper objects. Returns [] on any parse error."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logging.warning("arxiv_fetcher: failed to parse arXiv Atom feed")
        return []

    papers: list[Paper] = []
    for entry in root.findall("atom:entry", _NS_MAP):
        try:
            entry_id = entry.findtext("atom:id", default="", namespaces=_NS_MAP) or ""
            arxiv_id = _parse_arxiv_id(entry_id)
            if not arxiv_id:
                continue

            title_el = entry.find("atom:title", _NS_MAP)
            title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
            if not title:
                continue

            summary_el = entry.find("atom:summary", _NS_MAP)
            abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else None

            published = entry.findtext("atom:published", default="", namespaces=_NS_MAP) or ""
            year = int(published[:4]) if published and len(published) >= 4 else None

            authors = []
            for author_el in entry.findall("atom:author", _NS_MAP):
                name_el = author_el.find("atom:name", _NS_MAP)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            # HTML page URL
            url = f"https://arxiv.org/abs/{arxiv_id}"
            for link_el in entry.findall("atom:link", _NS_MAP):
                if link_el.get("rel") == "alternate" and link_el.get("type") == "text/html":
                    url = link_el.get("href", url)
                    break

            # PDF URL
            open_access_pdf = f"https://arxiv.org/pdf/{arxiv_id}"
            for link_el in entry.findall("atom:link", _NS_MAP):
                if link_el.get("title") == "pdf":
                    open_access_pdf = link_el.get("href", open_access_pdf)
                    break

            doi_el = entry.find("arxiv:doi", _NS_MAP)
            doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

            ext: dict = {"ArXiv": arxiv_id}
            if doi:
                ext["DOI"] = doi

            papers.append(Paper(
                paperId=f"arxiv:{arxiv_id}",
                title=title,
                abstract=abstract,
                year=year,
                authors=authors,
                url=url,
                openAccessPdf=open_access_pdf,
                externalIds=ext,
                source="arxiv",
            ))
        except Exception:
            logging.warning("arxiv_fetcher: failed to parse entry — skipping", exc_info=True)

    return papers


async def arxiv_search(query: str, limit: int = 20) -> list[Paper]:
    """Search arXiv REST API for papers matching *query*.

    Returns a list of Paper objects with source="arxiv" and
    paper_id="arxiv:<arxiv_id>".  DOI is included in external_ids when present
    so resolve_papers() can merge arXiv and S2 records by DOI.

    Always returns a list — empty on timeout or any network/parse error so
    callers can treat it as a non-fatal supplement.
    """
    params = {
        "search_query": f"all:{query}",
        "max_results": str(limit),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        async with httpx.AsyncClient(timeout=_ARXIV_SEARCH_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(_ARXIV_API_BASE, params=params)
        if resp.status_code != 200:
            logging.warning(
                "arxiv_search: HTTP %d for query=%r", resp.status_code, query[:60]
            )
            return []
        papers = _parse_arxiv_feed(resp.text)
        logging.info("arxiv_search: query=%r → %d papers", query[:60], len(papers))
        return papers
    except Exception as exc:
        logging.warning("arxiv_search: failed for query=%r: %s", query[:60], exc)
        return []
