"""PubMed search via NCBI E-utilities (esearch + efetch) — SPEC 2.0 §Step ①.

Free, no API key required. NCBI recommends (but does not enforce) a `tool`
and `email` param for identification — reuses OPENALEX_EMAIL if set.

Only invoked when the LLM-selected sources for a topic include "pubmed"
(biomedical / health domain queries) — see intent_router.py.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

from backend.config import get_settings
from backend.shared.models.paper import Paper

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


async def search_pubmed(query: str, limit: int = 100) -> list[Paper]:
    """Search PubMed by keyword, return up to *limit* Paper objects."""
    settings = get_settings()
    email = getattr(settings, "openalex_email", "") or "research@paperpulse.app"
    common = {"tool": "PaperPulse", "email": email}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            esearch = await client.get(
                f"{_BASE}/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmax": limit, "retmode": "json", **common},
            )
            esearch.raise_for_status()
            ids = esearch.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            efetch = await client.get(
                f"{_BASE}/efetch.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "xml", **common},
            )
            efetch.raise_for_status()
            return _parse_efetch(efetch.text)
    except Exception as exc:
        logging.warning("PubMed search failed: %s", exc)
        return []


def _parse_efetch(xml_text: str) -> list[Paper]:
    papers: list[Paper] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logging.warning("PubMed efetch XML parse error: %s", exc)
        return papers

    for article in root.findall(".//PubmedArticle"):
        try:
            paper = _parse_article(article)
            if paper:
                papers.append(paper)
        except Exception as exc:
            logging.warning("PubMed article parse error: %s", exc)

    return papers


def _parse_article(article: ET.Element) -> Paper | None:
    medline = article.find("MedlineCitation")
    if medline is None:
        return None
    pmid = (medline.findtext("PMID") or "").strip()

    art = medline.find("Article")
    if art is None:
        return None
    title = (art.findtext("ArticleTitle") or "").strip()
    if not title:
        return None

    abstract_parts = [node.text or "" for node in art.findall("Abstract/AbstractText")]
    abstract = " ".join(p.strip() for p in abstract_parts if p.strip()) or None

    year = None
    pub_date = art.find("Journal/JournalIssue/PubDate")
    if pub_date is not None:
        year_text = pub_date.findtext("Year")
        if year_text and year_text.isdigit():
            year = int(year_text)

    authors: list[str] = []
    for au in art.findall("AuthorList/Author"):
        last = au.findtext("LastName")
        fore = au.findtext("ForeName")
        if last:
            authors.append(f"{fore} {last}".strip() if fore else last)

    external_ids: dict[str, str] = {"PubMed": pmid} if pmid else {}
    for eid in article.findall(".//ArticleId"):
        if eid.get("IdType") == "doi" and eid.text:
            external_ids["DOI"] = eid.text

    return Paper(
        paperId=f"pubmed_{pmid}" if pmid else title[:50],
        title=title,
        abstract=abstract,
        year=year,
        citationCount=None,
        authors=authors,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
        externalIds=external_ids,
        source="pubmed",
    )
