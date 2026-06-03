#!/usr/bin/env python3
"""
Example: Using the Nextcloud Authentication Plugin System

This example demonstrates how to use the new authentication plugin system
with different Nextcloud integration components.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.features.integration.auth_manager import get_auth_manager
from backend.features.integration.nextcloud_client import NextcloudClient
from backend.features.tasks.simple import SimpleNextcloudTasks
from backend.features.calendar.simple import SimpleNextcloudCalendar


def example_basic_usage():
    """Example 1: Basic usage with username and password"""
    print("\n" + "="*60)
    print("Example 1: Basic Usage")
    print("="*60)

    # Get authentication manager
    auth_manager = get_auth_manager()

    # Create basic auth provider
    auth_provider = auth_manager.create_basic_auth(
        username='your_username',
        password='your_password'
    )

    # Use with NextcloudClient
    client = NextcloudClient(
        'https://cloud.example.com',
        auth_provider=auth_provider
    )

    # Use with Tasks
    tasks = SimpleNextcloudTasks(
        'https://cloud.example.com',
        auth_provider=auth_provider
    )

    # Use with Calendar
    calendar = SimpleNextcloudCalendar(
        'https://cloud.example.com',
        auth_provider=auth_provider
    )

    print("✓ All clients initialized with auth provider")


def example_backward_compatible():
    """Example 2: Backward compatible usage"""
    print("\n" + "="*60)
    print("Example 2: Backward Compatible Usage")
    print("="*60)

    # Old way still works - username and password directly
    client = NextcloudClient(
        'https://cloud.example.com',
        username='your_username',
        password='your_password'
    )

    tasks = SimpleNextcloudTasks(
        'https://cloud.example.com',
        username='your_username',
        password='your_password'
    )

    calendar = SimpleNextcloudCalendar(
        'https://cloud.example.com',
        username='your_username',
        password='your_password'
    )

    print("✓ All clients initialized with username/password (backward compatible)")


def example_reuse_auth_provider():
    """Example 3: Reusing auth provider across components"""
    print("\n" + "="*60)
    print("Example 3: Reusing Auth Provider")
    print("="*60)

    # Create auth provider once
    auth_manager = get_auth_manager()
    auth = auth_manager.create_basic_auth('user', 'pass')

    # Reuse across all components
    url = 'https://cloud.example.com'

    client = NextcloudClient(url, auth_provider=auth)
    tasks = SimpleNextcloudTasks(url, auth_provider=auth)
    calendar = SimpleNextcloudCalendar(url, auth_provider=auth)

    print("✓ Single auth provider reused across all clients")
    print("  This is efficient and maintains consistency")


def example_custom_provider():
    """Example 4: Creating a custom authentication provider"""
    print("\n" + "="*60)
    print("Example 4: Custom Authentication Provider")
    print("="*60)

    from backend.features.integration.auth_provider import AuthProvider
    from backend.features.integration.auth_manager import AuthManager

    # Define custom provider
    class TokenAuthProvider(AuthProvider):
        """Example: Token-based authentication"""

        def get_auth(self):
            from requests.auth import AuthBase

            class TokenAuth(AuthBase):
                def __init__(self, token):
                    self.token = token

                def __call__(self, r):
                    r.headers['X-Auth-Token'] = self.token
                    return r

            return TokenAuth(self.config.get('token', ''))

        def get_provider_name(self):
            return 'token'

        def validate_config(self):
            return bool(self.config.get('token'))

    # Register the custom provider
    AuthManager.register_provider('token', TokenAuthProvider)

    # Use it
    auth_manager = get_auth_manager()
    auth_provider = auth_manager.create_provider('token', {
        'token': 'my-secret-token'
    })

    client = NextcloudClient('https://cloud.example.com', auth_provider=auth_provider)

    print("✓ Custom authentication provider registered and used")
    print("  Available providers:", auth_manager.get_registered_providers())


def example_from_env():
    """Example 5: Loading credentials from environment"""
    print("\n" + "="*60)
    print("Example 5: Loading from Environment")
    print("="*60)

    # Typically loaded from .env file
    url = os.getenv('NEXTCLOUD_URL', 'https://cloud.example.com')
    username = os.getenv('NEXTCLOUD_USERNAME', 'user')
    password = os.getenv('NEXTCLOUD_PASSWORD', 'pass')

    # Create auth provider from env variables
    auth_manager = get_auth_manager()
    auth = auth_manager.create_basic_auth(username, password)

    # Use with any client
    client = NextcloudClient(url, auth_provider=auth)

    print("✓ Auth provider created from environment variables")
    print(f"  URL: {url}")
    print(f"  Username: {username}")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("NEXTCLOUD AUTHENTICATION PLUGIN - EXAMPLES")
    print("="*60)

    try:
        example_basic_usage()
    except Exception as e:
        print(f"Example 1 error: {e}")

    try:
        example_backward_compatible()
    except Exception as e:
        print(f"Example 2 error: {e}")

    try:
        example_reuse_auth_provider()
    except Exception as e:
        print(f"Example 3 error: {e}")

    try:
        example_custom_provider()
    except Exception as e:
        print(f"Example 4 error: {e}")

    try:
        example_from_env()
    except Exception as e:
        print(f"Example 5 error: {e}")

    print("\n" + "="*60)
    print("For more information, see docs/NEXTCLOUD_AUTH_PLUGIN.md")
    print("="*60)


if __name__ == "__main__":
    main()
