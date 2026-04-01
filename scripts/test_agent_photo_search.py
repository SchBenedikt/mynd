#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')

from core.app import load_ai_config, load_user_config, get_immich_client
import json

print("=== Testing Agent Photo Search ===\n")

# Load config
print("1. Loading configs...")
ai_config = load_ai_config()
print(f"   Immich URL: {ai_config.get('immich_url_default', 'Not set')[:50]}")
print(f"   Immich API Key configured: {bool(ai_config.get('immich_api_key_default'))}")

# Get immich client
print("\n2. Creating Immich client...")
client = get_immich_client("default")
if client:
    print(f"   ✓ Client created")
    print(f"   URL: {client.url}")
    
    # Test search
    print("\n3. Testing search_photos_intelligent...")
    result = client.search_photos_intelligent("Isabelle", limit=5)
    print(f"   Success: {result.get('success')}")
    print(f"   Count: {result.get('count')}")
    print(f"   Results: {len(result.get('results', []))}")
    if result.get('results'):
        print(f"   First result: {json.dumps(result['results'][0], indent=2)[:200]}")
else:
    print("   ✗ Failed to create client")
