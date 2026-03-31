#!/usr/bin/env python3
"""
Test script for Nextcloud API integrations

This script tests the CardDAV, Search, and Notifications API clients
"""

import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.features.integration import (
    NextcloudCardDAVClient,
    NextcloudSearchClient,
    NextcloudNotificationsClient,
    NextcloudActivityClient
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_carddav_client(url: str, username: str, password: str):
    """Test CardDAV client functionality"""
    logger.info("\n=== Testing CardDAV Client ===")

    try:
        client = NextcloudCardDAVClient(url, username, password)

        # Test connection
        logger.info("Testing connection...")
        if client.test_connection():
            logger.info("✓ CardDAV connection successful")
        else:
            logger.error("✗ CardDAV connection failed")
            return False

        # Get addressbooks
        logger.info("Getting addressbooks...")
        addressbooks = client.get_addressbooks()
        logger.info(f"✓ Found {len(addressbooks)} addressbooks")
        for ab in addressbooks:
            logger.info(f"  - {ab['display_name']} ({ab['name']})")

        # Get contacts
        if addressbooks:
            logger.info("Getting contacts from first addressbook...")
            contacts = client.get_contacts(addressbooks[0]['name'])
            logger.info(f"✓ Found {len(contacts)} contacts")

            # Display first few contacts
            for i, contact in enumerate(contacts[:3]):
                logger.info(f"  - {contact.get('full_name', 'N/A')} - {', '.join(contact.get('email', []))}")

        logger.info("✓ CardDAV client tests completed successfully")
        return True

    except Exception as e:
        logger.error(f"✗ CardDAV client test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_search_client(url: str, username: str, password: str):
    """Test Search API client functionality"""
    logger.info("\n=== Testing Search API Client ===")

    try:
        client = NextcloudSearchClient(url, username, password)

        # Test connection
        logger.info("Testing connection...")
        if client.test_connection():
            logger.info("✓ Search API connection successful")
        else:
            logger.error("✗ Search API connection failed")
            return False

        # Get search providers
        logger.info("Getting search providers...")
        providers = client.get_search_providers()
        logger.info(f"✓ Found {len(providers)} search providers")
        for provider in providers:
            logger.info(f"  - {provider['name']} (id: {provider['id']}, order: {provider['order']})")

        # Test unified search
        logger.info("Testing unified search with query 'test'...")
        results = client.search('test', limit=5)
        logger.info(f"✓ Unified search found {len(results.get('results', []))} results")

        # Display results
        for result in results.get('results', [])[:3]:
            logger.info(f"  - [{result['provider']}] {result['title']}")

        # Test file search
        logger.info("Testing file-specific search...")
        file_results = client.search_files('document', limit=5)
        logger.info(f"✓ File search found {len(file_results)} results")

        logger.info("✓ Search API client tests completed successfully")
        return True

    except Exception as e:
        logger.error(f"✗ Search API client test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_notifications_client(url: str, username: str, password: str):
    """Test Notifications API client functionality"""
    logger.info("\n=== Testing Notifications API Client ===")

    try:
        client = NextcloudNotificationsClient(url, username, password)

        # Test connection
        logger.info("Testing connection...")
        if client.test_connection():
            logger.info("✓ Notifications API connection successful")
        else:
            logger.error("✗ Notifications API connection failed")
            return False

        # Get notifications
        logger.info("Getting notifications...")
        notifications = client.get_notifications()
        logger.info(f"✓ Found {len(notifications)} notifications")

        # Display first few notifications
        for i, notif in enumerate(notifications[:3]):
            logger.info(f"  - [{notif['app']}] {notif['subject']}")
            if notif['message']:
                logger.info(f"    Message: {notif['message'][:80]}")

        # Get unread count
        unread_count = client.get_unread_count()
        logger.info(f"✓ Unread notifications: {unread_count}")

        # Get capabilities
        logger.info("Getting notification capabilities...")
        capabilities = client.get_notification_capabilities()
        logger.info(f"✓ Capabilities retrieved: {len(capabilities)} entries")

        logger.info("✓ Notifications API client tests completed successfully")
        return True

    except Exception as e:
        logger.error(f"✗ Notifications API client test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_activity_client(url: str, username: str, password: str):
    """Test Activity API client functionality"""
    logger.info("\n=== Testing Activity API Client ===")

    try:
        client = NextcloudActivityClient(url, username, password)

        # Test connection
        logger.info("Testing connection...")
        if client.test_connection():
            logger.info("✓ Activity API connection successful")
        else:
            logger.error("✗ Activity API connection failed")
            return False

        # Get available filters
        logger.info("Getting activity filters...")
        filters = client.get_filters()
        logger.info(f"✓ Found {len(filters)} activity filters")
        for filter_item in filters:
            logger.info(f"  - {filter_item['name']} (id: {filter_item['id']})")

        # Get recent activities
        logger.info("Getting recent activities...")
        recent = client.get_recent_activities(limit=10)
        logger.info(f"✓ Found {len(recent)} recent activities")

        # Display first few activities
        for i, activity in enumerate(recent[:5]):
            logger.info(f"  - [{activity['app']}] {activity['subject']}")
            logger.info(f"    Type: {activity['type']}, Time: {activity['datetime']}")

        # Get activity summary
        logger.info("Getting activity summary...")
        summary = client.get_activity_summary(limit=50)
        logger.info(f"✓ Activity Summary:")
        logger.info(f"  Total activities: {summary['total']}")
        logger.info(f"  By app: {summary['by_app']}")
        logger.info(f"  By type: {summary['by_type']}")

        logger.info("✓ Activity API client tests completed successfully")
        return True

    except Exception as e:
        logger.error(f"✗ Activity API client test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""

    # Check for environment variables or use defaults
    url = os.environ.get('NEXTCLOUD_URL', 'https://cloud.example.com')
    username = os.environ.get('NEXTCLOUD_USERNAME', 'testuser')
    password = os.environ.get('NEXTCLOUD_PASSWORD', 'testpassword')

    logger.info("=" * 70)
    logger.info("Nextcloud API Integration Tests")
    logger.info("=" * 70)
    logger.info(f"URL: {url}")
    logger.info(f"Username: {username}")
    logger.info("=" * 70)

    results = {
        'carddav': False,
        'search': False,
        'notifications': False,
        'activity': False
    }

    # Run tests
    results['carddav'] = test_carddav_client(url, username, password)
    results['search'] = test_search_client(url, username, password)
    results['notifications'] = test_notifications_client(url, username, password)
    results['activity'] = test_activity_client(url, username, password)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("Test Summary")
    logger.info("=" * 70)
    logger.info(f"CardDAV Client:       {'✓ PASS' if results['carddav'] else '✗ FAIL'}")
    logger.info(f"Search API Client:    {'✓ PASS' if results['search'] else '✗ FAIL'}")
    logger.info(f"Notifications Client: {'✓ PASS' if results['notifications'] else '✗ FAIL'}")
    logger.info(f"Activity Client:      {'✓ PASS' if results['activity'] else '✗ FAIL'}")
    logger.info("=" * 70)

    # Exit with appropriate code
    if all(results.values()):
        logger.info("✓ All tests passed!")
        return 0
    else:
        logger.error("✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
