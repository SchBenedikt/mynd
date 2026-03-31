"""
API Registry - Central management system for all API integrations
Provides a scalable system for registering, configuring, and monitoring APIs
"""

from typing import Dict, Any, Optional, Type, List
from datetime import datetime
import logging
import json
import os
from abc import ABC, abstractmethod


class APIClient(ABC):
    """Base class for all API clients"""

    @classmethod
    def requires_config(cls) -> bool:
        """Return True if this API requires user-provided configuration"""
        return True

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Return default config for optional/public APIs"""
        return {}

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the API connection is working"""
        pass

    @abstractmethod
    def get_api_name(self) -> str:
        """Get the name of this API"""
        pass

    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get the configuration schema for this API
        Returns a dictionary describing required/optional config fields
        """
        pass

    def get_health_info(self) -> Dict[str, Any]:
        """
        Get health information about this API
        Returns status, last_checked, response_time, etc.
        """
        try:
            start_time = datetime.now()
            is_healthy = self.test_connection()
            response_time = (datetime.now() - start_time).total_seconds()

            return {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'last_checked': datetime.now().isoformat(),
                'response_time': response_time,
                'error': None
            }
        except Exception as e:
            return {
                'status': 'error',
                'last_checked': datetime.now().isoformat(),
                'response_time': None,
                'error': str(e)
            }


class APIRegistry:
    """Central registry for all API integrations"""

    # Registry of available API types
    _api_types: Dict[str, Type[APIClient]] = {}

    def __init__(self, config_dir: str = None):
        self.logger = logging.getLogger(__name__)
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(__file__), '../../config'
        )
        os.makedirs(self.config_dir, exist_ok=True)

        # Cache for API instances
        self._api_instances: Dict[str, APIClient] = {}

        # Health check results cache
        self._health_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_api_type(cls, api_name: str, api_class: Type[APIClient]) -> None:
        """
        Register a new API type

        Args:
            api_name: Unique identifier for this API type
            api_class: Class implementing APIClient interface
        """
        if not issubclass(api_class, APIClient):
            raise TypeError(f"API class must inherit from APIClient")

        cls._api_types[api_name] = api_class
        logging.getLogger(__name__).info(f"Registered API type: {api_name}")

    @classmethod
    def get_registered_api_types(cls) -> List[str]:
        """Get list of registered API types"""
        return list(cls._api_types.keys())

    @classmethod
    def get_api_class(cls, api_name: str) -> Optional[Type[APIClient]]:
        """Get API client class for a registered API name"""
        return cls._api_types.get(api_name)

    def get_config_path(self, api_name: str, username: str = None) -> str:
        """Get the config file path for an API"""
        if username:
            return os.path.join(self.config_dir, f'{api_name}_{username}.json')
        return os.path.join(self.config_dir, f'{api_name}_config.json')

    def load_config(self, api_name: str, username: str = None) -> Dict[str, Any]:
        """Load configuration for an API"""
        config_path = self.get_config_path(api_name, username)

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config for {api_name}: {str(e)}")

        return {}

    def save_config(self, api_name: str, config: Dict[str, Any], username: str = None) -> bool:
        """Save configuration for an API"""
        config_path = self.get_config_path(api_name, username)

        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            self.logger.info(f"Saved config for {api_name}")

            # Invalidate instance cache
            cache_key = f"{api_name}:{username}" if username else api_name
            if cache_key in self._api_instances:
                del self._api_instances[cache_key]

            return True
        except Exception as e:
            self.logger.error(f"Error saving config for {api_name}: {str(e)}")
            return False

    def delete_config(self, api_name: str, username: str = None) -> bool:
        """Delete configuration for an API"""
        config_path = self.get_config_path(api_name, username)

        try:
            if os.path.exists(config_path):
                os.remove(config_path)
                self.logger.info(f"Deleted config for {api_name}")

                # Invalidate instance cache
                cache_key = f"{api_name}:{username}" if username else api_name
                if cache_key in self._api_instances:
                    del self._api_instances[cache_key]

                return True
        except Exception as e:
            self.logger.error(f"Error deleting config for {api_name}: {str(e)}")

        return False

    def create_api_instance(self, api_name: str, config: Dict[str, Any] = None,
                          username: str = None, use_cache: bool = True) -> Optional[APIClient]:
        """
        Create an API client instance

        Args:
            api_name: Type of API to create
            config: Optional config dict (if None, will load from file)
            username: Optional username for user-specific config
            use_cache: Whether to use cached instance

        Returns:
            APIClient instance or None if creation failed
        """
        cache_key = f"{api_name}:{username}" if username else api_name

        # Check cache
        if use_cache and cache_key in self._api_instances:
            return self._api_instances[cache_key]

        # Check if API type is registered
        if api_name not in self._api_types:
            self.logger.error(f"Unknown API type: {api_name}")
            self.logger.info(f"Available APIs: {self.get_registered_api_types()}")
            return None

        # Load config if not provided
        if config is None:
            config = self.load_config(api_name, username)
            if not config:
                api_class = self._api_types[api_name]
                if api_class.requires_config():
                    self.logger.warning(f"No configuration found for {api_name}")
                    return None
                config = api_class.get_default_config()

        try:
            api_class = self._api_types[api_name]
            instance = api_class(config)

            # Cache the instance
            if use_cache:
                self._api_instances[cache_key] = instance

            self.logger.info(f"Created API instance: {api_name}")
            return instance

        except Exception as e:
            self.logger.error(f"Error creating API instance {api_name}: {str(e)}")
            return None

    def get_all_configured_apis(self, username: str = None) -> List[Dict[str, Any]]:
        """
        Get list of all configured APIs with their status

        Returns:
            List of dicts with api_name, configured, and config_schema
        """
        apis = []

        for api_name in self.get_registered_api_types():
            api_class = self._api_types[api_name]
            config = self.load_config(api_name, username)
            configured = bool(config)

            if not config and not api_class.requires_config():
                config = api_class.get_default_config()
                configured = True

            # Try to create instance to get schema
            instance = self.create_api_instance(api_name, config if config else {}, username, use_cache=False)

            apis.append({
                'api_name': api_name,
                'configured': configured,
                'config_schema': instance.get_config_schema() if instance else {},
                'config': config if config else {}
            })

        return apis

    def check_api_health(self, api_name: str, username: str = None,
                        use_cache: bool = True, cache_ttl: int = 60) -> Dict[str, Any]:
        """
        Check health of an API

        Args:
            api_name: API to check
            username: Optional username for user-specific instance
            use_cache: Whether to use cached health results
            cache_ttl: Cache time-to-live in seconds

        Returns:
            Health info dict
        """
        cache_key = f"{api_name}:{username}" if username else api_name

        # Check cache
        if use_cache and cache_key in self._health_cache:
            cached = self._health_cache[cache_key]
            last_checked = datetime.fromisoformat(cached['last_checked'])
            age = (datetime.now() - last_checked).total_seconds()

            if age < cache_ttl:
                return cached

        # Create instance and check health
        instance = self.create_api_instance(api_name, username=username)

        if not instance:
            health = {
                'status': 'not_configured',
                'last_checked': datetime.now().isoformat(),
                'response_time': None,
                'error': 'API not configured or failed to initialize'
            }
        else:
            health = instance.get_health_info()

        # Cache the result
        self._health_cache[cache_key] = health

        return health

    def check_all_apis_health(self, username: str = None) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all configured APIs

        Returns:
            Dict mapping api_name to health info
        """
        results = {}

        for api_name in self.get_registered_api_types():
            api_class = self._api_types[api_name]
            config = self.load_config(api_name, username)
            if config or not api_class.requires_config():
                results[api_name] = self.check_api_health(api_name, username)

        return results


# Global instance
_api_registry = None


def get_api_registry() -> APIRegistry:
    """
    Get the global API registry instance

    Returns:
        APIRegistry singleton instance
    """
    global _api_registry
    if _api_registry is None:
        _api_registry = APIRegistry()
    return _api_registry
