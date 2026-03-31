import logging
from typing import List, Dict, Optional
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime


class NextcloudNotificationsClient:
    """Client for Nextcloud Notifications API integration using OCS API"""

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize Notifications API client

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
        Test Notifications API connection to Nextcloud

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/notifications/api/v2/notifications"
            self.logger.info(f"Testing Notifications API connection to: {url}")

            response = self.session.get(url, headers=self.ocs_headers, timeout=10)

            self.logger.info(f"Notifications API connection test response status: {response.status_code}")

            if response.status_code == 200:
                self.logger.info("Notifications API connection successful")
                return True
            elif response.status_code == 401:
                self.logger.error("Notifications API authentication failed - check username/password")
                return False
            elif response.status_code == 404:
                self.logger.warning("Notifications API not found - may not be enabled")
                return False
            else:
                self.logger.error(f"Notifications API unexpected status code: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("Notifications API connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("Notifications API connection error - check URL and network")
            return False
        except Exception as e:
            self.logger.error(f"Notifications API connection failed: {str(e)}")
            return False

    def get_notifications(self) -> List[Dict]:
        """
        Get all notifications for the current user

        Returns:
            List of notification dictionaries
        """
        notifications = []

        try:
            url = f"{self.url}/ocs/v2.php/apps/notifications/api/v2/notifications"

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                ocs_data = data.get('ocs', {})
                notifications_data = ocs_data.get('data', [])

                for notif in notifications_data:
                    notifications.append(self._format_notification(notif))

                self.logger.info(f"Retrieved {len(notifications)} notifications")
            else:
                self.logger.error(f"Failed to get notifications: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error getting notifications: {str(e)}")

        return notifications

    def get_notification(self, notification_id: int) -> Optional[Dict]:
        """
        Get a specific notification by ID

        Args:
            notification_id: Notification ID

        Returns:
            Notification dictionary or None if not found
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/notifications/api/v2/notifications/{notification_id}"

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                ocs_data = data.get('ocs', {})
                notif_data = ocs_data.get('data', {})

                if notif_data:
                    return self._format_notification(notif_data)
            else:
                self.logger.error(f"Failed to get notification {notification_id}: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error getting notification {notification_id}: {str(e)}")

        return None

    def _format_notification(self, notif: Dict) -> Dict:
        """
        Format a notification into a consistent structure

        Args:
            notif: Raw notification data from API

        Returns:
            Formatted notification dictionary
        """
        return {
            'id': notif.get('notification_id', 0),
            'app': notif.get('app', ''),
            'user': notif.get('user', ''),
            'datetime': notif.get('datetime', ''),
            'object_type': notif.get('object_type', ''),
            'object_id': notif.get('object_id', ''),
            'subject': notif.get('subject', ''),
            'message': notif.get('message', ''),
            'link': notif.get('link', ''),
            'icon': notif.get('icon', ''),
            'actions': notif.get('actions', [])
        }

    def delete_notification(self, notification_id: int) -> bool:
        """
        Delete a specific notification (mark as read/dismissed)

        Args:
            notification_id: Notification ID to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/notifications/api/v2/notifications/{notification_id}"

            response = self.session.delete(
                url,
                headers=self.ocs_headers,
                timeout=30
            )

            if response.status_code in [200, 204]:
                self.logger.info(f"Successfully deleted notification {notification_id}")
                return True
            else:
                self.logger.error(f"Failed to delete notification {notification_id}: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error deleting notification {notification_id}: {str(e)}")
            return False

    def delete_all_notifications(self) -> bool:
        """
        Delete all notifications for the current user

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/notifications/api/v2/notifications"

            response = self.session.delete(
                url,
                headers=self.ocs_headers,
                timeout=30
            )

            if response.status_code in [200, 204]:
                self.logger.info("Successfully deleted all notifications")
                return True
            else:
                self.logger.error(f"Failed to delete all notifications: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error deleting all notifications: {str(e)}")
            return False

    def get_unread_count(self) -> int:
        """
        Get count of unread notifications

        Returns:
            Number of unread notifications
        """
        try:
            notifications = self.get_notifications()
            return len(notifications)

        except Exception as e:
            self.logger.error(f"Error getting unread count: {str(e)}")
            return 0

    def filter_notifications(
        self,
        app: str = None,
        object_type: str = None,
        since: datetime = None
    ) -> List[Dict]:
        """
        Filter notifications by criteria

        Args:
            app: Filter by app name (e.g., 'files', 'calendar')
            object_type: Filter by object type
            since: Filter by datetime (only notifications after this time)

        Returns:
            List of filtered notifications
        """
        try:
            all_notifications = self.get_notifications()
            filtered = all_notifications

            if app:
                filtered = [n for n in filtered if n.get('app') == app]

            if object_type:
                filtered = [n for n in filtered if n.get('object_type') == object_type]

            if since:
                filtered = [
                    n for n in filtered
                    if self._parse_datetime(n.get('datetime', '')) > since
                ]

            self.logger.info(f"Filtered to {len(filtered)} notifications")
            return filtered

        except Exception as e:
            self.logger.error(f"Error filtering notifications: {str(e)}")
            return []

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """
        Parse datetime string from Nextcloud

        Args:
            datetime_str: Datetime string from API

        Returns:
            datetime object
        """
        try:
            # Nextcloud typically uses ISO 8601 format
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.min

    def send_admin_notification(
        self,
        user_id: str,
        short_message: str,
        long_message: str = None
    ) -> bool:
        """
        Send an admin notification to a user (requires admin privileges)

        Args:
            user_id: Target user ID
            short_message: Short notification message
            long_message: Optional detailed message

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.url}/ocs/v2.php/apps/notifications/api/v2/admin_notifications/{user_id}"

            payload = {
                'shortMessage': short_message
            }

            if long_message:
                payload['longMessage'] = long_message

            response = self.session.post(
                url,
                headers=self.ocs_headers,
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                self.logger.info(f"Successfully sent notification to {user_id}")
                return True
            else:
                self.logger.error(f"Failed to send notification: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending notification: {str(e)}")
            return False

    def get_notification_capabilities(self) -> Dict:
        """
        Get capabilities of the notifications app

        Returns:
            Dictionary of capabilities
        """
        try:
            url = f"{self.url}/ocs/v2.php/cloud/capabilities"

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                capabilities = data.get('ocs', {}).get('data', {}).get('capabilities', {})
                notifications_cap = capabilities.get('notifications', {})

                return {
                    'ocs_endpoints': notifications_cap.get('ocs-endpoints', []),
                    'push': notifications_cap.get('push', []),
                    'admin_notifications': notifications_cap.get('admin-notifications', [])
                }
            else:
                self.logger.error(f"Failed to get capabilities: {response.status_code}")
                return {}

        except Exception as e:
            self.logger.error(f"Error getting capabilities: {str(e)}")
            return {}
