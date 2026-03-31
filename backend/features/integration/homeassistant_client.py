"""
Home Assistant API Client
Provides integration with Home Assistant for smart home control and queries
"""

import requests
import logging
from typing import Dict, Any, List, Optional
from .api_registry import APIClient


class HomeAssistantClient(APIClient):
    """Client for Home Assistant API"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Home Assistant client

        Args:
            config: Configuration dict with:
                - url: Home Assistant URL (e.g., http://homeassistant.local:8123)
                - access_token: Long-lived access token
        """
        self.logger = logging.getLogger(__name__)
        self.url = config.get('url', '').rstrip('/')
        self.access_token = config.get('access_token', '')
        self.timeout = config.get('timeout', 10)

        if not self.url or not self.access_token:
            raise ValueError("Home Assistant URL and access token are required")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> bool:
        """Test Home Assistant connection"""
        try:
            response = requests.get(
                f'{self.url}/api/',
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"Connected to Home Assistant: {data.get('message', 'OK')}")
                return True
            elif response.status_code == 401:
                self.logger.error("Home Assistant authentication failed - invalid access token")
                return False
            else:
                self.logger.error(f"Home Assistant connection failed: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("Home Assistant connection timeout")
            return False
        except Exception as e:
            self.logger.error(f"Home Assistant connection error: {str(e)}")
            return False

    def get_api_name(self) -> str:
        """Get API name"""
        return "homeassistant"

    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            'url': {
                'type': 'string',
                'required': True,
                'description': 'Home Assistant URL (e.g., http://homeassistant.local:8123)',
                'example': 'http://homeassistant.local:8123'
            },
            'access_token': {
                'type': 'string',
                'required': True,
                'description': 'Long-lived access token from Home Assistant',
                'secret': True
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'description': 'Request timeout in seconds',
                'default': 10
            }
        }

    def get_config(self) -> Dict[str, Any]:
        """Get Home Assistant configuration"""
        try:
            response = requests.get(
                f'{self.url}/api/config',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting config: {str(e)}")
            return {}

    def get_states(self) -> List[Dict[str, Any]]:
        """Get all entity states"""
        try:
            response = requests.get(
                f'{self.url}/api/states',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting states: {str(e)}")
            return []

    def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get state of a specific entity

        Args:
            entity_id: Entity ID (e.g., 'light.living_room')

        Returns:
            Entity state dict or None
        """
        try:
            response = requests.get(
                f'{self.url}/api/states/{entity_id}',
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                self.logger.warning(f"Entity not found: {entity_id}")
                return None
            else:
                response.raise_for_status()
                return None

        except Exception as e:
            self.logger.error(f"Error getting state for {entity_id}: {str(e)}")
            return None

    def call_service(self, domain: str, service: str,
                    entity_id: str = None, data: Dict[str, Any] = None) -> bool:
        """
        Call a Home Assistant service

        Args:
            domain: Service domain (e.g., 'light', 'switch')
            service: Service name (e.g., 'turn_on', 'turn_off')
            entity_id: Optional entity ID to target
            data: Optional service data

        Returns:
            True if successful
        """
        try:
            service_data = data or {}
            if entity_id:
                service_data['entity_id'] = entity_id

            response = requests.post(
                f'{self.url}/api/services/{domain}/{service}',
                headers=self._get_headers(),
                json=service_data,
                timeout=self.timeout
            )
            response.raise_for_status()

            self.logger.info(f"Called service {domain}.{service} successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error calling service {domain}.{service}: {str(e)}")
            return False

    def get_services(self) -> Dict[str, Any]:
        """Get all available services"""
        try:
            response = requests.get(
                f'{self.url}/api/services',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting services: {str(e)}")
            return {}

    def get_events(self) -> List[Dict[str, Any]]:
        """Get all event types"""
        try:
            response = requests.get(
                f'{self.url}/api/events',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting events: {str(e)}")
            return []

    def get_history(self, entity_id: str = None,
                   start_time: str = None, end_time: str = None) -> List[Dict[str, Any]]:
        """
        Get history for entities

        Args:
            entity_id: Optional specific entity ID
            start_time: ISO 8601 timestamp for start
            end_time: ISO 8601 timestamp for end

        Returns:
            List of history entries
        """
        try:
            url = f'{self.url}/api/history/period'
            if start_time:
                url += f'/{start_time}'

            params = {}
            if entity_id:
                params['filter_entity_id'] = entity_id
            if end_time:
                params['end_time'] = end_time

            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout * 2  # History can take longer
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            self.logger.error(f"Error getting history: {str(e)}")
            return []

    def search_entities(self, query: str, domains: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search for entities matching a query

        Args:
            query: Search query (matches entity_id and friendly_name)
            domains: Optional list of domains to filter (e.g., ['light', 'switch'])

        Returns:
            List of matching entities
        """
        try:
            all_states = self.get_states()
            query_lower = query.lower()
            results = []

            for state in all_states:
                entity_id = state.get('entity_id', '')
                friendly_name = state.get('attributes', {}).get('friendly_name', '')

                # Filter by domain if specified
                if domains:
                    domain = entity_id.split('.')[0]
                    if domain not in domains:
                        continue

                # Check if query matches
                if (query_lower in entity_id.lower() or
                    query_lower in friendly_name.lower()):
                    results.append(state)

            return results

        except Exception as e:
            self.logger.error(f"Error searching entities: {str(e)}")
            return []

    def turn_on(self, entity_id: str) -> bool:
        """Turn on an entity (light, switch, etc.)"""
        domain = entity_id.split('.')[0]
        return self.call_service(domain, 'turn_on', entity_id)

    def turn_off(self, entity_id: str) -> bool:
        """Turn off an entity (light, switch, etc.)"""
        domain = entity_id.split('.')[0]
        return self.call_service(domain, 'turn_off', entity_id)

    def toggle(self, entity_id: str) -> bool:
        """Toggle an entity (light, switch, etc.)"""
        domain = entity_id.split('.')[0]
        return self.call_service(domain, 'toggle', entity_id)
