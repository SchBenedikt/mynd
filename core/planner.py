import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

_PLANS_FILE = None
_plans_lock = threading.Lock()
_cache = None
_dirty = False
_flush_counter = 0
_FLUSH_INTERVAL = 5


def _get_plans_file():
    global _PLANS_FILE
    if _PLANS_FILE is None:
        data_dir = Path(__file__).resolve().parent.parent / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        _PLANS_FILE = data_dir / 'plans.json'
    return _PLANS_FILE


def _load():
    global _cache
    if _cache is not None:
        return _cache
    path = _get_plans_file()
    if path.exists():
        try:
            _cache = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            _cache = {}
    else:
        _cache = {}
    return _cache


def _flush():
    global _dirty, _cache
    if _dirty and _cache is not None:
        path = _get_plans_file()
        path.write_text(json.dumps(_cache, indent=2, ensure_ascii=False))
        _dirty = False


def _maybe_flush():
    global _flush_counter
    _flush_counter += 1
    if _flush_counter >= _FLUSH_INTERVAL:
        _flush()
        _flush_counter = 0


def _reset_cache():
    global _cache, _dirty, _flush_counter
    _cache = None
    _dirty = False
    _flush_counter = 0


def create_plan(steps, description=''):
    if isinstance(steps, str):
        steps = [s.strip() for s in steps.split('\n') if s.strip()]
    if not steps:
        return None, '❌ Keine Schritte angegeben.'
    plan_id = uuid.uuid4().hex[:12]
    plan = {
        'id': plan_id,
        'description': description or 'Mehrschritt-Plan',
        'created': datetime.now().isoformat(),
        'updated': datetime.now().isoformat(),
        'status': 'active',
        'total_steps': len(steps),
        'completed_steps': 0,
        'failed_steps': 0,
        'steps': [
            {'id': i + 1, 'task': s, 'status': 'pending', 'result': '', 'verified': False}
            for i, s in enumerate(steps)
        ],
        'current_step': 0,
    }
    with _plans_lock:
        plans = _load()
        plans[plan_id] = plan
        _dirty = True
        _maybe_flush()
    plan_text = _format_plan(plan)
    return plan_id, plan_text


def get_plan(plan_id):
    with _plans_lock:
        plans = _load()
        plan = plans.get(plan_id)
        if plan is None:
            return None, f'❌ Plan {plan_id!r} nicht gefunden.'
        return plan, _format_plan(plan)


def update_step(plan_id, step_id, status, result='', verified=False):
    with _plans_lock:
        plans = _load()
        plan = plans.get(plan_id)
        if plan is None:
            return f'❌ Plan {plan_id!r} nicht gefunden.'
        step = next((s for s in plan['steps'] if s['id'] == step_id), None)
        if step is None:
            return f'❌ Schritt {step_id} in Plan {plan_id!r} nicht gefunden.'
        old_status = step['status']
        step['status'] = status
        if result:
            step['result'] = str(result)[:500]
        if verified:
            step['verified'] = True
        plan['updated'] = datetime.now().isoformat()
        completed = sum(1 for s in plan['steps'] if s['status'] == 'done')
        failed = sum(1 for s in plan['steps'] if s['status'] == 'failed')
        plan['completed_steps'] = completed
        plan['failed_steps'] = failed
        if completed + failed == plan['total_steps']:
            plan['status'] = 'completed' if failed == 0 else 'completed_with_errors'
        plan['current_step'] = max(0, completed + failed)
        _dirty = True
        _maybe_flush()
        progress = f'{completed + failed}/{plan["total_steps"]}'
        return f'✅ Schritt {step_id} ({step["task"][:50]}): {old_status} → {status}. Fortschritt: {progress}'


def advance_plan(plan_id, result=''):
    with _plans_lock:
        plans = _load()
        plan = plans.get(plan_id)
        if plan is None:
            return None, f'❌ Plan {plan_id!r} nicht gefunden.'
        if plan['status'] == 'completed':
            return None, '✅ Plan bereits abgeschlossen.'
        current = plan['current_step']
        if current >= plan['total_steps']:
            plan['status'] = 'completed'
            _dirty = True
            _maybe_flush()
            return None, '✅ Alle Schritte abgeschlossen.'
        step = plan['steps'][current]
        step['status'] = 'in_progress'
        if result:
            step['result'] = str(result)[:500]
        plan['updated'] = datetime.now().isoformat()
        _dirty = True
        _maybe_flush()
        return step, f'▶️ Schritt {step["id"]}: {step["task"][:100]}'


def complete_step(plan_id, step_id, result='', verified=True):
    return update_step(plan_id, step_id, 'done', result=result, verified=verified)


def fail_step(plan_id, step_id, error=''):
    msg = update_step(plan_id, step_id, 'failed', result=error)
    with _plans_lock:
        plans = _load()
        plan = plans.get(plan_id)
        if plan and plan['failed_steps'] >= 2:
            return msg + '\n⚠️ Zwei Fehlschläge – erwäge Strategiewechsel.'
    return msg


def list_plans(status=None):
    with _plans_lock:
        plans = _load()
    result = []
    for plan_id, plan in sorted(plans.items(), key=lambda x: x[1].get('created', ''), reverse=True):
        if status and plan.get('status') != status:
            continue
        done = plan.get('completed_steps', 0) + plan.get('failed_steps', 0)
        total = plan.get('total_steps', 1)
        result.append({
            'id': plan_id,
            'description': plan.get('description', ''),
            'status': plan.get('status', 'unknown'),
            'progress': f'{done}/{total}',
            'created': plan.get('created', ''),
        })
    return result


def delete_plan(plan_id):
    with _plans_lock:
        plans = _load()
        if plan_id not in plans:
            return f'❌ Plan {plan_id!r} nicht gefunden.'
        del plans[plan_id]
        _dirty = True
        _maybe_flush()
    return f'🗑 Plan {plan_id!r} gelöscht.'


def _format_plan(plan):
    lines = [f'📋 Plan: {plan["description"]}', f'Status: {plan["status"]}', '']
    for s in plan['steps']:
        status_icon = {'pending': '⬜', 'in_progress': '🔄', 'done': '✅', 'failed': '❌'}.get(s['status'], '⬜')
        task = s['task'][:80]
        if len(s['task']) > 80:
            task += '...'
        lines.append(f'  {status_icon} [{s["id"]}] {task}')
        if s.get('verified') and s['status'] == 'done':
            lines[-1] += ' ✓'
        if s.get('result'):
            preview = s['result'][:60]
            lines.append(f'       └─ {preview}')
    done = plan['completed_steps'] + plan['failed_steps']
    total = plan['total_steps']
    pct = int(done / max(total, 1) * 100)
    bar = '█' * (pct // 10) + '░' * (10 - pct // 10)
    lines.append(f'\n{bar} {done}/{total} ({pct}%)')
    return '\n'.join(lines)
