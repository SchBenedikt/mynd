"""Tests for the combined multi-source deep_research tool (core/tools.py)."""

from unittest.mock import patch

import pytest

from core import tools as tools_module


@pytest.fixture
def kb_chunks(tmp_path):
    import json

    import numpy as np

    chunks_file = tmp_path / "chunks.json"
    embs_file = tmp_path / "embeddings.npy"
    chunks = [
        {"source": "doc:meeting.md", "text": "Nextcloud Terminplanung für nächste Woche"},
        {"source": "affine://ws/abc123", "text": "Persönliche Notiz zu Terminen"},
        {"source": "doc:other.md", "text": "Unrelated content about recipes"},
    ]
    chunks_file.write_text(json.dumps(chunks))
    # 3 identical 1-dim embeddings -> cosine ~1 for identical query embedding
    embs_file.write_bytes(np.zeros((3, 4), dtype=np.float32).tobytes())
    return chunks_file, embs_file


def test_deep_research_registered_in_map():
    assert "deep_research" in tools_module.CORE_MAP
    assert any(
        t["function"]["name"] == "deep_research" for t in tools_module.CORE_TOOLS
    )


def test_deep_research_returns_no_results_message(monkeypatch):
    monkeypatch.setattr(tools_module, "_kb_search_structured", lambda *a, **k: [])
    monkeypatch.setattr(tools_module, "_affine_search_structured", lambda *a, **k: [])
    monkeypatch.setattr(tools_module, "_web_search_structured", lambda *a, **k: [])
    result = tools_module.deep_research("gibtsnicht")
    assert "Keine Ergebnisse" in result
    assert "❌" in result


def test_deep_research_combines_all_sources(monkeypatch):
    monkeypatch.setattr(
        tools_module, "_kb_search_structured",
        lambda *a, **k: [{"source": "doc:a.md", "text": "KB text", "score": 0.9, "kind": "doc"}],
    )
    monkeypatch.setattr(
        tools_module, "_affine_search_structured",
        lambda *a, **k: [{"source": "affine://x", "title": "Affine Doc", "text": "Affine text", "kind": "affine"}],
    )
    monkeypatch.setattr(
        tools_module, "_web_search_structured",
        lambda *a, **k: [{"title": "Web result", "url": "https://example.com", "snippet": "web snippet"}],
    )
    result = tools_module.deep_research("testfrage")
    assert "Lokale Dokumente & Notizen" in result
    assert "AFFiNE" in result
    assert "Internet" in result
    assert "(1)" in result
    assert "(2)" in result
    assert "(3)" in result
    assert "doc:a.md" in result
    assert "Affine Doc" in result
    assert "https://example.com" in result


def test_deep_research_respects_includes(monkeypatch):
    monkeypatch.setattr(tools_module, "_kb_search_structured",
                        lambda *a, **k: [{"source": "doc:a.md", "text": "KB", "score": 0.9, "kind": "doc"}])
    monkeypatch.setattr(tools_module, "_affine_search_structured",
                        lambda *a, **k: [{"source": "affine://x", "title": "A", "text": "t", "kind": "affine"}])
    monkeypatch.setattr(tools_module, "_web_search_structured",
                        lambda *a, **k: [{"title": "W", "url": "https://w", "snippet": "s"}])
    result = tools_module.deep_research("frage", include_kb=False)
    assert "Lokale Dokumente & Notizen" not in result
    assert "AFFiNE" in result
    assert "Internet" in result


def test_deep_research_validation_error():
    result = tools_module.deep_research("x" * 6000)
    assert "❌" in result


@patch.object(tools_module, "_kb_search_structured")
@patch.object(tools_module, "_affine_search_structured")
@patch.object(tools_module, "_web_search_structured")
def test_deep_research_empty_fallback(mock_web, mock_affine, mock_kb):
    mock_kb.return_value = []
    mock_affine.return_value = []
    mock_web.return_value = []
    result = tools_module.deep_research("test")
    assert "Keine Ergebnisse" in result
    assert "❌" in result


def test_kb_search_structured_filters_by_kind(monkeypatch):
    def fake_embed(items):
        return [[1.0, 0.0, 0.0, 0.0]] * len(items)

    monkeypatch.setattr(tools_module, "embed", fake_embed)
    monkeypatch.setattr(tools_module, "CHUNKS", type("P", (), {
        "read_text": lambda self: '[{"source": "affine://x/1", "text": "a"}, {"source": "doc:b.md", "text": "b"}]',
    })())
    monkeypatch.setattr(tools_module, "EMBS", type("P", (), {
        "read_bytes": lambda self: __import__("numpy").zeros((2, 4), dtype="float32").tobytes(),
    })())
    result = tools_module._kb_search_structured("test", top_k=2, min_score=0.0)
    assert isinstance(result, list)
    kinds = {r["kind"] for r in result}
    assert kinds <= {"affine", "doc"}
