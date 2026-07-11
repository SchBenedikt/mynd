import requests as _requests
import numpy as np
from .config import OLLAMA

def embed(texts, model="bge-m3:latest"):
    try:
        r = _requests.post(f"{OLLAMA}/api/embed", json={"model": model, "input": texts}, timeout=120)
        return np.array(r.json()["embeddings"], dtype=np.float32)
    except:
        out = []
        for t in texts:
            r = _requests.post(f"{OLLAMA}/api/embed", json={"model": model, "input": [t]}, timeout=120)
            out.append(r.json()["embeddings"][0])
        return np.array(out, dtype=np.float32)
