#!/usr/bin/env python3
"""
Quick diagnostic to check if Backend has the /api/health endpoint
"""
import subprocess
import sys

# Check if requests module is available
try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests"])
    import requests

def check_endpoints():
    """Check if backend endpoints exist"""
    base_url = "http://localhost:5001"
    
    endpoints = [
        ("/api/health", "GET"),
        ("/api/nextcloud/loginflow/start", "POST"),
        ("/api/nextcloud/loginflow/poll", "GET"),
    ]
    
    print("\n" + "="*60)
    print("Backend Endpoint Check")
    print("="*60 + "\n")
    
    for endpoint, method in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            print(f"[{method}] {url}")
            
            if method == "GET":
                response = requests.get(url, timeout=2)
            else:
                response = requests.post(url, timeout=2)
            
            print(f"  ✓ Status: {response.status_code}")
            
        except requests.exceptions.ConnectionError:
            print(f"  ✗ Connection refused - Backend läuft nicht?")
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    check_endpoints()
