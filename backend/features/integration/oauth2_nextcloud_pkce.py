"""
Nextcloud OAuth2 Provider with PKCE support.
Does not require a client secret - suitable for browser-based apps.
"""

import base64
import hashlib
import secrets
import logging
from urllib.parse import urljoin, parse_qs, urlparse
import requests

logger = logging.getLogger(__name__)


class OAuth2PKCENextcloudProvider:
    """
    OAuth2 provider for Nextcloud using PKCE flow.
    No client secret required - suitable for browser apps.
    """

    def __init__(self, nextcloud_url, client_id="mynd-app"):
        """
        Initialize OAuth2 PKCE provider.
        
        Args:
            nextcloud_url: Base URL of Nextcloud instance (e.g., https://cloud.example.com)
            client_id: OAuth2 client ID (default: "mynd-app")
        """
        self.nextcloud_url = nextcloud_url.rstrip("/")
        self.client_id = client_id
        self.redirect_uri = "http://localhost:5001/api/nextcloud/pkce/callback"
        
    @staticmethod
    def generate_pkce_pair():
        """
        Generate PKCE code verifier and challenge.
        
        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode("utf-8").rstrip("=")
        return code_verifier, code_challenge
    
    def get_authorization_url(self):
        """
        Get the authorization URL to redirect user to.
        
        Returns:
            Tuple of (auth_url, code_verifier) - store code_verifier in session
        """
        code_verifier, code_challenge = self.generate_pkce_pair()
        
        auth_url = urljoin(
            self.nextcloud_url,
            "/index.php/apps/oauth2/authorize"
        )
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "openid profile email"
        }
        
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{auth_url}?{query_string}"
        
        return full_url, code_verifier
    
    def exchange_code_for_token(self, code, code_verifier):
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from Nextcloud
            code_verifier: PKCE code verifier from session
            
        Returns:
            Dict with 'access_token' and other token info, or None if failed
        """
        try:
            token_url = urljoin(
                self.nextcloud_url,
                "/index.php/apps/oauth2/api/v1/token"
            )
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": code_verifier
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            logger.info(f"Successfully exchanged code for token from {self.nextcloud_url}")
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            return None
    
    def get_user_info(self, access_token):
        """
        Get user information using access token.
        
        Args:
            access_token: OAuth2 access token
            
        Returns:
            Dict with user info (id, display_name, email), or None if failed
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "OCS-APIRequest": "true"
            }
            
            # Try OpenID Connect endpoint first
            user_url = urljoin(
                self.nextcloud_url,
                "/ocs/v2.php/apps/provisioning_api/api/v1/users/me"
            )
            
            response = requests.get(user_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("ocs", {}).get("meta", {}).get("status") == "ok":
                user_data = data["ocs"]["data"]
                return {
                    "id": user_data.get("id"),
                    "display_name": user_data.get("displayname", user_data.get("id")),
                    "email": user_data.get("email")
                }
            
            logger.warning(f"Unexpected response from user endpoint: {data}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None
    
    def validate_nextcloud_url(self):
        """
        Validate that the Nextcloud URL is accessible.
        
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            status_url = urljoin(self.nextcloud_url, "/status.php")
            response = requests.get(status_url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            if data.get("installed"):
                version = data.get("version", "unknown")
                logger.info(f"Nextcloud {version} found at {self.nextcloud_url}")
                return True, f"Nextcloud {version} is accessible"
            else:
                return False, "Nextcloud installation incomplete"
                
        except requests.exceptions.Timeout:
            return False, "Connection timeout - check URL"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect - check URL and network"
        except Exception as e:
            return False, f"Invalid Nextcloud URL: {str(e)}"
