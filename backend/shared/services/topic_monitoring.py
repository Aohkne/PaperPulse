from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException

from backend.config import get_settings
from backend.module.research_agent.services.openalex import search_openalex
from backend.module.research_agent.services.pubmed_search import search_pubmed
from backend.shared.models.paper import Paper
from backend.shared.services import arxiv_fetcher, semantic_scholar
from supabase import Client, create_client

log = logging.getLogger(__name__)

_SPACE_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\W_]+|[\W_]+$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ELIGIBLE_STATES = {"candidate", "auto_watching"}
_BLOCKED_STATES = {"muted", "deleted"}
_VISIBLE_TOPIC_STATES = {"auto_watching", "candidate", "muted"}
_DEFAULT_AUTO_WATCH_REASON = "top_interest_rank"
TOPIC_SCORE_NEW_SESSION = 5.0
TOPIC_SCORE_FOLLOWUP = 3.0
TOPIC_SCORE_PLAN_APPROVAL = 3.0
TOPIC_SCORE_REOPEN = 1.0

_TOPIC_SIGNAL_WEIGHTS = {
    "new_session": TOPIC_SCORE_NEW_SESSION,
    "followup": TOPIC_SCORE_FOLLOWUP,
    "plan_approval": TOPIC_SCORE_PLAN_APPROVAL,
    "reopen": TOPIC_SCORE_REOPEN,
}


class TopicMonitorError(RuntimeError):
    pass


def _service_db_client() -> Client:
    settings = get_settings()
    if not settings.supabase_service_key:
        raise HTTPException(status_code=500, detail="SUPABASE_SERVICE_KEY is required for topic monitoring writes.")
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _collapse_spaces(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip())


def _strip_edge_punctuation(value: str) -> str:
    return _EDGE_PUNCT_RE.sub("", value).strip()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_iso(dt: datetime | None = None) -> str:
    base = dt or _utcnow()
    return base.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def normalize_topic_identity(raw_query: str, label: str | None = None) -> tuple[str, str]:
    base_label = label if label is not None else raw_query
    cleaned_label = _strip_edge_punctuation(_collapse_spaces(base_label or ""))
    normalized_query = _strip_edge_punctuation(_collapse_spaces((raw_query or "").lower()))

    if not cleaned_label or not normalized_query or not any(ch.isalnum() for ch in normalized_query):
        raise HTTPException(status_code=400, detail="Topic input is empty after normalization.")

    return cleaned_label, normalized_query


def _normalize_keywords(keywords: list[str] | None) -> list[str]:
    if not keywords:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in keywords:
        value = _strip_edge_punctuation(_collapse_spaces(str(item or "")))
        if not value:
            continue
        dedup_key = value.lower()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        normalized.append(value)
    return normalized


def _topic_select(db: Client):
    return db.table("research_topics").select("id,label,normalized_query,keywords,created_at,updated_at")


def _interest_select(db: Client):
    return db.table("user_topic_interests").select(
        "id,user_id,topic_id,interest_score,state,auto_watch_reason,last_checked_at,last_notified_at,created_at,updated_at"
    )


def _chat_select(db: Client):
    return db.table("chats").select(
        "id,user_id,title,feature,status,summary,thread_id,topic_id,created_at,updated_at,last_message_at,deleted_at"
    )


def _paper_select(db: Client):
    return db.table("papers").select(
        "id,doi,arxiv_id,s2_paper_id,openalex_id,pubmed_id,title,abstract,authors,year,published_at,url,open_access_pdf,source_metadata,created_at,updated_at"
    )


def _match_select(db: Client):
    return db.table("topic_paper_matches").select(
        "id,topic_id,paper_id,vector_score,lexical_score,recency_score,authority_score,hybrid_score,reason,first_seen_at,created_at,updated_at"
    )


def _event_select(db: Client):
    return db.table("notification_events").select("id,user_id,topic_id,paper_id,channel,status,created_at,updated_at")


def _notification_select(db: Client):
    return db.table("notifications").select(
        "id,user_id,type,content,paper_ref,is_read,created_at,topic_id,paper_id,reason,score"
    )


def _settings_select(db: Client):
    return db.table("notification_settings").select("user_id,pause_all_in_app,created_at,updated_at")


def _score(value: Any) -> float:
    return float(value or 0)


def _sort_interest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _score(row.get("interest_score")),
            row.get("updated_at") or row.get("created_at") or "",
        ),
        reverse=True,
    )


def _sort_visible_topic_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"auto_watching": 0, "muted": 1, "candidate": 2}
    return sorted(
        rows,
        key=lambda row: (
            priority.get(row.get("state"), 9),
            -_score(row.get("interest_score")),
            row.get("updated_at") or row.get("created_at") or "",
        ),
    )


def _tokenize(value: str | None) -> list[str]:
    if not value:
        return []
    return _TOKEN_RE.findall(value.lower())


def _unique_tokens(value: str | None) -> set[str]:
    return set(_tokenize(value))


def _normalized_title(value: str | None) -> str:
    lowered = _collapse_spaces((value or "").lower())
    return _strip_edge_punctuation(lowered)


def _published_at_from_paper(paper: Paper) -> str | None:
    if paper.year:
        return f"{int(paper.year):04d}-01-01T00:00:00Z"
    return None


def _open_access_payload(paper: Paper) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if paper.open_access_pdf:
        payload["url"] = paper.open_access_pdf
    if paper.open_access_pdf_status:
        payload["status"] = paper.open_access_pdf_status
    return payload


def _paper_source_metadata(paper: Paper) -> dict[str, Any]:
    return {
        "source": paper.source,
        "citation_count": paper.citation_count,
        "external_ids": dict(paper.external_ids or {}),
        "raw_paper_id": paper.paper_id,
    }


def _paper_identity_fields(paper: Paper) -> dict[str, str | None]:
    external_ids = paper.external_ids or {}
    doi = external_ids.get("DOI") or external_ids.get("doi")
    arxiv_id = external_ids.get("ArXiv") or external_ids.get("arXiv") or external_ids.get("arxiv")
    pubmed_id = external_ids.get("PubMed") or external_ids.get("pubmed")
    openalex_id = None
    s2_paper_id = None
    paper_id = paper.paper_id or ""
    if paper.source == "semantic_scholar":
        s2_paper_id = paper_id
    elif paper.source == "openalex":
        openalex_id = paper_id if paper_id.startswith("OA_") else paper_id
    elif paper.source == "pubmed" and not pubmed_id:
        pubmed_id = paper_id.removeprefix("pubmed_") if paper_id.startswith("pubmed_") else paper_id
    elif paper.source == "arxiv" and not arxiv_id:
        arxiv_id = paper_id.removeprefix("arxiv:") if paper_id.startswith("arxiv:") else paper_id

    return {
        "doi": doi,
        "arxiv_id": arxiv_id,
        "s2_paper_id": s2_paper_id,
        "openalex_id": openalex_id,
        "pubmed_id": pubmed_id,
        "normalized_title": _normalized_title(paper.title),
    }


async def get_or_create_research_topic(
    raw_query: str,
    *,
    label: str | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    cleaned_label, normalized_query = normalize_topic_identity(raw_query, label=label)
    db = _service_db_client()

    existing = _topic_select(db).eq("normalized_query", normalized_query).limit(1).execute()
    if existing.data:
        return existing.data[0]

    payload = {
        "label": cleaned_label,
        "normalized_query": normalized_query,
        "keywords": _normalize_keywords(keywords),
    }
    created = db.table("research_topics").insert(payload).execute()
    if created.data:
        return created.data[0]

    fallback = _topic_select(db).eq("normalized_query", normalized_query).limit(1).execute()
    if fallback.data:
        return fallback.data[0]
    raise HTTPException(status_code=500, detail="Failed to create research topic")


async def get_notification_settings(user_id: str) -> dict[str, Any]:
    db = _service_db_client()
    existing = _settings_select(db).eq("user_id", user_id).limit(1).execute().data or []
    if existing:
        return existing[0]
    created = db.table("notification_settings").insert({"user_id": user_id, "pause_all_in_app": False}).execute()
    if not created.data:
        raise HTTPException(status_code=500, detail="Failed to initialize notification settings")
    return created.data[0]


async def update_notification_settings(user_id: str, *, pause_all_in_app: bool) -> dict[str, Any]:
    await get_notification_settings(user_id)
    db = _service_db_client()
    updated = (
        db.table("notification_settings")
        .update({"pause_all_in_app": pause_all_in_app})
        .eq("user_id", user_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Failed to update notification settings")
    return updated.data[0]


async def rebalance_auto_watch_topics(
    user_id: str,
    *,
    auto_watch_reason: str | None = None,
) -> list[dict[str, Any]]:
    db = _service_db_client()
    rows = _interest_select(db).eq("user_id", user_id).execute().data or []
    eligible = [row for row in rows if row.get("state") in _ELIGIBLE_STATES]
    ranked = _sort_interest_rows(eligible)
    winner_ids = {row["id"] for row in ranked[: get_settings().max_auto_topics_per_user]}

    for row in ranked:
        desired_state = "auto_watching" if row["id"] in winner_ids else "candidate"
        desired_reason = row.get("auto_watch_reason")
        if desired_state == "auto_watching" and auto_watch_reason is not None:
            desired_reason = auto_watch_reason
        elif desired_state == "auto_watching" and not desired_reason:
            desired_reason = _DEFAULT_AUTO_WATCH_REASON
        elif desired_state == "candidate":
            desired_reason = None

        if row.get("state") == desired_state and row.get("auto_watch_reason") == desired_reason:
            continue

        db.table("user_topic_interests").update(
            {
                "state": desired_state,
                "auto_watch_reason": desired_reason,
            }
        ).eq("id", row["id"]).execute()

    return _interest_select(db).eq("user_id", user_id).execute().data or []


async def list_user_topic_interests(user_id: str) -> list[dict[str, Any]]:
    db = _service_db_client()
    interests = _interest_select(db).eq("user_id", user_id).execute().data or []
    topics = {row["id"]: row for row in (_topic_select(db).execute().data or [])}
    visible: list[dict[str, Any]] = []
    for interest in interests:
        if interest.get("state") not in _VISIBLE_TOPIC_STATES:
            continue
        topic = topics.get(interest.get("topic_id"))
        if not topic:
            continue
        visible.append(
            {
                "topic_id": topic["id"],
                "label": topic.get("label"),
                "normalized_query": topic.get("normalized_query"),
                "state": interest.get("state"),
                "interest_score": _score(interest.get("interest_score")),
                "auto_watch_reason": interest.get("auto_watch_reason"),
                "last_checked_at": interest.get("last_checked_at"),
                "last_notified_at": interest.get("last_notified_at"),
                "updated_at": interest.get("updated_at"),
            }
        )
    return _sort_visible_topic_rows(visible)


async def update_user_topic_state(user_id: str, topic_id: str, *, state: str) -> dict[str, Any]:
    if state not in {"muted", "candidate"}:
        raise HTTPException(status_code=400, detail="Unsupported topic state transition")
    db = _service_db_client()
    existing_rows = _interest_select(db).eq("user_id", user_id).eq("topic_id", topic_id).limit(1).execute().data or []
    if not existing_rows:
        raise HTTPException(status_code=404, detail="Topic interest not found")
    existing = existing_rows[0]
    current_state = existing.get("state")
    if current_state == "deleted":
        raise HTTPException(status_code=404, detail="Topic interest not found")
    if state == "candidate" and current_state != "muted":
        raise HTTPException(status_code=400, detail="Only muted topics can be restored to candidate")

    updated = (
        db.table("user_topic_interests")
        .update(
            {
                "state": state,
                "auto_watch_reason": None if state != "auto_watching" else existing.get("auto_watch_reason"),
            }
        )
        .eq("id", existing["id"])
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Failed to update topic interest")
    await rebalance_auto_watch_topics(user_id)
    latest_rows = _interest_select(db).eq("user_id", user_id).eq("topic_id", topic_id).limit(1).execute().data or []
    latest = latest_rows[0] if latest_rows else updated.data[0]
    topic = (_topic_select(db).eq("id", topic_id).limit(1).execute().data or [None])[0]
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {
        "topic_id": topic["id"],
        "label": topic.get("label"),
        "normalized_query": topic.get("normalized_query"),
        "state": latest.get("state"),
        "interest_score": _score(latest.get("interest_score")),
        "auto_watch_reason": latest.get("auto_watch_reason"),
        "last_checked_at": latest.get("last_checked_at"),
        "last_notified_at": latest.get("last_notified_at"),
        "updated_at": latest.get("updated_at"),
    }


async def delete_user_topic_interest(user_id: str, topic_id: str) -> None:
    db = _service_db_client()
    existing_rows = _interest_select(db).eq("user_id", user_id).eq("topic_id", topic_id).limit(1).execute().data or []
    if not existing_rows:
        raise HTTPException(status_code=404, detail="Topic interest not found")
    updated = (
        db.table("user_topic_interests")
        .update(
            {
                "state": "deleted",
                "auto_watch_reason": None,
            }
        )
        .eq("id", existing_rows[0]["id"])
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Failed to delete topic interest")
    await rebalance_auto_watch_topics(user_id)


async def upsert_user_topic_interest(
    user_id: str,
    raw_query: str,
    *,
    label: str | None = None,
    keywords: list[str] | None = None,
    interest_score: float | None = None,
    score_delta: float | None = None,
    auto_watch_reason: str | None = None,
) -> dict[str, Any]:
    if (interest_score is None) == (score_delta is None):
        raise HTTPException(status_code=400, detail="Provide exactly one of interest_score or score_delta.")

    topic = await get_or_create_research_topic(raw_query, label=label, keywords=keywords)
    db = _service_db_client()
    existing_rows = (
        _interest_select(db).eq("user_id", user_id).eq("topic_id", topic["id"]).limit(1).execute().data or []
    )

    if existing_rows:
        existing = existing_rows[0]
        next_score = (
            float(interest_score)
            if interest_score is not None
            else _score(existing.get("interest_score")) + float(score_delta)
        )
        payload = {"interest_score": next_score}
        if existing.get("state") == "deleted":
            payload["state"] = "candidate"
            payload["auto_watch_reason"] = None
        updated = db.table("user_topic_interests").update(payload).eq("id", existing["id"]).execute()
        interest = updated.data[0] if updated.data else {**existing, **payload}
    else:
        next_score = float(interest_score) if interest_score is not None else float(score_delta)
        created = (
            db.table("user_topic_interests")
            .insert(
                {
                    "user_id": user_id,
                    "topic_id": topic["id"],
                    "interest_score": next_score,
                    "state": "candidate",
                    "auto_watch_reason": None,
                }
            )
            .execute()
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Failed to create user topic interest")
        interest = created.data[0]

    await rebalance_auto_watch_topics(user_id, auto_watch_reason=auto_watch_reason)
    latest_rows = _interest_select(db).eq("user_id", user_id).eq("topic_id", topic["id"]).limit(1).execute().data or []
    latest_interest = latest_rows[0] if latest_rows else interest
    return {"topic": topic, "interest": latest_interest}


def extract_topic_candidate(query: str) -> dict[str, str] | None:
    settings = get_settings()
    trimmed = (query or "").strip()
    if not trimmed:
        return None

    trimmed = trimmed[: settings.topic_extraction_max_query_length]
    lowered = _collapse_spaces(trimmed.lower())
    for prefix in (
        "find papers about ",
        "find papers on ",
        "research about ",
        "research on ",
        "literature review on ",
        "literature review about ",
        "show me papers about ",
        "show me papers on ",
    ):
        if lowered.startswith(prefix):
            trimmed = trimmed[len(prefix) :].strip()
            break

    trimmed = _strip_edge_punctuation(_collapse_spaces(trimmed))
    if sum(ch.isalnum() for ch in trimmed) < settings.topic_extraction_min_alnum_chars:
        return None

    label, normalized_query = normalize_topic_identity(trimmed)
    return {"label": label, "normalized_query": normalized_query}


async def set_chat_topic(token: str, user_id: str, chat_id: str, topic_id: str | None) -> dict[str, Any]:
    db = _service_db_client()
    res = db.table("chats").update({"topic_id": topic_id}).eq("id", chat_id).eq("user_id", user_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return res.data[0]


async def get_chat_topic(token: str, user_id: str, chat_id: str) -> dict[str, Any] | None:
    db = _service_db_client()
    res = _chat_select(db).eq("id", chat_id).eq("user_id", user_id).is_("deleted_at", "null").limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    row = res.data[0]
    topic_id = row.get("topic_id")
    if not topic_id:
        return None
    topic_res = _topic_select(db).eq("id", topic_id).limit(1).execute()
    return topic_res.data[0] if topic_res.data else None


async def score_topic_signal(
    user_id: str,
    *,
    signal: str,
    query: str | None = None,
    chat_id: str | None = None,
    token: str | None = None,
) -> dict[str, Any] | None:
    if signal not in _TOPIC_SIGNAL_WEIGHTS:
        raise HTTPException(status_code=400, detail=f"Unsupported topic signal: {signal}")

    candidate: dict[str, str] | None = None
    if query is not None:
        candidate = extract_topic_candidate(query)
        if candidate is None:
            return None
    elif chat_id and token:
        topic = await get_chat_topic(token, user_id, chat_id)
        if topic is None:
            return None
        candidate = {
            "label": topic.get("label") or topic.get("normalized_query") or "",
            "normalized_query": topic.get("normalized_query") or "",
        }
    else:
        raise HTTPException(status_code=400, detail="Topic scoring requires query text or a chat topic marker.")

    result = await upsert_user_topic_interest(
        user_id,
        candidate["normalized_query"],
        label=candidate["label"],
        score_delta=_TOPIC_SIGNAL_WEIGHTS[signal],
        auto_watch_reason=signal,
    )

    if chat_id and token:
        await set_chat_topic(token, user_id, chat_id, result["topic"]["id"])

    return result


def _paper_text(paper: Paper) -> str:
    return " ".join(part for part in [paper.title, paper.abstract] if part)


def _score_lexical(topic: dict[str, Any], paper: Paper) -> float:
    topic_tokens = _unique_tokens(f"{topic.get('label', '')} {topic.get('normalized_query', '')}")
    if not topic_tokens:
        return 0.0
    paper_tokens = _unique_tokens(_paper_text(paper))
    overlap = len(topic_tokens & paper_tokens) / len(topic_tokens)
    phrase_bonus = 0.25 if (topic.get("normalized_query") or "") in _normalized_title(_paper_text(paper)) else 0.0
    title_overlap = len(topic_tokens & _unique_tokens(paper.title)) / len(topic_tokens)
    return min(1.0, overlap * 0.65 + title_overlap * 0.25 + phrase_bonus)


def _score_vector(topic: dict[str, Any], paper: Paper) -> float:
    normalized_topic = topic.get("normalized_query") or ""
    title = _normalized_title(paper.title)
    abstract = _normalized_title(paper.abstract)
    title_similarity = SequenceMatcher(None, normalized_topic, title).ratio() if title else 0.0
    abstract_similarity = (
        SequenceMatcher(None, normalized_topic, abstract[: max(len(normalized_topic) * 4, 1)]).ratio()
        if abstract
        else 0.0
    )
    lexical = _score_lexical(topic, paper)
    return min(1.0, title_similarity * 0.55 + abstract_similarity * 0.15 + lexical * 0.30)


def _score_recency(paper: Paper) -> float:
    current_year = _utcnow().year
    year = paper.year
    if not year:
        return 0.2
    age = max(0, current_year - int(year))
    if age <= 1:
        return 1.0
    if age <= 2:
        return 0.85
    if age <= 4:
        return 0.65
    if age <= 7:
        return 0.45
    if age <= 10:
        return 0.3
    return 0.1


def _score_authority(paper: Paper) -> float:
    citation_component = min(float(paper.citation_count or 0) / 200.0, 0.7)
    completeness = 0.0
    if paper.abstract:
        completeness += 0.1
    if paper.authors:
        completeness += 0.05
    if paper.url:
        completeness += 0.05
    oa_bonus = 0.1 if paper.open_access_pdf else 0.0
    influential_bonus = 0.1 if getattr(paper, "is_influential", False) else 0.0
    return min(1.0, citation_component + completeness + oa_bonus + influential_bonus)


def compute_topic_paper_scores(topic: dict[str, Any], paper: Paper) -> dict[str, float | str]:
    vector_score = _score_vector(topic, paper)
    lexical_score = _score_lexical(topic, paper)
    recency_score = _score_recency(paper)
    authority_score = _score_authority(paper)
    hybrid_score = 0.45 * vector_score + 0.25 * lexical_score + 0.20 * recency_score + 0.10 * authority_score

    reason_parts: list[str] = []
    if lexical_score >= 0.55:
        reason_parts.append("strong keyword overlap")
    if recency_score >= 0.6:
        reason_parts.append("recent publication")
    if authority_score >= 0.45:
        reason_parts.append("credible metadata")
    if not reason_parts:
        reason_parts.append("semantic-topic similarity")

    return {
        "vector_score": round(vector_score, 6),
        "lexical_score": round(lexical_score, 6),
        "recency_score": round(recency_score, 6),
        "authority_score": round(authority_score, 6),
        "hybrid_score": round(hybrid_score, 6),
        "reason": ", ".join(reason_parts[:3]),
    }


def paper_passes_in_app_threshold(scores: dict[str, Any]) -> bool:
    settings = get_settings()
    return (
        float(scores.get("hybrid_score") or 0) >= settings.topic_monitor_in_app_threshold
        and float(scores.get("recency_score") or 0) >= 0.35
        and (float(scores.get("vector_score") or 0) >= 0.70 or float(scores.get("lexical_score") or 0) >= 0.55)
    )


async def fetch_topic_candidate_papers(topic: dict[str, Any], *, limit: int | None = None) -> list[Paper]:
    settings = get_settings()
    max_limit = limit or settings.topic_monitor_max_papers_per_topic_per_run
    query = topic.get("normalized_query") or topic.get("label") or ""
    per_source = max(1, min(15, max_limit // 4 or 1))

    seen_keys: set[tuple[str, str]] = set()
    candidates: list[Paper] = []
    source_batches = [
        await semantic_scholar.search_papers(query, limit=per_source),
        await search_openalex(query, limit=per_source),
        await arxiv_fetcher.arxiv_search(query, limit=per_source),
        await search_pubmed(query, limit=per_source),
    ]

    for batch in source_batches:
        for paper in batch:
            identities = _paper_identity_fields(paper)
            dedup_key = (
                "doi",
                str(
                    identities.get("doi")
                    or identities.get("arxiv_id")
                    or identities.get("s2_paper_id")
                    or identities.get("openalex_id")
                    or identities.get("pubmed_id")
                    or identities.get("normalized_title")
                    or paper.paper_id
                ),
            )
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            candidates.append(paper)
            if len(candidates) >= max_limit:
                return candidates

    return candidates


async def upsert_canonical_paper(paper: Paper) -> dict[str, Any]:
    db = _service_db_client()
    identities = _paper_identity_fields(paper)

    for field in ("doi", "arxiv_id", "s2_paper_id", "openalex_id", "pubmed_id"):
        value = identities.get(field)
        if not value:
            continue
        existing = _paper_select(db).eq(field, value).limit(1).execute().data or []
        if existing:
            row = existing[0]
            payload = {
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": list(paper.authors or []),
                "year": paper.year,
                "published_at": _published_at_from_paper(paper),
                "url": paper.url,
                "open_access_pdf": _open_access_payload(paper),
                "source_metadata": _paper_source_metadata(paper),
            }
            for id_field in ("doi", "arxiv_id", "s2_paper_id", "openalex_id", "pubmed_id"):
                if identities.get(id_field):
                    payload[id_field] = identities[id_field]
            updated = db.table("papers").update(payload).eq("id", row["id"]).execute()
            return updated.data[0] if updated.data else {**row, **payload}

    title_key = identities.get("normalized_title")
    if title_key:
        title_matches = _paper_select(db).eq("title", paper.title).limit(1).execute().data or []
        if title_matches:
            row = title_matches[0]
            payload = {
                "abstract": paper.abstract,
                "authors": list(paper.authors or []),
                "year": paper.year,
                "published_at": _published_at_from_paper(paper),
                "url": paper.url,
                "open_access_pdf": _open_access_payload(paper),
                "source_metadata": _paper_source_metadata(paper),
            }
            updated = db.table("papers").update(payload).eq("id", row["id"]).execute()
            return updated.data[0] if updated.data else {**row, **payload}

    payload = {
        "doi": identities.get("doi"),
        "arxiv_id": identities.get("arxiv_id"),
        "s2_paper_id": identities.get("s2_paper_id"),
        "openalex_id": identities.get("openalex_id"),
        "pubmed_id": identities.get("pubmed_id"),
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": list(paper.authors or []),
        "year": paper.year,
        "published_at": _published_at_from_paper(paper),
        "url": paper.url,
        "open_access_pdf": _open_access_payload(paper),
        "source_metadata": _paper_source_metadata(paper),
    }
    created = db.table("papers").insert(payload).execute()
    if not created.data:
        raise TopicMonitorError("Failed to create canonical paper")
    return created.data[0]


async def upsert_topic_paper_match(topic_id: str, paper_id: str, scores: dict[str, Any]) -> dict[str, Any]:
    db = _service_db_client()
    existing = _match_select(db).eq("topic_id", topic_id).eq("paper_id", paper_id).limit(1).execute().data or []
    payload = {
        "vector_score": float(scores.get("vector_score") or 0),
        "lexical_score": float(scores.get("lexical_score") or 0),
        "recency_score": float(scores.get("recency_score") or 0),
        "authority_score": float(scores.get("authority_score") or 0),
        "hybrid_score": float(scores.get("hybrid_score") or 0),
        "reason": scores.get("reason"),
    }
    if existing:
        updated = db.table("topic_paper_matches").update(payload).eq("id", existing[0]["id"]).execute()
        return updated.data[0] if updated.data else {**existing[0], **payload}

    created = (
        db.table("topic_paper_matches")
        .insert(
            {
                "topic_id": topic_id,
                "paper_id": paper_id,
                **payload,
            }
        )
        .execute()
    )
    if not created.data:
        raise TopicMonitorError("Failed to create topic-paper match")
    return created.data[0]


async def create_notification_event_if_needed(
    *,
    user_id: str,
    topic_id: str,
    paper_id: str,
    scores: dict[str, Any],
    channel: str = "in_app",
) -> dict[str, Any] | None:
    if channel != "in_app":
        raise HTTPException(status_code=400, detail="TIP-TM-003 only supports in_app notification events.")
    if not paper_passes_in_app_threshold(scores):
        return None

    db = _service_db_client()
    interest_rows = _interest_select(db).eq("user_id", user_id).eq("topic_id", topic_id).limit(1).execute().data or []
    if not interest_rows:
        return None
    if interest_rows[0].get("state") in _BLOCKED_STATES:
        return None

    existing = (
        _event_select(db)
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .eq("paper_id", paper_id)
        .eq("channel", channel)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        return existing[0]

    created = (
        db.table("notification_events")
        .insert(
            {
                "user_id": user_id,
                "topic_id": topic_id,
                "paper_id": paper_id,
                "channel": channel,
                "status": "created",
            }
        )
        .execute()
    )
    if not created.data:
        raise TopicMonitorError("Failed to create notification event")
    return created.data[0]


def _build_notification_content(topic: dict[str, Any]) -> str:
    label = topic.get("label") or topic.get("normalized_query") or "your topic"
    return f'New paper for your topic "{label}"'


def _paper_ref_payload(paper: dict[str, Any]) -> dict[str, Any]:
    abstract = (paper.get("abstract") or "").strip()
    return {
        "id": paper.get("id"),
        "title": paper.get("title"),
        "doi": paper.get("doi"),
        "url": paper.get("url"),
        "abstract_snippet": abstract[:180] or None,
        "year": paper.get("year"),
    }


async def deliver_in_app_notifications(*, user_id: str | None = None) -> dict[str, Any]:
    db = _service_db_client()
    events = _event_select(db).eq("channel", "in_app").eq("status", "created").execute().data or []
    if user_id is not None:
        events = [row for row in events if row.get("user_id") == user_id]
    if not events:
        return {"processed": 0, "created": 0, "sent": 0, "skipped": 0, "failed": 0}

    topic_rows = {row["id"]: row for row in (_topic_select(db).execute().data or [])}
    paper_rows = {row["id"]: row for row in (_paper_select(db).execute().data or [])}
    match_rows = {(row["topic_id"], row["paper_id"]): row for row in (_match_select(db).execute().data or [])}
    settings_rows = {row["user_id"]: row for row in (_settings_select(db).execute().data or [])}
    interest_rows = {(row["user_id"], row["topic_id"]): row for row in (_interest_select(db).execute().data or [])}
    existing_notifications = _notification_select(db).execute().data or []

    summary = {"processed": 0, "created": 0, "sent": 0, "skipped": 0, "failed": 0}
    for event in events:
        summary["processed"] += 1
        try:
            settings_row = settings_rows.get(event["user_id"]) or await get_notification_settings(event["user_id"])
            settings_rows[event["user_id"]] = settings_row
            if settings_row.get("pause_all_in_app"):
                continue

            interest = interest_rows.get((event["user_id"], event["topic_id"]))
            if interest is None or interest.get("state") in _BLOCKED_STATES:
                db.table("notification_events").update({"status": "skipped"}).eq("id", event["id"]).execute()
                summary["skipped"] += 1
                continue

            duplicate = next(
                (
                    row
                    for row in existing_notifications
                    if row.get("user_id") == event.get("user_id")
                    and row.get("type") == "new_paper"
                    and row.get("topic_id") == event.get("topic_id")
                    and row.get("paper_id") == event.get("paper_id")
                ),
                None,
            )
            if duplicate is not None:
                db.table("notification_events").update({"status": "sent"}).eq("id", event["id"]).execute()
                summary["sent"] += 1
                continue

            topic = topic_rows.get(event.get("topic_id"))
            paper = paper_rows.get(event.get("paper_id"))
            if topic is None or paper is None:
                db.table("notification_events").update({"status": "failed"}).eq("id", event["id"]).execute()
                summary["failed"] += 1
                continue

            match = match_rows.get((event.get("topic_id"), event.get("paper_id"))) or {}
            payload = {
                "user_id": event["user_id"],
                "type": "new_paper",
                "content": _build_notification_content(topic),
                "paper_ref": _paper_ref_payload(paper),
                "topic_id": event.get("topic_id"),
                "paper_id": event.get("paper_id"),
                "reason": match.get("reason"),
                "score": match.get("hybrid_score"),
            }
            created = db.table("notifications").insert(payload).execute()
            if not created.data:
                db.table("notification_events").update({"status": "failed"}).eq("id", event["id"]).execute()
                summary["failed"] += 1
                continue

            existing_notifications.append(created.data[0])
            db.table("notification_events").update({"status": "sent"}).eq("id", event["id"]).execute()
            summary["created"] += 1
            summary["sent"] += 1
        except Exception as exc:
            log.warning("notification delivery failed for event %s: %s", event.get("id"), exc)
            db.table("notification_events").update({"status": "failed"}).eq("id", event["id"]).execute()
            summary["failed"] += 1

    return summary


async def list_monitor_candidates(*, now: datetime | None = None, user_id: str | None = None) -> list[dict[str, Any]]:
    db = _service_db_client()
    rows = _interest_select(db).execute().data or []
    topics = {row["id"]: row for row in (_topic_select(db).execute().data or [])}
    cutoff = (now or _utcnow()) - timedelta(hours=get_settings().topic_monitor_cooldown_hours)
    candidates: list[dict[str, Any]] = []

    for row in rows:
        if user_id is not None and row.get("user_id") != user_id:
            continue
        if row.get("state") != "auto_watching":
            continue
        last_checked_at = _parse_timestamp(row.get("last_checked_at"))
        if last_checked_at and last_checked_at > cutoff:
            continue
        topic = topics.get(row.get("topic_id"))
        if not topic:
            log.warning("Skipping auto-watching interest without topic row: %s", row.get("id"))
            continue
        candidates.append({"interest": row, "topic": topic})

    candidates.sort(
        key=lambda item: (
            _score(item["interest"].get("interest_score")),
            item["interest"].get("updated_at") or item["interest"].get("created_at") or "",
        ),
        reverse=True,
    )
    return candidates


async def process_monitor_topic(interest: dict[str, Any], topic: dict[str, Any]) -> dict[str, Any]:
    db = _service_db_client()
    checked_at = _to_iso()
    db.table("user_topic_interests").update({"last_checked_at": checked_at}).eq("id", interest["id"]).execute()

    fetched = await fetch_topic_candidate_papers(topic)
    matches = 0
    events = 0
    failures = 0

    for paper in fetched:
        try:
            canonical_paper = await upsert_canonical_paper(paper)
            scores = compute_topic_paper_scores(topic, paper)
            await upsert_topic_paper_match(topic["id"], canonical_paper["id"], scores)
            matches += 1
            created_event = await create_notification_event_if_needed(
                user_id=interest["user_id"],
                topic_id=topic["id"],
                paper_id=canonical_paper["id"],
                scores=scores,
            )
            if created_event is not None:
                events += 1
        except Exception as exc:
            failures += 1
            log.warning("Topic monitor skipped paper for topic %s: %s", topic.get("id"), exc)

    return {
        "topic_id": topic["id"],
        "interest_id": interest["id"],
        "checked_at": checked_at,
        "fetched": len(fetched),
        "matches": matches,
        "events_created": events,
        "failures": failures,
    }


async def run_topic_monitor(*, now: datetime | None = None, user_id: str | None = None) -> dict[str, Any]:
    candidates = await list_monitor_candidates(now=now, user_id=user_id)
    processed: list[dict[str, Any]] = []
    skipped = 0

    for item in candidates:
        try:
            processed.append(await process_monitor_topic(item["interest"], item["topic"]))
        except Exception as exc:
            skipped += 1
            log.warning("Topic monitor skipped topic %s: %s", item["topic"].get("id"), exc)

    return {
        "processed_topics": len(processed),
        "skipped_topics": skipped,
        "results": processed,
    }
