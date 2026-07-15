import logging
import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

from core.config import CHUNKS as CHUNKS
from core.config import EMBS as EMBS

load_dotenv()

_app_lock = threading.Lock()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
FRONTEND_DIR = BASE_DIR / 'frontend'
STATIC_EXPORT_DIR = FRONTEND_DIR / 'out'
AI_CONFIG_FILE = DATA_DIR / 'ai_config.json'
GENERATED_DIR = DATA_DIR / 'generated'
SETUP_DONE_FILE = DATA_DIR / 'setup_done.json'
AUTH_CONFIG_FILE = DATA_DIR / 'auth_config.json'
AUTH_FILE = DATA_DIR / 'auth_users.json'
MEMORY_FILE = DATA_DIR / 'memory.json'
VAULT_FILE = DATA_DIR / 'vault.json'
API_REFS_PATH = DATA_DIR / 'api_refs.json'
SECURITY_MODE_FILE = DATA_DIR / 'security_mode.json'
BROWSER_SCREENSHOTS_DIR = DATA_DIR / 'browser_screenshots'
UPLOAD_DIR = DATA_DIR / 'uploads'

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(BROWSER_SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(BASE_DIR))
