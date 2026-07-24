"""Test core/embed.py – embedding functions with mocked HTTP."""

from unittest.mock import ANY, MagicMock, patch

import numpy as np


class TestEmbed:
    @patch("core.embed._requests.post")
    def test_embed_single_text(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.embed import embed
        result = embed(["hello"], model="test-model")
        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 3)
        mock_post.assert_called_once_with(
            ANY,
            json={"model": "test-model", "input": ["hello"]},
            timeout=120,
        )

    @patch("core.embed._requests.post")
    def test_embed_multiple_texts(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1, 0.0], [0.2, 0.0], [0.3, 0.0]]}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.embed import embed
        result = embed(["a", "b", "c"])
        assert result.shape == (3, 2)

    @patch("core.embed._requests.post")
    def test_embed_fallback_on_batch_failure(self, mock_post):
        """When batch fails, fallback makes individual requests."""
        mock_batch = MagicMock()
        mock_batch.json.return_value = {}  # no embeddings key → triggers ValueError
        mock_batch.raise_for_status.return_value = None

        mock_single = MagicMock()
        mock_single.json.return_value = {"embeddings": [[0.5]]}
        mock_single.raise_for_status.return_value = None

        mock_post.side_effect = [mock_batch, mock_single, mock_single]

        from core.embed import embed
        result = embed(["x", "y"])
        assert result.shape == (2, 1)
        assert mock_post.call_count >= 2

    @patch("core.embed._requests.post")
    def test_embed_uses_default_model(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1]]}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.embed import embed
        embed(["test"])
        called_with = mock_post.call_args[1]["json"]
        # Should use env var or default nomic-embed-text
        assert "model" in called_with

    @patch("core.embed._requests.post")
    def test_embed_returns_float32(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1, 0.2]]}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.embed import embed
        result = embed(["test"])
        assert result.dtype == np.float32

    @patch("core.embed._requests.post")
    def test_embed_handles_empty_input(self, mock_post):
        import numpy as np

        from core.embed import embed
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": []}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        result = embed([])
        assert isinstance(result, np.ndarray)
