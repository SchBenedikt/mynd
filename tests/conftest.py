import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory with a minimal vault for testing."""
    tmp = Path(tempfile.mkdtemp())
    vault = tmp / "vault.json"
    vault.write_text(json.dumps({
        "test/key": "test_value",
        "immich/url": "http://immich.local:2283",
        "immich/api_key": "test_key_123",
        "homeassistant/url": "http://ha.local:8123",
        "homeassistant/token": "test_ha_token",
    }))
    # Patch Path in plugins that use VAULT_FILE
    yield tmp
    shutil.rmtree(tmp)


@pytest.fixture
def sample_timers():
    """Return a sample timer list for testing."""
    import time
    now = time.time()
    return [
        {"id": "abc123", "label": "Test Timer", "expiry": now + 60,
         "duration": "1m", "created": "2026-07-09T10:00:00",
         "expired": False, "notified": False},
        {"id": "def456", "label": "Expired Timer", "expiry": now - 60,
         "duration": "1m", "created": "2026-07-09T09:58:00",
         "expired": True, "notified": True},
    ]
