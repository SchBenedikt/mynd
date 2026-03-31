"""
Deutscher Wetterdienst (DWD) API Client
Public API for weather warnings and station data.
"""

import logging
import math
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
        self.station_ids = self._normalize_station_ids(config.get('station_ids'))

    @classmethod
    def requires_config(cls) -> bool:
        return False

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            'base_url': cls.DEFAULT_BASE_URL,
            'timeout': 10,
            'station_ids': ''
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
            },
            'station_ids': {
                'type': 'string',
                'required': False,
                'description': 'Default station IDs (comma separated) for local weather',
                'example': 'G005, P003'
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

    def get_station_overview_extended(self, station_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if station_ids:
            params = {'stationIds': ','.join(station_ids)}
            return self._get_json("/stationOverviewExtended", params=params)
        return self._get_json("/stationOverviewExtended")

    def find_nearest_station(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        if not self.station_ids:
            # The DWD proxy requires stationIds. Without configured IDs we cannot compute a nearest station.
            return None

        data = self.get_station_overview_extended(self.station_ids)
        stations = self._extract_stations(data)
        if not stations:
            return None

        closest = None
        closest_distance = None
        for station in stations:
            lat = station.get('latitude')
            lon = station.get('longitude')
            if lat is None or lon is None:
                continue

            distance = self._haversine_km(latitude, longitude, lat, lon)
            if closest_distance is None or distance < closest_distance:
                closest_distance = distance
                closest = station

        if closest is None:
            return None

        if closest_distance is None:
            return None

        closest = dict(closest)
        closest['distance_km'] = round(float(closest_distance), 2)
        return closest

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

    def _normalize_station_ids(self, station_ids: Any) -> List[str]:
        if not station_ids:
            return []
        if isinstance(station_ids, str):
            return [entry.strip() for entry in station_ids.split(',') if entry.strip()]
        if isinstance(station_ids, list):
            return [str(entry).strip() for entry in station_ids if str(entry).strip()]
        return []

    def _extract_stations(self, payload: Any) -> List[Dict[str, Any]]:
        stations = []
        if not payload:
            return stations

        if isinstance(payload, dict):
            if isinstance(payload.get('stationOverview'), dict):
                for station_id, data in payload['stationOverview'].items():
                    station = self._normalize_station_entry(station_id, data)
                    if station:
                        stations.append(station)
                return stations

            if isinstance(payload.get('stations'), list):
                for data in payload['stations']:
                    station = self._normalize_station_entry(data.get('id') or data.get('stationId'), data)
                    if station:
                        stations.append(station)
                return stations

            if isinstance(payload.get('data'), dict):
                return self._extract_stations(payload['data'])

        return stations

    def _normalize_station_entry(self, station_id: Any, data: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict):
            return None
        lat = data.get('latitude') or data.get('lat')
        lon = data.get('longitude') or data.get('lon')
        if lat is None or lon is None:
            return None
        return {
            'station_id': str(station_id or data.get('stationId') or data.get('id') or '').strip(),
            'name': data.get('name') or data.get('stationName') or '',
            'latitude': float(lat),
            'longitude': float(lon)
        }

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius * c
