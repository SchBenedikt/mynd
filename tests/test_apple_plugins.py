"""Tests for the Apple Reminders and iMessage plugins (macOS)."""

from unittest.mock import patch


def _reminders():
    return __import__("data.plugins.reminders", fromlist=["x"])


def _imessage():
    return __import__("data.plugins.imessage", fromlist=["x"])


class TestRemindersNonMac:
    def test_returns_error_on_non_macos(self):
        mod = _reminders()
        with patch.object(mod, "_IS_MAC", False):
            result = mod.reminders_lists()
            assert "nur auf macOS" in result

    def test_create_requires_title(self):
        mod = _reminders()
        result = mod.reminders_create("")
        assert "Titel fehlt" in result

    def test_due_date_validation(self):
        mod = _reminders()
        with patch.object(mod, "_IS_MAC", True), patch.object(mod, "_run_script", return_value=("ok", None)):
            result = mod.reminders_create("Test", due_date="not-a-date")
            assert "YYYY-MM-DD HH:MM" in result

    def test_applescript_escaping(self):
        mod = _reminders()
        assert mod._asec('a"b\\c') == 'a\\"b\\\\c'

    def test_create_builds_safe_script(self):
        mod = _reminders()
        captured = {}

        def fake_run(script, timeout=20):
            captured["script"] = script
            return ("ok", None)

        with patch.object(mod, "_IS_MAC", True), patch.object(mod, "_run_script", side_effect=fake_run):
            result = mod.reminders_create('O\'Hare "Meeting"', due_date="2026-08-01 09:30", notes="n1", list_name="Persönlich")

        assert "✅" in result
        assert 'O\'Hare \\"Meeting\\"' in captured["script"]
        assert "set year of d to 2026" in captured["script"]
        assert "set time of d to (9 * 3600 + 30 * 60)" in captured["script"]

    def test_search_requires_query(self):
        mod = _reminders()
        result = mod.reminders_search("")
        assert "Suchbegriff fehlt" in result

    def test_parse_reminder_line(self):
        mod = _reminders()
        r = mod._parse_reminder_line("Einkaufen||2026-08-01 09:00|false")
        assert r["name"] == "Einkaufen"
        assert r["completed"] is False
        assert r["due_date"] == "2026-08-01 09:00"


class TestIMessageNonMac:
    def test_send_requires_args(self):
        mod = _imessage()
        assert "Empfänger fehlt" in mod.imessage_send("", "hi")
        assert "Nachrichtentext fehlt" in mod.imessage_send("+491520000", "")

    def test_returns_error_on_non_macos(self):
        mod = _imessage()
        with patch.object(mod, "_IS_MAC", False):
            assert "nur auf macOS" in mod.imessage_send("+491520000", "hi")
            assert "nur auf macOS" in mod.imessage_list_recent()

    def test_send_builds_safe_script(self):
        mod = _imessage()
        captured = {}

        def fake_run(script, timeout=20):
            captured["script"] = script
            return ("ok", None)

        with patch.object(mod, "_IS_MAC", True), patch.object(mod, "_run_script", side_effect=fake_run):
            result = mod.imessage_send('+49 "150"', 'Hallo "Welt"')

        assert "✅" in result
        assert 'send "Hallo \\"Welt\\"" to buddy "+49 \\"150\\""' in captured["script"]

    def test_missing_db_error(self):
        mod = _imessage()
        with patch.object(mod, "_IS_MAC", True), patch.object(mod, "_CHAT_DB", "/nonexistent/chat.db"):
            result = mod.imessage_search("hello")
            assert "nicht gefunden" in result or "Datenbank" in result

    def test_query_limits(self):
        mod = _imessage()
        rows = [("1", "2026-07-31 12:00:00", "hi there", "+491520000", 0, "guid1")]

        class FakeCursor:
            def __init__(self, _sql, _params):
                self._params = _params

            def fetchall(self):
                return rows

        class FakeConn:
            def execute(self, sql, params):
                return FakeCursor(sql, params)

            def close(self):
                pass

        fake_conn = FakeConn()
        with patch.object(mod, "_db_connect", return_value=(fake_conn, None)):
            result = mod.imessage_list_recent(limit=5)
            assert "hi there" in result


class TestApplePluginsSchema:
    def test_reminders_and_imessage_tools_valid(self):
        from core.plugin_base import get_all_tools, load_plugins

        load_plugins()
        tools, tool_map = get_all_tools()
        names = {t["function"]["name"] for t in tools}
        assert {"reminders_lists", "reminders_create", "reminders_search"} <= names
        assert {"imessage_send", "imessage_list_recent", "imessage_search"} <= names
        for tool in tools:
            if tool["function"]["name"].startswith(("reminders_", "imessage_")):
                assert callable(tool_map[tool["function"]["name"]])
