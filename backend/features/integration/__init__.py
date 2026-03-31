"""
API Integration clients for various services
"""

from .nextcloud_client import NextcloudClient
from .carddav_client import NextcloudCardDAVClient
from .search_client import NextcloudSearchClient
from .notifications_client import NextcloudNotificationsClient
from .activity_client import NextcloudActivityClient
from .api_registry import APIRegistry, APIClient, get_api_registry
from .homeassistant_client import HomeAssistantClient
from .uptimekuma_client import UptimeKumaClient

__all__ = [
    'NextcloudClient',
    'NextcloudCardDAVClient',
    'NextcloudSearchClient',
    'NextcloudNotificationsClient',
    'NextcloudActivityClient',
    'APIRegistry',
    'APIClient',
    'get_api_registry',
    'HomeAssistantClient',
    'UptimeKumaClient'
]

# Register API types on module import
def _register_api_types():
    """Register all available API types with the registry"""
    registry = get_api_registry()
    APIRegistry.register_api_type('homeassistant', HomeAssistantClient)
    APIRegistry.register_api_type('uptimekuma', UptimeKumaClient)

_register_api_types()
