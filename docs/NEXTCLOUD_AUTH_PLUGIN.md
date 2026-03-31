# Nextcloud Authentication Plugin System

## Overview

The Nextcloud Authentication Plugin System provides a flexible, extensible architecture for authenticating with Nextcloud services. It allows different authentication methods to be used interchangeably across all Nextcloud integration components (Files, Tasks, Calendar).

## Architecture

The authentication system consists of three main components:

1. **AuthProvider** - Base interface for all authentication providers
2. **BasicAuthProvider** - HTTP Basic Authentication implementation
3. **AuthManager** - Manages provider registration and instantiation

## Components

### AuthProvider (Interface)

Located in: `backend/features/integration/auth_provider.py`

Base abstract class that all authentication providers must implement:

```python
from backend.features.integration.auth_provider import AuthProvider

class MyAuthProvider(AuthProvider):
    def get_auth(self):
        """Return authentication object for requests library"""
        pass

    def get_provider_name(self):
        """Return provider name as string"""
        pass

    def validate_config(self):
        """Validate configuration, return True if valid"""
        pass
```

### BasicAuthProvider

Located in: `backend/features/integration/auth_basic.py`

Implements HTTP Basic Authentication using username and password:

```python
from backend.features.integration.auth_manager import get_auth_manager

# Create basic auth provider
auth_manager = get_auth_manager()
auth_provider = auth_manager.create_basic_auth('username', 'password')
```

### AuthManager

Located in: `backend/features/integration/auth_manager.py`

Central manager for authentication providers:

```python
from backend.features.integration.auth_manager import get_auth_manager

# Get the singleton instance
auth_manager = get_auth_manager()

# List available providers
providers = auth_manager.get_registered_providers()  # ['basic']

# Create a provider
auth_provider = auth_manager.create_provider('basic', {
    'username': 'user',
    'password': 'pass'
})

# Convenience method for basic auth
auth_provider = auth_manager.create_basic_auth('user', 'pass')
```

## Usage

### Using with NextcloudClient

```python
from backend.features.integration.nextcloud_client import NextcloudClient
from backend.features.integration.auth_manager import get_auth_manager

# Method 1: Using auth provider (recommended)
auth_manager = get_auth_manager()
auth_provider = auth_manager.create_basic_auth('username', 'password')
client = NextcloudClient('https://cloud.example.com', auth_provider=auth_provider)

# Method 2: Using username/password directly (backward compatible)
client = NextcloudClient('https://cloud.example.com',
                        username='username',
                        password='password')
```

### Using with SimpleNextcloudTasks

```python
from backend.features.tasks.simple import SimpleNextcloudTasks
from backend.features.integration.auth_manager import get_auth_manager

# Method 1: Using auth provider
auth_manager = get_auth_manager()
auth_provider = auth_manager.create_basic_auth('username', 'password')
tasks = SimpleNextcloudTasks('https://cloud.example.com', auth_provider=auth_provider)

# Method 2: Backward compatible
tasks = SimpleNextcloudTasks('https://cloud.example.com',
                             username='username',
                             password='password')
```

### Using with SimpleNextcloudCalendar

```python
from backend.features.calendar.simple import SimpleNextcloudCalendar
from backend.features.integration.auth_manager import get_auth_manager

# Method 1: Using auth provider
auth_manager = get_auth_manager()
auth_provider = auth_manager.create_basic_auth('username', 'password')
calendar = SimpleNextcloudCalendar('https://cloud.example.com', auth_provider=auth_provider)

# Method 2: Backward compatible
calendar = SimpleNextcloudCalendar('https://cloud.example.com',
                                  username='username',
                                  password='password')
```

## Extending with Custom Authentication

You can add new authentication methods by creating a custom provider:

### 1. Create a Custom Provider

```python
from backend.features.integration.auth_provider import AuthProvider
from typing import Dict, Any

class OAuth2Provider(AuthProvider):
    """OAuth2 Authentication Provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_token = config.get('access_token', '')

    def get_auth(self):
        """Return OAuth2 auth for requests"""
        from requests.auth import AuthBase

        class BearerAuth(AuthBase):
            def __init__(self, token):
                self.token = token

            def __call__(self, r):
                r.headers["Authorization"] = f"Bearer {self.token}"
                return r

        return BearerAuth(self.access_token)

    def get_provider_name(self):
        return 'oauth2'

    def validate_config(self):
        if not self.access_token:
            self.logger.error("Access token is required for OAuth2")
            return False
        return True
```

### 2. Register the Provider

```python
from backend.features.integration.auth_manager import AuthManager

# Register the custom provider
AuthManager.register_provider('oauth2', OAuth2Provider)
```

### 3. Use the Custom Provider

```python
from backend.features.integration.auth_manager import get_auth_manager
from backend.features.integration.nextcloud_client import NextcloudClient

# Create the custom provider
auth_manager = get_auth_manager()
auth_provider = auth_manager.create_provider('oauth2', {
    'access_token': 'your-oauth-token-here'
})

# Use it with any Nextcloud client
client = NextcloudClient('https://cloud.example.com', auth_provider=auth_provider)
```

## Backward Compatibility

All existing code using username/password authentication will continue to work without modification. The authentication plugin system automatically creates a BasicAuthProvider when username and password are provided:

```python
# This still works!
client = NextcloudClient('https://cloud.example.com',
                        username='user',
                        password='pass')

# Internally, it creates: BasicAuthProvider({'username': 'user', 'password': 'pass'})
```

## Testing

Run the unit tests to verify the authentication system:

```bash
# Run unit tests (no external dependencies required)
python test_auth_unit.py

# Run integration tests (requires .env with Nextcloud credentials)
python test_auth_plugin.py
```

## Benefits

1. **Extensibility** - Easy to add new authentication methods (OAuth2, API tokens, etc.)
2. **Consistency** - Same authentication interface across all Nextcloud integrations
3. **Flexibility** - Swap authentication methods without changing client code
4. **Backward Compatible** - Existing code continues to work
5. **Testability** - Authentication can be mocked/stubbed for testing
6. **Future-Proof** - Ready for additional authentication methods as Nextcloud evolves

## Future Enhancements

Potential future authentication providers:

- **OAuth2Provider** - OAuth2/OpenID Connect authentication
- **AppPasswordProvider** - Dedicated app password handling
- **TokenProvider** - API token-based authentication
- **CertificateProvider** - Certificate-based authentication
- **KerberosProvider** - Kerberos/SSO authentication

## Files Added

- `backend/features/integration/auth_provider.py` - Base AuthProvider interface
- `backend/features/integration/auth_basic.py` - Basic authentication implementation
- `backend/features/integration/auth_manager.py` - Authentication manager
- `test_auth_unit.py` - Unit tests for authentication system
- `test_auth_plugin.py` - Integration tests with Nextcloud
- `docs/NEXTCLOUD_AUTH_PLUGIN.md` - This documentation

## Files Modified

- `backend/features/integration/nextcloud_client.py` - Updated to use auth providers
- `backend/features/tasks/simple.py` - Updated to use auth providers
- `backend/features/calendar/simple.py` - Updated to use auth providers
