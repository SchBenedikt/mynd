import json
import re
import threading
from datetime import datetime
from pathlib import Path

_SKILLS_FILE = None
_skills_lock = threading.Lock()
_cache = None
_dirty = False
_flush_counter = 0
_FLUSH_INTERVAL = 5


def _get_skills_file():
    global _SKILLS_FILE
    if _SKILLS_FILE is None:
        data_dir = Path(__file__).resolve().parent.parent / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        _SKILLS_FILE = data_dir / 'skills.json'
    return _SKILLS_FILE


def _load():
    global _cache
    if _cache is not None:
        return _cache
    path = _get_skills_file()
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
        path = _get_skills_file()
        path.write_text(json.dumps(_cache, indent=2, ensure_ascii=False))
        _dirty = False


def learn_skill(name, description, pattern, tags=None, context=''):
    if not name or not description:
        return '❌ Name und Beschreibung sind erforderlich.'
    if not isinstance(pattern, list):
        return '❌ Pattern muss eine Liste von Tool-Schritten sein.'
    with _skills_lock:
        skills = _load()
        if tags is None:
            tags = _auto_extract_tags(description)
        skills[name] = {
            'name': name,
            'description': description[:500],
            'pattern': pattern[:20],
            'tags': list(set(tags))[:10],
            'context': context[:500],
            'created': datetime.now().isoformat(),
            'used_count': 0,
        }
        _dirty = True
        _maybe_flush()
        return f'✅ Skill "{name}" gelernt ({len(pattern)} Schritte, Tags: {", ".join(tags[:5])})'


def recall_skills(context, max_results=5):
    if not context:
        return []
    with _skills_lock:
        skills = _load()
    if not skills:
        return []
    query_lower = context.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    scored = []
    for name, skill in skills.items():
        score = 0
        text = f'{name} {skill.get("description", "")} {skill.get("context", "")} {" ".join(skill.get("tags", []))}'.lower()
        text_words = set(re.findall(r'\w+', text))
        common = query_words & text_words
        score += len(common) * 2
        for tag in skill.get('tags', []):
            if tag.lower() in query_lower:
                score += 5
        if name.lower() in query_lower:
            score += 10
        score += skill.get('used_count', 0) * 0.5
        if score > 0:
            scored.append((score, name, skill))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, name, skill in scored[:max_results]:
        results.append(
            {
                'name': name,
                'description': skill.get('description', ''),
                'tags': skill.get('tags', []),
                'pattern': skill.get('pattern', []),
                'context': skill.get('context', ''),
                'relevance': score,
                'used_count': skill.get('used_count', 0),
            }
        )
    return results


def skill_list(tag=''):
    with _skills_lock:
        skills = _load()
    if not skills:
        return []
    result = []
    for name, skill in sorted(skills.items()):
        if tag and tag not in skill.get('tags', []):
            continue
        result.append(
            {
                'name': name,
                'description': skill.get('description', '')[:200],
                'tags': skill.get('tags', []),
                'step_count': len(skill.get('pattern', [])),
                'used_count': skill.get('used_count', 0),
                'created': skill.get('created', ''),
            }
        )
    return result


def skill_delete(name):
    with _skills_lock:
        skills = _load()
        if name in skills:
            del skills[name]
            _dirty = True
            _maybe_flush()
            return f'🗑 Skill "{name}" gelöscht.'
        return f'❌ Skill "{name}" nicht gefunden.'


def use_skill(name):
    with _skills_lock:
        skills = _load()
        if name not in skills:
            return None
        skills[name]['used_count'] = skills[name].get('used_count', 0) + 1
        _dirty = True
        _maybe_flush()
        return skills[name]['pattern']


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


def _auto_extract_tags(text):
    common_tags = {
        'nextcloud',
        'calendar',
        'tasks',
        'contacts',
        'files',
        'email',
        'immich',
        'foto',
        'photos',
        'homeassistant',
        'smart home',
        'automation',
        'truenas',
        'nas',
        'server',
        'ssh',
        'docker',
        'search',
        'web',
        'news',
        'document',
        'calendar',
        'termin',
        'event',
        'monitoring',
        'backup',
        'config',
        'python',
        'bash',
        'script',
        'vault',
        'memory',
        'knowledge',
    }
    found = set()
    text_lower = text.lower()
    for tag in common_tags:
        if tag in text_lower:
            found.add(tag)
    return sorted(found)
