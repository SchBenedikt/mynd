"""Test app/helpers.py – KnowledgeBase, system prompt builder, sanitize, helpers."""

import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import numpy as np

# ── KnowledgeBase ─────────────────────────────────────────────

class TestKnowledgeBase:
    def test_empty_kb_returns_empty_search(self):
        from app.helpers import KnowledgeBase
        kb = KnowledgeBase()
        kb.chunks = []
        kb.embs = np.array([]).reshape(0, 0)
        results = kb.search("anything")
        assert results == []

    @patch("app.helpers._embed_fn")
    def test_search_returns_ranked_results(self, mock_embed):
        # embed returns 2D array: shape (1, 3) → one embedding of dimension 3
        mock_embed.return_value = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        from app.helpers import KnowledgeBase
        kb = KnowledgeBase()
        kb.chunks = [
            {"text": "doc about python", "source": "affine://doc1"},
            {"text": "doc about cooking", "source": "affine://doc2"},
            {"text": "doc about python", "source": "affine://doc3"},
        ]
        kb.embs = np.array([
            [1.0, 0.0, 0.0],  # doc1 – cosine ~1.0 with query
            [0.0, 1.0, 0.0],  # doc2 – cosine 0.0
            [0.9, 0.1, 0.0],  # doc3 – cosine ~0.9 with query
        ], dtype=np.float32)

        results = kb.search("python programming", k=5)
        assert len(results) >= 2
        assert results[0]["similarity_score"] > 0.5

    @patch("app.helpers._embed_fn")
    def test_search_filters_low_similarity(self, mock_embed):
        mock_embed.return_value = np.array([1.0, 0.0], dtype=np.float32)
        from app.helpers import KnowledgeBase
        kb = KnowledgeBase()
        kb.chunks = [
            {"text": "irrelevant text", "source": "src1"},
        ]
        kb.embs = np.array([[0.0, 1.0]], dtype=np.float32)  # orthogonal to query
        results = kb.search("something", k=5)
        assert len(results) == 0  # score below 0.15 threshold

    def test_load_handles_missing_files(self, tmp_path):
        from app.helpers import KnowledgeBase
        kb = KnowledgeBase()
        # Should not crash when files don't exist
        kb.chunks = []
        kb.embs = np.array([]).reshape(0, 0)

    @patch("app.helpers.logger")
    @patch("app.helpers.CHUNKS")
    @patch("app.helpers.EMBS")
    def test_load_logs_on_corrupt_files(self, mock_embs, mock_chunks, mock_logger):
        mock_chunks.exists.return_value = True
        mock_embs.exists.return_value = True
        mock_chunks.read_text.return_value = "invalid json"
        from app.helpers import KnowledgeBase
        KnowledgeBase()  # Should not crash, should log warning
        assert mock_logger.warning.called


# ── System Prompt Builder ─────────────────────────────────────

class TestBuildSystemPrompt:
    @patch("app.helpers.locale.setlocale")
    @patch("app.helpers.datetime")
    def test_prompt_includes_date_and_language(self, mock_dt, mock_locale):
        mock_dt.now.return_value = datetime(2026, 7, 24, 10, 30)
        mock_dt.strftime = datetime.strftime
        from app.helpers import _build_agent_system_prompt
        prompt = _build_agent_system_prompt("hello", language="de")
        assert "2026" in prompt
        assert "10:30" in prompt
        assert "language is de" in prompt
        assert "MUST respond in de" in prompt

    @patch("app.helpers.locale.setlocale")
    @patch("app.helpers.datetime")
    def test_prompt_includes_english_locale(self, mock_dt, mock_locale):
        mock_dt.now.return_value = datetime(2026, 7, 24, 15, 0)
        mock_dt.strftime = datetime.strftime
        from app.helpers import _build_agent_system_prompt
        prompt = _build_agent_system_prompt("hello", language="en")
        assert "language is en" in prompt
        # Should set locale to en_US.UTF-8
        mock_locale.assert_called_once()

    @patch("app.helpers.locale.setlocale", side_effect=Exception("locale error"))
    @patch("app.helpers.datetime")
    def test_prompt_does_not_crash_on_locale_error(self, mock_dt, mock_locale):
        mock_dt.now.return_value = datetime(2026, 7, 24, 10, 0)
        mock_dt.strftime = datetime.strftime
        from app.helpers import _build_agent_system_prompt
        prompt = _build_agent_system_prompt("hi")
        assert "2026" in prompt  # should still work

    @patch("app.helpers.DATA_DIR")
    @patch("app.helpers.locale.setlocale")
    @patch("app.helpers.datetime")
    def test_prompt_includes_memory(self, mock_dt, mock_locale, mock_data_dir):
        mock_dt.now.return_value = datetime(2026, 7, 24, 10, 0)
        mock_dt.strftime = datetime.strftime

        mem_file = MagicMock()
        mem_file.exists.return_value = True
        mem_file.read_text.return_value = json.dumps({"name": "Alice", "city": "Berlin"})
        mock_data_dir.__truediv__.return_value = mem_file

        from app.helpers import _build_agent_system_prompt
        prompt = _build_agent_system_prompt("hi")
        assert "Alice" in prompt
        assert "Berlin" in prompt

    @patch("app.helpers.DATA_DIR")
    @patch("app.helpers.locale.setlocale")
    @patch("app.helpers.datetime")
    def test_prompt_includes_vault_keys(self, mock_dt, mock_locale, mock_data_dir):
        mock_dt.now.return_value = datetime(2026, 7, 24, 10, 0)
        mock_dt.strftime = datetime.strftime

        vault_file = MagicMock()
        vault_file.exists.return_value = True
        mock_data_dir.__truediv__.return_value = vault_file

        from app.helpers import _build_agent_system_prompt
        with patch("app.helpers.load_vault", return_value={"nextcloud/url": "nc.url", "nextcloud/user": "admin"}):
            prompt = _build_agent_system_prompt("hi")
            assert "nextcloud" in prompt


# ── Sanitize Response ─────────────────────────────────────────

class TestSanitizeResponse:
    def test_blocks_traceback(self):
        from app.helpers import sanitize_response_text
        text = "Some output\nTraceback (most recent call last):\n  File \"test.py\", line 1\nError: boom"
        result = sanitize_response_text(text)
        assert "interner Fehler" in result

    def test_allows_normal_text(self):
        from app.helpers import sanitize_response_text
        text = "This is a normal response with no errors."
        assert sanitize_response_text(text) == text

    def test_handles_non_string_input(self):
        from app.helpers import sanitize_response_text
        assert "interner Fehler" in sanitize_response_text(42)


# ── Helper Functions ──────────────────────────────────────────

class TestHelpers:
    def test_safe_json_valid(self):
        from app.helpers import safe_json
        class MockResp:
            text = '{"key": "value"}'
            def json(self):
                return {"key": "value"}
        assert safe_json(MockResp()) == {"key": "value"}

    def test_safe_json_empty(self):
        from app.helpers import safe_json
        class MockResp:
            text = ""
            def json(self):
                raise ValueError("no content")
        assert safe_json(MockResp()) == {}

    def test_now_iso_returns_iso_string(self):
        from app.helpers import now_iso
        result = now_iso()
        assert isinstance(result, str)
        assert "T" in result  # ISO format includes T separator

    def test_calendar_range_today(self):
        from app.helpers import _calendar_range
        today = date.today()
        start, end = _calendar_range("today")
        assert start == today
        assert end == today

    def test_calendar_range_tomorrow(self):
        from datetime import timedelta

        from app.helpers import _calendar_range
        today = date.today()
        start, end = _calendar_range("tomorrow")
        assert start == today + timedelta(days=1)
        assert end == today + timedelta(days=1)

    def test_calendar_range_week(self):
        from app.helpers import _calendar_range
        start, end = _calendar_range("week")
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6  # Sunday
        diff = (end - start).days
        assert diff == 6

    def test_calendar_range_next_week(self):

        from app.helpers import _calendar_range
        start, end = _calendar_range("next-week")
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6  # Sunday
        assert start > date.today()  # Must be in the future
