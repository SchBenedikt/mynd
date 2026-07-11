"""Test immich plugin – formatting, URL building, and safe guards."""

import pytest

from data.plugins.immich import (
    _fmt_bytes,
    _format_asset,
    immich_get_server_stats,
)


class TestFormatAsset:
    def test_image_asset_creates_markdown_link(self):
        asset = {
            "id": "abc-123",
            "originalFileName": "test.jpg",
            "fileCreatedAt": "2026-07-08T14:30:00.000Z",
            "width": 1920,
            "height": 1080,
            "type": "IMAGE",
        }
        result = _format_asset(asset)
        assert "![test.jpg" in result
        assert "abc-123" in result
        assert "1920x1080" in result

    def test_video_asset_no_image_link(self):
        asset = {
            "id": "vid-456",
            "originalFileName": "video.mp4",
            "fileCreatedAt": "2026-07-08T12:00:00.000Z",
            "type": "VIDEO",
        }
        result = _format_asset(asset)
        assert "video.mp4" in result
        assert "![" not in result

    def test_asset_with_no_id_does_not_crash(self):
        asset = {"originalFileName": "no_id.jpg", "type": "IMAGE"}
        result = _format_asset(asset)
        assert isinstance(result, str)


class TestFmtBytes:
    @pytest.mark.parametrize("input_bytes,expected_unit", [
        (500, "B"),
        (2048, "KB"),
        (1048576 * 2, "MB"),
        (1073741824 * 3, "GB"),
        (1099511627776 * 5, "TB"),
    ])
    def test_fmt_bytes_units(self, input_bytes, expected_unit):
        result = _fmt_bytes(input_bytes)
        assert expected_unit in result


class TestServerStats:
    def test_get_server_stats_returns_string(self):
        result = immich_get_server_stats()
        assert isinstance(result, str)
        assert len(result) > 0
