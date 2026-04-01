#!/usr/bin/env python3
"""Inspect actual ICS file format"""

import sys
sys.path.insert(0, '.')

from backend.features.knowledge.indexing import indexing_manager
import requests
from requests.auth import HTTPBasicAuth

indexing_manager.load_nextcloud_config()
config = indexing_manager.get_config(mask_password=False)

url = config.get('url')
username = config.get('username')
password = config.get('password')

base_url = f"{url}/remote.php/dav"
session = requests.Session()
session.auth = HTTPBasicAuth(username, password)

print("Lade erste Task-ICS-Datei...\n")

# Hole erste Task-Pfade
url_tasks = f"{base_url}/calendars/{username}/todo/"
response = session.request('PROPFIND', url_tasks, timeout=10)

import xml.etree.ElementTree as ET
root = ET.fromstring(response.text)

paths = []
for response_elem in root.findall('.//d:response', {'d': 'DAV:'}):
    href_elem = response_elem.find('.//d:href', {'d': 'DAV:'})
    if href_elem is not None and href_elem.text.endswith('.ics'):
        paths.append(href_elem.text)

if paths:
    ics_path = paths[0]
    ics_url = f"{url}{ics_path}"
    ics_response = session.get(ics_url, timeout=2)
    
    if ics_response.status_code == 200:
        text = ics_response.text
        print(text[:1200])
        print("\n... (gekürzt) ...\n")
        
        print("="*60)
        print("CHECKS:")
        print("="*60)
        print(f"Hat COMPLETED: {'STATUS:COMPLETED' in text}")
        print(f"Hat VEVENT (Ereignis): {'BEGIN:VEVENT' in text}")
        print(f"Hat VTODO (Todo): {'BEGIN:VTODO' in text}")
        print(f"Hat SUMMARY: {'SUMMARY:' in text}")
        print(f"Hat DUE: {'DUE' in text}")
        
        # Extract SUMMARY
        import re
        match = re.search(r'SUMMARY:(.+?)(?:\r?\n|$)', text)
        if match:
            print(f"\nSUMMARY: {match.group(1)[:80]}")
else:
    print("Keine Tasks gefunden!")
