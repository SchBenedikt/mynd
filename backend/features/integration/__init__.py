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
from .openweather_client import OpenWeatherClient
from .nina_client import NINAClient
from .autobahn_client import AutobahnClient
from .dashboard_deutschland_client import DashboardDeutschlandClient
from .deutschland_atlas_client import DeutschlandAtlasClient
from .email_client import EmailClient

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
    'UptimeKumaClient',
    'OpenWeatherClient',
    'NINAClient',
    'AutobahnClient',
    'DashboardDeutschlandClient',
    'DeutschlandAtlasClient',
    'EmailClient'
]

# Register API types on module import
def _register_api_types():
    """Register all available API types with the registry"""
    registry = get_api_registry()
    APIRegistry.register_api_type('homeassistant', HomeAssistantClient)
    APIRegistry.register_api_type('uptimekuma', UptimeKumaClient)
    APIRegistry.register_api_type('openweather', OpenWeatherClient)
    APIRegistry.register_api_type('nina', NINAClient)
    APIRegistry.register_api_type('autobahn', AutobahnClient)
    APIRegistry.register_api_type('dashboard_deutschland', DashboardDeutschlandClient)
    APIRegistry.register_api_type('deutschland_atlas', DeutschlandAtlasClient)
    APIRegistry.register_api_type('email', EmailClient)

_register_api_types()
