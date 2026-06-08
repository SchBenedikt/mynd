"""
Simple per-user Nextcloud accounts storage.
Stores accounts in backend/config/nextcloud_accounts.json as a dict keyed by username.
"""
import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')), 'backend', 'config')
ACCOUNTS_FILE = os.path.join(CONFIG_PATH, 'nextcloud_accounts.json')


def _ensure_config_dir():
    os.makedirs(CONFIG_PATH, exist_ok=True)


def load_accounts() -> Dict[str, Any]:
    _ensure_config_dir()
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception as e:
        logger.error(f"Error loading nextcloud accounts: {e}")
        return {}


def save_accounts(accounts: Dict[str, Any]) -> None:
    _ensure_config_dir()
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        logger.info("Nextcloud accounts saved")
    except Exception as e:
        logger.error(f"Error saving nextcloud accounts: {e}")


def save_account(username: str, config: Dict[str, Any]) -> None:
    if not username:
        logger.error("save_account: username required")
        return
    accounts = load_accounts()
    accounts[str(username)] = config
    save_accounts(accounts)


def get_account(username: str) -> Optional[Dict[str, Any]]:
    if not username:
        return None
    accounts = load_accounts()
    return accounts.get(str(username))


def list_accounts() -> Dict[str, Any]:
    return load_accounts()


def remove_account(username: str) -> bool:
    accounts = load_accounts()
    if username in accounts:
        del accounts[username]
        save_accounts(accounts)
        return True
    return False
