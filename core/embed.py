import numpy as np
import requests as _requests

from .config import OLLAMA


def _request_embeddings(texts, model):
    response = _requests.post(
        f"{OLLAMA}/api/embed", json={"model": model, "input": texts}, timeout=120
    )
    response.raise_for_status()
    payload = response.json()
    if "embeddings" not in payload:
        raise ValueError("Ollama response does not contain embeddings")
    return payload["embeddings"]


def embed(texts, model="bge-m3:latest"):
    """Embed texts in one request, with a compatibility fallback for old Ollama versions."""
    try:
        return np.asarray(_request_embeddings(texts, model), dtype=np.float32)
    except (_requests.RequestException, KeyError, TypeError, ValueError):
        embeddings = [_request_embeddings([text], model)[0] for text in texts]
        return np.asarray(embeddings, dtype=np.float32)
