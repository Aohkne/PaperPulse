"""Tests for TIP-P3-03: clean_query() + retrieval.search() fieldsOfStudy filter."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.gap_detection.retrieval import clean_query, search
from backend.agent.gap_detection.settings import get_default_fields_of_study
from backend.shared.models.paper import Paper


# ── Helpers ───────────────────────────────────────────────────────────────────

def _paper(pid: str = "p1", title: str = "Test") -> Paper:
    return Paper(paperId=pid, title=title)


# ── clean_query() — pure function tests ──────────────────────────────────────

class TestCleanQuery:
    def test_strip_viet_meta_words(self):
        raw = "Tìm research gap về transformer long-context"
        assert clean_query(raw) == "transformer long-context"

    def test_strip_english_meta_words(self):
        raw = "research gaps in federated learning"
        assert clean_query(raw) == "federated learning"

    def test_strip_phat_hien_khong_trong(self):
        raw = "phát hiện khoảng trống về federated learning"
        assert clean_query(raw) == "federated learning"

    def test_fallback_when_only_meta_words(self):
        raw = "tìm research gap"
        assert clean_query(raw) == "tìm research gap"

    def test_fallback_not_empty_string(self):
        raw = "tìm research gap"
        result = clean_query(raw)
        assert result != ""

    def test_no_meta_passthrough(self):
        raw = "transformer long-context"
        assert clean_query(raw) == "transformer long-context"

    def test_strip_literature_review(self):
        raw = "literature review về attention mechanisms"
        assert clean_query(raw) == "attention mechanisms"

    def test_case_insensitive(self):
        raw = "Research Gaps In graph neural networks"
        assert clean_query(raw) == "graph neural networks"

    def test_gaps_about(self):
        raw = "gaps about vision transformers"
        assert clean_query(raw) == "vision transformers"

    def test_find_keyword(self):
        raw = "find research gaps in diffusion models"
        assert clean_query(raw) == "diffusion models"


# ── get_default_fields_of_study() — settings tests ───────────────────────────

class TestGetDefaultFieldsOfStudy:
    def test_default_returns_cs(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEFAULT_FIELDS_OF_STUDY", None)
            result = get_default_fields_of_study()
        assert result == ["Computer Science"]

    def test_none_string_returns_none(self):
        with patch.dict(os.environ, {"DEFAULT_FIELDS_OF_STUDY": "None"}):
            assert get_default_fields_of_study() is None

    def test_empty_string_returns_none(self):
        with patch.dict(os.environ, {"DEFAULT_FIELDS_OF_STUDY": ""}):
            assert get_default_fields_of_study() is None

    def test_multi_field(self):
        with patch.dict(os.environ, {"DEFAULT_FIELDS_OF_STUDY": "Computer Science,Mathematics"}):
            assert get_default_fields_of_study() == ["Computer Science", "Mathematics"]

    def test_single_override(self):
        with patch.dict(os.environ, {"DEFAULT_FIELDS_OF_STUDY": "Biology"}):
            assert get_default_fields_of_study() == ["Biology"]


# ── retrieval.search() — integration with mocked search_papers ───────────────

class TestRetrievalSearch:
    @pytest.mark.asyncio
    async def test_cleaned_query_passed_to_search_papers(self):
        """search_papers receives cleaned query, not raw."""
        mock_papers = [_paper("p1")]
        with patch(
            "backend.agent.gap_detection.retrieval.search_papers",
            new_callable=AsyncMock,
            return_value=mock_papers,
        ) as mock_sp, patch.dict(os.environ, {"DEFAULT_FIELDS_OF_STUDY": "None"}):
            await search("Tìm research gap về transformer long-context", limit=5)

        mock_sp.assert_awaited_once()
        call_args = mock_sp.call_args
        assert call_args[0][0] == "transformer long-context"

    @pytest.mark.asyncio
    async def test_fields_of_study_passed_when_set(self):
        """search_papers receives fields_of_study=["Computer Science"] from env."""
        mock_papers = [_paper("p1")]
        with patch(
            "backend.agent.gap_detection.retrieval.search_papers",
            new_callable=AsyncMock,
            return_value=mock_papers,
        ) as mock_sp, patch.dict(os.environ, {"DEFAULT_FIELDS_OF_STUDY": "Computer Science"}):
            await search("transformer", limit=5)

        call_kwargs = mock_sp.call_args[1]
        assert call_kwargs.get("fields_of_study") == ["Computer Science"]

    @pytest.mark.asyncio
    async def test_fields_of_study_none_when_env_none(self):
        """When DEFAULT_FIELDS_OF_STUDY=None, fields_of_study=None passed."""
        mock_papers = [_paper("p1")]
        with patch(
            "backend.agent.gap_detection.retrieval.search_papers",
            new_callable=AsyncMock,
            return_value=mock_papers,
        ) as mock_sp, patch.dict(os.environ, {"DEFAULT_FIELDS_OF_STUDY": "None"}):
            await search("transformer", limit=5)

        call_kwargs = mock_sp.call_args[1]
        assert call_kwargs.get("fields_of_study") is None

    @pytest.mark.asyncio
    async def test_signature_unchanged(self):
        """search() still accepts (query, limit) positionally — callers unbroken."""
        import inspect
        sig = inspect.signature(search)
        params = list(sig.parameters.keys())
        assert params[0] == "query"
        assert params[1] == "limit"
