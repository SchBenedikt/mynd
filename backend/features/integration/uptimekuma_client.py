"""
Uptime Kuma API Client
Provides integration with Uptime Kuma for monitoring and uptime statistics
"""

import requests
import logging
from typing import Dict, Any, List, Optional
from .api_registry import APIClient


class UptimeKumaClient(APIClient):
    """Client for Uptime Kuma API"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Uptime Kuma client

        Args:
            config: Configuration dict with:
                - url: Uptime Kuma URL (e.g., http://uptime-kuma.local:3001)
                - api_key: API key for authentication
        """
        self.logger = logging.getLogger(__name__)
        self.url = config.get('url', '').rstrip('/')
        self.api_key = config.get('api_key', '')
        self.timeout = config.get('timeout', 10)

        if not self.url or not self.api_key:
            raise ValueError("Uptime Kuma URL and API key are required")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> bool:
        """Test Uptime Kuma connection"""
        try:
            # Try to get monitors list as a connection test
            response = requests.get(
                f'{self.url}/api/monitors',
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                self.logger.info("Successfully connected to Uptime Kuma")
                return True
            elif response.status_code == 401:
                self.logger.error("Uptime Kuma authentication failed - invalid API key")
                return False
            else:
                self.logger.error(f"Uptime Kuma connection failed: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("Uptime Kuma connection timeout")
            return False
        except Exception as e:
            self.logger.error(f"Uptime Kuma connection error: {str(e)}")
            return False

    def get_api_name(self) -> str:
        """Get API name"""
        return "uptimekuma"

    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            'url': {
                'type': 'string',
                'required': True,
                'description': 'Uptime Kuma URL (e.g., http://uptime-kuma.local:3001)',
                'example': 'http://uptime-kuma.local:3001'
            },
            'api_key': {
                'type': 'string',
                'required': True,
                'description': 'API key from Uptime Kuma settings',
                'secret': True
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'description': 'Request timeout in seconds',
                'default': 10
            }
        }

    def get_monitors(self) -> List[Dict[str, Any]]:
        """
        Get all monitors

        Returns:
            List of monitor objects
        """
        try:
            response = requests.get(
                f'{self.url}/api/monitors',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting monitors: {str(e)}")
            return []

    def get_monitor(self, monitor_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific monitor

        Args:
            monitor_id: Monitor ID

        Returns:
            Monitor object or None
        """
        try:
            response = requests.get(
                f'{self.url}/api/monitor/{monitor_id}',
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                self.logger.warning(f"Monitor not found: {monitor_id}")
                return None
            else:
                response.raise_for_status()
                return None

        except Exception as e:
            self.logger.error(f"Error getting monitor {monitor_id}: {str(e)}")
            return None

    def get_monitor_beats(self, monitor_id: int, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get heartbeat history for a monitor

        Args:
            monitor_id: Monitor ID
            hours: Number of hours of history to retrieve

        Returns:
            List of heartbeat objects
        """
        try:
            response = requests.get(
                f'{self.url}/api/monitor/{monitor_id}/beats',
                headers=self._get_headers(),
                params={'hours': hours},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting beats for monitor {monitor_id}: {str(e)}")
            return []

    def get_status_pages(self) -> List[Dict[str, Any]]:
        """
        Get all status pages

        Returns:
            List of status page objects
        """
        try:
            response = requests.get(
                f'{self.url}/api/status-pages',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting status pages: {str(e)}")
            return []

    def get_uptime_stats(self, monitor_id: int = None) -> Dict[str, Any]:
        """
        Get uptime statistics

        Args:
            monitor_id: Optional specific monitor ID, or None for all monitors

        Returns:
            Dictionary with uptime statistics
        """
        try:
            if monitor_id:
                monitor = self.get_monitor(monitor_id)
                if not monitor:
                    return {}

                return {
                    'monitor_id': monitor_id,
                    'name': monitor.get('name', ''),
                    'uptime_24h': monitor.get('uptime24h', 0),
                    'uptime_7d': monitor.get('uptime7d', 0),
                    'uptime_30d': monitor.get('uptime30d', 0),
                    'avg_ping': monitor.get('avgPing', 0),
                    'status': monitor.get('status', 'unknown')
                }
            else:
                # Get stats for all monitors
                monitors = self.get_monitors()
                stats = {
                    'total_monitors': len(monitors),
                    'up': 0,
                    'down': 0,
                    'pending': 0,
                    'monitors': []
                }

                for monitor in monitors:
                    status = monitor.get('status', 'unknown')
                    if status == 1:
                        stats['up'] += 1
                    elif status == 0:
                        stats['down'] += 1
                    else:
                        stats['pending'] += 1

                    stats['monitors'].append({
                        'id': monitor.get('id'),
                        'name': monitor.get('name', ''),
                        'status': status,
                        'uptime_24h': monitor.get('uptime24h', 0)
                    })

                return stats

        except Exception as e:
            self.logger.error(f"Error getting uptime stats: {str(e)}")
            return {}

    def search_monitors(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for monitors by name or URL

        Args:
            query: Search query

        Returns:
            List of matching monitors
        """
        try:
            all_monitors = self.get_monitors()
            query_lower = query.lower()
            results = []

            for monitor in all_monitors:
                name = monitor.get('name', '').lower()
                url = monitor.get('url', '').lower()

                if query_lower in name or query_lower in url:
                    results.append(monitor)

            return results

        except Exception as e:
            self.logger.error(f"Error searching monitors: {str(e)}")
            return []

    def get_notifications(self) -> List[Dict[str, Any]]:
        """
        Get all notification providers

        Returns:
            List of notification provider objects
        """
        try:
            response = requests.get(
                f'{self.url}/api/notifications',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting notifications: {str(e)}")
            return []

    def get_incidents(self, monitor_id: int = None) -> List[Dict[str, Any]]:
        """
        Get incidents/downtime events

        Args:
            monitor_id: Optional specific monitor ID

        Returns:
            List of incident objects
        """
        try:
            url = f'{self.url}/api/incidents'
            params = {}
            if monitor_id:
                params['monitor_id'] = monitor_id

            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting incidents: {str(e)}")
            return []

    def pause_monitor(self, monitor_id: int) -> bool:
        """
        Pause a monitor

        Args:
            monitor_id: Monitor ID

        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f'{self.url}/api/monitor/{monitor_id}/pause',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            self.logger.info(f"Paused monitor {monitor_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error pausing monitor {monitor_id}: {str(e)}")
            return False

    def resume_monitor(self, monitor_id: int) -> bool:
        """
        Resume a paused monitor

        Args:
            monitor_id: Monitor ID

        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f'{self.url}/api/monitor/{monitor_id}/resume',
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            self.logger.info(f"Resumed monitor {monitor_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error resuming monitor {monitor_id}: {str(e)}")
            return False
