#!/usr/bin/env python3
"""
Example usage of the new Nextcloud API integrations

This script demonstrates how to use the CardDAV, Search, and Notifications
clients together to create a unified Nextcloud experience.
"""

import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.features.integration import (
    NextcloudCardDAVClient,
    NextcloudSearchClient,
    NextcloudNotificationsClient
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def example_contact_search(url: str, username: str, password: str):
    """Example: Search for contacts"""
    print("\n" + "="*70)
    print("Example 1: Contact Search")
    print("="*70)

    carddav = NextcloudCardDAVClient(url, username, password)

    if not carddav.test_connection():
        print("❌ CardDAV connection failed")
        return

    # Search for contacts
    search_query = input("Enter contact name to search: ")
    contacts = carddav.search_contacts(search_query)

    if contacts:
        print(f"\n✓ Found {len(contacts)} matching contacts:")
        for contact in contacts:
            print(f"\n📇 {contact['full_name']}")
            if contact['email']:
                print(f"   📧 {', '.join(contact['email'])}")
            if contact['phone']:
                print(f"   📱 {', '.join(contact['phone'])}")
            if contact['organization']:
                print(f"   🏢 {contact['organization']}")
    else:
        print(f"❌ No contacts found matching '{search_query}'")


def example_unified_search(url: str, username: str, password: str):
    """Example: Unified search across all resources"""
    print("\n" + "="*70)
    print("Example 2: Unified Search")
    print("="*70)

    search = NextcloudSearchClient(url, username, password)

    if not search.test_connection():
        print("❌ Search API connection failed")
        return

    # Show available providers
    providers = search.get_search_providers()
    print(f"\n📋 Available search providers:")
    for provider in providers:
        print(f"   • {provider['name']}")

    # Perform search
    search_query = input("\nEnter search term: ")
    results = search.search(search_query, limit=10)

    if results['results']:
        print(f"\n✓ Found {len(results['results'])} results:\n")
        for result in results['results']:
            print(f"[{result['provider'].upper()}] {result['title']}")
            if result['subline']:
                print(f"   ↳ {result['subline']}")
            if result['resource_url']:
                print(f"   🔗 {result['resource_url']}")
            print()
    else:
        print(f"❌ No results found for '{search_query}'")


def example_notifications_monitor(url: str, username: str, password: str):
    """Example: Monitor notifications"""
    print("\n" + "="*70)
    print("Example 3: Notifications Monitor")
    print("="*70)

    notif = NextcloudNotificationsClient(url, username, password)

    if not notif.test_connection():
        print("❌ Notifications API connection failed")
        return

    # Get all notifications
    notifications = notif.get_notifications()

    print(f"\n📬 You have {len(notifications)} notifications:\n")

    if notifications:
        for notification in notifications:
            print(f"[{notification['app'].upper()}] {notification['subject']}")
            if notification['message']:
                # Truncate long messages
                message = notification['message']
                if len(message) > 100:
                    message = message[:97] + "..."
                print(f"   {message}")
            print(f"   ⏰ {notification['datetime']}")
            print()

        # Ask if user wants to clear notifications
        clear = input("Do you want to clear all notifications? (y/n): ")
        if clear.lower() == 'y':
            if notif.delete_all_notifications():
                print("✓ All notifications cleared")
            else:
                print("❌ Failed to clear notifications")
    else:
        print("✓ No notifications - you're all caught up!")


def example_combined_search(url: str, username: str, password: str):
    """Example: Combined search across contacts, files, and calendar"""
    print("\n" + "="*70)
    print("Example 4: Combined Resource Search")
    print("="*70)

    search = NextcloudSearchClient(url, username, password)
    carddav = NextcloudCardDAVClient(url, username, password)

    query = input("Enter search term: ")

    print(f"\n🔍 Searching for '{query}' across all resources...\n")

    # Search contacts via CardDAV
    print("📇 Contacts:")
    contacts = carddav.search_contacts(query)
    if contacts:
        for contact in contacts[:3]:  # Show first 3
            print(f"   • {contact['full_name']}")
    else:
        print("   No contacts found")

    # Search files
    print("\n📄 Files:")
    files = search.search_files(query, limit=5)
    if files:
        for file in files[:3]:  # Show first 3
            print(f"   • {file['title']}")
    else:
        print("   No files found")

    # Search calendar events
    print("\n📅 Calendar Events:")
    events = search.search_calendar(query, limit=5)
    if events:
        for event in events[:3]:  # Show first 3
            print(f"   • {event['title']}")
    else:
        print("   No calendar events found")

    # Search tasks
    print("\n✅ Tasks:")
    tasks = search.search_tasks(query, limit=5)
    if tasks:
        for task in tasks[:3]:  # Show first 3
            print(f"   • {task['title']}")
    else:
        print("   No tasks found")


def main():
    """Main function"""

    # Get Nextcloud credentials
    url = os.environ.get('NEXTCLOUD_URL')
    username = os.environ.get('NEXTCLOUD_USERNAME')
    password = os.environ.get('NEXTCLOUD_PASSWORD')

    if not all([url, username, password]):
        print("❌ Please set environment variables:")
        print("   NEXTCLOUD_URL")
        print("   NEXTCLOUD_USERNAME")
        print("   NEXTCLOUD_PASSWORD")
        return 1

    print("="*70)
    print("Nextcloud API Integration Examples")
    print("="*70)
    print(f"Connected to: {url}")
    print(f"Username: {username}")

    while True:
        print("\n" + "="*70)
        print("Select an example:")
        print("="*70)
        print("1. Contact Search (CardDAV)")
        print("2. Unified Search (Search API)")
        print("3. Notifications Monitor (Notifications API)")
        print("4. Combined Resource Search")
        print("0. Exit")
        print()

        choice = input("Enter choice (0-4): ").strip()

        if choice == '0':
            print("\n👋 Goodbye!")
            break
        elif choice == '1':
            example_contact_search(url, username, password)
        elif choice == '2':
            example_unified_search(url, username, password)
        elif choice == '3':
            example_notifications_monitor(url, username, password)
        elif choice == '4':
            example_combined_search(url, username, password)
        else:
            print("❌ Invalid choice. Please select 0-4.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
