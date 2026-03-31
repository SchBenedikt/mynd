"""
Authentication Manager for Nextcloud Integration
Manages authentication provider plugins and creation
"""

from typing import Dict, Any, Optional, Type
import logging
from .auth_provider import AuthProvider
from .auth_basic import BasicAuthProvider


class AuthManager:
    """Manages authentication providers and plugin registration"""

    # Registry of available authentication providers
    _providers: Dict[str, Type[AuthProvider]] = {}

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Register default providers
        self.register_provider('basic', BasicAuthProvider)

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[AuthProvider]) -> None:
        """
        Register a new authentication provider

        Args:
            name: Provider name/identifier
            provider_class: Provider class (must inherit from AuthProvider)
        """
        if not issubclass(provider_class, AuthProvider):
            raise TypeError(f"Provider class must inherit from AuthProvider")

        cls._providers[name] = provider_class
        logging.getLogger(__name__).info(f"Registered auth provider: {name}")

    @classmethod
    def get_registered_providers(cls) -> list:
        """
        Get list of registered provider names

        Returns:
            List of provider names
        """
        return list(cls._providers.keys())

    def create_provider(self, provider_type: str, config: Dict[str, Any]) -> Optional[AuthProvider]:
        """
        Create an authentication provider instance

        Args:
            provider_type: Type of provider (e.g., 'basic', 'oauth2')
            config: Configuration dictionary for the provider

        Returns:
            AuthProvider instance or None if creation failed
        """
        if provider_type not in self._providers:
            self.logger.error(f"Unknown auth provider type: {provider_type}")
            self.logger.info(f"Available providers: {self.get_registered_providers()}")
            return None

        try:
            provider_class = self._providers[provider_type]
            provider = provider_class(config)

            # Validate configuration
            if not provider.validate_config():
                self.logger.error(f"Invalid configuration for {provider_type} provider")
                return None

            self.logger.info(f"Created auth provider: {provider}")
            return provider

        except Exception as e:
            self.logger.error(f"Error creating auth provider {provider_type}: {str(e)}")
            return None

    def create_basic_auth(self, username: str, password: str) -> Optional[AuthProvider]:
        """
        Convenience method to create basic authentication provider

        Args:
            username: Nextcloud username
            password: Nextcloud password or app password

        Returns:
            BasicAuthProvider instance or None if creation failed
        """
        return self.create_provider('basic', {
            'username': username,
            'password': password
        })


# Global instance
_auth_manager = None


def get_auth_manager() -> AuthManager:
    """
    Get the global authentication manager instance

    Returns:
        AuthManager singleton instance
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
