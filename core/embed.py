import json
import os
from pathlib import Path

import numpy as np
import requests as _requests

from .config import OLLAMA


def _request_embeddings(texts, model):
    base_url = OLLAMA
    config_file = Path(__file__).resolve().parents[1] / 'data' / 'ai_config.json'
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
            if config.get('provider') == 'ollama' and config.get('base_url'):
                base_url = str(config['base_url']).rstrip('/')
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
    response = _requests.post(f'{base_url}/api/embed', json={'model': model, 'input': texts}, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if 'embeddings' not in payload:
        raise ValueError('Ollama response does not contain embeddings')
    return payload['embeddings']


def embed(texts, model=None):
    """Embed texts in one request, with a compatibility fallback for old Ollama versions.
    Model defaults to EMBEDDING_MODEL env var, then 'nomic-embed-text'."""
    if model is None:
        model = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
    try:
        return np.asarray(_request_embeddings(texts, model), dtype=np.float32)
    except (_requests.RequestException, KeyError, TypeError, ValueError):
        embeddings = [_request_embeddings([text], model)[0] for text in texts]
        return np.asarray(embeddings, dtype=np.float32)
