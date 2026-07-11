"""Test homeassistant plugin – tools that work without a live HA instance."""

import pytest

from data.plugins.homeassistant import (
    _extract_area,
    _format_entity,
    _parse_color,
    homeassistant_list_scenes,
    homeassistant_list_scripts,
)


class TestAreaExtraction:
    def test_wohnzimmer(self):
        assert _extract_area("light.wohnzimmer", {}) == "Wohnzimmer"
        assert _extract_area("light.schlafzimmer_decke", {}) == "Schlafzimmer"

    def test_kueche(self):
        assert _extract_area("switch.kueche_light", {}) == "Küche"

    def test_terrasse(self):
        assert _extract_area("light.terrasse", {}) == "Terrasse"

    def test_hof(self):
        assert _extract_area("sensor.hof_temperatur", {}) == "Hof"

    def test_unknown_returns_empty(self):
        assert _extract_area("sensor.abc123", {}) == ""

    def test_friendly_name_priority(self):
        attrs = {"friendly_name": "Wohnzimmer Lampe"}
        assert _extract_area("light.xyz", attrs) == "Wohnzimmer"


class TestFormatEntity:
    def test_light_on(self):
        s = {"entity_id": "light.test", "state": "on", "attributes": {"friendly_name": "Test"}}
        result = _format_entity(s)
        assert "🟢" in result
        assert "`light.test`" in result

    def test_light_off(self):
        s = {"entity_id": "light.test", "state": "off", "attributes": {}}
        result = _format_entity(s)
        assert "⚫" in result

    def test_with_brightness(self):
        s = {"entity_id": "light.test", "state": "on",
             "attributes": {"friendly_name": "Test", "brightness": 200}}
        result = _format_entity(s)
        assert "Helligkeit" in result
        assert "200" in result


class TestParseColor:
    @pytest.mark.parametrize("input_color,expected", [
        ("rot", (255, 0, 0)),
        ("blau", (0, 0, 255)),
        ("green", (0, 255, 0)),
        ("gelb", (255, 255, 0)),
        ("255,0,0", (255, 0, 0)),
        ("100,200,50", (100, 200, 50)),
        ("", None),
        ("unknown", None),
    ])
    def test_parse_color(self, input_color, expected):
        result = _parse_color(input_color)
        assert result == expected


class TestListScenesAndScripts:
    """These rely on HA connection, so they should return error messages gracefully."""

    def test_list_scenes_returns_error_if_no_ha(self):
        result = homeassistant_list_scenes()
        assert isinstance(result, str)
        # Should indicate missing HA config
        assert "HA" in result or "fehlt" in result or "Keine" in result or "Szenen" in result or "❌" in result

    def test_list_scripts_returns_string(self):
        result = homeassistant_list_scripts()
        assert isinstance(result, str)
