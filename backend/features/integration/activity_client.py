import logging
from typing import List, Dict, Optional
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime


class NextcloudActivityClient:
    """Client for Nextcloud Activity API integration using OCS API"""

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize Activity API client

        Args:
            url: Nextcloud server URL (e.g., https://cloud.example.com)
            username: Nextcloud username
            password: Nextcloud password or app password
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.logger = logging.getLogger(__name__)

        # OCS API headers for JSON responses
        self.ocs_headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> bool:
        """
        Test Activity API connection to Nextcloud

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/activity/api/v2/activity"
            self.logger.info(f"Testing Activity API connection to: {url}")

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                params={'limit': 1},  # Just get 1 activity to test
                timeout=10
            )

            self.logger.info(f"Activity API connection test response status: {response.status_code}")

            if response.status_code == 200:
                self.logger.info("Activity API connection successful")
                return True
            elif response.status_code == 204:
                # No activities but connection is fine
                self.logger.info("Activity API connection successful (no activities)")
                return True
            elif response.status_code == 401:
                self.logger.error("Activity API authentication failed - check username/password")
                return False
            elif response.status_code == 404:
                self.logger.warning("Activity API not found - may not be enabled")
                return False
            else:
                self.logger.error(f"Activity API unexpected status code: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("Activity API connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("Activity API connection error - check URL and network")
            return False
        except Exception as e:
            self.logger.error(f"Activity API connection failed: {str(e)}")
            return False

    def get_activity(
        self,
        limit: int = 50,
        since: int = None,
        sort: str = 'desc',
        object_type: str = None,
        object_id: str = None
    ) -> Dict:
        """
        Get activity stream for the user

        Args:
            limit: Maximum number of activities to return (default: 50)
            since: Integer ID of last activity seen (for pagination)
            sort: Sort order - 'asc' or 'desc' (default: 'desc')
            object_type: Filter by object type (requires object_id and filter='all')
            object_id: Filter by object ID (requires object_type and filter='all')

        Returns:
            Dictionary with activities and metadata
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/activity/api/v2/activity"

            params = {
                'limit': limit,
                'sort': sort
            }

            if since is not None:
                params['since'] = since
            if object_type:
                params['object_type'] = object_type
            if object_id:
                params['object_id'] = object_id

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                params=params,
                timeout=60
            )

            result = {
                'activities': [],
                'since': since,
                'first_known': None,
                'last_given': None,
                'has_more': False
            }

            if response.status_code == 200:
                data = response.json()
                ocs_data = data.get('ocs', {})
                activities_data = ocs_data.get('data', [])

                # Extract header metadata
                if 'X-Activity-First-Known' in response.headers:
                    result['first_known'] = int(response.headers['X-Activity-First-Known'])
                if 'X-Activity-Last-Given' in response.headers:
                    result['last_given'] = int(response.headers['X-Activity-Last-Given'])
                if 'Link' in response.headers:
                    result['has_more'] = True

                result['activities'] = [self._format_activity(a) for a in activities_data]
                self.logger.info(f"Retrieved {len(result['activities'])} activities")

            elif response.status_code == 204:
                self.logger.info("No activities available (user has selected no activities to be listed)")
            elif response.status_code == 304:
                self.logger.info("No new activities (not modified)")
            else:
                self.logger.error(f"Failed to get activities: {response.status_code}")

            return result

        except Exception as e:
            self.logger.error(f"Error getting activities: {str(e)}")
            return {
                'activities': [],
                'since': since,
                'first_known': None,
                'last_given': None,
                'has_more': False
            }

    def get_activity_by_filter(
        self,
        filter_id: str,
        limit: int = 50,
        since: int = None,
        sort: str = 'desc'
    ) -> Dict:
        """
        Get filtered activity stream

        Args:
            filter_id: Filter ID (e.g., 'all', 'self', 'by', 'filter')
            limit: Maximum number of activities to return (default: 50)
            since: Integer ID of last activity seen (for pagination)
            sort: Sort order - 'asc' or 'desc' (default: 'desc')

        Returns:
            Dictionary with activities and metadata
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/activity/api/v2/activity/{filter_id}"

            params = {
                'limit': limit,
                'sort': sort
            }

            if since is not None:
                params['since'] = since

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                params=params,
                timeout=60
            )

            result = {
                'filter': filter_id,
                'activities': [],
                'since': since,
                'first_known': None,
                'last_given': None,
                'has_more': False
            }

            if response.status_code == 200:
                data = response.json()
                ocs_data = data.get('ocs', {})
                activities_data = ocs_data.get('data', [])

                # Extract header metadata
                if 'X-Activity-First-Known' in response.headers:
                    result['first_known'] = int(response.headers['X-Activity-First-Known'])
                if 'X-Activity-Last-Given' in response.headers:
                    result['last_given'] = int(response.headers['X-Activity-Last-Given'])
                if 'Link' in response.headers:
                    result['has_more'] = True

                result['activities'] = [self._format_activity(a) for a in activities_data]
                self.logger.info(f"Retrieved {len(result['activities'])} activities for filter '{filter_id}'")

            elif response.status_code == 204:
                self.logger.info(f"No activities for filter '{filter_id}'")
            elif response.status_code == 304:
                self.logger.info("No new activities (not modified)")
            elif response.status_code == 404:
                self.logger.error(f"Filter '{filter_id}' not found")
            else:
                self.logger.error(f"Failed to get filtered activities: {response.status_code}")

            return result

        except Exception as e:
            self.logger.error(f"Error getting filtered activities: {str(e)}")
            return {
                'filter': filter_id,
                'activities': [],
                'since': since,
                'first_known': None,
                'last_given': None,
                'has_more': False
            }

    def get_filters(self) -> List[Dict]:
        """
        Get available activity filters

        Returns:
            List of filter dictionaries with id and name
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/activity/api/v2/activity/filters"

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                ocs_data = data.get('ocs', {})
                filters_data = ocs_data.get('data', [])

                filters = []
                for filter_item in filters_data:
                    filters.append({
                        'id': filter_item.get('id', ''),
                        'name': filter_item.get('name', ''),
                        'icon': filter_item.get('icon', ''),
                        'priority': filter_item.get('priority', 0)
                    })

                self.logger.info(f"Retrieved {len(filters)} activity filters")
                return filters
            else:
                self.logger.error(f"Failed to get filters: {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"Error getting filters: {str(e)}")
            return []

    def _format_activity(self, activity: Dict) -> Dict:
        """
        Format a raw activity into a consistent structure

        Args:
            activity: Raw activity data from API

        Returns:
            Formatted activity dictionary
        """
        return {
            'activity_id': activity.get('activity_id', 0),
            'datetime': activity.get('datetime', ''),
            'timestamp': self._parse_datetime(activity.get('datetime', '')),
            'app': activity.get('app', ''),
            'type': activity.get('type', ''),
            'user': activity.get('user', ''),
            'subject': activity.get('subject', ''),
            'subject_rich': activity.get('subject_rich', {}),
            'message': activity.get('message', ''),
            'message_rich': activity.get('message_rich', {}),
            'icon': activity.get('icon', ''),
            'link': activity.get('link', ''),
            'object_type': activity.get('object_type', ''),
            'object_id': activity.get('object_id', ''),
            'object_name': activity.get('object_name', ''),
            'objects': activity.get('objects', {}),
            'previews': activity.get('previews', [])
        }

    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """
        Parse datetime string from Nextcloud

        Args:
            datetime_str: Datetime string from API (ISO 8601)

        Returns:
            datetime object or None
        """
        try:
            # Nextcloud uses ISO 8601 format
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except Exception:
            return None

    def get_recent_activities(self, limit: int = 10) -> List[Dict]:
        """
        Convenience method to get recent activities

        Args:
            limit: Number of recent activities to retrieve

        Returns:
            List of recent activity dictionaries
        """
        result = self.get_activity(limit=limit, sort='desc')
        return result.get('activities', [])

    def get_activities_by_app(self, app: str, limit: int = 50) -> List[Dict]:
        """
        Get activities filtered by app

        Args:
            app: App name (e.g., 'files', 'calendar', 'tasks')
            limit: Maximum number of activities

        Returns:
            List of activity dictionaries
        """
        result = self.get_activity(limit=limit)
        activities = result.get('activities', [])

        # Filter by app
        return [a for a in activities if a.get('app') == app]

    def get_activities_by_type(self, activity_type: str, limit: int = 50) -> List[Dict]:
        """
        Get activities filtered by type

        Args:
            activity_type: Activity type (e.g., 'file_created', 'file_changed')
            limit: Maximum number of activities

        Returns:
            List of activity dictionaries
        """
        result = self.get_activity(limit=limit)
        activities = result.get('activities', [])

        # Filter by type
        return [a for a in activities if a.get('type') == activity_type]

    def get_activity_summary(self, limit: int = 50) -> Dict:
        """
        Get a summary of recent activities grouped by app and type

        Args:
            limit: Number of activities to analyze

        Returns:
            Dictionary with activity summary statistics
        """
        result = self.get_activity(limit=limit)
        activities = result.get('activities', [])

        summary = {
            'total': len(activities),
            'by_app': {},
            'by_type': {},
            'recent_subjects': []
        }

        for activity in activities:
            app = activity.get('app', 'unknown')
            activity_type = activity.get('type', 'unknown')

            # Count by app
            summary['by_app'][app] = summary['by_app'].get(app, 0) + 1

            # Count by type
            summary['by_type'][activity_type] = summary['by_type'].get(activity_type, 0) + 1

            # Add recent subjects (first 10)
            if len(summary['recent_subjects']) < 10:
                summary['recent_subjects'].append({
                    'subject': activity.get('subject', ''),
                    'app': app,
                    'datetime': activity.get('datetime', '')
                })

        return summary
