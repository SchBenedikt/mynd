"""
Autobahn App API Client
Public API for roadworks, warnings, and services.
"""

import logging
from typing import Dict, Any, Optional
import requests
from .api_registry import APIClient


class AutobahnClient(APIClient):
    """Client for the Autobahn API"""

    DEFAULT_BASE_URL = "https://verkehr.autobahn.de/o/autobahn"

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
        return "autobahn"

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'base_url': {
                'type': 'string',
                'required': False,
                'description': 'Autobahn API base URL',
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
                f"{self.base_url}/",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True
            self.logger.error("Autobahn connection failed: %s", response.status_code)
            return False
        except requests.exceptions.Timeout:
            self.logger.error("Autobahn connection timeout")
            return False
        except Exception as exc:
            self.logger.error("Autobahn connection error: %s", exc)
            return False

    def list_roads(self) -> Dict[str, Any]:
        return self._get_json("/")

    def get_road_services(self, road_id: str, service: str) -> Dict[str, Any]:
        return self._get_json(f"/{road_id}/services/{service}")

    def get_roadwork_details(self, roadwork_id: str) -> Dict[str, Any]:
        return self._get_json(f"/details/roadworks/{roadwork_id}")

    def get_webcam_details(self, webcam_id: str) -> Dict[str, Any]:
        return self._get_json(f"/details/webcam/{webcam_id}")

    def get_parking_details(self, lorry_id: str) -> Dict[str, Any]:
        return self._get_json(f"/details/parking_lorry/{lorry_id}")

    def get_warning_details(self, warning_id: str) -> Dict[str, Any]:
        return self._get_json(f"/details/warning/{warning_id}")

    def get_closure_details(self, closure_id: str) -> Dict[str, Any]:
        return self._get_json(f"/details/closure/{closure_id}")

    def get_charging_station_details(self, station_id: str) -> Dict[str, Any]:
        return self._get_json(f"/details/electric_charging_station/{station_id}")

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
