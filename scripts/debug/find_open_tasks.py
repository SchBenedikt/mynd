#!/usr/bin/env python3
"""Find open/incomplete tasks"""

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

print("Suche nach OFFENEN Tasks...\n")

url_tasks = f"{base_url}/calendars/{username}/todo/"
response = session.request('PROPFIND', url_tasks, timeout=10)

import xml.etree.ElementTree as ET
root = ET.fromstring(response.text)

paths = []
for response_elem in root.findall('.//d:response', {'d': 'DAV:'}):
    href_elem = response_elem.find('.//d:href', {'d': 'DAV:'})
    if href_elem is not None and href_elem.text.endswith('.ics'):
        paths.append(href_elem.text)

print(f"Total Tasks: {len(paths)}\n")

completed_count = 0
open_count = 0
open_tasks = []

for i, ics_path in enumerate(paths[:50]):
    try:
        ics_url = f"{url}{ics_path}"
        ics_response = session.get(ics_url, timeout=1)
        
        if ics_response.status_code == 200:
            text = ics_response.text
            is_completed = 'STATUS:COMPLETED' in text
            
            if is_completed:
                completed_count += 1
            else:
                open_count += 1
                import re
                match = re.search(r'SUMMARY:(.+?)(?:\r?\n|$)', text)
                if match:
                    open_tasks.append(match.group(1)[:60])
    except:
        pass

print(f"Geladen: {completed_count} abgehakt, {open_count} offen\n")

if open_tasks:
    print("OFFENE TASKS:")
    for task in open_tasks:
        print(f"  - {task}")
else:
    print("Keine offenen Tasks in den ersten 50!")
