"""
Nextcloud integration clients for various APIs
"""

from .nextcloud_client import NextcloudClient
from .carddav_client import NextcloudCardDAVClient
from .search_client import NextcloudSearchClient
from .notifications_client import NextcloudNotificationsClient

__all__ = [
    'NextcloudClient',
    'NextcloudCardDAVClient',
    'NextcloudSearchClient',
    'NextcloudNotificationsClient'
]
