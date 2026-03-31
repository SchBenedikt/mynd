"""
Deutscher Wetterdienst (DWD) API Client
Public API for weather warnings and station data.
"""

import logging
from typing import Dict, Any, List, Optional
import requests
from .api_registry import APIClient


class DWDClient(APIClient):
    """Client for the DWD public API"""

    DEFAULT_BASE_URL = "https://dwd.api.proxy.bund.dev/v30"

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
        return "dwd"

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'base_url': {
                'type': 'string',
                'required': False,
                'description': 'DWD API base URL',
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
                f"{self.base_url}/stationOverviewExtended",
                params={'stationIds': 'G005'},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True
            self.logger.error("DWD connection failed: %s", response.status_code)
            return False
        except requests.exceptions.Timeout:
            self.logger.error("DWD connection timeout")
            return False
        except Exception as exc:
            self.logger.error("DWD connection error: %s", exc)
            return False

    def get_station_overview_extended(self, station_ids: List[str]) -> Dict[str, Any]:
        params = {'stationIds': ','.join(station_ids)}
        return self._get_json("/stationOverviewExtended", params=params)

    def get_crowd_meldungen(self) -> Dict[str, Any]:
        return self._get_json("/crowd_meldungen_overview_v2.json")

    def get_warnings_nowcast(self, language: str = 'de') -> Dict[str, Any]:
        path = "/warnings_nowcast_en.json" if language == 'en' else "/warnings_nowcast.json"
        return self._get_json(path)

    def get_gemeinde_warnings(self, language: str = 'de') -> Dict[str, Any]:
        path = "/gemeinde_warnings_v2_en.json" if language == 'en' else "/gemeinde_warnings_v2.json"
        return self._get_json(path)

    def get_coast_warnings(self, language: str = 'de') -> Dict[str, Any]:
        path = "/warnings_coast_en.json" if language == 'en' else "/warnings_coast.json"
        return self._get_json(path)

    def get_sea_warning_text(self) -> Dict[str, Any]:
        return self._get_json("/sea_warning_text.json")

    def get_alpen_forecast_text(self) -> Dict[str, Any]:
        return self._get_json("/alpen_forecast_text_dwms.json")

    def get_lawine_warnings(self) -> Dict[str, Any]:
        return self._get_json("/warnings_lawine.json")

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
