#!/usr/bin/env python3
import requests
import json
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IMMICH_URL = "https://fotos.xn--schchner-2za.de"
IMMICH_KEY = "r8hRtGPc8CvdLD08PTFc97sW9o7NHsPl9aFPm0qvQ"

headers = {
    'X-Api-Key': IMMICH_KEY,
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

print("1. Testing ping...")
try:
    r = requests.get(f"{IMMICH_URL}/api/server/ping", headers=headers, timeout=10, verify=False)
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text}")
except Exception as e:
    print(f"   Error: {e}")

print("\n2. Getting people...")
try:
    r = requests.get(f"{IMMICH_URL}/api/person", headers=headers, timeout=10, verify=False)
    print(f"   Status: {r.status_code}")
    data = r.json()
    print(f"   People count: {len(data.get('people', []))}")
except Exception as e:
    print(f"   Error: {e}")

print("\n3. Getting assets...")
try:
    r = requests.get(f"{IMMICH_URL}/api/asset?take=5", headers=headers, timeout=10, verify=False)
    print(f"   Status: {r.status_code}")
    data = r.json()
    if isinstance(data, list):
        print(f"   Assets count: {len(data)}")
    else:
        print(f"   Response type: {type(data)}")
        print(f"   Response: {json.dumps(data)[:200]}")
except Exception as e:
    print(f"   Error: {e}")
