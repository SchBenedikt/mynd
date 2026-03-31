#!/usr/bin/env python3
"""
Einfacher Nextcloud Kalender-Client (ohne caldav-Dependencies)
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Union
import logging
import os
import sys
from urllib.parse import quote
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from backend.features.integration.auth_provider import AuthProvider
from backend.features.integration.auth_manager import get_auth_manager

load_dotenv()  # WICHTIG: .env Datei laden

logger = logging.getLogger(__name__)

class SimpleNextcloudCalendar:
    def __init__(self, nextcloud_url: str, username: str = None, password: str = None, auth_provider: AuthProvider = None):
        """
        Initialisiert den einfachen Nextcloud Kalender-Client

        Args:
            nextcloud_url: Nextcloud Server URL (z.B. https://cloud.deine-domain.de)
            username: Nextcloud Benutzername (for backward compatibility)
            password: Nextcloud Passwort oder App-Passwort (for backward compatibility)
            auth_provider: AuthProvider instance (recommended)
        """
        self.nextcloud_url = nextcloud_url.rstrip('/')
        self.username = username
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
        
    def _make_dav_request(self, endpoint: str) -> requests.Response:
        """Macht eine DAV-Anfrage"""
        url = f"{self.nextcloud_url}/remote.php/dav/calendars/{self.username}/{endpoint}"
        headers = {
            'Depth': '1',
            'Content-Type': 'application/xml; charset=utf-8'
        }
        
        response = self.session.request('PROPFIND', url, headers=headers)
        return response
    
    def get_calendars(self) -> List[Dict]:
        """Holt alle Kalender mit korrekter PROPFIND Methode"""
        try:
            # Korrekte CalDAV URL für Kalender-Liste
            url = f"{self.nextcloud_url}/remote.php/dav/calendars/{self.username}/"
            
            headers = {
                'Depth': '1'
            }
            
            # PROPFIND request um Kalender zu finden
            response = self.session.request('PROPFIND', url, headers=headers)
            
            if response.status_code == 207:
                # XML parsing für Kalender-URLs
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                
                # Namespace definitions
                namespaces = {
                    'd': 'DAV:',
                    'cs': 'http://calendarserver.org/ns/',
                    'c': 'urn:ietf:params:xml:ns:caldav',
                    'oc': 'http://owncloud.org/ns'
                }
                
                calendars = []
                
                # Finde alle responses mit calendar resource type
                for response_elem in root.findall('.//d:response', namespaces):
                    href_elem = response_elem.find('.//d:href', namespaces)
                    if href_elem is not None:
                        href = href_elem.text
                        
                        # Prüfe nur auf echten CalDAV-Resource-Typ, nicht auf URL-Namensmuster.
                        # Geteilte Kalender können Pfade ohne den String "calendar" haben.
                        resource_type_elem = response_elem.find('.//d:resourcetype/c:calendar', namespaces)
                        if resource_type_elem is not None and href:
                            # Extrahiere Kalendername aus displayname
                            displayname_elem = response_elem.find('.//d:displayname', namespaces)
                            calendar_name = displayname_elem.text if displayname_elem is not None else 'Unknown'
                            
                            calendars.append({
                                'name': calendar_name,
                                'url': href,
                                'calendar_path': href.split('/')[-2] if href.endswith('/') else href.split('/')[-1]
                            })
                
                logger.info(f"Found {len(calendars)} calendars: {[c['name'] for c in calendars]}")
                return calendars
            else:
                logger.error(f"Failed to get calendars: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting calendars: {e}")
            return []
    
    def get_events(self, calendar_url: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Holt Ereignisse für einen Kalender mit korrekter REPORT Methode"""
        try:
            # Volle URL für den Kalender
            full_url = f"{self.nextcloud_url}{calendar_url}"
            
            # Korrektes CalDAV REPORT request basierend auf deinem curl-Befehl
            report_body = f'''<?xml version="1.0" encoding="UTF-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
    <d:prop>
        <c:calendar-data/>
    </d:prop>
    <c:filter>
        <c:comp-filter name="VCALENDAR">
            <c:comp-filter name="VEVENT">
                <c:time-range start="{start_date.strftime('%Y%m%dT%H%M%SZ')}" end="{end_date.strftime('%Y%m%dT%H%M%SZ')}"/>
            </c:comp-filter>
        </c:comp-filter>
    </c:filter>
</c:calendar-query>'''
            
            headers = {
                'Depth': '1',
                'Content-Type': 'application/xml'
            }
            
            # REPORT request für Ereignisse
            response = self.session.request('REPORT', full_url, headers=headers, data=report_body)
            
            if response.status_code == 207:
                return self._parse_events_from_ical(response.text)
            else:
                logger.error(f"Failed to get events: {response.status_code} - {response.text[:200]}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    def _parse_events_from_ical(self, xml_response: str) -> List[Dict]:
        """Parst Ereignisse aus CalDAV XML-Response mit iCal-Daten"""
        try:
            events = []
            import xml.etree.ElementTree as ET
            
            # Parse die XML-Antwort
            root = ET.fromstring(xml_response)
            
            # Namespace definitions
            namespaces = {
                'd': 'DAV:',
                'cal': 'urn:ietf:params:xml:ns:caldav'
            }
            
            # Finde alle calendar-data Elemente
            for cal_data_elem in root.findall('.//cal:calendar-data', namespaces):
                if cal_data_elem.text:
                    ical_text = cal_data_elem.text.strip()
                    # Parse das iCal-Daten
                    parsed_events = self._parse_ical_text(ical_text)
                    events.extend(parsed_events)
            
            logger.info(f"Parsed {len(events)} events from CalDAV response")
            return events
            
        except Exception as e:
            logger.error(f"Error parsing CalDAV events: {e}")
            return []
    
    def _parse_ical_text(self, ical_text: str) -> List[Dict]:
        """Parst reines iCal-Format in Ereignisse"""
        events = []
        lines = ical_text.strip().split('\n')
        current_event = {}
        
        for line in lines:
            line = line.strip()
            
            if line == 'BEGIN:VEVENT':
                current_event = {}
            elif line == 'END:VEVENT':
                if current_event:
                    # Formatiere das Ereignis
                    formatted_event = {
                        'summary': current_event.get('SUMMARY', 'Kein Titel'),
                        'start': self._format_ical_datetime(current_event.get('DTSTART')),
                        'end': self._format_ical_datetime(current_event.get('DTEND')),
                        'location': current_event.get('LOCATION', '').replace('\\', '').replace('\n', ', '),
                        'description': current_event.get('DESCRIPTION', '').replace('\\', '').replace('\n', ' '),
                        'all_day': self._is_all_day_ical(current_event.get('DTSTART'), current_event.get('DTEND')),
                        # Rohdaten für Debugging
                        'raw_start': current_event.get('DTSTART'),
                        'raw_end': current_event.get('DTEND')
                    }
                    events.append(formatted_event)
                current_event = {}
            elif ':' in line:
                # Handle folded lines (continuation lines starting with space)
                if line.startswith(' ') and current_event:
                    # Fortsetzungszeile
                    last_key = list(current_event.keys())[-1]
                    current_event[last_key] += line[1:]  # Remove leading space
                else:
                    # Handle parameterized keys like DTSTART;TZID=Europe/Berlin
                    if ';' in line and ':' in line:
                        key_part, value = line.split(':', 1)
                        # Extrahiere den eigentlichen Key vor dem ersten Semikolon
                        key = key_part.split(';')[0]
                        current_event[key] = value
                        # Speichere auch den vollen Key für Referenz
                        current_event[key_part] = value
                    else:
                        key, value = line.split(':', 1)
                        current_event[key] = value
        
        return events
    
    def _format_ical_datetime(self, dt_str: str) -> str:
        """Formatiert iCal Datum/Zeit für Anzeige"""
        if not dt_str:
            return ''
        
        try:
            # Handle TZID format (z.B. DTSTART;TZID=Europe/Berlin:20260328T093000)
            if ';' in dt_str:
                # Entferne Parameter wie TZID
                dt_str = dt_str.split(':')[-1] if ':' in dt_str else dt_str
            
            # iCal Format: 20260328T093000 oder 20260328
            if 'T' in dt_str:
                # Mit Zeit
                if dt_str.endswith('Z'):
                    # UTC Zeit
                    dt = datetime.strptime(dt_str, '%Y%m%dT%H%M%SZ')
                else:
                    # Lokale Zeit
                    dt = datetime.strptime(dt_str, '%Y%m%dT%H%M%S')
                return dt.strftime('%d.%m.%Y %H:%M')
            else:
                # Nur Datum
                dt = datetime.strptime(dt_str, '%Y%m%d')
                return dt.strftime('%d.%m.%Y')
        except Exception as e:
            logger.warning(f"Error parsing datetime '{dt_str}': {e}")
            return dt_str
    
    def _is_all_day_ical(self, start_str: str, end_str: str) -> bool:
        """Prüft ob es ein ganztägiges Ereignis ist (iCal Format)"""
        try:
            if not start_str or not end_str:
                return False
            
            # Wenn beide ohne Zeit, dann ganztägig
            if 'T' not in start_str and 'T' not in end_str:
                return True
            
            # Wenn Zeit aber 00:00-00:00 oder 23:59, dann wahrscheinlich ganztägig
            if 'T' in start_str and 'T' in end_str:
                start_time = start_str.split('T')[1].replace('Z', '')
                end_time = end_str.split('T')[1].replace('Z', '')
                
                if start_time in ['000000', '000000'] and end_time in ['000000', '235959']:
                    return True
            
            return False
        except:
            return False
    
    def get_today_info(self) -> Dict:
        """Gibt Informationen über heute zurück"""
        try:
            today = date.today()
            weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
            months = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 
                     'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
            
            return {
                'date': today.strftime('%d.%m.%Y'),
                'weekday': weekdays[today.weekday()],
                'weekday_number': today.weekday(),
                'month': months[today.month - 1],
                'day': today.day,
                'year': today.year,
                'is_weekend': today.weekday() >= 5,
                'calendar_week': today.isocalendar()[1]
            }
        except Exception as e:
            logger.error(f"Error getting today info: {e}")
            return {
                'date': date.today().strftime('%d.%m.%Y'),
                'weekday': 'Unbekannt',
                'calendar_week': date.today().isocalendar()[1]
            }
    
    def get_events_today(self) -> List[Dict]:
        """Holt alle Ereignisse für heute"""
        try:
            today = date.today()
            # Verwende UTC-Zeit für CalDAV
            start = datetime.combine(today, datetime.min.time())
            end = datetime.combine(today, datetime.max.time())
            
            calendars = self.get_calendars()
            all_events = []
            
            for cal in calendars:
                events = self.get_events(cal['url'], start, end)
                for event in events:
                    event['calendar'] = cal.get('name', 'Unknown')
                    all_events.append(event)
            
            # Sortiere nach Startzeit
            all_events.sort(key=lambda x: x.get('start', ''))
            return all_events
            
        except Exception as e:
            logger.error(f"Error getting today events: {e}")
            return []
    
    def get_events_tomorrow(self) -> List[Dict]:
        """Holt alle Ereignisse für morgen"""
        try:
            tomorrow = date.today() + timedelta(days=1)
            start = datetime.combine(tomorrow, datetime.min.time())
            end = datetime.combine(tomorrow, datetime.max.time())
            
            calendars = self.get_calendars()
            all_events = []
            
            for cal in calendars:
                events = self.get_events(cal['url'], start, end)
                for event in events:
                    event['calendar'] = cal.get('name', 'Unknown')
                    all_events.append(event)
            
            all_events.sort(key=lambda x: x.get('start', ''))
            return all_events
            
        except Exception as e:
            logger.error(f"Error getting tomorrow events: {e}")
            return []
    
    def get_events_this_week(self) -> List[Dict]:
        """Holt alle Ereignisse für diese Woche"""
        try:
            today = date.today()
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)
            sunday = monday + timedelta(days=6)
            
            start = datetime.combine(monday, datetime.min.time())
            end = datetime.combine(sunday, datetime.max.time())
            
            calendars = self.get_calendars()
            all_events = []
            
            for cal in calendars:
                events = self.get_events(cal['url'], start, end)
                for event in events:
                    event['calendar'] = cal.get('name', 'Unknown')
                    all_events.append(event)
            
            all_events.sort(key=lambda x: x.get('start', ''))
            return all_events
            
        except Exception as e:
            logger.error(f"Error getting this week events: {e}")
            return []
    
    def get_events_next_week(self) -> List[Dict]:
        """Holt alle Ereignisse für nächste Woche"""
        try:
            today = date.today()
            days_since_monday = today.weekday()
            next_monday = today + timedelta(days=(7 - days_since_monday))
            next_sunday = next_monday + timedelta(days=6)
            
            start = datetime.combine(next_monday, datetime.min.time())
            end = datetime.combine(next_sunday, datetime.max.time())
            
            calendars = self.get_calendars()
            all_events = []
            
            for cal in calendars:
                events = self.get_events(cal['url'], start, end)
                for event in events:
                    event['calendar'] = cal.get('name', 'Unknown')
                    all_events.append(event)
            
            all_events.sort(key=lambda x: x.get('start', ''))
            return all_events
            
        except Exception as e:
            logger.error(f"Error getting next week events: {e}")
            return []
    
    def get_events_for_day(self, day_name: str) -> List[Dict]:
        """Holt Ereignisse für einen bestimmten Wochentag"""
        try:
            day_mapping = {
                'montag': 0, 'dienstag': 1, 'mittwoch': 2, 'donnerstag': 3,
                'freitag': 4, 'samstag': 5, 'sonntag': 6
            }
            
            day_name_lower = day_name.lower()
            if day_name_lower not in day_mapping:
                return []
            
            today = date.today()
            current_weekday = today.weekday()
            
            # Berechne Tage bis zum gewünschten Wochentag
            days_until = (day_mapping[day_name_lower] - current_weekday) % 7
            if days_until == 0:
                target_date = today  # Heute
            else:
                target_date = today + timedelta(days=days_until)
            
            start = datetime.combine(target_date, datetime.min.time())
            end = datetime.combine(target_date, datetime.max.time())
            
            calendars = self.get_calendars()
            all_events = []
            
            for cal in calendars:
                events = self.get_events(cal['url'], start, end)
                for event in events:
                    event['calendar'] = cal.get('name', 'Unknown')
                    all_events.append(event)
            
            all_events.sort(key=lambda x: x.get('start', ''))
            return all_events
            
        except Exception as e:
            logger.error(f"Error getting day events: {e}")
            return []


def create_simple_calendar_manager(nextcloud_url: str = None, username: str = None, password: str = None, auth_provider: AuthProvider = None) -> Optional[SimpleNextcloudCalendar]:
    """
    Erstellt einfachen Kalender-Manager aus Umgebungsvariablen oder direkten Parametern

    Args:
        nextcloud_url: Nextcloud server URL (optional, uses env var if not provided)
        username: Username (optional, uses env var if not provided)
        password: Password (optional, uses env var if not provided)
        auth_provider: AuthProvider instance (recommended)

    Returns:
        SimpleNextcloudCalendar instance or None if creation failed
    """
    try:
        # Konfiguration aus .env Datei falls nicht direkt übergeben
        if not nextcloud_url:
            nextcloud_url = os.getenv('NEXTCLOUD_URL')
        if not username:
            username = os.getenv('NEXTCLOUD_USERNAME')
        if not password:
            password = os.getenv('NEXTCLOUD_PASSWORD')

        print(f"DEBUG: URL={nextcloud_url}")
        print(f"DEBUG: Username={username}")
        print(f"DEBUG: Password configured={password is not None}")

        if not nextcloud_url:
            logger.error("Missing Nextcloud URL")
            return None

        if not auth_provider and not (username and password):
            logger.error("Missing Nextcloud configuration (username/password or auth_provider)")
            return None

        manager = SimpleNextcloudCalendar(nextcloud_url, username, password, auth_provider)
        return manager

    except Exception as e:
        logger.error(f"Error creating calendar manager: {e}")
        return None


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    manager = create_simple_calendar_manager()
    if manager:
        print("Einfacher Kalender-Manager erstellt")
        calendars = manager.get_calendars()
        print(f"Kalender: {calendars}")
        
        if calendars:
            # Teste Ereignisse für heute
            from datetime import date, timedelta
            today = date.today()
            start = datetime.combine(today, datetime.min.time())
            end = datetime.combine(today, datetime.max.time())
            
            events = manager.get_events(calendars[0]['url'], start, end)
            print(f"Heutige Ereignisse: {len(events)}")
            for event in events[:3]:
                print(f"- {event['summary']} ({event['start']})")
    else:
        print("Keine Kalender gefunden")
