"""
OAuth2 Authentication Provider for Nextcloud
Handles OAuth2 authentication flow with Nextcloud servers
"""

from typing import Dict, Any, Optional, Tuple
from requests.auth import AuthBase
from requests_oauthlib import OAuth2Session
from urllib.parse import urljoin
import logging
import os
from .auth_provider import AuthProvider


class OAuth2TokenAuth(AuthBase):
    """Custom auth handler for OAuth2 Bearer tokens"""

    def __init__(self, access_token: str):
        self.access_token = access_token

    def __call__(self, r):
        r.headers['Authorization'] = f'Bearer {self.access_token}'
        return r


class OAuth2NextcloudProvider(AuthProvider):
    """OAuth2 Authentication Provider for Nextcloud"""

    # OAuth2 endpoints on Nextcloud server
    OAUTH2_AUTHORIZE_ENDPOINT = '/index.php/apps/oauth2/authorize'
    OAUTH2_TOKEN_ENDPOINT = '/index.php/apps/oauth2/api/v1/token'

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OAuth2 Nextcloud Provider

        Args:
            config: Dictionary with configuration:
                - nextcloud_url: Nextcloud server URL
                - client_id: OAuth2 client ID (from Nextcloud)
                - client_secret: OAuth2 client secret (from Nextcloud)
                - access_token: OAuth2 access token (obtained after auth)
                - refresh_token: OAuth2 refresh token (optional)
                - scope: Scope string (default: 'files')
        """
        super().__init__(config)
        self.nextcloud_url = config.get('nextcloud_url', '').rstrip('/')
        self.client_id = config.get('client_id', '')
        self.client_secret = config.get('client_secret', '')
        self.access_token = config.get('access_token', '')
        self.refresh_token = config.get('refresh_token', '')
        self.scope = config.get('scope', 'files')

    def get_auth(self) -> OAuth2TokenAuth:
        """
        Get OAuth2 Bearer token auth for requests

        Returns:
            OAuth2TokenAuth object with access token
        """
        if not self.access_token:
            raise ValueError("No access token available")
        return OAuth2TokenAuth(self.access_token)

    def get_provider_name(self) -> str:
        """Get provider name"""
        return 'oauth2_nextcloud'

    def validate_config(self) -> bool:
        """Validate OAuth2 configuration"""
        if not self.nextcloud_url:
            self.logger.error("Nextcloud URL is required")
            return False

        if not self.client_id:
            self.logger.error("Client ID is required")
            return False

        if not self.client_secret:
            self.logger.error("Client secret is required")
            return False

        if not self.access_token:
            self.logger.error("Access token is required")
            return False

        return True

    def get_authorization_url(self, redirect_uri: str) -> str:
        """
        Generate the authorization URL to redirect user to Nextcloud

        Args:
            redirect_uri: Where user should be redirected after auth

        Returns:
            Authorization URL
        """
        oauth = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=redirect_uri,
            scope=[self.scope]
        )

        authorization_url, state = oauth.authorization_url(
            urljoin(self.nextcloud_url, self.OAUTH2_AUTHORIZE_ENDPOINT)
        )

        return authorization_url, state

    def exchange_code_for_token(
        self,
        authorization_code: str,
        redirect_uri: str
    ) -> Tuple[str, Optional[str]]:
        """
        Exchange authorization code for access token

        Args:
            authorization_code: Code received from Nextcloud
            redirect_uri: Same redirect_uri used in authorization

        Returns:
            Tuple of (access_token, refresh_token)
        """
        try:
            oauth = OAuth2Session(
                client_id=self.client_id,
                redirect_uri=redirect_uri
            )

            token = oauth.fetch_token(
                url=urljoin(self.nextcloud_url, self.OAUTH2_TOKEN_ENDPOINT),
                client_secret=self.client_secret,
                authorization_response=authorization_code
            )

            self.access_token = token.get('access_token', '')
            self.refresh_token = token.get('refresh_token', '')

            return self.access_token, self.refresh_token

        except Exception as e:
            self.logger.error(f"Error exchanging code for token: {str(e)}")
            raise

    def refresh_access_token(self) -> str:
        """
        Refresh the access token using the refresh token

        Returns:
            New access token
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        try:
            oauth = OAuth2Session(client_id=self.client_id)

            token = oauth.refresh_token(
                url=urljoin(self.nextcloud_url, self.OAUTH2_TOKEN_ENDPOINT),
                client_id=self.client_id,
                client_secret=self.client_secret,
                refresh_token=self.refresh_token
            )

            self.access_token = token.get('access_token', '')
            self.refresh_token = token.get('refresh_token', self.refresh_token)

            return self.access_token

        except Exception as e:
            self.logger.error(f"Error refreshing access token: {str(e)}")
            raise

    def get_user_info(self) -> Dict[str, Any]:
        """
        Get authenticated user information from Nextcloud

        Returns:
            User information dictionary
        """
        if not self.access_token:
            raise ValueError("Not authenticated")

        try:
            import requests
            headers = {'Authorization': f'Bearer {self.access_token}'}
            response = requests.get(
                urljoin(self.nextcloud_url, '/ocs/v2.php/apps/provisioning_api/api/v1/users/me'),
                headers=headers,
                params={'format': 'json'},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('ocs', {}).get('data', {})
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
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'scope': self.scope
        }
