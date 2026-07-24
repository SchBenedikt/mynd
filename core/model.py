import json
import os
import sys

import requests

from .config import BASE, LLM_BLACKLIST, OLLAMA, RICH, C, _is_openai, _openai_cfg

_PROMPT = None
if RICH:
    from rich.prompt import Prompt as _RichPrompt
    _PROMPT = _RichPrompt


def _no_tool_keywords():
    raw = os.getenv('NO_TOOL_MODEL_KEYWORDS', 'phi,tinyllama')
    return [k.strip().lower() for k in raw.split(',') if k.strip()]


def _openai_provider_cfg():
    """Read OpenAI provider config from ai_config.json, fall back to env vars."""
    ai_cfg_file = BASE / 'data' / 'ai_config.json'
    if ai_cfg_file.exists():
        try:
            fc = json.loads(ai_cfg_file.read_text())
            if fc.get('provider') == 'openai':
                key = str(fc.get('api_key', ''))
                if key == '***':
                    from core.vault import vault_get as _vg
                    key = _vg('ai/api_key') or ''
                return str(fc.get('base_url', '')).rstrip('/').removesuffix('/v1'), key
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
    ob, ok, _ = _openai_cfg()
    return ob.removesuffix('/v1'), ok

def check_tool_support(model, base_url=None):
    model_lower = model.lower()
    if any(k in model_lower for k in _no_tool_keywords()):
        return False
    try:
        url = (base_url or OLLAMA).rstrip('/')
        if _is_openai(model):
            ob, ok = _openai_provider_cfg()
            body = {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            }
            r = requests.post(
                f"{ob}/v1/chat/completions", json=body,
                headers={"Authorization": f"Bearer {ok}", "Content-Type": "application/json"},
                timeout=15,
            )
            data = r.json()
            if "error" in data:
                return False
            # OpenAI-kompatible Endpunkte unterstützen Tools immer
            return True
        r = requests.post(f"{url}/api/chat", json={
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        }, timeout=15)
        data = r.json()
        if "error" in data:
            return False
        return True
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return False


def select_model(force=None):
    raw = []
    try:
        r = requests.get(f"{OLLAMA}/api/tags", timeout=5)
        raw = [
            m["name"] for m in r.json().get("models", [])
            if not any(b in m["name"] for b in LLM_BLACKLIST)
        ]
    except (requests.RequestException, KeyError, TypeError, ValueError):
        pass

    _, _, openai_models = _openai_cfg()
    openai_list = [f"🌐 {m}" for m in openai_models] if openai_models else []

    if not raw and not openai_list:
        print(f"  {C.RED}❌ Kein LLM-Modell verfügbar{C.RESET}")
        sys.exit(1)

    print(f"  {C.DIM}Prüfe Tool-Support...{C.RESET}", end='', flush=True)
    models = []
    for m in raw:
        ok = check_tool_support(m)
        models.append((m, ok))
        print(f" {C.GREEN if ok else C.RED}{'✓' if ok else '✗'}{C.RESET}", end='', flush=True)
    for m in openai_list:
        ok = check_tool_support(m.removeprefix('🌐 '))
        models.append((m, ok))
        print(f" {C.GREEN if ok else C.RED}{'✓' if ok else '✗'}{C.RESET}", end='', flush=True)
    print()

    if force:
        for m, ok in models:
            clean = m.removeprefix('🌐 ')
            if (m == force or clean == force) and ok:
                return clean
        if force in [m for m, _ in models] or force in [m.removeprefix('🌐 ') for m, _ in models]:
            print(f"  {C.YELLOW}⚠️  {force} hat keine Tool-Unterstützung – wähle anderes{C.RESET}")
        else:
            print(f"  {C.YELLOW}⚠️  {force} nicht gefunden – zeige Auswahl{C.RESET}")

    tool_models = [m for m, ok in models if ok]
    if not tool_models:
        print(f"  {C.RED}❌ Kein Modell unterstützt Tools.{C.RESET}")
        print(f"  {C.YELLOW}Tip: 'ollama pull gemma3:12b' oder 'ollama pull llama3.1'{C.RESET}")
        sys.exit(1)

    if len(tool_models) == 1:
        print(f"  {C.GREEN}🧠 {tool_models[0]}{C.RESET}")
        return tool_models[0].removeprefix('🌐 ')

    print(f"\n  {C.CYAN}{C.BOLD}🤖 Verfügbare Modelle:{C.RESET}")
    for i, (m, ok) in enumerate(models, 1):
        tag = f" {C.GREEN}✓ Tools{C.RESET}" if ok else f" {C.RED}✗ kein Tool-Support{C.RESET}"
        print(f"    {C.CYAN}{i}{C.RESET}. {m}{tag}")
    print()
    try:
        choice = int(
            (_PROMPT.ask(f"{C.BOLD}Modell wählen{C.RESET}", default="1") if RICH
             else input(f"  {C.BOLD}Modell (1-{len(models)}){C.RESET}: "))
            .strip() or "1"
        )
        m, ok = models[max(0, min(choice, len(models)) - 1)]
        if not ok:
            print(f"  {C.YELLOW}⚠️  {m} hat keine Tools – Chat ohne Tool-Zugriff{C.RESET}")
        return m.removeprefix('🌐 ')
    except (ValueError, EOFError):
        return tool_models[0].removeprefix('🌐 ')
