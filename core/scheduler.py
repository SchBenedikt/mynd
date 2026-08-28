import json
import logging
import os
import re
import secrets
import tempfile
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
AUTOMATIONS_FILE = DATA_DIR / 'automations.json'
HISTORY_FILE = DATA_DIR / 'automations_history.json'
NOTIFICATIONS_FILE = DATA_DIR / 'notifications.json'

TRIGGER_TYPES = {'cron', 'interval', 'webhook'}

CRON_HELP = {
    'minute': '0-59 (z.B. 0 = volle Stunde, */5 = alle 5 Min.)',
    'hour': '0-23 (z.B. 6 = 6 Uhr morgens)',
    'day': '1-31 (Tag im Monat)',
    'month': '1-12',
    'day_of_week': '0-6 oder mon,tue,wed,thu,fri,sat,sun (0=Montag, 6=Sonntag)',
}

TRIGGER_EXAMPLES = [
    {'label': 'T\u00e4glich um 06:00', 'value': {'hour': '6', 'minute': '0'}},
    {'label': 'Werktags um 07:00', 'value': {'hour': '7', 'minute': '0', 'day_of_week': 'mon-fri'}},
    {'label': 'Jede Stunde', 'value': {'minute': '0'}},
    {'label': 'Alle 30 Minuten', 'value': {'minute': '*/30'}},
    {'label': 'Jeden Montag 09:00', 'value': {'hour': '9', 'minute': '0', 'day_of_week': 'mon'}},
]


def _load_json(path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f'Fehler beim Lesen von {path}: {e}')
    return default if default is not None else []


_scheduler_lock = threading.RLock()


def _save_json(path, data):
    with _scheduler_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


def _validate_condition(condition: dict, context: dict) -> bool:
    ctype = condition.get('type', '')
    if ctype == 'contains':
        value = str(context.get(condition.get('field', condition.get('variable', '')), ''))
        return condition.get('value', '') in value
    elif ctype == 'equals':
        value = str(context.get(condition.get('field', condition.get('variable', '')), ''))
        return value == str(condition.get('value', ''))
    elif ctype == 'gt':
        try:
            return float(context.get(condition.get('field', condition.get('variable', '')), 0)) > float(
                condition.get('value', 0)
            )
        except (ValueError, TypeError):
            return False
    elif ctype == 'lt':
        try:
            return float(context.get(condition.get('field', condition.get('variable', '')), 0)) < float(
                condition.get('value', 0)
            )
        except (ValueError, TypeError):
            return False
    elif ctype == 'and':
        return all(_validate_condition(c, context) for c in condition.get('conditions', []))
    elif ctype == 'or':
        return any(_validate_condition(c, context) for c in condition.get('conditions', []))
    elif ctype == 'not':
        return not _validate_condition(condition.get('condition', {}), context)
    return False


def _redact_result(value):
    text = str(value)
    text = re.sub(r'(?i)(password|passwd|secret|api[_-]?key|token)(\s*[:=]\s*)[^\s,;]+', r'\1\2***', text)
    text = re.sub(r'(?i)bearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer ***', text)
    return text[:2000]


class AutomationEngine:
    def __init__(self, tool_map: dict, data_dir: Path = None):
        self.tool_map = tool_map
        self.data_dir = data_dir or DATA_DIR
        self.automations_file = self.data_dir / 'automations.json'
        self.history_file = self.data_dir / 'automations_history.json'
        self.notifications_file = self.data_dir / 'notifications.json'
        self._running = False
        self._scheduler = None

    def load_automations(self):
        return _load_json(self.automations_file, [])

    def save_automations(self, automations):
        _save_json(self.automations_file, automations)

    def load_history(self):
        return _load_json(self.history_file, [])

    def save_history(self, history):
        _save_json(self.history_file, history)

    def load_notifications(self):
        return _load_json(self.notifications_file, [])

    def save_notifications(self, notifications):
        _save_json(self.notifications_file, notifications)

    def add_notification(self, title, content=''):
        with _scheduler_lock:
            notifications = self.load_notifications()
            entry = {
                'id': secrets.token_hex(12),
                'title': _redact_result(title)[:200],
                'content': _redact_result(content),
                'created_at': datetime.now().isoformat(),
                'read': False,
            }
            notifications.append(entry)
            notifications[:] = notifications[-100:]
            self.save_notifications(notifications)
        return entry

    def get_automation(self, aid: str) -> dict | None:
        for a in self.load_automations():
            if a.get('id') == aid:
                return a
        return None

    def add_automation(self, auto: dict):
        with _scheduler_lock:
            if auto.get('trigger', {}).get('type') == 'webhook' and not auto.get('webhook_token'):
                auto['webhook_token'] = self.generate_webhook_token()
            automations = self.load_automations()
            if any(item.get('id') == auto.get('id') for item in automations):
                raise ValueError('Automation id already exists')
            automations.append(auto)
            self.save_automations(automations)
        if self._scheduler and auto.get('enabled', True):
            self._schedule_auto(auto)

    def update_automation(self, aid: str, updates: dict) -> bool:
        with _scheduler_lock:
            automations = self.load_automations()
            for i, a in enumerate(automations):
                if a.get('id') == aid:
                    self._unschedule(aid)
                    updates = {key: value for key, value in updates.items() if key not in {'id', 'webhook_token'}}
                    automations[i].update(updates)
                    self.save_automations(automations)
                    if self._scheduler and automations[i].get('enabled', True):
                        self._schedule_auto(automations[i])
                    return True
        return False

    def delete_automation(self, aid: str):
        with _scheduler_lock:
            self._unschedule(aid)
            automations = self.load_automations()
            automations[:] = [a for a in automations if a.get('id') != aid]
            self.save_automations(automations)

    def _template(self, text: str, context: dict) -> str:
        def repl(m):
            key = m.group(1)
            val = context.get(key, '')
            if not isinstance(val, str):
                val = str(val)
            return val

        return re.sub(r'\{\{\s*(\w+(?:\.\w+)*)\s*\}\}', repl, text)

    def _resolve_params(self, params: dict, context: dict) -> dict:
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str):
                resolved[k] = self._template(v, context)
            elif isinstance(v, dict):
                resolved[k] = self._resolve_params(v, context)
            elif isinstance(v, list):
                resolved[k] = [self._template(item, context) if isinstance(item, str) else item for item in v]
            else:
                resolved[k] = v
        return resolved

    def execute_steps(self, steps: list, context: dict = None) -> list:
        if context is None:
            now = datetime.now()
            context = {
                'date': now.strftime('%Y-%m-%d'),
                'time': now.strftime('%H:%M'),
                'datetime': now.strftime('%Y-%m-%d %H:%M'),
                'hour': now.strftime('%H'),
                'minute': now.strftime('%M'),
                'weekday': now.strftime('%A'),
                'weekday_num': str(now.weekday()),
            }
        results = []
        env = dict(context)
        for step in steps:
            tool_name = step.get('tool', '')
            params = step.get('params', {})
            conditions = step.get('conditions', [])
            if conditions and not all(_validate_condition(c, env) for c in conditions):
                results.append({'step': tool_name, 'status': 'skipped', 'result': 'Bedingung nicht erf\u00fcllt'})
                continue
            resolved_params = self._resolve_params(params, env)
            if tool_name == 'ai_task':
                result, err = self._run_ai_step(resolved_params, results)
                if err:
                    results.append({'step': tool_name, 'status': 'error', 'result': err})
                    env[f'step_{len(results) - 1}'] = err
                    break
                results.append({'step': tool_name, 'status': 'success', 'result': _redact_result(result)})
                env[f'step_{len(results) - 1}'] = str(result)
                env[tool_name + '_result'] = str(result)
                continue
            if tool_name == 'notify':
                title = str(resolved_params.get('title', 'MYND Automation'))
                content = str(resolved_params.get('content', ''))
                self.add_notification(title, content)
                result = f'✅ Benachrichtigung gespeichert: {title}'
                results.append({'step': tool_name, 'status': 'success', 'result': result})
                env[f'step_{len(results) - 1}'] = result
                env[tool_name + '_result'] = result
                continue
            func = self.tool_map.get(tool_name)
            if not func:
                raise ValueError(f'Unbekanntes Tool: {tool_name}')
            try:
                result = func(**resolved_params)
                results.append({'step': tool_name, 'status': 'success', 'result': _redact_result(result)})
                env[f'step_{len(results) - 1}'] = str(result)
                env[tool_name + '_result'] = str(result)
            except Exception as e:
                err = f'\u274c {e}'
                results.append({'step': tool_name, 'status': 'error', 'result': err})
                env[f'step_{len(results) - 1}'] = err
                break
        return results

    def _run_ai_step(self, params, results):
        """Execute an 'ai_task' step: LLM summarizes/analyzes prior step results."""
        prompt = str(params.get('prompt', '')).strip()
        if not prompt:
            return None, '❌ ai_task braucht einen prompt'
        context_lines = [
            f'### Schritt {i + 1}: {r.get("step")}\n{r.get("result")}'
            for i, r in enumerate(results)
            if r.get('status') == 'success'
        ]
        if context_lines:
            prompt += '\n\nKontext aus vorherigen Schritten:\n' + '\n\n'.join(context_lines)
        language = str(params.get('language', 'de'))
        prompt += f'\n\nAntworte in {language}.'
        model = str(params.get('model', '')).strip() or self._default_model()
        try:
            from core.llm import chat_with_tools

            resp = chat_with_tools(model, [{'role': 'user', 'content': prompt}], [])
            content = (resp.get('message') or resp).get('content', '').strip()
            if not content:
                return None, '❌ LLM lieferte eine leere Antwort'
            return content, None
        except Exception as e:
            return None, f'❌ AI-Schritt fehlgeschlagen: {e}'

    @staticmethod
    def _default_model():
        try:
            from app.ollama_client import ollama_client

            return ollama_client.model
        except Exception:
            return ''

    def trigger_by_token(self, aid: str, token: str) -> dict:
        """Trigger an automation via its webhook secret token."""
        auto = self.get_automation(aid)
        if not auto:
            return {'success': False, 'error': 'Automation nicht gefunden'}
        if auto.get('trigger', {}).get('type') != 'webhook':
            return {'success': False, 'error': 'Automation hat keinen Webhook-Trigger'}
        if not auto.get('webhook_token') or not secrets.compare_digest(str(auto.get('webhook_token')), str(token)):
            return {'success': False, 'error': 'Ungültiges Webhook-Token'}
        if not auto.get('enabled', True):
            return {'success': False, 'error': 'Automation ist deaktiviert'}
        return self.run_automation(aid)

    def generate_webhook_token(self):
        import secrets

        return secrets.token_urlsafe(24)

    def run_automation(self, aid: str) -> dict:
        auto = self.get_automation(aid)
        if not auto:
            return {'success': False, 'error': 'Automation nicht gefunden'}
        try:
            results = self.execute_steps(auto.get('steps', []))
            success = all(r.get('status') == 'success' or r.get('status') == 'skipped' for r in results)
            log = {
                'id': aid,
                'name': auto.get('name', aid),
                'timestamp': datetime.now().isoformat(),
                'trigger': 'manual' if not threading.current_thread().name.startswith('APScheduler') else 'scheduled',
                'success': success,
                'steps': results,
            }
            with _scheduler_lock:
                history = self.load_history()
                history.append(log)
                if len(history) > 500:
                    history = history[-500:]
                self.save_history(history)
            if auto.get('notify', False):
                summary_lines = [
                    f'  {"✅" if r.get("status") == "success" else "⏭" if r.get("status") == "skipped" else "❌"} {r.get("step")}: {str(r.get("result", ""))[:200]}'
                    for r in results
                ]
                title = f'{"✅" if success else "⚠️"} Automation: {auto.get("name", aid)}'
                self.add_notification(title, '\n'.join(summary_lines))
            return {'success': True, 'results': results, 'log': log}
        except Exception as e:
            logger.exception(f'Automation {aid} fehlgeschlagen: {e}')
            return {'success': False, 'error': 'Automation execution failed'}

    def _schedule_auto(self, auto: dict):
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        aid = auto.get('id')
        trigger_cfg = auto.get('trigger', {})
        ttype = trigger_cfg.get('type', 'cron')

        if ttype == 'webhook':
            # Webhook automations run on demand via trigger_by_token(), not scheduled.
            logger.info(f"Automation '{auto.get('name', aid)}' läuft über Webhook (nicht geplant)")
            return
        if ttype == 'cron':
            trigger = CronTrigger(
                year=trigger_cfg.get('year'),
                month=trigger_cfg.get('month'),
                day=trigger_cfg.get('day'),
                week=trigger_cfg.get('week'),
                day_of_week=trigger_cfg.get('day_of_week'),
                hour=trigger_cfg.get('hour'),
                minute=trigger_cfg.get('minute'),
                second=trigger_cfg.get('second', '0'),
                timezone=trigger_cfg.get('timezone', 'Europe/Berlin'),
            )
        elif ttype == 'interval':
            trigger = IntervalTrigger(
                weeks=trigger_cfg.get('weeks', 0),
                days=trigger_cfg.get('days', 0),
                hours=trigger_cfg.get('hours', 0),
                minutes=trigger_cfg.get('minutes', 0),
                seconds=trigger_cfg.get('seconds', 0),
                timezone=trigger_cfg.get('timezone', 'Europe/Berlin'),
            )
        else:
            logger.warning(f'Unbekannter Trigger-Typ: {ttype}')
            return

        self._scheduler.add_job(
            self.run_automation,
            trigger=trigger,
            args=[aid],
            id=f'auto_{aid}',
            name=auto.get('name', aid),
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info(f"Automation '{auto.get('name', aid)}' eingeplant (Trigger: {ttype})")

    def _unschedule(self, aid: str):
        if self._scheduler and self._scheduler.get_job(f'auto_{aid}'):
            self._scheduler.remove_job(f'auto_{aid}')
            logger.info(f'Automation {aid} entfernt')

    def start(self):
        from apscheduler.schedulers.background import BackgroundScheduler

        if self._running:
            return
        self._running = True
        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.start()
        self.reload_all()

    def stop(self):
        self._running = False
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def reload_all(self):
        if self._scheduler:
            for job in list(self._scheduler.get_jobs()):
                if job.id.startswith('auto_'):
                    job.remove()
        for auto in self.load_automations():
            if auto.get('enabled', True):
                try:
                    self._schedule_auto(auto)
                except Exception as e:
                    logger.warning(f"Fehler beim Planen von '{auto.get('name', auto.get('id'))}': {e}")
