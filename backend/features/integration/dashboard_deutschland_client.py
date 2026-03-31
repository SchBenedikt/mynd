"""
Dashboard Deutschland API Client
Public API for indicators and dashboard data.
"""

import logging
from typing import Dict, Any, List, Optional
import requests
from .api_registry import APIClient


class DashboardDeutschlandClient(APIClient):
    """Client for the Dashboard Deutschland API"""

    DEFAULT_BASE_URL = "https://www.dashboard-deutschland.de"

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.base_url = (config.get('base_url') or self.DEFAULT_BASE_URL).rstrip('/')
        self.timeout = int(config.get('timeout', 10))

    @classmethod
    def requires_config(cls) -> bool:
        return False

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            'base_url': cls.DEFAULT_BASE_URL,
            'timeout': 10
        }

    def get_api_name(self) -> str:
        return "dashboard_deutschland"

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'base_url': {
                'type': 'string',
                'required': False,
                'description': 'Dashboard Deutschland base URL',
                'example': self.DEFAULT_BASE_URL,
                'default': self.DEFAULT_BASE_URL
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'description': 'Request timeout in seconds',
                'default': 10
            }
        }

    def test_connection(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}/api/dashboard/get",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True
            self.logger.error("Dashboard Deutschland connection failed: %s", response.status_code)
            return False
        except requests.exceptions.Timeout:
            self.logger.error("Dashboard Deutschland connection timeout")
            return False
        except Exception as exc:
            self.logger.error("Dashboard Deutschland connection error: %s", exc)
            return False

    def get_dashboard_entries(self) -> Dict[str, Any]:
        return self._get_json("/api/dashboard/get")

    def get_indicators(self, ids: List[str]) -> Dict[str, Any]:
        params = {'ids': ','.join(ids)}
        return self._get_json("/api/tile/indicators", params=params)

    def get_geojson(self) -> Dict[str, Any]:
        return self._get_json("/geojson/de-all.geo.json")

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
