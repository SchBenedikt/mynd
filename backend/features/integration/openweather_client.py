"""
OpenWeather One Call 3.0 API Client
Provides current weather, forecast, and weather alerts by coordinates.
"""

import logging
from typing import Dict, Any, Optional

import requests

from .api_registry import APIClient


class OpenWeatherClient(APIClient):
    """Client for OpenWeather One Call 3.0 API."""

    DEFAULT_BASE_URL = "https://api.openweathermap.org/data/3.0"

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.base_url = (config.get('base_url') or self.DEFAULT_BASE_URL).rstrip('/')
        self.api_key = str(config.get('api_key') or '').strip()
        self.timeout = int(config.get('timeout', 10))
        self.units = str(config.get('units') or 'metric').strip() or 'metric'
        self.lang = str(config.get('lang') or 'de').strip() or 'de'

        self.latitude = self._to_float(config.get('lat'))
        self.longitude = self._to_float(config.get('lon'))
        self.location_name = str(config.get('location_name') or '').strip()

    @classmethod
    def requires_config(cls) -> bool:
        return True

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            'base_url': cls.DEFAULT_BASE_URL,
            'api_key': '',
            'timeout': 10,
            'units': 'metric',
            'lang': 'de',
            'lat': '',
            'lon': '',
            'location_name': ''
        }

    def get_api_name(self) -> str:
        return 'openweather'

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'api_key': {
                'type': 'string',
                'required': True,
                'secret': True,
                'description': 'OpenWeather API Key',
                'example': 'dein-openweather-key'
            },
            'lat': {
                'type': 'string',
                'required': False,
                'description': 'Standard-Breitengrad fuer lokalen Wetterabruf',
                'example': '49.8728'
            },
            'lon': {
                'type': 'string',
                'required': False,
                'description': 'Standard-Laengengrad fuer lokalen Wetterabruf',
                'example': '8.6512'
            },
            'location_name': {
                'type': 'string',
                'required': False,
                'description': 'Optionaler Name des Standorts',
                'example': 'Darmstadt'
            },
            'units': {
                'type': 'string',
                'required': False,
                'description': 'Einheiten (metric, imperial, standard)',
                'default': 'metric',
                'example': 'metric'
            },
            'lang': {
                'type': 'string',
                'required': False,
                'description': 'Sprache fuer Wetterbeschreibungen',
                'default': 'de',
                'example': 'de'
            },
            'base_url': {
                'type': 'string',
                'required': False,
                'description': 'OpenWeather API base URL',
                'default': self.DEFAULT_BASE_URL,
                'example': self.DEFAULT_BASE_URL
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'description': 'Request timeout in seconds',
                'default': 10
            }
        }

    def test_connection(self) -> bool:
        if not self.api_key:
            return False

        lat = self.latitude if self.latitude is not None else 52.52
        lon = self.longitude if self.longitude is not None else 13.405

        try:
            data = self.get_current_and_forecast(lat=lat, lon=lon, exclude='minutely,hourly,daily,alerts')
            return bool(data and isinstance(data, dict) and data.get('current'))
        except requests.exceptions.RequestException as exc:
            self.logger.error('OpenWeather connection failed: %s', exc)
            return False
        except Exception as exc:
            self.logger.error('OpenWeather connection error: %s', exc)
            return False

    def get_current_and_forecast(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        exclude: Optional[str] = None,
        units: Optional[str] = None,
        lang: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError('OpenWeather api_key is required')

        latitude, longitude = self._resolve_coordinates(lat, lon)

        params = {
            'lat': latitude,
            'lon': longitude,
            'appid': self.api_key,
            'units': units or self.units,
            'lang': lang or self.lang
        }
        if exclude:
            params['exclude'] = exclude

        response = requests.get(
            f"{self.base_url}/onecall",
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def get_alerts_only(self, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
        return self.get_current_and_forecast(
            lat=lat,
            lon=lon,
            exclude='current,minutely,hourly,daily'
        )

    def _resolve_coordinates(self, lat: Optional[float], lon: Optional[float]) -> tuple[float, float]:
        latitude = lat if lat is not None else self.latitude
        longitude = lon if lon is not None else self.longitude

        if latitude is None or longitude is None:
            raise ValueError('OpenWeather lat/lon are required (configure them in settings or pass query params)')

        return float(latitude), float(longitude)

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
