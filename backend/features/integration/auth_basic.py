"""
HTTP Basic Authentication Provider for Nextcloud
"""

from typing import Dict, Any
from requests.auth import HTTPBasicAuth
from .auth_provider import AuthProvider


class BasicAuthProvider(AuthProvider):
    """HTTP Basic Authentication Provider"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Basic Authentication Provider

        Args:
            config: Dictionary with 'username' and 'password' keys
        """
        super().__init__(config)
        self.username = config.get('username', '')
        self.password = config.get('password', '')

    def get_auth(self) -> HTTPBasicAuth:
        """
        Get HTTPBasicAuth object for requests

        Returns:
            HTTPBasicAuth object
        """
        return HTTPBasicAuth(self.username, self.password)

    def get_provider_name(self) -> str:
        """
        Get provider name

        Returns:
            'basic' as the provider name
        """
        return 'basic'

    def validate_config(self) -> bool:
        """
        Validate configuration has username and password

        Returns:
            True if both username and password are provided
        """
        if not self.username:
            self.logger.error("Username is required for Basic Auth")
            return False

        if not self.password:
            self.logger.error("Password is required for Basic Auth")
            return False

        return True
