"""
Authentication Provider Interface for Nextcloud Integration
Provides a plugin architecture for different authentication methods
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging


class AuthProvider(ABC):
    """Base class for authentication providers"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize authentication provider

        Args:
            config: Configuration dictionary with provider-specific settings
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_auth(self) -> Any:
        """
        Get authentication object for requests library

        Returns:
            Authentication object compatible with requests library
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this authentication provider

        Returns:
            Provider name as string
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate the configuration for this provider

        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    def get_headers(self) -> Dict[str, str]:
        """
        Get additional headers required for this authentication method

        Returns:
            Dictionary of headers
        """
        return {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.get_provider_name()})"
