#!/usr/bin/env python3
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IMMICH_URL = "https://fotos.xn--schchner-2za.de"
IMMICH_KEY = "r8hRtGPc8CvdLD08PTFc97sW9o7NHsPl9aFPm0qvQ"

headers = {
    'X-Api-Key': IMMICH_KEY,
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

# Get version
endpoints_version = [
    "/api/server/version",
    "/api/server/__version__",
    "/api/__version__",
    "/api/system/info",
    "/api/server/config",
]

print("Trying to get Immich version...\n")
for endpoint in endpoints_version:
    try:
        r = requests.get(f"{IMMICH_URL}{endpoint}", headers=headers, timeout=5, verify=False)
        if r.status_code == 200:
            print(f"{endpoint:<40} -> {r.status_code}")
            print(json.dumps(r.json(), indent=2))
            print()
    except Exception as e:
        pass

# Try search endpoints
print("\nTrying search endpoints...")
search_endpoints = [
    "/api/search/search",
    "/api/search",
    "/api/photos/search",
]

for endpoint in search_endpoints:
    try:
        r = requests.post(f"{IMMICH_URL}{endpoint}", headers=headers, json={"query": "test"}, timeout=5, verify=False)
        print(f"{endpoint:<40} -> {r.status_code} {r.reason}")
    except Exception as e:
        print(f"{endpoint:<40} -> {str(e)[:30]}")

# Try to get first album
print("\n\nTrying to get album content...")
try:
    r = requests.get(f"{IMMICH_URL}/api/albums", headers=headers, timeout=5, verify=False)
    if r.status_code == 200:
        albums = r.json()
        print(f"Got {len(albums)} albums")
        if albums:
            print(f"First album: {json.dumps(albums[0], indent=2)[:500]}")
except Exception as e:
    print(f"Error: {e}")
