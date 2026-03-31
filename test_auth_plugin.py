#!/usr/bin/env python3
"""
Test script for the Nextcloud authentication plugin system
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.features.integration.auth_manager import get_auth_manager
from backend.features.integration.nextcloud_client import NextcloudClient
from backend.features.tasks.simple import SimpleNextcloudTasks
from backend.features.calendar.simple import SimpleNextcloudCalendar

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def test_auth_manager():
    """Test the authentication manager"""
    print("\n" + "="*60)
    print("Testing Authentication Manager")
    print("="*60)

    auth_manager = get_auth_manager()

    # Check registered providers
    providers = auth_manager.get_registered_providers()
    print(f"✓ Registered providers: {providers}")

    # Get credentials
    url = os.getenv('NEXTCLOUD_URL')
    username = os.getenv('NEXTCLOUD_USERNAME')
    password = os.getenv('NEXTCLOUD_PASSWORD')

    if not all([url, username, password]):
        print("✗ Missing credentials in .env file")
        return False

    # Create basic auth provider
    auth_provider = auth_manager.create_basic_auth(username, password)
    if not auth_provider:
        print("✗ Failed to create auth provider")
        return False

    print(f"✓ Created auth provider: {auth_provider}")
    print(f"✓ Provider name: {auth_provider.get_provider_name()}")
    print(f"✓ Config valid: {auth_provider.validate_config()}")

    return True


def test_nextcloud_client_with_auth():
    """Test NextcloudClient with authentication plugin"""
    print("\n" + "="*60)
    print("Testing NextcloudClient with Auth Plugin")
    print("="*60)

    url = os.getenv('NEXTCLOUD_URL')
    username = os.getenv('NEXTCLOUD_USERNAME')
    password = os.getenv('NEXTCLOUD_PASSWORD')

    if not all([url, username, password]):
        print("✗ Missing credentials in .env file")
        return False

    # Test 1: Using auth provider directly
    print("\nTest 1: Using auth provider")
    auth_manager = get_auth_manager()
    auth_provider = auth_manager.create_basic_auth(username, password)

    client = NextcloudClient(url, auth_provider=auth_provider)
    if client.test_connection():
        print("✓ NextcloudClient connection successful with auth provider")
    else:
        print("✗ NextcloudClient connection failed")
        return False

    # Test 2: Using backward compatibility (username/password)
    print("\nTest 2: Using backward compatibility (username/password)")
    client_legacy = NextcloudClient(url, username=username, password=password)
    if client_legacy.test_connection():
        print("✓ NextcloudClient connection successful with username/password")
    else:
        print("✗ NextcloudClient connection failed")
        return False

    return True


def test_tasks_with_auth():
    """Test SimpleNextcloudTasks with authentication plugin"""
    print("\n" + "="*60)
    print("Testing SimpleNextcloudTasks with Auth Plugin")
    print("="*60)

    url = os.getenv('NEXTCLOUD_URL')
    username = os.getenv('NEXTCLOUD_USERNAME')
    password = os.getenv('NEXTCLOUD_PASSWORD')

    if not all([url, username, password]):
        print("✗ Missing credentials in .env file")
        return False

    # Test 1: Using auth provider
    print("\nTest 1: Using auth provider")
    auth_manager = get_auth_manager()
    auth_provider = auth_manager.create_basic_auth(username, password)

    tasks_client = SimpleNextcloudTasks(url, auth_provider=auth_provider)
    if tasks_client.test_connection():
        print("✓ SimpleNextcloudTasks connection successful with auth provider")
    else:
        print("✗ SimpleNextcloudTasks connection failed")
        return False

    # Test 2: Using backward compatibility
    print("\nTest 2: Using backward compatibility (username/password)")
    tasks_client_legacy = SimpleNextcloudTasks(url, username=username, password=password)
    if tasks_client_legacy.test_connection():
        print("✓ SimpleNextcloudTasks connection successful with username/password")
    else:
        print("✗ SimpleNextcloudTasks connection failed")
        return False

    return True


def test_calendar_with_auth():
    """Test SimpleNextcloudCalendar with authentication plugin"""
    print("\n" + "="*60)
    print("Testing SimpleNextcloudCalendar with Auth Plugin")
    print("="*60)

    url = os.getenv('NEXTCLOUD_URL')
    username = os.getenv('NEXTCLOUD_USERNAME')
    password = os.getenv('NEXTCLOUD_PASSWORD')

    if not all([url, username, password]):
        print("✗ Missing credentials in .env file")
        return False

    # Test 1: Using auth provider
    print("\nTest 1: Using auth provider")
    auth_manager = get_auth_manager()
    auth_provider = auth_manager.create_basic_auth(username, password)

    cal_client = SimpleNextcloudCalendar(url, auth_provider=auth_provider)
    calendars = cal_client.get_calendars()
    if calendars:
        print(f"✓ SimpleNextcloudCalendar connection successful with auth provider")
        print(f"  Found {len(calendars)} calendars")
    else:
        print("✗ SimpleNextcloudCalendar connection failed or no calendars found")
        return False

    # Test 2: Using backward compatibility
    print("\nTest 2: Using backward compatibility (username/password)")
    cal_client_legacy = SimpleNextcloudCalendar(url, username=username, password=password)
    calendars_legacy = cal_client_legacy.get_calendars()
    if calendars_legacy:
        print(f"✓ SimpleNextcloudCalendar connection successful with username/password")
        print(f"  Found {len(calendars_legacy)} calendars")
    else:
        print("✗ SimpleNextcloudCalendar connection failed")
        return False

    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("NEXTCLOUD AUTHENTICATION PLUGIN TEST SUITE")
    print("="*60)

    all_passed = True

    # Test 1: Auth Manager
    if not test_auth_manager():
        all_passed = False

    # Test 2: NextcloudClient
    if not test_nextcloud_client_with_auth():
        all_passed = False

    # Test 3: Tasks
    if not test_tasks_with_auth():
        all_passed = False

    # Test 4: Calendar
    if not test_calendar_with_auth():
        all_passed = False

    # Summary
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("="*60)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
