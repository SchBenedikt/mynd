"""
Direct Nextcloud WebDAV Token Authentication
Simplified flow that uses Nextcloud WebDAV capabilities
without requiring OAuth2 app registration
"""

from typing import Dict, Any, Optional, Tuple
from requests.auth import HTTPBasicAuth
import requests
import logging
from .auth_provider import AuthProvider


class DirectNextcloudProvider(AuthProvider):
    """Direct Nextcloud Authentication via WebDAV"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Direct Nextcloud Provider

        Args:
            config: Dictionary with configuration:
                - nextcloud_url: Nextcloud server URL
                - username: Username
                - password: Password or app password
        """
        super().__init__(config)
        self.nextcloud_url = config.get('nextcloud_url', '').rstrip('/')
        self.username = config.get('username', '')
        self.password = config.get('password', '')

    def get_auth(self) -> HTTPBasicAuth:
        """
        Get HTTP Basic Auth for requests

        Returns:
            HTTPBasicAuth object
        """
        if not self.username or not self.password:
            raise ValueError("Username and password are required")
        return HTTPBasicAuth(self.username, self.password)

    def get_provider_name(self) -> str:
        """Get provider name"""
        return 'nextcloud_direct'

    def validate_config(self) -> bool:
        """Validate configuration"""
        if not self.nextcloud_url:
            self.logger.error("Nextcloud URL is required")
            return False

        if not self.username:
            self.logger.error("Username is required")
            return False

        if not self.password:
            self.logger.error("Password is required")
            return False

        return True

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to Nextcloud via WebDAV

        Returns:
            Tuple of (success, message)
        """
        try:
            url = f"{self.nextcloud_url}/remote.php/dav/files/{self.username}/"
            response = requests.request(
                'PROPFIND',
                url,
                auth=self.get_auth(),
                timeout=10
            )

            if response.status_code in [200, 207]:
                return True, "Connected successfully"
            elif response.status_code == 401:
                return False, "Authentication failed (invalid credentials)"
            elif response.status_code == 404:
                return False, "Nextcloud not found (invalid URL?)"
            else:
                return False, f"Connection failed (HTTP {response.status_code})"

        except requests.exceptions.ConnectionError:
            return False, "Connection refused (wrong URL?)"
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def create_app_password(self) -> Optional[str]:
        """
        Create an app-specific password on Nextcloud
        Requires initial credentials (username/password)

        Returns:
            New app password or None if failed
        """
        try:
            url = f"{self.nextcloud_url}/ocs/v2.php/apps/admin_audit/api/v1/logs"
            
            # Try to create app password via API
            response = requests.post(
                f"{self.nextcloud_url}/ocs/v2.php/apps/provisioning_api/api/v1/apppasswords",
                auth=self.get_auth(),
                headers={'OCS-APIRequest': 'true'},
                json={},
                timeout=10
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    app_password = data.get('ocs', {}).get('data', {}).get('appPassword', '')
                    if app_password:
                        self.password = app_password  # Update to use app password
                        return app_password
                except:
                    pass

            return None

        except Exception as e:
            self.logger.error(f"Error creating app password: {str(e)}")
            return None

    def get_user_info(self) -> Dict[str, Any]:
        """
        Get authenticated user information from Nextcloud

        Returns:
            User information dictionary
        """
        try:
            headers = {'OCS-APIRequest': 'true'}
            response = requests.get(
                f"{self.nextcloud_url}/ocs/v2.php/apps/provisioning_api/api/v1/users/me",
                auth=self.get_auth(),
                headers=headers,
                params={'format': 'json'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                user_data = data.get('ocs', {}).get('data', {})
                return user_data
            else:
                self.logger.error(f"Failed to get user info: {response.status_code}")
                return {}

        except Exception as e:
            self.logger.error(f"Error getting user info: {str(e)}")
            return {}

    def to_config_dict(self) -> Dict[str, Any]:
        """Convert provider state to configuration dictionary"""
        return {
            'nextcloud_url': self.nextcloud_url,
            'username': self.username,
            'password': self.password,
            'auth_type': 'direct'
        }
