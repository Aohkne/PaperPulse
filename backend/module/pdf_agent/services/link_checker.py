"""Link Liveness Check — Step P3c (PLAN §7 Phase 5).

`httpx.AsyncClient().head()` in parallel for raw URLs found in prose — not the
academic citations already covered by citation_lookup.py, no LLM involved.
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

from backend.config import get_settings
from backend.module.pdf_agent.graph.state import Section

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s\\{}\"'<>]+")


def extract_urls(sections: list[Section]) -> dict[str, str]:
    """Returns {url: first_section_title_it_appeared_in}, deduped."""
    found: dict[str, str] = {}
    for s in sections:
        for m in _URL_RE.finditer(s["raw_latex"]):
            url = m.group(0).rstrip(".,;)")
            found.setdefault(url, s["title"])
    return found


async def check_url(url: str) -> dict:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=settings.pdf_agent_link_check_timeout_s
        ) as client:
            resp = await client.head(url)
            if resp.status_code >= 400:
                # Some servers reject HEAD outright — a lightweight GET before declaring it dead.
                resp = await client.get(url)
            return {"url": url, "alive": resp.status_code < 400, "status_code": resp.status_code}
    except Exception as exc:
        logger.info("link check failed for %s: %s", url, exc)
        return {"url": url, "alive": False, "status_code": None}


async def check_links_batch(sections: list[Section]) -> list[dict]:
    """Returns [{"section_title", "url", "alive", "status_code"}] for every distinct URL found."""
    urls = extract_urls(sections)
    if not urls:
        return []
    results = await asyncio.gather(*(check_url(u) for u in urls), return_exceptions=True)
    out: list[dict] = []
    for (url, title), r in zip(urls.items(), results):
        if isinstance(r, Exception):
            out.append({"section_title": title, "url": url, "alive": False, "status_code": None})
        else:
            out.append({"section_title": title, **r})
    return out
