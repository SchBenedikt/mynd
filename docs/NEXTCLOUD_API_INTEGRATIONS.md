# Nextcloud API Integrations

This document describes the new Nextcloud API integrations added to the mynd application.

## Overview

Four new Nextcloud API clients have been implemented, plus WebDAV write operations:

1. **CardDAV Client** - Manage contacts and addressbooks
2. **Search API Client** - Unified search across Nextcloud resources
3. **Notifications API Client** - Access and manage notifications
4. **Activity API Client** - Access activity stream (What's new on Nextcloud)
5. **WebDAV Write Operations** - Create, upload, delete, move, copy files and folders

## 1. CardDAV Client

**File:** `backend/features/integration/carddav_client.py`

### Purpose
Provides access to Nextcloud contacts via the CardDAV protocol.

### Key Features
- Test CardDAV connection
- List all addressbooks
- Get contacts from addressbooks
- Search contacts by name, email, or organization
- Get specific contact by ID
- Parse vCard format

### Usage Example

```python
from backend.features.integration import NextcloudCardDAVClient

# Initialize client
client = NextcloudCardDAVClient(
    url="https://cloud.example.com",
    username="your-username",
    password="your-password"
)

# Test connection
if client.test_connection():
    print("Connected successfully")

# Get all addressbooks
addressbooks = client.get_addressbooks()
for ab in addressbooks:
    print(f"Addressbook: {ab['display_name']}")

# Get contacts from default addressbook
contacts = client.get_contacts('contacts')
for contact in contacts:
    print(f"Name: {contact['full_name']}")
    print(f"Email: {', '.join(contact['email'])}")

# Search for contacts
results = client.search_contacts('john')
```

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `test_connection()` | Test CardDAV connection | bool |
| `get_addressbooks()` | List all addressbooks | List[Dict] |
| `get_contacts(addressbook_name)` | Get contacts from addressbook | List[Dict] |
| `search_contacts(query, addressbook_name)` | Search contacts | List[Dict] |
| `get_contact_by_id(contact_id, addressbook_name)` | Get specific contact | Dict \| None |

### Contact Dictionary Structure

```python
{
    'id': 'contact-123',
    'url': 'https://cloud.example.com/...',
    'full_name': 'John Doe',
    'given_name': 'John',
    'family_name': 'Doe',
    'organization': 'Example Corp',
    'email': ['john@example.com', 'john.doe@work.com'],
    'phone': ['+1234567890'],
    'address': ['123 Main St...'],
    'note': 'Some notes',
    'raw_vcard': 'BEGIN:VCARD...'
}
```

## 2. Search API Client

**File:** `backend/features/integration/search_client.py`

### Purpose
Provides unified search across all Nextcloud resources (files, contacts, calendar, tasks, etc.).

### Key Features
- Test Search API connection
- List available search providers
- Unified search across all providers
- Provider-specific searches (files, contacts, calendar, tasks)
- WebDAV SEARCH method support
- Pagination support

### Usage Example

```python
from backend.features.integration import NextcloudSearchClient

# Initialize client
client = NextcloudSearchClient(
    url="https://cloud.example.com",
    username="your-username",
    password="your-password"
)

# Test connection
if client.test_connection():
    print("Connected successfully")

# Get available search providers
providers = client.get_search_providers()
for provider in providers:
    print(f"Provider: {provider['name']}")

# Unified search across all providers
results = client.search('meeting notes', limit=10)
for result in results['results']:
    print(f"[{result['provider']}] {result['title']}")
    print(f"  {result['subline']}")
    print(f"  Link: {result['resource_url']}")

# Search only files
file_results = client.search_files('document', limit=5)

# Search only contacts
contact_results = client.search_contacts('john', limit=5)

# Search only calendar events
calendar_results = client.search_calendar('meeting', limit=5)

# Search using WebDAV SEARCH method
webdav_results = client.search_files_webdav('project', path='/', limit=100)
```

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `test_connection()` | Test Search API connection | bool |
| `get_search_providers()` | List available search providers | List[Dict] |
| `search(query, provider, limit, cursor)` | Unified search | Dict |
| `search_files(query, limit)` | Search only files | List[Dict] |
| `search_contacts(query, limit)` | Search only contacts | List[Dict] |
| `search_calendar(query, limit)` | Search only calendar events | List[Dict] |
| `search_tasks(query, limit)` | Search only tasks | List[Dict] |
| `search_files_webdav(query, path, limit)` | WebDAV SEARCH method | List[Dict] |

### Search Result Structure

```python
{
    'query': 'search query',
    'results': [
        {
            'provider': 'files',
            'title': 'Document.pdf',
            'subline': 'Modified yesterday',
            'resource_url': 'https://cloud.example.com/...',
            'icon': 'icon-url',
            'rounded': False,
            'thumbnailUrl': 'thumbnail-url',
            'attributes': {}
        }
    ],
    'cursor': 'next-page-cursor'
}
```

## 3. Notifications API Client

**File:** `backend/features/integration/notifications_client.py`

### Purpose
Provides access to Nextcloud notifications via the OCS API.

### Key Features
- Test Notifications API connection
- Get all notifications
- Get specific notification by ID
- Delete notifications
- Delete all notifications
- Get unread count
- Filter notifications by app, type, or date
- Send admin notifications (requires admin privileges)
- Get notification capabilities

### Usage Example

```python
from backend.features.integration import NextcloudNotificationsClient

# Initialize client
client = NextcloudNotificationsClient(
    url="https://cloud.example.com",
    username="your-username",
    password="your-password"
)

# Test connection
if client.test_connection():
    print("Connected successfully")

# Get all notifications
notifications = client.get_notifications()
for notif in notifications:
    print(f"[{notif['app']}] {notif['subject']}")
    print(f"  {notif['message']}")
    print(f"  Time: {notif['datetime']}")

# Get unread count
unread = client.get_unread_count()
print(f"Unread notifications: {unread}")

# Filter notifications
from datetime import datetime, timedelta
recent = client.filter_notifications(
    app='files',
    since=datetime.now() - timedelta(days=7)
)

# Get specific notification
notif = client.get_notification(notification_id=123)

# Delete notification
client.delete_notification(notification_id=123)

# Delete all notifications
client.delete_all_notifications()

# Get capabilities
capabilities = client.get_notification_capabilities()
```

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `test_connection()` | Test Notifications API connection | bool |
| `get_notifications()` | Get all notifications | List[Dict] |
| `get_notification(notification_id)` | Get specific notification | Dict \| None |
| `delete_notification(notification_id)` | Delete notification | bool |
| `delete_all_notifications()` | Delete all notifications | bool |
| `get_unread_count()` | Get unread count | int |
| `filter_notifications(app, object_type, since)` | Filter notifications | List[Dict] |
| `send_admin_notification(user_id, short_message, long_message)` | Send admin notification | bool |
| `get_notification_capabilities()` | Get capabilities | Dict |

### Notification Structure

```python
{
    'id': 123,
    'app': 'files',
    'user': 'username',
    'datetime': '2026-03-31T12:00:00+00:00',
    'object_type': 'files',
    'object_id': '456',
    'subject': 'File was shared',
    'message': 'User shared document.pdf with you',
    'link': 'https://cloud.example.com/...',
    'icon': 'icon-url',
    'actions': []
}
```

## 4. Activity API Client

**File:** `backend/features/integration/activity_client.py`

### Purpose
Provides access to Nextcloud Activity stream - answering questions like "What's new on my Nextcloud?"

### Key Features
- Test Activity API connection
- Get activity stream with filters
- Get available activity filters
- Get activities by filter type
- Activity summary and statistics
- Filter by app, type, object
- Pagination support

### Usage Example

```python
from backend.features.integration import NextcloudActivityClient

# Initialize client
client = NextcloudActivityClient(
    url="https://cloud.example.com",
    username="your-username",
    password="your-password"
)

# Test connection
if client.test_connection():
    print("Connected successfully")

# Get recent activities (What's new?)
recent = client.get_recent_activities(limit=10)
for activity in recent:
    print(f"[{activity['app']}] {activity['subject']}")
    print(f"  Time: {activity['datetime']}")

# Get activity summary
summary = client.get_activity_summary(limit=50)
print(f"Total activities: {summary['total']}")
print(f"By app: {summary['by_app']}")
print(f"By type: {summary['by_type']}")

# Get available filters
filters = client.get_filters()
for f in filters:
    print(f"Filter: {f['name']} (id: {f['id']})")

# Get activities by specific filter
result = client.get_activity_by_filter('all', limit=20)
activities = result['activities']

# Get full activity stream with pagination
result = client.get_activity(limit=50, sort='desc')
for activity in result['activities']:
    print(activity['subject'])

# Filter by object
result = client.get_activity(
    object_type='files',
    object_id='123',
    limit=10
)
```

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `test_connection()` | Test Activity API connection | bool |
| `get_activity(limit, since, sort, object_type, object_id)` | Get activity stream | Dict |
| `get_activity_by_filter(filter_id, limit, since, sort)` | Get filtered activities | Dict |
| `get_filters()` | Get available filters | List[Dict] |
| `get_recent_activities(limit)` | Convenience method for recent activities | List[Dict] |
| `get_activities_by_app(app, limit)` | Filter activities by app | List[Dict] |
| `get_activities_by_type(activity_type, limit)` | Filter activities by type | List[Dict] |
| `get_activity_summary(limit)` | Get summary statistics | Dict |

### Activity Structure

```python
{
    'activity_id': 12345,
    'datetime': '2026-03-31T10:30:00+00:00',
    'timestamp': datetime_object,
    'app': 'files',
    'type': 'file_created',
    'user': 'admin',
    'subject': 'You created document.pdf',
    'subject_rich': {
        '0': 'You created {file}',
        '1': {'file': {'type': 'file', 'id': 42, 'name': 'document.pdf'}}
    },
    'message': '',
    'message_rich': {},
    'icon': 'https://cloud.example.com/apps/files/img/add-color.svg',
    'link': 'https://cloud.example.com/index.php/f/42',
    'object_type': 'files',
    'object_id': 42,
    'object_name': '/documents/document.pdf',
    'objects': {},
    'previews': []
}
```

### Activity Result Structure

```python
{
    'activities': [...],  # List of activity dictionaries
    'since': 0,           # Last activity ID seen
    'first_known': 100,   # First known activity ID
    'last_given': 150,    # Last activity ID in this response
    'has_more': True      # Whether more activities are available
}
```

## 5. WebDAV Write Operations (NextcloudClient)

**File:** `backend/features/integration/nextcloud_client.py`

### Purpose
The NextcloudClient has been enhanced with WebDAV write operations to enable file creation, manipulation, and organization.

### Key Features
- Upload files from local filesystem or text content
- Create folders
- Delete files and folders
- Move and copy files
- Mark/unmark files as favorites
- List favorite files

### Usage Example

```python
from backend.features.integration import NextcloudClient

# Initialize client
client = NextcloudClient(
    url="https://cloud.example.com",
    username="your-username",
    password="your-password"
)

# Upload a file
client.upload_file('/local/path/document.pdf', '/Documents/document.pdf')

# Upload text content directly
client.upload_content('Hello World!', '/Documents/hello.txt')

# Create a folder
client.create_folder('/Documents/NewFolder')

# Move a file
client.move_file('/Documents/old.txt', '/Documents/new.txt')

# Copy a file
client.copy_file('/Documents/file.txt', '/Backup/file.txt')

# Mark as favorite
client.set_favorite('/Documents/important.txt', favorite=True)

# List all favorites
favorites = client.list_favorites()
for fav in favorites:
    print(f"{fav['name']} - {fav['size']} bytes")

# Delete a file
client.delete_file('/Documents/old_file.txt')
```

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `upload_file(local_path, remote_path, overwrite)` | Upload file from local filesystem | bool |
| `upload_content(content, remote_path, overwrite)` | Upload text content directly | bool |
| `create_folder(remote_path)` | Create a folder | bool |
| `delete_file(remote_path)` | Delete file or folder | bool |
| `move_file(source_path, destination_path, overwrite)` | Move file or folder | bool |
| `copy_file(source_path, destination_path, overwrite)` | Copy file or folder | bool |
| `set_favorite(remote_path, favorite)` | Mark/unmark as favorite | bool |
| `list_favorites(remote_path)` | List favorite files | List[Dict] |

### WebDAV Operations Reference

These methods implement standard WebDAV operations:

- **PUT** - Upload files (RFC 4918)
- **MKCOL** - Create folders (RFC 4918)
- **DELETE** - Delete files/folders (RFC 4918)
- **MOVE** - Move files/folders (RFC 4918)
- **COPY** - Copy files/folders (RFC 4918)
- **PROPPATCH** - Set properties like favorites (RFC 4918)
- **REPORT** - Query with filters like favorites (RFC 3253)

All operations use HTTP Basic Authentication and follow Nextcloud's WebDAV endpoint structure: `/remote.php/dav/files/{username}/`

## Testing

A comprehensive test script is provided: `test_nextcloud_apis.py`

### Running Tests

```bash
# Set environment variables
export NEXTCLOUD_URL="https://cloud.example.com"
export NEXTCLOUD_USERNAME="your-username"
export NEXTCLOUD_PASSWORD="your-password"

# Run tests
python3 test_nextcloud_apis.py
```

The test script will:
1. Test each API client connection
2. Verify basic functionality
3. Display sample results
4. Provide a summary report

## Integration with mynd

These clients can be integrated into the mynd application in several ways:

### 1. Contact Search Integration
```python
# Use CardDAV client to search contacts and include in knowledge base
carddav = NextcloudCardDAVClient(url, username, password)
contacts = carddav.search_contacts('john')
# Include contact information in AI responses
```

### 2. Unified Search Integration
```python
# Use Search API for intelligent search across all resources
search = NextcloudSearchClient(url, username, password)
results = search.search('meeting notes')
# Present results to user with sources
```

### 3. Notification Monitoring
```python
# Use Notifications API to stay updated on changes
notifications = NextcloudNotificationsClient(url, username, password)
unread = notifications.get_notifications()
# Show notifications in UI or process automatically
```

### 4. Activity Stream Integration
```python
# Use Activity API to answer "What's new on my Nextcloud?"
activity = NextcloudActivityClient(url, username, password)
recent = activity.get_recent_activities(limit=20)
# Present recent activities to user or use in AI context
```

## API Endpoints

### CardDAV
- Base: `/remote.php/dav/addressbooks/users/{username}/`
- Protocol: WebDAV with CardDAV extensions
- Methods: PROPFIND, GET, PUT, DELETE, REPORT
- Response: XML (vCard format)

### Search API
- Base: `/ocs/v2.php/search`
- Protocol: OCS API v2
- Methods: GET
- Response: JSON
- Alternative: WebDAV SEARCH method at `/remote.php/dav/files/{username}/`

### Notifications API
- Base: `/ocs/v2.php/apps/notifications/api/v2/`
- Protocol: OCS API v2
- Methods: GET, POST, DELETE
- Response: JSON

### Activity API
- Base: `/ocs/v2.php/apps/activity/api/v2/`
- Protocol: OCS API v2
- Methods: GET
- Response: JSON
- Endpoints:
  - `/ocs/v2.php/apps/activity/api/v2/activity` - Get all activities
  - `/ocs/v2.php/apps/activity/api/v2/activity/{filter}` - Get filtered activities
  - `/ocs/v2.php/apps/activity/api/v2/activity/filters` - Get available filters

## Error Handling

All clients implement consistent error handling:

- Connection errors are logged and return False/empty results
- Timeouts are handled gracefully
- HTTP status codes are checked and logged
- XML/JSON parsing errors are caught
- Detailed error messages are logged for debugging

## Authentication

All clients use HTTP Basic Authentication via `requests.Session`:

```python
self.session = requests.Session()
self.session.auth = HTTPBasicAuth(username, password)
```

For production use, consider using Nextcloud app passwords instead of the main password.

## Dependencies

Required Python packages:
- `requests` - HTTP client
- `xml.etree.ElementTree` - XML parsing (built-in)
- `logging` - Logging (built-in)

## Future Enhancements

Potential improvements:

1. **CardDAV**: Support for creating/updating/deleting contacts
2. **Search**: Advanced filtering and sorting options
3. **Notifications**: Push notification support
4. **All**: Async/await support for better performance
5. **All**: Caching to reduce API calls
6. **All**: Batch operations
7. **All**: OAuth2 authentication support

## References

- [Nextcloud CardDAV Documentation](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/CardDAV/index.html)
- [Nextcloud OCS API](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/OCS/index.html)
- [Nextcloud Search API](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/OCS/ocs-search-api.html)
- [Nextcloud Notifications API](https://github.com/nextcloud/notifications/blob/master/docs/ocs-endpoint-v2.md)
