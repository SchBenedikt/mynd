"""Test core/model.py – model selection, tool support detection."""

from unittest.mock import MagicMock, patch


class TestCheckToolSupport:
    @patch("core.model.requests.post")
    @patch("core.model._is_openai")
    def test_ollama_model_supported(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"role": "assistant", "content": "hi"}}
        mock_post.return_value = mock_resp

        from core.model import check_tool_support
        assert check_tool_support("gemma3") is True

    @patch("core.model.requests.post")
    @patch("core.model._is_openai")
    def test_ollama_model_error_returns_false(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": "model not found"}
        mock_post.return_value = mock_resp

        from core.model import check_tool_support
        assert check_tool_support("nonexistent") is False

    @patch("core.model.requests.post")
    @patch("core.model._is_openai")
    def test_connection_error_returns_false(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        import requests
        mock_post.side_effect = requests.RequestException("refused")

        from core.model import check_tool_support
        assert check_tool_support("gemma3") is False

    def test_no_tool_keywords_blocked(self):
        from core.model import _no_tool_keywords
        keywords = _no_tool_keywords()
        assert isinstance(keywords, list)
        assert "phi" in keywords
        assert "tinyllama" in keywords

    @patch("core.model.requests.post")
    def test_phi_model_rejected(self, mock_post):
        """Models with 'phi' in name should be rejected before any HTTP call."""
        from core.model import check_tool_support
        assert check_tool_support("phi4") is False
        mock_post.assert_not_called()

    @patch("core.model._openai_provider_cfg")
    @patch("core.model.requests.post")
    @patch("core.model._is_openai")
    def test_openai_model_always_supported(self, mock_is_openai, mock_post, mock_cfg):
        mock_is_openai.return_value = True
        mock_cfg.return_value = ("https://api.openai.com/v1", "sk-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "hi"}}]}
        mock_post.return_value = mock_resp

        from core.model import check_tool_support
        assert check_tool_support("gpt-4") is True


class TestNoToolKeywords:
    @patch.dict("os.environ", {"NO_TOOL_MODEL_KEYWORDS": "phi,tinyllama,minicpm"})
    def test_custom_keywords_from_env(self):
        from core.model import _no_tool_keywords
        assert "phi" in _no_tool_keywords()
        assert "minicpm" in _no_tool_keywords()

    @patch.dict("os.environ", {}, clear=True)
    def test_default_keywords_when_env_empty(self):
        from core.model import _no_tool_keywords
        keywords = _no_tool_keywords()
        assert len(keywords) > 0


class TestOpenAIProviderCfg:
    @patch("core.model._openai_cfg")
    @patch("core.model.os.path.exists")
    def test_falls_back_to_env(self, mock_exists, mock_cfg):
        mock_exists.return_value = False
        mock_cfg.return_value = ("https://custom.ai", "sk-env", ["gpt-4"])
        from core.model import _openai_provider_cfg
        base, key = _openai_provider_cfg()
        assert "custom.ai" in base
        assert key == "sk-env"

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_reads_ai_config(self, mock_read_text, mock_exists):
        mock_exists.return_value = True
        mock_read_text.return_value = '{"provider": "openai", "base_url": "https://cfg.ai/v1", "api_key": "sk-cfg"}'
        from core.model import _openai_provider_cfg
        base, key = _openai_provider_cfg()
        assert "cfg.ai" in base
        assert key == "sk-cfg"
