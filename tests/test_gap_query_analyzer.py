"""Tests for TIP-P3-08: GapQuery schema + analyze_query() node."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.nodes.query_analyzer import analyze_query
from backend.agent.gap_detection.schemas import GapQuery
from backend.agent.gap_detection.settings import is_query_analyzer_enabled

# ── Helpers ───────────────────────────────────────────────────────────────────

_META_WORDS = {"tìm", "research gap", "research gaps", "về", "find", "gap", "gaps"}


def _llm_response(**kwargs) -> str:
    payload = {
        "core_topic": kwargs.get("core_topic", "transformer efficiency"),
        "facets": kwargs.get("facets", ["efficient attention", "long-context modeling"]),
        "year_range": kwargs.get("year_range", [2019, 2026]),
        "field_of_study": kwargs.get("field_of_study", "Computer Science"),
        "recency_bias": kwargs.get("recency_bias", True),
        "seminal_bias": kwargs.get("seminal_bias", True),
    }
    return json.dumps(payload)


# ── GapQuery schema ──────────────────────────────────────────────────────────


class TestGapQuerySchema:
    def test_defaults(self):
        q = GapQuery(core_topic="transformers")
        assert q.facets == []
        assert q.year_range == (2019, 2026)
        assert q.field_of_study == "Computer Science"
        assert q.recency_bias is True
        assert q.seminal_bias is True

    def test_year_range_is_tuple(self):
        q = GapQuery(core_topic="x", year_range=(2020, 2025))
        assert isinstance(q.year_range, tuple)
        assert q.year_range == (2020, 2025)

    def test_year_range_coerced_from_list(self):
        q = GapQuery(core_topic="x", year_range=[2020, 2025])  # type: ignore[arg-type]
        assert isinstance(q.year_range, tuple)

    def test_facets_populated(self):
        q = GapQuery(core_topic="federated learning", facets=["privacy", "communication efficiency"])
        assert len(q.facets) == 2


# ── is_query_analyzer_enabled() ──────────────────────────────────────────────


class TestIsQueryAnalyzerEnabled:
    def test_default_true(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QUERY_ANALYZER_ENABLED", None)
            assert is_query_analyzer_enabled() is True

    def test_false_string(self):
        with patch.dict(os.environ, {"QUERY_ANALYZER_ENABLED": "false"}):
            assert is_query_analyzer_enabled() is False

    def test_zero_string(self):
        with patch.dict(os.environ, {"QUERY_ANALYZER_ENABLED": "0"}):
            assert is_query_analyzer_enabled() is False

    def test_true_string(self):
        with patch.dict(os.environ, {"QUERY_ANALYZER_ENABLED": "true"}):
            assert is_query_analyzer_enabled() is True


# ── analyze_query() — AC scenarios ──────────────────────────────────────────


class TestAnalyzeQuery:
    @pytest.mark.asyncio
    async def test_viet_meta_words_stripped_from_core_topic(self):
        """AC: Vietnamese input → core_topic EN, no meta-words."""
        response = _llm_response(
            core_topic="transformer efficiency long-context",
            facets=["efficient attention mechanisms", "long-context modeling", "KV-cache compression"],
        )
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await analyze_query("Tìm research gap về transformer efficiency cho long-context")

        for meta in _META_WORDS:
            assert meta.lower() not in result.core_topic.lower(), f"meta-word '{meta}' in core_topic"
        assert len(result.facets) >= 2

    @pytest.mark.asyncio
    async def test_facets_at_least_two(self):
        """AC: facets >= 2 for a well-formed query."""
        response = _llm_response(
            core_topic="federated learning privacy",
            facets=["differential privacy FL", "communication efficiency", "secure aggregation"],
        )
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await analyze_query("federated learning privacy")

        assert len(result.facets) >= 2

    @pytest.mark.asyncio
    async def test_json_parse_error_fallback(self):
        """AC: LLM returns invalid JSON → fallback GapQuery, no exception."""
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            return_value="{invalid json",
        ):
            result = await analyze_query("transformer long-context")

        assert isinstance(result, GapQuery)
        assert result.core_topic  # not empty
        assert result.facets == [result.core_topic]

    @pytest.mark.asyncio
    async def test_llm_exception_fallback(self):
        """AC: LLM raises timeout → fallback GapQuery, no exception."""
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            side_effect=TimeoutError("LLM timeout"),
        ):
            result = await analyze_query("federated learning")

        assert isinstance(result, GapQuery)
        assert result.core_topic == "federated learning"
        assert result.facets == ["federated learning"]

    @pytest.mark.asyncio
    async def test_empty_facets_filled_from_core_topic(self):
        """AC: LLM returns empty facets list → auto-filled with core_topic."""
        response = _llm_response(core_topic="graph neural networks", facets=[])
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await analyze_query("graph neural networks")

        assert result.facets == ["graph neural networks"]

    @pytest.mark.asyncio
    async def test_year_range_tuple_after_llm(self):
        """year_range is coerced from JSON list [2020, 2025] to tuple."""
        response = _llm_response(core_topic="diffusion models", year_range=[2020, 2025])
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await analyze_query("diffusion models")

        assert isinstance(result.year_range, tuple)
        assert result.year_range == (2020, 2025)

    @pytest.mark.asyncio
    async def test_only_one_llm_call(self):
        """AC: exactly 1 LLM call per analyze_query()."""
        response = _llm_response()
        mock = AsyncMock(return_value=response)
        with patch("backend.agent.gap_detection.nodes.query_analyzer.chat_completion", mock):
            await analyze_query("some query")

        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_does_not_raise(self):
        """Any exception from LLM → GapQuery, never raises."""
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network error"),
        ):
            result = await analyze_query("attention mechanism")  # must not raise

        assert isinstance(result, GapQuery)

    @pytest.mark.asyncio
    async def test_markdown_fence_stripped(self):
        """LLM wraps JSON in ```json ... ``` → still parsed correctly."""
        inner = _llm_response(core_topic="vision transformers", facets=["ViT", "CLIP"])
        fenced = f"```json\n{inner}\n```"
        with patch(
            "backend.agent.gap_detection.nodes.query_analyzer.chat_completion",
            new_callable=AsyncMock,
            return_value=fenced,
        ):
            result = await analyze_query("vision transformers")

        assert result.core_topic == "vision transformers"
        assert "ViT" in result.facets
