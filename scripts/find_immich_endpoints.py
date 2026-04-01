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

print("Testing different API endpoints to find the correct ones...\n")

# Test various endpoints for Immich
endpoints = [
    "/api/server/info",
    "/api/server-info",
    "/api/people",
    "/api/person",
    "/api/asset",
    "/api/assets",
    "/api/server/statistics",
    "/api/statistics",
    "/api/search/metadata",
    "/api/search/smart",
    "/api/asset/search",
    "/api/photos",
    "/api/albums",
    "/api/cine",
]

for endpoint in endpoints:
    try:
        r = requests.get(f"{IMMICH_URL}{endpoint}", headers=headers, timeout=5, verify=False)
        print(f"{endpoint:<40} -> {r.status_code} {r.reason}")
    except Exception as e:
        print(f"{endpoint:<40} -> ERROR: {str(e)[:50]}")

# Test /api/people endpoint
print("\n\nGetting people from /api/people:")
try:
    r = requests.get(f"{IMMICH_URL}/api/people", headers=headers, timeout=5, verify=False)
    if r.status_code == 200:
        data = r.json()
        print(f"Success! Response structure: {json.dumps(data, indent=2)[:500]}")
except Exception as e:
    print(f"Error: {e}")
