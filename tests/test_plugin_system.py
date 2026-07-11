"""Test system.py plugin: timers, weather search mode, system info helpers."""



from data.plugins.system import (
    system_get_disk_usage,
    system_get_info,
    system_get_processes,
    timer_list,
    timer_remove,
    timer_set,
    weather_forecast,
    weather_get,
    web_search,
)


class TestSystemInfo:
    def test_get_info_returns_string(self):
        result = system_get_info()
        assert isinstance(result, str)
        assert len(result) > 20
        assert "Server-Info" in result
        assert "CPU" in result or "Python" in result

    def test_get_disk_usage_returns_string(self):
        result = system_get_disk_usage()
        assert isinstance(result, str)
        assert "Festplatten" in result or "GB" in result or "%" in result

    def test_get_processes_returns_top_processes(self):
        result = system_get_processes(top_n=5)
        assert isinstance(result, str)
        assert "CPU" in result
        # Should list at least a few processes
        lines = result.strip().split("\n")
        assert len(lines) >= 3


class TestTimers:
    def test_set_and_list_timer(self, sample_timers):
        tid = timer_set(label="Pytest Timer", minutes=1)
        assert tid.startswith("⏰")
        assert "Pytest Timer" in tid

        result = timer_list()
        assert isinstance(result, str)
        assert "Aktive Timer" in result or "Keine Timer" in result

    def test_set_seconds_timer(self):
        tid = timer_set(label="Short", seconds=30)
        assert "Short" in tid

    def test_set_hours_timer(self):
        tid = timer_set(label="Long", hours=2)
        assert "Long" in tid
        assert "2h" in tid

    def test_remove_nonexistent_timer(self):
        result = timer_remove("nonexistent_id_12345")
        assert "nicht gefunden" in result


class TestWeather:
    def test_weather_get_returns_string(self):
        result = weather_get()
        assert isinstance(result, str)
        assert len(result) > 10

    def test_weather_forecast_returns_forecast(self):
        result = weather_forecast(days=2)
        assert isinstance(result, str)
        assert "Wettervorhersage" in result


class TestWebSearch:
    def test_web_search_returns_results(self):
        result = web_search("Python Programmierung", max_results=3)
        assert isinstance(result, str)
        # Should either return results or a meaningful error
        if result.startswith("❌"):
            assert "fehlgeschlagen" in result or "Keine Ergebnisse" in result
        else:
            assert "Web-Suche" in result
