#!/usr/bin/env python3
"""
Simple unit test for the authentication plugin system
Tests only the auth components without external dependencies
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.features.integration.auth_manager import get_auth_manager, AuthManager
from backend.features.integration.auth_provider import AuthProvider
from backend.features.integration.auth_basic import BasicAuthProvider


def test_auth_provider_interface():
    """Test the base AuthProvider interface"""
    print("\n" + "="*60)
    print("Test 1: AuthProvider Interface")
    print("="*60)

    # Create a basic auth provider
    config = {'username': 'testuser', 'password': 'testpass'}
    provider = BasicAuthProvider(config)

    # Test methods
    assert provider.get_provider_name() == 'basic', "Provider name should be 'basic'"
    print("✓ Provider name: 'basic'")

    assert provider.validate_config() == True, "Config should be valid"
    print("✓ Config validation passed")

    auth = provider.get_auth()
    assert auth is not None, "Auth object should not be None"
    print(f"✓ Auth object created: {type(auth).__name__}")

    print(f"✓ Provider repr: {provider}")

    return True


def test_basic_auth_provider():
    """Test BasicAuthProvider"""
    print("\n" + "="*60)
    print("Test 2: BasicAuthProvider")
    print("="*60)

    # Test valid configuration
    config = {'username': 'user1', 'password': 'pass1'}
    provider = BasicAuthProvider(config)

    assert provider.username == 'user1', "Username should match"
    print("✓ Username extracted correctly")

    assert provider.password == 'pass1', "Password should match"
    print("✓ Password extracted correctly")

    # Test invalid configuration - missing username
    print("\nTesting invalid config (missing username)...")
    invalid_config1 = {'password': 'pass1'}
    provider1 = BasicAuthProvider(invalid_config1)
    assert provider1.validate_config() == False, "Should fail validation without username"
    print("✓ Correctly rejected missing username")

    # Test invalid configuration - missing password
    print("\nTesting invalid config (missing password)...")
    invalid_config2 = {'username': 'user1'}
    provider2 = BasicAuthProvider(invalid_config2)
    assert provider2.validate_config() == False, "Should fail validation without password"
    print("✓ Correctly rejected missing password")

    return True


def test_auth_manager():
    """Test AuthManager"""
    print("\n" + "="*60)
    print("Test 3: AuthManager")
    print("="*60)

    # Get auth manager
    auth_manager = get_auth_manager()
    assert auth_manager is not None, "Auth manager should not be None"
    print("✓ Auth manager created")

    # Check registered providers
    providers = auth_manager.get_registered_providers()
    assert 'basic' in providers, "Basic provider should be registered"
    print(f"✓ Registered providers: {providers}")

    # Create basic auth provider
    provider = auth_manager.create_basic_auth('testuser', 'testpass')
    assert provider is not None, "Provider should be created"
    print(f"✓ Created provider via create_basic_auth: {provider}")

    # Test create_provider method
    provider2 = auth_manager.create_provider('basic', {
        'username': 'user2',
        'password': 'pass2'
    })
    assert provider2 is not None, "Provider should be created via create_provider"
    print(f"✓ Created provider via create_provider: {provider2}")

    # Test unknown provider type
    print("\nTesting unknown provider type...")
    unknown_provider = auth_manager.create_provider('oauth2', {})
    assert unknown_provider is None, "Unknown provider should return None"
    print("✓ Correctly rejected unknown provider type")

    # Test invalid configuration
    print("\nTesting invalid configuration...")
    invalid_provider = auth_manager.create_provider('basic', {})
    assert invalid_provider is None, "Invalid config should return None"
    print("✓ Correctly rejected invalid configuration")

    return True


def test_provider_registration():
    """Test custom provider registration"""
    print("\n" + "="*60)
    print("Test 4: Custom Provider Registration")
    print("="*60)

    # Create a custom auth provider
    class CustomAuthProvider(AuthProvider):
        def get_auth(self):
            return "custom_auth"

        def get_provider_name(self):
            return "custom"

        def validate_config(self):
            return True

    # Register it
    AuthManager.register_provider('custom', CustomAuthProvider)
    print("✓ Registered custom provider")

    # Check it's registered
    auth_manager = get_auth_manager()
    providers = auth_manager.get_registered_providers()
    assert 'custom' in providers, "Custom provider should be registered"
    print(f"✓ Provider list includes custom: {providers}")

    # Create instance
    custom = auth_manager.create_provider('custom', {})
    assert custom is not None, "Custom provider should be created"
    assert custom.get_provider_name() == 'custom', "Provider name should be 'custom'"
    print(f"✓ Created custom provider: {custom}")

    return True


def test_singleton_pattern():
    """Test that auth manager is a singleton"""
    print("\n" + "="*60)
    print("Test 5: Singleton Pattern")
    print("="*60)

    manager1 = get_auth_manager()
    manager2 = get_auth_manager()

    assert manager1 is manager2, "Should return the same instance"
    print("✓ Auth manager follows singleton pattern")

    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("NEXTCLOUD AUTHENTICATION PLUGIN UNIT TESTS")
    print("="*60)

    all_passed = True

    try:
        if not test_auth_provider_interface():
            all_passed = False
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        all_passed = False

    try:
        if not test_basic_auth_provider():
            all_passed = False
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        all_passed = False

    try:
        if not test_auth_manager():
            all_passed = False
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        all_passed = False

    try:
        if not test_provider_registration():
            all_passed = False
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")
        all_passed = False

    try:
        if not test_singleton_pattern():
            all_passed = False
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
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
