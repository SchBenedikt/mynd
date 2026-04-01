#!/usr/bin/env python3
"""Debug: Check available calendars and task lists"""

import sys
sys.path.insert(0, '.')

from backend.features.tasks.simple import SimpleNextcloudTasks
from backend.features.knowledge.indexing import indexing_manager
import requests
from requests.auth import HTTPBasicAuth

# Lade Config
indexing_manager.load_nextcloud_config()
config = indexing_manager.get_config(mask_password=False)

url = config.get('url')
username = config.get('username')
password = config.get('password')

print("\n" + "="*60)
print("DEBUG: NEXTCLOUD STRUCTURE")
print("="*60 + "\n")

# Test 1: Direct WebDAV request zum Calendars-Verzeichnis
print("1️⃣  Alle Kalender und Listen:")
print("-" * 60)

base_url = f"{url}/remote.php/dav"
session = requests.Session()
session.auth = HTTPBasicAuth(username, password)

try:
    url_calendars = f"{base_url}/calendars/{username}/"
    response = session.request('PROPFIND', url_calendars, timeout=10)
    
    if response.status_code in [207, 200]:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        
        namespaces = {
            'd': 'DAV:',
            'cs': 'http://calendarserver.org/ns/',
        }
        
        for resp_elem in root.findall('.//d:response', namespaces):
            href_elem = resp_elem.find('d:href', namespaces)
            if href_elem is not None:
                href = href_elem.text
                # Get resourcetype to identify if it's a calendar/tasklist
                rt = resp_elem.find('.//d:resourcetype', namespaces)
                is_calendar = rt is not None and 'calendar' in ET.tostring(rt).decode()
                is_task = rt is not None and 'tasks' in ET.tostring(rt).decode()
                
                if 'calendar' in href or 'tasks' in href:
                    item_type = 'Tasks' if 'tasks' in href else 'Calendar'
                    print(f"  {item_type}: {href}")
    else:
        print(f"  Error: {response.status_code}")
except Exception as e:
    print(f"  Error: {e}")

print("\n2️⃣  Versuche einzelne Task-Listen direkt abzurufen:")
print("-" * 60)

# Test 2: Check different task list names
task_list_names = ['tasks', 'Todos', 'todo', 'Task list', 'My tasks', 'Work']
for list_name in task_list_names:
    try:
        url_tasks = f"{base_url}/calendars/{username}/{list_name}/"
        response = session.request('PROPFIND', url_tasks, timeout=5)
        
        if response.status_code in [207, 200]:
            print(f"  ✅ {list_name}: GEFUNDEN ({response.status_code})")
            
            # Parse and count items
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            responses = root.findall('.//d:response', {'d': 'DAV:'})
            items = [r for r in responses if r.find('.//d:href', {'d': 'DAV:'}).text.endswith('.ics')]
            print(f"      Items: {len(items)}")
        elif response.status_code == 404:
            pass  # Not found, skip
    except:
        pass

print("\n" + "="*60 + "\n")
