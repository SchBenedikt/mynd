import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent
STATE = BASE / 'data' / 'state.json'
CHUNKS = BASE / 'data' / 'chunks.json'
EMBS = BASE / 'data' / 'embeddings.npy'
VAULT_FILE = BASE / 'data' / 'vault.json'
MEMORY_FILE = BASE / 'data' / 'memory.json'
PLUGIN_DIR = BASE / 'data' / 'plugins'
PLUGIN_STATE = BASE / 'data' / 'plugins' / 'plugin_state.json'

OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")

LLM_BLACKLIST = {"bge-m3", "nomic-embed-text", "snowflake-arctic-embed", "mxbai-embed"}

try:
    from rich.console import Console
    CON = Console()
    RICH = True
except ImportError:
    CON = None
    RICH = False

C = type('C', (), {
    'CYAN': '\033[96m', 'GREEN': '\033[92m', 'YELLOW': '\033[93m',
    'RED': '\033[91m', 'BOLD': '\033[1m', 'DIM': '\033[2m', 'RESET': '\033[0m'
})()

def _openai_cfg():
    ob = os.environ.get("OPENAI_BASE_URL", "").rstrip('/')
    ok = os.environ.get("OPENAI_API_KEY", "")
    oms = [m.strip() for m in os.environ.get("OPENAI_MODELS", "").split(",") if m.strip()]
    return ob, ok, oms

def _openai_prefixes():
    raw = os.environ.get("OPENAI_MODEL_PREFIXES", "gpt-,o1-,o3-,claude-,gemini-,minimax-")
    return [p.strip() for p in raw.split(",") if p.strip()]

def _is_openai(model):
    ob, ok, oms = _openai_cfg()
    return ob and (model in oms or any(model.startswith(p) for p in _openai_prefixes()))
