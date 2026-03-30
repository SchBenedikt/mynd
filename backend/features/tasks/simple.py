"""
SimpleNextcloudTasks - Minimal Nextcloud Tasks Integration über WebDAV
Unterstützt Nextcloud Tasks Plugin via WebDAV/CalDAV
"""

import requests
from requests.auth import HTTPBasicAuth
import logging
from typing import List, Dict, Optional
from datetime import datetime
import re

class SimpleNextcloudTasks:
    """Einfache Nextcloud Tasks Integration über WebDAV"""
    
    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)
        self.base_url = f"{self.url}/remote.php/dav"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
    
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
        Holt unvollständige Tasks schnell ohne alle zu parsen.
        MINIMAL-OPTIMIERT: Nur 1 Task laden in max 5 Sekunden
        """
        tasks = []
        try:
            url = f"{self.base_url}/calendars/{self.username}/{list_name}/"
            
            # Schnelle PROPFIND um nur Namen zu sehen
            response = self.session.request('PROPFIND', url, timeout=5)
            
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
                    
                    self.logger.info(f"Found {len(ics_paths)} items in {list_name}, loading first 1 ONLY...")
                    
                    # Lade SEQUENZIEL - nur erste Task!
                    if ics_paths:
                        task_data = self._get_task_quick(ics_paths[0])
                        if task_data:
                            tasks.append(task_data)
                    
                except Exception as e:
                    self.logger.error(f"Error parsing tasks XML: {str(e)}")
            
            # Sortiere: Zuerst unvollständige, dann abgehakte
            # Nach Fälligkeitsdatum
            open_tasks = [t for t in tasks if not t.get('completed', False)]
            completed_tasks = [t for t in tasks if t.get('completed', False)]
            
            open_tasks.sort(key=lambda x: x.get('due_date', '9999-12-31'))
            completed_tasks.sort(key=lambda x: x.get('due_date', '9999-12-31'))
            
            all_tasks = open_tasks + completed_tasks
            
            self.logger.info(f"Loaded {len(open_tasks)} open, {len(completed_tasks)} completed tasks")
            return all_tasks
            
        except Exception as e:
            self.logger.error(f"Error fetching tasks: {str(e)}")
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
            
            # TIMEOUT sehr kurz halten - 1 Sekunde max
            response = self.session.get(url, timeout=1)
            
            if response.status_code == 200:
                text = response.text
                
                # Check if completed (aber zeige es trotzdem an)
                is_completed = 'STATUS:COMPLETED' in text
                
                # Schnell SUMMARY extrahieren
                import re
                title_match = re.search(r'SUMMARY:(.+?)(?:\r?\n|$)', text)
                if not title_match:
                    return None
                
                title = title_match.group(1).strip()
                
                # DUE (Fälligkeitsdatum)
                due_match = re.search(r'DUE[^:]*:(\d{8})', text)
                due_date = None
                if due_match:
                    date_str = due_match.group(1)
                    due_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                return {
                    'title': title,
                    'due_date': due_date,
                    'description': '',
                    'priority': 0,
                    'completed': is_completed,  # Speichere Status
                    'created': None,
                    'modified': None
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
            # Einfaches Parsing der wichtigsten Felder
            task = {
                'title': '',
                'description': '',
                'due_date': None,
                'priority': 0,
                'completed': False,
                'created': None,
                'modified': None
            }
            
            # SUMMARY (Title)
            match = re.search(r'SUMMARY:(.+?)(?:\r?\n|$)', ics_content)
            if match:
                task['title'] = match.group(1).strip()
            
            # DESCRIPTION
            match = re.search(r'DESCRIPTION:(.+?)(?:\r?\n(?:[A-Z])|$)', ics_content)
            if match:
                task['description'] = match.group(1).strip()
            
            # DUE (Fälligkeitsdatum)
            match = re.search(r'DUE[^:]*:(\d{8}T?\d*)?', ics_content)
            if match and match.group(1):
                date_str = match.group(1)
                # Konvertiere zu ISO-Format
                if 'T' in date_str:
                    task['due_date'] = date_str[:4] + '-' + date_str[4:6] + '-' + date_str[6:8]
                else:
                    task['due_date'] = date_str[:4] + '-' + date_str[4:6] + '-' + date_str[6:8]
            
            # PRIORITY (0=undefined, 1-4=high, 5=medium, 6-9=low)
            match = re.search(r'PRIORITY:(\d+)', ics_content)
            if match:
                priority = int(match.group(1))
                task['priority'] = priority
            
            # COMPLETED (STATUS:COMPLETED oder COMPLETED-Flag)
            if 'STATUS:COMPLETED' in ics_content or 'COMPLETED:' in ics_content:
                task['completed'] = True
            
            # CREATED
            match = re.search(r'CREATED:(\d{8}T\d{6}Z)', ics_content)
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


def create_simple_tasks_manager(url: str, username: str, password: str) -> Optional[SimpleNextcloudTasks]:
    """Factory-Funktion zur Erstellung eines SimpleNextcloudTasks"""
    try:
        manager = SimpleNextcloudTasks(url, username, password)
        if manager.test_connection():
            return manager
        else:
            logging.warning("Could not connect to Nextcloud Tasks")
            return None
    except Exception as e:
        logging.error(f"Error creating tasks manager: {str(e)}")
        return None
