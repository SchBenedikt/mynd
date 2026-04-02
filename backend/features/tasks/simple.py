"""
SimpleNextcloudTasks - Minimal Nextcloud Tasks Integration über WebDAV
Unterstützt Nextcloud Tasks Plugin via WebDAV/CalDAV
"""

import requests
import logging
from typing import List, Dict, Optional, Union
from datetime import datetime
import re
from urllib.parse import unquote
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from backend.features.integration.auth_provider import AuthProvider
from backend.features.integration.auth_manager import get_auth_manager


def _unfold_ics_lines(ics_content: str) -> List[str]:
    """Unfold folded iCalendar lines according to RFC 5545."""
    lines = ics_content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    unfolded: List[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith((' ', '\t')) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def _extract_ics_property(ics_content: str, property_name: str) -> Optional[str]:
    """Return first iCalendar property value and support optional parameters."""
    prefix = property_name.upper()
    for line in _unfold_ics_lines(ics_content):
        upper = line.upper()
        if upper.startswith(prefix + ':') or upper.startswith(prefix + ';'):
            _, _, value = line.partition(':')
            return value.strip() if value is not None else None
    return None


def _extract_component_block(ics_content: str, component_name: str) -> Optional[str]:
    """Extract first iCalendar component block including nested content."""
    lines = _unfold_ics_lines(ics_content)
    begin_marker = f"BEGIN:{component_name.upper()}"
    end_marker = f"END:{component_name.upper()}"

    collecting = False
    depth = 0
    block: List[str] = []

    for line in lines:
        upper = line.upper()

        if upper == begin_marker:
            if not collecting:
                collecting = True
                block = [line]
                depth = 1
                continue
            depth += 1
            block.append(line)
            continue

        if collecting:
            block.append(line)
            if upper == end_marker:
                depth -= 1
                if depth == 0:
                    return "\n".join(block)

    return None


def _extract_alarm_trigger(vtodo_content: str) -> Optional[str]:
    """Extract reminder trigger from first VALARM inside a VTODO block."""
    alarm_block = _extract_component_block(vtodo_content, 'VALARM')
    if not alarm_block:
        return None
    return _extract_ics_property(alarm_block, 'TRIGGER')

class SimpleNextcloudTasks:
    """Einfache Nextcloud Tasks Integration über WebDAV"""

    def __init__(self, url: str, username: str = None, password: str = None, auth_provider: AuthProvider = None):
        """
        Initialize SimpleNextcloudTasks

        Args:
            url: Nextcloud server URL
            username: Username (for backward compatibility with basic auth)
            password: Password (for backward compatibility with basic auth)
            auth_provider: AuthProvider instance (recommended)
        """
        self.url = url.rstrip('/')
        self.username = username
        self.logger = logging.getLogger(__name__)
        self.base_url = f"{self.url}/remote.php/dav"
        self.session = requests.Session()

        # Set up authentication
        if auth_provider:
            self.auth_provider = auth_provider
            self.session.auth = auth_provider.get_auth()
        elif username and password:
            # Backward compatibility: create basic auth provider
            auth_manager = get_auth_manager()
            self.auth_provider = auth_manager.create_basic_auth(username, password)
            self.session.auth = self.auth_provider.get_auth()
        else:
            raise ValueError("Either auth_provider or username/password must be provided")

        # Get username from auth provider if not provided
        if not self.username:
            self.username = self.auth_provider.config.get('username', 'unknown')
    
    def test_connection(self) -> bool:
        """Testet die Verbindung zu Nextcloud Tasks"""
        try:
            # Versuche auf Tasks zu zugreifen
            url = f"{self.base_url}/calendars/{self.username}/"
            response = self.session.request('PROPFIND', url, timeout=10)
            
            if response.status_code in [207, 200]:
                self.logger.info("Nextcloud Tasks connection successful")
                return True
            else:
                self.logger.warning(f"Unexpected status code: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Tasks connection failed: {str(e)}")
            return False
    
    def get_tasks(self, list_name: str = 'tasks') -> List[Dict]:
        """
        Holt Tasks aus einer Nextcloud-Taskliste.
        Lädt alle ICS-Einträge der Liste und parsed diese robust.
        """
        tasks = []
        try:
            url = f"{self.base_url}/calendars/{self.username}/{list_name}/"
            
            # Schnelle PROPFIND um nur Namen zu sehen
            response = self.session.request('PROPFIND', url, headers={'Depth': '1'}, timeout=8)
            
            if response.status_code in [207, 200]:
                import xml.etree.ElementTree as ET
                
                try:
                    root = ET.fromstring(response.text)
                    namespaces = {
                        'd': 'DAV:',
                        'cs': 'http://calendarserver.org/ns/',
                        'c': 'urn:ietf:params:xml:ns:caldav'
                    }
                    
                    # Sammle ICS-Pfade
                    ics_paths = []
                    for response_elem in root.findall('.//d:response', namespaces):
                        href_elem = response_elem.find('d:href', namespaces)
                        if href_elem is not None and href_elem.text.endswith('.ics'):
                            ics_paths.append(href_elem.text)
                    
                    self.logger.info(f"Found {len(ics_paths)} items in {list_name}, loading tasks...")

                    for ics_path in ics_paths:
                        task_data = self._get_task_quick(ics_path)
                        if task_data:
                            tasks.append(task_data)
                    
                except Exception as e:
                    self.logger.error(f"Error parsing tasks XML: {str(e)}")
            
            # Sortiere: Zuerst unvollständige, dann abgehakte
            # Nach Fälligkeitsdatum
            open_tasks = [t for t in tasks if not t.get('completed', False)]
            completed_tasks = [t for t in tasks if t.get('completed', False)]
            
            def _due_sort_key(task: Dict) -> str:
                due = task.get('due_date')
                return due if due else '9999-12-31'

            open_tasks.sort(key=_due_sort_key)
            completed_tasks.sort(key=_due_sort_key)
            
            all_tasks = open_tasks + completed_tasks
            
            self.logger.info(f"Loaded {len(open_tasks)} open, {len(completed_tasks)} completed tasks")
            return all_tasks
            
        except Exception as e:
            self.logger.error(f"Error fetching tasks: {str(e)}")
            return []

    def get_task_lists(self) -> List[str]:
        """Liest verfuegbare Task-Listen aus Nextcloud (VTODO-Kalender)."""
        try:
            url = f"{self.base_url}/calendars/{self.username}/"
            response = self.session.request('PROPFIND', url, headers={'Depth': '1'}, timeout=8)

            if response.status_code not in [207, 200]:
                self.logger.warning(f"Could not fetch task lists: {response.status_code}")
                return []

            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            namespaces = {
                'd': 'DAV:',
                'c': 'urn:ietf:params:xml:ns:caldav'
            }

            discovered: List[str] = []
            for response_elem in root.findall('.//d:response', namespaces):
                href_elem = response_elem.find('d:href', namespaces)
                if href_elem is None or not href_elem.text:
                    continue

                href = unquote(href_elem.text.strip())
                path_parts = [part for part in href.rstrip('/').split('/') if part]
                if not path_parts:
                    continue

                list_name = path_parts[-1]
                if list_name in [self.username, 'calendars', 'inbox', 'outbox', 'trashbin']:
                    continue

                component_names = {
                    comp.attrib.get('name', '').upper()
                    for comp in response_elem.findall('.//c:supported-calendar-component-set/c:comp', namespaces)
                    if comp is not None
                }

                # Only keep VTODO-capable collections when explicitly declared.
                if component_names and 'VTODO' not in component_names:
                    continue

                if list_name not in discovered:
                    discovered.append(list_name)

            return discovered
        except Exception as e:
            self.logger.error(f"Error fetching task lists: {str(e)}")
            return []
    
    def _get_task_quick(self, ics_path: str) -> Optional[Dict]:
        """
        ULTRA-schnelle Task-Prüfung: HEAD-Request + streaming parse
        Zeigt auch abgehakte Todos an
        """
        try:
            if not ics_path.startswith('http'):
                url = f"{self.url}{ics_path}"
            else:
                url = ics_path
            
            # Kurzer Timeout fuer gute Responsiveness, aber nicht zu aggressiv.
            response = self.session.get(url, timeout=3)
            
            if response.status_code == 200:
                text = response.text
                vtodo_block = _extract_component_block(text, 'VTODO')
                if not vtodo_block:
                    return None
                
                # Check if completed (aber zeige es trotzdem an)
                status_value = (_extract_ics_property(vtodo_block, 'STATUS') or '').upper()
                is_completed = status_value == 'COMPLETED' or bool(_extract_ics_property(vtodo_block, 'COMPLETED'))
                
                # Schnell SUMMARY extrahieren
                title = _extract_ics_property(vtodo_block, 'SUMMARY')
                if not title:
                    return None
                
                # DUE (Fälligkeitsdatum)
                due_value = _extract_ics_property(vtodo_block, 'DUE')
                due_date = None
                due_match = re.search(r'(\d{8})', due_value or '')
                if due_match:
                    date_str = due_match.group(1)
                    due_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

                uid = _extract_ics_property(vtodo_block, 'UID') or unquote(ics_path.rsplit('/', 1)[-1]).replace('.ics', '')
                alarm_trigger = _extract_alarm_trigger(vtodo_block)
                
                return {
                    'uid': uid,
                    'title': title,
                    'due_date': due_date,
                    'description': _extract_ics_property(vtodo_block, 'DESCRIPTION') or '',
                    'priority': 0,
                    'completed': is_completed,  # Speichere Status
                    'has_alarm': bool(alarm_trigger),
                    'alarm_trigger': alarm_trigger,
                    'created': None,
                    'modified': None,
                    'nextcloud_path': ics_path
                }
                
        except Exception as e:
            self.logger.debug(f"Quick parse failed for {ics_path}: {str(e)}")
        
        return None
    
    def _get_task_from_ics(self, ics_path: str) -> Optional[Dict]:
        """Holt einzelne Task via WebDAV und parsed die iCalendar-Daten"""
        try:
            # Vollständige URL konstruieren
            if not ics_path.startswith('http'):
                url = f"{self.url}{ics_path}"
            else:
                url = ics_path
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                return self._parse_vtodo(response.text)
        except Exception as e:
            self.logger.debug(f"Error fetching task from {ics_path}: {str(e)}")
        
        return None
    
    def _parse_vtodo(self, ics_content: str) -> Optional[Dict]:
        """Parsed iCalendar VTODO-Format"""
        try:
            vtodo_content = _extract_component_block(ics_content, 'VTODO')
            if not vtodo_content:
                return None

            # Einfaches Parsing der wichtigsten Felder
            task = {
                'title': '',
                'description': '',
                'due_date': None,
                'priority': 0,
                'completed': False,
                'has_alarm': False,
                'alarm_trigger': None,
                'created': None,
                'modified': None
            }
            
            # SUMMARY (Title)
            match = re.search(r'SUMMARY:(.+?)(?:\r?\n|$)', vtodo_content)
            if match:
                task['title'] = match.group(1).strip()
            
            # DESCRIPTION
            match = re.search(r'DESCRIPTION:(.+?)(?:\r?\n(?:[A-Z])|$)', vtodo_content)
            if match:
                task['description'] = match.group(1).strip()
            
            # DUE (Fälligkeitsdatum)
            match = re.search(r'DUE[^:]*:(\d{8}T?\d*)?', vtodo_content)
            if match and match.group(1):
                date_str = match.group(1)
                # Konvertiere zu ISO-Format
                if 'T' in date_str:
                    task['due_date'] = date_str[:4] + '-' + date_str[4:6] + '-' + date_str[6:8]
                else:
                    task['due_date'] = date_str[:4] + '-' + date_str[4:6] + '-' + date_str[6:8]
            
            # PRIORITY (0=undefined, 1-4=high, 5=medium, 6-9=low)
            match = re.search(r'PRIORITY:(\d+)', vtodo_content)
            if match:
                priority = int(match.group(1))
                task['priority'] = priority
            
            # COMPLETED (STATUS:COMPLETED oder COMPLETED-Flag)
            if 'STATUS:COMPLETED' in vtodo_content or 'COMPLETED:' in vtodo_content:
                task['completed'] = True

            alarm_trigger = _extract_alarm_trigger(vtodo_content)
            task['has_alarm'] = bool(alarm_trigger)
            task['alarm_trigger'] = alarm_trigger
            
            # CREATED
            match = re.search(r'CREATED:(\d{8}T\d{6}Z)', vtodo_content)
            if match:
                task['created'] = match.group(1)
            
            # Nur zurückgeben, wenn Titel vorhanden
            if task['title']:
                return task
        
        except Exception as e:
            self.logger.debug(f"Error parsing VTODO: {str(e)}")
        
        return None
    
    def create_task(self, title: str, description: str = '', due_date: Optional[str] = None, 
                   priority: int = 0, list_name: str = 'tasks') -> bool:
        """
        Erstellt ein neues Task/Todo
        :param title: Task-Titel
        :param description: Task-Beschreibung
        :param due_date: Fälligkeitsdatum (YYYY-MM-DD)
        :param priority: Priorität (1-9, 5=medium)
        :param list_name: Name des Task-Kalenders
        """
        try:
            # Generiere UID
            import uuid
            uid = f"nextcloud-task-{uuid.uuid4()}@mynd"
            
            # Erstelle VTODO
            ics_content = self._generate_vtodo(title, description, due_date, priority, uid)
            
            # URL für neue Task
            url = f"{self.base_url}/calendars/{self.username}/{list_name}/{uid}.ics"
            
            # Speichere
            response = self.session.put(url, data=ics_content, 
                                       headers={'Content-Type': 'text/calendar; charset=utf-8'},
                                       timeout=10)
            
            if response.status_code in [201, 204]:
                self.logger.info(f"Task created: {title}")
                return True
            else:
                self.logger.error(f"Failed to create task: {response.status_code}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error creating task: {str(e)}")
            return False
    
    def _generate_vtodo(self, title: str, description: str, due_date: Optional[str], 
                       priority: int, uid: str) -> str:
        """Generiert iCalendar VTODO-Format"""
        from datetime import datetime
        
        now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        
        ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//MYND//NONSGML TODO//EN
CALSCALE:GREGORIAN
BEGIN:VTODO
UID:{uid}
CREATED:{now}
LAST-MODIFIED:{now}
DTSTAMP:{now}
SUMMARY:{title}"""
        
        if description:
            # Escape newlines in description
            desc = description.replace('\n', '\\n')
            ics += f"\nDESCRIPTION:{desc}"
        
        if due_date:
            # Konvertiere YYYY-MM-DD zu YYYYMMDD
            due_converted = due_date.replace('-', '')
            ics += f"\nDUE:{due_converted}"
        
        if priority > 0:
            ics += f"\nPRIORITY:{priority}"
        
        ics += "\nEND:VTODO\nEND:VCALENDAR"
        
        return ics

    def _set_or_append_vtodo_property(self, ics_content: str, prop: str, value: str) -> str:
        """Set or append a VTODO property in the first VTODO block."""
        vtodo_match = re.search(r'BEGIN:VTODO[\s\S]*?END:VTODO', ics_content)
        if not vtodo_match:
            return ics_content

        block = vtodo_match.group(0)
        prop_pattern = rf'^{re.escape(prop)}[^\r\n]*$'

        if re.search(prop_pattern, block, flags=re.MULTILINE):
            updated_block = re.sub(prop_pattern, f'{prop}:{value}', block, count=1, flags=re.MULTILINE)
        else:
            updated_block = block.replace('END:VTODO', f'{prop}:{value}\nEND:VTODO', 1)

        return ics_content.replace(block, updated_block, 1)

    def update_task(self, task_uid: str, list_name: str = 'tasks', title: Optional[str] = None,
                    description: Optional[str] = None, due_date: Optional[str] = None,
                    priority: Optional[int] = None) -> bool:
        """Updates an existing VTODO by UID."""
        try:
            url = f"{self.base_url}/calendars/{self.username}/{list_name}/{task_uid}.ics"
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                self.logger.error(f"Failed to fetch task for update: {response.status_code}")
                return False

            ics_content = response.text
            updated = ics_content

            if title is not None:
                updated = self._set_or_append_vtodo_property(updated, 'SUMMARY', title.strip())

            if description is not None:
                updated = self._set_or_append_vtodo_property(
                    updated,
                    'DESCRIPTION',
                    description.replace('\n', '\\n').strip()
                )

            if due_date is not None:
                if due_date.strip():
                    updated = self._set_or_append_vtodo_property(updated, 'DUE', due_date.replace('-', '').strip())
                else:
                    updated = re.sub(r'^DUE[^\r\n]*\r?\n?', '', updated, flags=re.MULTILINE)

            if priority is not None:
                if int(priority) > 0:
                    updated = self._set_or_append_vtodo_property(updated, 'PRIORITY', str(int(priority)))
                else:
                    updated = re.sub(r'^PRIORITY[^\r\n]*\r?\n?', '', updated, flags=re.MULTILINE)

            put_response = self.session.put(
                url,
                data=updated,
                headers={'Content-Type': 'text/calendar; charset=utf-8'},
                timeout=10
            )

            if put_response.status_code in [200, 201, 204]:
                self.logger.info(f"Task updated: {task_uid}")
                return True

            self.logger.error(f"Failed to update task: {put_response.status_code}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating task: {str(e)}")
            return False
    
    def complete_task(self, task_uid: str, list_name: str = 'tasks') -> bool:
        """Markiert ein Task als erledigt"""
        try:
            # Hole die aktuelle Task
            url = f"{self.base_url}/calendars/{self.username}/{list_name}/{task_uid}.ics"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                ics_content = response.text
                
                # Füge COMPLETED Flag hinzu
                if 'STATUS:COMPLETED' not in ics_content:
                    ics_content = ics_content.replace(
                        'END:VTODO',
                        f'STATUS:COMPLETED\nCOMPLETED:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}\nEND:VTODO'
                    )
                
                # Speichere zurück
                response = self.session.put(url, data=ics_content,
                                           headers={'Content-Type': 'text/calendar; charset=utf-8'},
                                           timeout=10)
                
                if response.status_code in [201, 204]:
                    self.logger.info(f"Task marked as completed: {task_uid}")
                    return True
        
        except Exception as e:
            self.logger.error(f"Error completing task: {str(e)}")
        
        return False


def create_simple_tasks_manager(url: str, username: str = None, password: str = None, auth_provider: AuthProvider = None) -> Optional[SimpleNextcloudTasks]:
    """
    Factory-Funktion zur Erstellung eines SimpleNextcloudTasks

    Args:
        url: Nextcloud server URL
        username: Username (for backward compatibility)
        password: Password (for backward compatibility)
        auth_provider: AuthProvider instance (recommended)

    Returns:
        SimpleNextcloudTasks instance or None if connection failed
    """
    try:
        manager = SimpleNextcloudTasks(url, username, password, auth_provider)
        if manager.test_connection():
            return manager
        else:
            logging.warning("Could not connect to Nextcloud Tasks")
            return None
    except Exception as e:
        logging.error(f"Error creating tasks manager: {str(e)}")
        return None
