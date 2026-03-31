#!/usr/bin/env python3
import os
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IMMICH_URL = os.getenv("IMMICH_URL", "").strip()
IMMICH_KEY = os.getenv("IMMICH_API_KEY", "").strip()

if not IMMICH_URL or not IMMICH_KEY:
    raise SystemExit(
        "Bitte IMMICH_URL und IMMICH_API_KEY als Umgebungsvariablen setzen."
    )

headers = {
    'X-Api-Key': IMMICH_KEY,
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

# Try more endpoints
endpoints = [
    "/api/library/statistics",
    "/api/asset/statistics",
    "/api/photos",
    "/api/library",
    "/api/user",
    "/api/users",
]

print("Trying more endpoints...\n")
for endpoint in endpoints:
    try:
        r = requests.get(f"{IMMICH_URL}{endpoint}", headers=headers, timeout=5, verify=False)
        print(f"{endpoint:<40} -> {r.status_code} {r.reason}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                print(f"   Sample: {json.dumps(data[0], indent=2)[:200]}")
            elif isinstance(data, dict):
                print(f"   Keys: {list(data.keys())}")
            print()
    except Exception as e:
        print(f"{endpoint:<40} -> ERROR: {str(e)[:30]}")

# Try to get album by ID
print("\n\nGetting assets from first album...")
try:
    r = requests.get(f"{IMMICH_URL}/api/albums", headers=headers, timeout=5, verify=False)
    if r.status_code == 200:
        albums = r.json()
        if albums:
            album_id = albums[0]['id']
            print(f"Album ID: {album_id}")
            
            # Try to get album details
            r2 = requests.get(f"{IMMICH_URL}/api/albums/{album_id}", headers=headers, timeout=5, verify=False)
            if r2.status_code == 200:
                album = r2.json()
                print(f"Album structure: {json.dumps(album, indent=2)[:600]}")
except Exception as e:
    print(f"Error: {e}")

# Try downloading assets endpoint
print("\n\nTrying asset-related endpoints...")
asset_endpoints = [
    "/api/asset/info",
    "/api/asset",
    "/api/asset/file",
    "/api/asset/download",
    "/api/sharedLinks",
]

for endpoint in asset_endpoints:
    try:
        r = requests.get(f"{IMMICH_URL}{endpoint}", headers=headers, timeout=2, verify=False)
        print(f"{endpoint:<40} -> {r.status_code} {r.reason}")
    except requests.exceptions.Timeout:
        print(f"{endpoint:<40} -> TIMEOUT")
    except Exception as e:
        print(f"{endpoint:<40} -> {str(e)[:30]}")
