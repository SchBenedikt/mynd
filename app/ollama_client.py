import json
import os

import requests

from app.config import AI_CONFIG_FILE, logger
from core.vault import vault_get as _vg
from core.vault import vault_set as _vs


class OllamaClient:
    def __init__(self, base_url=None, model=None):
        self.base_url = (base_url or os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')).rstrip('/')
        self.model = model or os.getenv('OLLAMA_MODEL', 'gemma3:latest')

    def update_config(self, base_url, model):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def chat(self, messages, context=None):
        q = ''
        for m in (messages or []):
            if m.get('role') == 'user':
                q = m.get('content', '')
                break

        system_prompt = "You are a helpful AI assistant. Reply in the language requested by the user."

        if context:
            ctx_text = '\n\n'.join([
                f"[{c.get('source', 'Quelle')}]\n{c.get('content', '')}" for c in context
            ])
            system_prompt = (
                "You are a helpful AI assistant with access to the following information.\n"
                "Answer in the user's language, use the context, and cite sources.\n\n"
                f"=== CONTEXT ===\n{ctx_text}"
            )

        msgs = [{"role": "system", "content": system_prompt}]
        for m in (messages or []):
            msgs.append(m)

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": msgs,
            "stream": False,
            "options": {"temperature": 0.1, "max_tokens": 2048}
        }

        try:
            resp = requests.post(url, json=payload, timeout=120)
            if resp.status_code == 404:
                gen_url = f"{self.base_url}/api/generate"
                gen_payload = {"model": self.model, "prompt": q, "stream": False}
                gr = requests.post(gen_url, json=gen_payload, timeout=120)
                gr.raise_for_status()
                gd = gr.json()
                return {"message": {"role": "assistant", "content": gd.get("response", "")}}
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.warning('Ollama connection failed: %s', e)
            return {"error": "Model provider unavailable"}

    def check_connection(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=8)
            r.raise_for_status()
            return sorted(set(m['name'] for m in r.json().get('models', [])))
        except Exception:
            return []


ollama_client = OllamaClient()


def load_ai_config():
    cfg = {
        'provider': 'ollama',
        'base_url': os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/'),
        'model': os.getenv('OLLAMA_MODEL', 'gemma3:latest'),
        'embedding_model': os.getenv('EMBEDDING_MODEL', 'nomic-embed-text'),
        'api_key': ''
    }
    if AI_CONFIG_FILE.exists():
        try:
            fc = json.loads(AI_CONFIG_FILE.read_text())
            cfg['provider'] = str(fc.get('provider', cfg['provider']))
            cfg['base_url'] = str(fc.get('base_url', cfg['base_url'])).rstrip('/')
            cfg['model'] = str(fc.get('model', cfg['model']))
            cfg['embedding_model'] = str(fc.get('embedding_model', cfg['embedding_model']))
            stored_key = str(fc.get('api_key', ''))
            if stored_key and stored_key != '***':
                cfg['api_key'] = stored_key
            elif stored_key == '***':
                cfg['api_key'] = _vg('ai/api_key') or ''
        except Exception:
            pass
    if cfg['provider'] == 'ollama':
        ollama_client.update_config(cfg['base_url'], cfg['model'])
    return cfg


def save_ai_config(provider, base_url, model, api_key='', embedding_model=None):
    cfg = {
        'provider': provider or 'ollama',
        'base_url': base_url.rstrip('/'),
        'model': model,
        'embedding_model': embedding_model or os.getenv('EMBEDDING_MODEL', 'nomic-embed-text'),
        'api_key': api_key or ''
    }
    if cfg.get('api_key'):
        _vs('ai/api_key', cfg['api_key'])
    display_cfg = {**cfg}
    if display_cfg.get('api_key'):
        display_cfg['api_key'] = '***'
    AI_CONFIG_FILE.write_text(json.dumps(display_cfg, indent=2, ensure_ascii=False))
    if cfg['provider'] == 'ollama':
        ollama_client.update_config(cfg['base_url'], cfg['model'])


load_ai_config()
