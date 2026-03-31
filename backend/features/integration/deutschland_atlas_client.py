"""
Deutschland Atlas API Client
Public API for map services hosted on karto365.
"""

import logging
from typing import Dict, Any, List, Optional
import requests
from .api_registry import APIClient


class DeutschlandAtlasClient(APIClient):
    """Client for the Deutschland Atlas API"""

    DEFAULT_BASE_URL = "https://www.karto365.de/hosting/rest/services"
    DEFAULT_SERVICES = [
        "Basemap_light",
        "erw_mini_HA2023",
        "pendel_b_HA2023",
        "p_nelade_r_HA2023"
    ]

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.base_url = (config.get('base_url') or self.DEFAULT_BASE_URL).rstrip('/')
        self.timeout = int(config.get('timeout', 10))
        self.services = config.get('services') or list(self.DEFAULT_SERVICES)

    @classmethod
    def requires_config(cls) -> bool:
        return False

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            'base_url': cls.DEFAULT_BASE_URL,
            'timeout': 10,
            'services': ','.join(cls.DEFAULT_SERVICES)
        }

    def get_api_name(self) -> str:
        return "deutschland_atlas"

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'base_url': {
                'type': 'string',
                'required': False,
                'description': 'Deutschland Atlas base URL',
                'example': self.DEFAULT_BASE_URL,
                'default': self.DEFAULT_BASE_URL
            },
            'services': {
                'type': 'string',
                'required': False,
                'description': 'Comma-separated service names to query',
                'example': ','.join(self.DEFAULT_SERVICES),
                'default': ','.join(self.DEFAULT_SERVICES)
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
            service = self._get_first_service()
            response = requests.get(
                f"{self.base_url}/{service}/MapServer",
                params={'f': 'json'},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True
            self.logger.error("Deutschland Atlas connection failed: %s", response.status_code)
            return False
        except requests.exceptions.Timeout:
            self.logger.error("Deutschland Atlas connection timeout")
            return False
        except Exception as exc:
            self.logger.error("Deutschland Atlas connection error: %s", exc)
            return False

    def list_services(self) -> List[str]:
        if isinstance(self.services, str):
            return [entry.strip() for entry in self.services.split(',') if entry.strip()]
        return list(self.services)

    def get_service_info(self, service_name: str) -> Dict[str, Any]:
        return self._get_json(f"/{service_name}/MapServer", params={'f': 'json'})

    def get_layer_info(self, service_name: str, layer_id: int) -> Dict[str, Any]:
        return self._get_json(f"/{service_name}/MapServer/{layer_id}", params={'f': 'json'})

    def _get_first_service(self) -> str:
        if isinstance(self.services, str):
            services = [entry.strip() for entry in self.services.split(',') if entry.strip()]
            if services:
                return services[0]
            return self.DEFAULT_SERVICES[0]
        if self.services:
            return self.services[0]
        return self.DEFAULT_SERVICES[0]

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
