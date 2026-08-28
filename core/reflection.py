import json
import threading
from datetime import datetime
from pathlib import Path

_REFLECTION_FILE = None
_reflection_lock = threading.Lock()
_cache = None
_dirty = False
_flush_counter = 0
_FLUSH_INTERVAL = 5


def _get_reflection_file():
    global _REFLECTION_FILE
    if _REFLECTION_FILE is None:
        data_dir = Path(__file__).resolve().parent.parent / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        _REFLECTION_FILE = data_dir / 'reflections.json'
    return _REFLECTION_FILE


def _load():
    global _cache
    if _cache is not None:
        return _cache
    path = _get_reflection_file()
    if path.exists():
        try:
            _cache = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            _cache = {'history': [], 'consecutive_failures': {}}
    else:
        _cache = {'history': [], 'consecutive_failures': {}}
    return _cache


def _flush():
    global _dirty, _cache
    if _dirty and _cache is not None:
        path = _get_reflection_file()
        path.write_text(json.dumps(_cache, indent=2, ensure_ascii=False))
        _dirty = False


def record_tool_result(name, args, result, success, duration_ms):
    global _dirty, _flush_counter
    with _reflection_lock:
        data = _load()
        data.setdefault('history', [])
        data.setdefault('consecutive_failures', {})
        data['history'].append(
            {
                'name': name,
                'args': _safe_args(args),
                'success': success,
                'duration_ms': duration_ms,
                'result_preview': str(result)[:200],
                'timestamp': datetime.now().isoformat(),
            }
        )
        if len(data['history']) > 500:
            data['history'] = data['history'][-300:]
        if not success:
            cf = data['consecutive_failures']
            cf[name] = cf.get(name, 0) + 1
        else:
            data['consecutive_failures'].pop(name, None)
        _dirty = True
        _flush_counter += 1
        if _flush_counter >= _FLUSH_INTERVAL:
            _flush()
            _flush_counter = 0


def get_consecutive_failures(tool_name):
    with _reflection_lock:
        data = _load()
        return data.get('consecutive_failures', {}).get(tool_name, 0)


def get_tool_performance(tool_name=None):
    with _reflection_lock:
        data = _load()
        history = data.get('history', [])
        if tool_name:
            history = [h for h in history if h['name'] == tool_name]
    stats = {}
    for h in history:
        name = h['name']
        if name not in stats:
            stats[name] = {
                'calls': 0,
                'failures': 0,
                'total_ms': 0,
                'min_ms': float('inf'),
                'max_ms': 0,
                'consecutive_failures': 0,
            }
        stats[name]['calls'] += 1
        stats[name]['total_ms'] += h.get('duration_ms', 0)
        stats[name]['min_ms'] = min(stats[name]['min_ms'], h.get('duration_ms', 0))
        stats[name]['max_ms'] = max(stats[name]['max_ms'], h.get('duration_ms', 0))
        if not h['success']:
            stats[name]['failures'] += 1
            stats[name]['consecutive_failures'] += 1
        else:
            stats[name]['consecutive_failures'] = 0
    for s in stats.values():
        s['avg_ms'] = s['total_ms'] / max(s['calls'], 1)
        s['success_rate'] = (s['calls'] - s['failures']) / max(s['calls'], 1) * 100
        s.pop('total_ms', None)
    return stats


def get_improvement_suggestions():
    stats = get_tool_performance()
    suggestions = []
    for name, s in sorted(stats.items(), key=lambda x: x[1]['success_rate']):
        if s['success_rate'] < 50 and s['calls'] >= 3:
            suggestions.append(
                f'⚠️ {name}: {s["success_rate"]:.0f}% Erfolgsrate ({s["failures"]}/{s["calls"]}) '
                f'– Parameter oder Strategie überprüfen'
            )
        elif s['success_rate'] < 80 and s['calls'] >= 5:
            suggestions.append(f'⚡ {name}: {s["success_rate"]:.0f}% Erfolgsrate – leicht verbesserungswürdig')
        if s['avg_ms'] > 10000 and s['calls'] >= 3:
            suggestions.append(f'🐌 {name}: Ø {s["avg_ms"]:.0f}ms ({s["calls"]}x) – sehr langsam, Timeout erhöhen?')
        if s['avg_ms'] > 5000 and s['calls'] >= 5:
            suggestions.append(f'⏱ {name}: Ø {s["avg_ms"]:.0f}ms – monitoringwürdig')
        if s['calls'] < 3 and s['failures'] == 0:
            suggestions.append(f'📌 {name}: erst {s["calls"]}x genutzt, alle erfolgreich – neue Fähigkeit?')
    if not suggestions:
        suggestions.append('✅ Alle Tools arbeiten innerhalb der erwarteten Parameter.')
    return '\n'.join(suggestions[:10])


def get_daily_summary():
    from datetime import date as _date

    today = _date.today().isoformat()
    with _reflection_lock:
        data = _load()
        today_history = [h for h in data.get('history', []) if h.get('timestamp', '').startswith(today)]
    if not today_history:
        return 'Heute noch keine Tool-Aufrufe.'
    total = len(today_history)
    success = sum(1 for h in today_history if h['success'])
    failures = total - success
    unique_tools = len({h['name'] for h in today_history})
    avg_duration = sum(h.get('duration_ms', 0) for h in today_history) / max(total, 1)
    top_tools = {}
    for h in today_history:
        top_tools[h['name']] = top_tools.get(h['name'], 0) + 1
    top_3 = sorted(top_tools.items(), key=lambda x: x[1], reverse=True)[:3]
    lines = [
        f'📊 Tagesübersicht ({today}):',
        f'Aufrufe: {total} | Erfolgreich: {success} | Fehlgeschlagen: {failures}',
        f'Eindeutige Tools: {unique_tools} | Ø Dauer: {avg_duration:.0f}ms',
        '',
        'Häufigste Tools:',
    ]
    for name, count in top_3:
        lines.append(f'  {name}: {count}x')
    return '\n'.join(lines)


def prune_history(days=30):
    global _dirty
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    cutoff = (_dt.now() - _td(days=days)).isoformat()
    with _reflection_lock:
        data = _load()
        original = len(data.get('history', []))
        data['history'] = [h for h in data.get('history', []) if h.get('timestamp', '') >= cutoff]
        kept = len(data['history'])
        pruned = original - kept
        _dirty = True
        _flush()
        return f'🧹 Aufräumen: {pruned} alte Einträge entfernt ({kept} verbleibend)'


def get_failure_analysis(tool_name=None, max_recent=5):
    with _reflection_lock:
        data = _load()
        history = data.get('history', [])
        if tool_name:
            history = [h for h in history if h['name'] == tool_name]
        recent = history[-max_recent:]
        if not recent:
            return None
        failures = [h for h in recent if not h['success']]
        if not failures:
            return None
        total = len(recent)
        fail_count = len(failures)
        fail_rate = fail_count / total * 100
        lines = [
            f'Analyse der letzten {total} Aufrufe von {tool_name or "allen Tools"}:',
            f'Fehlerrate: {fail_rate:.0f}% ({fail_count}/{total})',
        ]
        if fail_count >= 3:
            lines.append('Mehrere Fehler in Folge – wechsle komplett die Strategie.')
        elif fail_count >= 2:
            lines.append('Wiederholte Fehler – versuche einen alternativen Ansatz.')
        if fail_rate > 50:
            lines.append(f'Hohe Fehlerquote bei {tool_name}. Überprüfe die Parameter oder nutze ein anderes Tool.')
        return '\n'.join(lines)


def get_recent_success_pattern(tool_name, min_successes=2):
    with _reflection_lock:
        data = _load()
        history = [h for h in data.get('history', []) if h['name'] == tool_name]
        if len(history) < min_successes:
            return None
        recent = history[-min_successes:]
        if all(h['success'] for h in recent):
            args_pattern = {k: type(v).__name__ for k, v in recent[0].get('args', {}).items()}
            return {
                'tool': tool_name,
                'consecutive_successes': min_successes,
                'args_pattern': args_pattern,
            }
        return None


def _reset_cache():
    global _cache, _dirty, _flush_counter
    _cache = None
    _dirty = False
    _flush_counter = 0


def _safe_args(args):
    if not isinstance(args, dict):
        return {}
    safe = {}
    for k, v in args.items():
        if any(secret in k.lower() for secret in ['password', 'pass', 'secret', 'api', 'token', 'key']):
            safe[k] = '***'
        else:
            safe[k] = str(v)[:100]
    return safe
