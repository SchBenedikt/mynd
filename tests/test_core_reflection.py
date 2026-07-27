import pytest


@pytest.fixture(autouse=True)
def reset_reflection():
    from core.reflection import _reset_cache
    _reset_cache()


@pytest.fixture
def temp_reflection(tmp_path, monkeypatch):
    from core.reflection import _reset_cache
    _reset_cache()
    ref_file = tmp_path / 'reflections.json'
    monkeypatch.setattr('core.reflection._REFLECTION_FILE', ref_file)
    return ref_file


class TestRecordToolResult:
    def test_records_first_result(self, temp_reflection):
        from core.reflection import _flush, record_tool_result
        record_tool_result('test_tool', {'arg1': 'val1'}, 'ok', True, 100)
        _flush()
        data = __import__('json').loads(temp_reflection.read_text())
        assert len(data['history']) == 1
        assert data['history'][0]['name'] == 'test_tool'
        assert data['history'][0]['success'] is True

    def test_tracks_consecutive_failures(self, temp_reflection):
        from core.reflection import _flush, record_tool_result
        record_tool_result('ssh_tool', {'cmd': 'ls'}, 'error: timeout', False, 5000)
        record_tool_result('ssh_tool', {'cmd': 'ls'}, 'error: timeout', False, 5000)
        _flush()
        data = __import__('json').loads(temp_reflection.read_text())
        assert data['consecutive_failures'].get('ssh_tool') == 2

    def test_resets_consecutive_failures_on_success(self, temp_reflection):
        from core.reflection import _flush, record_tool_result
        record_tool_result('ssh_tool', {}, 'error', False, 100)
        record_tool_result('ssh_tool', {}, 'ok', True, 50)
        _flush()
        data = __import__('json').loads(temp_reflection.read_text())
        assert 'ssh_tool' not in data.get('consecutive_failures', {})

    def test_limits_history_size(self, temp_reflection):
        from core.reflection import _flush, record_tool_result
        for i in range(600):
            record_tool_result('t', {}, 'ok', True, 1)
        _flush()
        data = __import__('json').loads(temp_reflection.read_text())
        assert len(data['history']) <= 400

    def test_masks_secrets_in_args(self, temp_reflection):
        from core.reflection import _flush, record_tool_result
        record_tool_result('login', {'password': 'secret123', 'user': 'admin'}, 'ok', True, 50)
        _flush()
        data = __import__('json').loads(temp_reflection.read_text())
        assert data['history'][0]['args']['password'] == '***'


class TestGetConsecutiveFailures:
    def test_returns_zero_for_unknown_tool(self, temp_reflection):
        from core.reflection import get_consecutive_failures
        assert get_consecutive_failures('unknown') == 0

    def test_returns_correct_count(self, temp_reflection):
        from core.reflection import get_consecutive_failures, record_tool_result
        record_tool_result('tool_a', {}, 'err', False, 100)
        record_tool_result('tool_a', {}, 'err', False, 100)
        assert get_consecutive_failures('tool_a') == 2


class TestGetFailureAnalysis:
    def test_returns_none_when_no_failures(self, temp_reflection):
        from core.reflection import get_failure_analysis
        assert get_failure_analysis('any_tool') is None

    def test_returns_analysis_on_failures(self, temp_reflection):
        from core.reflection import get_failure_analysis, record_tool_result
        record_tool_result('ssh_exec', {}, 'timeout', False, 5000)
        record_tool_result('ssh_exec', {}, 'denied', False, 3000)
        analysis = get_failure_analysis('ssh_exec', max_recent=5)
        assert analysis is not None
        assert 'ssh_exec' in analysis
        assert 'Fehler' in analysis

    def test_mixed_success_and_failure(self, temp_reflection):
        from core.reflection import get_failure_analysis, record_tool_result
        record_tool_result('api', {}, 'ok', True, 100)
        record_tool_result('api', {}, 'err', False, 200)
        record_tool_result('api', {}, 'err', False, 300)
        analysis = get_failure_analysis('api', max_recent=5)
        assert analysis is not None
        assert '66%' in analysis or '67%' in analysis

    def test_uses_all_tools_when_no_name_given(self, temp_reflection):
        from core.reflection import get_failure_analysis, record_tool_result
        record_tool_result('a', {}, 'err', False, 50)
        record_tool_result('b', {}, 'ok', True, 50)
        analysis = get_failure_analysis(max_recent=5)
        assert analysis is not None

    def test_suggests_strategy_change_after_3_failures(self, temp_reflection):
        from core.reflection import get_failure_analysis, record_tool_result
        for _ in range(3):
            record_tool_result('api_call', {}, 'error', False, 100)
        analysis = get_failure_analysis('api_call', max_recent=5)
        assert analysis is not None
        assert 'Strategie' in analysis


class TestGetRecentSuccessPattern:
    def test_returns_none_with_insufficient_data(self, temp_reflection):
        from core.reflection import get_recent_success_pattern
        assert get_recent_success_pattern('t') is None

    def test_returns_pattern_on_consecutive_successes(self, temp_reflection):
        from core.reflection import get_recent_success_pattern, record_tool_result
        record_tool_result('search', {'q': 'test'}, 'found', True, 50)
        record_tool_result('search', {'q': 'test2'}, 'found', True, 60)
        pattern = get_recent_success_pattern('search', min_successes=2)
        assert pattern is not None
        assert pattern['tool'] == 'search'
        assert pattern['consecutive_successes'] == 2


def _write_history(temp_reflection, entries):
    import json

    from core.reflection import _reset_cache
    data = {'history': entries, 'consecutive_failures': {}}
    temp_reflection.write_text(json.dumps(data))
    _reset_cache()


class TestGetToolPerformance:
    def test_empty_history(self, temp_reflection):
        from core.reflection import get_tool_performance
        assert get_tool_performance() == {}
        assert get_tool_performance('anything') == {}

    def test_filter_non_existent_tool_returns_empty(self, temp_reflection):
        from core.reflection import get_tool_performance, record_tool_result
        record_tool_result('a', {}, 'ok', True, 10)
        stats = get_tool_performance('non_existent')
        assert stats == {}

    def test_single_tool_multiple_calls(self, temp_reflection):
        from core.reflection import get_tool_performance, record_tool_result
        record_tool_result('tool_a', {'x': 1}, 'ok', True, 100)
        record_tool_result('tool_a', {'x': 2}, 'ok', True, 200)
        record_tool_result('tool_a', {'x': 3}, 'err', False, 150)
        stats = get_tool_performance()
        assert 'tool_a' in stats
        s = stats['tool_a']
        assert s['calls'] == 3
        assert s['failures'] == 1
        assert s['success_rate'] == pytest.approx(66.666, 0.1)
        assert s['avg_ms'] == pytest.approx(150, 0.1)
        assert s['min_ms'] == 100
        assert s['max_ms'] == 200

    def test_multiple_tools(self, temp_reflection):
        from core.reflection import get_tool_performance, record_tool_result
        record_tool_result('a', {}, 'ok', True, 10)
        record_tool_result('a', {}, 'err', False, 20)
        record_tool_result('b', {}, 'ok', True, 30)
        stats = get_tool_performance()
        assert set(stats.keys()) == {'a', 'b'}
        assert stats['a']['calls'] == 2
        assert stats['a']['failures'] == 1
        assert stats['b']['calls'] == 1
        assert stats['b']['failures'] == 0

    def test_filter_by_tool_name(self, temp_reflection):
        from core.reflection import get_tool_performance, record_tool_result
        record_tool_result('a', {}, 'ok', True, 10)
        record_tool_result('b', {}, 'ok', True, 20)
        stats = get_tool_performance('a')
        assert 'a' in stats
        assert 'b' not in stats

    def test_consecutive_failures_resets_on_success(self, temp_reflection):
        from core.reflection import get_tool_performance, record_tool_result
        record_tool_result('t', {}, 'err', False, 10)
        record_tool_result('t', {}, 'err', False, 10)
        record_tool_result('t', {}, 'ok', True, 10)
        stats = get_tool_performance('t')
        assert stats['t']['consecutive_failures'] == 0

    def test_all_failures_updates_consecutive(self, temp_reflection):
        from core.reflection import get_tool_performance, record_tool_result
        record_tool_result('t', {}, 'err', False, 10)
        record_tool_result('t', {}, 'err', False, 10)
        record_tool_result('t', {}, 'err', False, 10)
        stats = get_tool_performance('t')
        assert stats['t']['consecutive_failures'] == 3

    def test_zero_calls_edge_case(self, temp_reflection):
        from core.reflection import get_tool_performance, record_tool_result
        record_tool_result('t', {}, 'ok', True, 0)
        stats = get_tool_performance('t')
        assert stats['t']['avg_ms'] == 0
        assert stats['t']['success_rate'] == 100.0


class TestGetImprovementSuggestions:
    def test_empty_history_returns_all_ok(self, temp_reflection):
        from core.reflection import get_improvement_suggestions
        result = get_improvement_suggestions()
        assert '✅' in result

    def test_no_issues_returns_all_ok(self, temp_reflection):
        from core.reflection import get_improvement_suggestions, record_tool_result
        for _ in range(5):
            record_tool_result('t', {}, 'ok', True, 100)
        result = get_improvement_suggestions()
        assert '✅' in result

    def test_suggests_low_success_rate(self, temp_reflection):
        from core.reflection import get_improvement_suggestions, record_tool_result
        for _ in range(3):
            record_tool_result('failing_tool', {}, 'err', False, 100)
        result = get_improvement_suggestions()
        assert 'failing_tool' in result
        assert '⚠️' in result

    def test_suggests_slow_tool(self, temp_reflection):
        from core.reflection import get_improvement_suggestions, record_tool_result
        for _ in range(3):
            record_tool_result('slow_tool', {}, 'ok', True, 15000)
        result = get_improvement_suggestions()
        assert 'slow_tool' in result
        assert '🐌' in result

    def test_suggests_new_tool(self, temp_reflection):
        from core.reflection import get_improvement_suggestions, record_tool_result
        record_tool_result('new_tool', {}, 'ok', True, 50)
        result = get_improvement_suggestions()
        assert 'new_tool' in result
        assert '📌' in result

    def test_no_suggestion_for_healthy_tool(self, temp_reflection):
        from core.reflection import get_improvement_suggestions, record_tool_result
        for _ in range(5):
            record_tool_result('healthy', {}, 'ok', True, 100)
        result = get_improvement_suggestions()
        assert 'healthy' not in result


class TestGetDailySummary:
    def test_empty_history(self, temp_reflection):
        from core.reflection import get_daily_summary
        result = get_daily_summary()
        assert 'Heute noch keine Tool-Aufrufe' in result

    def test_summary_with_todays_calls(self, temp_reflection):
        from core.reflection import get_daily_summary, record_tool_result
        record_tool_result('a', {}, 'ok', True, 100)
        record_tool_result('a', {}, 'ok', True, 200)
        record_tool_result('b', {}, 'err', False, 50)
        result = get_daily_summary()
        assert 'Aufrufe: 3' in result
        assert 'Erfolgreich: 2' in result
        assert 'Fehlgeschlagen: 1' in result
        assert 'Eindeutige Tools: 2' in result
        assert 'Tagesübersicht' in result

    def test_all_failures(self, temp_reflection):
        from core.reflection import get_daily_summary, record_tool_result
        for _ in range(3):
            record_tool_result('buggy', {}, 'err', False, 500)
        result = get_daily_summary()
        assert 'Aufrufe: 3' in result
        assert 'Erfolgreich: 0' in result
        assert 'Fehlgeschlagen: 3' in result

    def test_ignores_old_dates(self, temp_reflection):
        from datetime import datetime, timedelta

        from core.reflection import get_daily_summary
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        _write_history(temp_reflection, [
            {'name': 'old_tool', 'args': {}, 'success': True, 'duration_ms': 100, 'result_preview': 'ok', 'timestamp': yesterday},
        ])
        result = get_daily_summary()
        assert 'Heute noch keine Tool-Aufrufe' in result

    def test_lists_top_3_tools(self, temp_reflection):
        from core.reflection import get_daily_summary, record_tool_result
        for _ in range(5):
            record_tool_result('popular', {}, 'ok', True, 10)
        for _ in range(3):
            record_tool_result('medium', {}, 'ok', True, 10)
        record_tool_result('rare', {}, 'ok', True, 10)
        result = get_daily_summary()
        assert 'popular: 5x' in result
        assert 'medium: 3x' in result

    def test_no_failures_today(self, temp_reflection):
        from core.reflection import get_daily_summary, record_tool_result
        record_tool_result('x', {}, 'ok', True, 50)
        result = get_daily_summary()
        assert 'Fehlgeschlagen: 0' in result


class TestPruneHistory:
    def test_empty_history(self, temp_reflection):
        from core.reflection import prune_history
        result = prune_history(days=30)
        assert '0 alte Einträge entfernt' in result

    def test_removes_old_entries(self, temp_reflection):
        from datetime import datetime, timedelta

        from core.reflection import _load, prune_history
        old = (datetime.now() - timedelta(days=100)).isoformat()
        recent = (datetime.now() - timedelta(days=1)).isoformat()
        _write_history(temp_reflection, [
            {'name': 'old', 'args': {}, 'success': True, 'duration_ms': 10, 'result_preview': 'ok', 'timestamp': old},
            {'name': 'recent', 'args': {}, 'success': True, 'duration_ms': 10, 'result_preview': 'ok', 'timestamp': recent},
        ])
        result = prune_history(days=30)
        assert '1 alte Einträge entfernt (1 verbleibend)' in result
        data = _load()
        assert len(data['history']) == 1
        assert data['history'][0]['name'] == 'recent'

    def test_keeps_all_within_range(self, temp_reflection):
        from datetime import datetime, timedelta

        from core.reflection import _load, prune_history
        today = datetime.now().isoformat()
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        _write_history(temp_reflection, [
            {'name': 'a', 'args': {}, 'success': True, 'duration_ms': 10, 'result_preview': 'ok', 'timestamp': today},
            {'name': 'b', 'args': {}, 'success': True, 'duration_ms': 10, 'result_preview': 'ok', 'timestamp': yesterday},
        ])
        result = prune_history(days=2)
        assert '0 alte Einträge entfernt' in result
        data = _load()
        assert len(data['history']) == 2

    def test_days_zero_removes_old(self, temp_reflection):
        from datetime import datetime, timedelta

        from core.reflection import _load, prune_history
        old = (datetime.now() - timedelta(days=1)).isoformat()
        _write_history(temp_reflection, [
            {'name': 'a', 'args': {}, 'success': True, 'duration_ms': 10, 'result_preview': 'ok', 'timestamp': old},
        ])
        result = prune_history(days=0)
        assert '1 alte Einträge entfernt' in result
        data = _load()
        assert len(data['history']) == 0

    def test_negative_days_removes_all(self, temp_reflection):
        from datetime import datetime

        from core.reflection import _load, prune_history
        now = datetime.now().isoformat()
        _write_history(temp_reflection, [
            {'name': 'a', 'args': {}, 'success': True, 'duration_ms': 10, 'result_preview': 'ok', 'timestamp': now},
        ])
        prune_history(days=-1)
        data = _load()
        assert len(data['history']) == 0
