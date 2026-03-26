#!/usr/bin/env python3
"""
Nextcloud CalDAV Kalender-Integration
Ermöglicht der KI, auf Kalendereinträge zuzugreifen und diese zu beantworten
"""

import caldav
import requests
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import logging
from urllib.parse import urlparse
import os

logger = logging.getLogger(__name__)

class NextcloudCalendarManager:
    def __init__(self, nextcloud_url: str, username: str, password: str):
        """
        Initialisiert den CalDAV Kalender-Manager
        
        Args:
            nextcloud_url: Nextcloud Server URL (z.B. https://cloud.deine-domain.de)
            username: Nextcloud Benutzername
            password: Nextcloud Passwort oder App-Passwort
        """
        self.nextcloud_url = nextcloud_url.rstrip('/')
        self.username = username
        self.password = password
        self.client = None
        self.calendars = []
        
    def connect(self) -> bool:
        """Stellt Verbindung zum CalDAV Server her"""
        try:
            # CalDAV URL erstellen
            caldav_url = f"{self.nextcloud_url}/remote.php/dav/calendars/{self.username}/"
            
            logger.info(f"Connecting to CalDAV URL: {caldav_url}")
            
            # Verbindung herstellen
            self.client = caldav.DAVClient(
                url=caldav_url,
                username=self.username,
                password=self.password
            )
            
            # Kalender abrufen
            calendars = self.client.calendar_search()
            self.calendars = calendars
            
            logger.info(f"Connected to Nextcloud CalDAV. Found {len(calendars)} calendars")
            for i, cal in enumerate(calendars):
                logger.info(f"Calendar {i+1}: {cal.name} - {cal.url}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to CalDAV: {e}")
            return False
    
    def get_events_for_period(self, start_date: datetime, end_date: datetime, 
                           calendar_names: List[str] = None) -> List[Dict]:
        """
        Holt alle Ereignisse für einen Zeitraum
        
        Args:
            start_date: Startdatum
            end_date: Enddatum
            calendar_names: Optionale Liste von Kalendernamen (leer = alle)
            
        Returns:
            Liste von Ereignissen mit Details
        """
        if not self.client:
            if not self.connect():
                return []
        
        events = []
        
        try:
            # Filtere Kalender nach Namen falls angegeben
            target_calendars = self.calendars
            if calendar_names:
                target_calendars = [cal for cal in self.calendars 
                                 if cal.name in calendar_names]
            
            for calendar in target_calendars:
                try:
                    # Ereignisse abrufen
                    result = calendar.search(
                        start=start_date,
                        end=end_date
                    )
                    
                    for event in result:
                        event_data = self._parse_event(event, calendar.name)
                        events.append(event_data)
                        
                except Exception as e:
                    logger.warning(f"Error fetching events from calendar {calendar.name}: {e}")
                    continue
            
            # Sortiere nach Startzeit
            events.sort(key=lambda x: x.get('start', ''))
            
            logger.info(f"Found {len(events)} events between {start_date.date()} and {end_date.date()}")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return []
    
    def get_events_today(self) -> List[Dict]:
        """Holt alle Ereignisse für heute"""
        today = date.today()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        return self.get_events_for_period(start, end)
    
    def get_events_tomorrow(self) -> List[Dict]:
        """Holt alle Ereignisse für morgen"""
        tomorrow = date.today() + timedelta(days=1)
        start = datetime.combine(tomorrow, datetime.min.time())
        end = datetime.combine(tomorrow, datetime.max.time())
        return self.get_events_for_period(start, end)
    
    def get_events_this_week(self) -> List[Dict]:
        """Holt alle Ereignisse für diese Woche (Montag-Sonntag)"""
        today = date.today()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        sunday = monday + timedelta(days=6)
        
        start = datetime.combine(monday, datetime.min.time())
        end = datetime.combine(sunday, datetime.max.time())
        
        return self.get_events_for_period(start, end)
    
    def get_events_next_week(self) -> List[Dict]:
        """Holt alle Ereignisse für nächste Woche"""
        today = date.today()
        days_since_monday = today.weekday()
        next_monday = today + timedelta(days=(7 - days_since_monday))
        next_sunday = next_monday + timedelta(days=6)
        
        start = datetime.combine(next_monday, datetime.min.time())
        end = datetime.combine(next_sunday, datetime.max.time())
        
        return self.get_events_for_period(start, end)
    
    def get_events_for_day(self, day_name: str) -> List[Dict]:
        """
        Holt Ereignisse für einen bestimmten Wochentag
        z.B. "montag", "dienstag", etc.
        """
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
        
        return self.get_events_for_period(start, end)
    
    def _parse_event(self, event, calendar_name: str) -> Dict:
        """Parst ein einzelnes Ereignis"""
        try:
            # Grundlegende Informationen
            event_data = {
                'calendar': calendar_name,
                'summary': event.vobject_instance.vevent.summary.value if event.vobject_instance.vevent.summary else 'Kein Titel',
                'start': self._format_datetime(event.vobject_instance.vevent.dtstart.value),
                'end': self._format_datetime(event.vobject_instance.vevent.dtend.value),
                'all_day': self._is_all_day(event.vobject_instance.vevent),
                'location': event.vobject_instance.vevent.location.value if event.vobject_instance.vevent.location else None,
                'description': event.vobject_instance.vevent.description.value if event.vobject_instance.vevent.description else None,
                'url': None
            }
            
            # URL falls vorhanden
            if hasattr(event.vobject_instance.vevent, 'url'):
                event_data['url'] = event.vobject_instance.vevent.url.value
            
            return event_data
            
        except Exception as e:
            logger.warning(f"Error parsing event: {e}")
            return {
                'calendar': calendar_name,
                'summary': 'Fehler beim Parsen',
                'start': None,
                'end': None,
                'all_day': False,
                'location': None,
                'description': None,
                'url': None
            }
    
    def _format_datetime(self, dt) -> str:
        """Formatiert datetime für Anzeige"""
        if isinstance(dt, datetime):
            return dt.strftime('%d.%m.%Y %H:%M')
        elif isinstance(dt, date):
            return dt.strftime('%d.%m.%Y')
        else:
            return str(dt)
    
    def _is_all_day(self, vevent) -> bool:
        """Prüft ob es ein ganztägiges Ereignis ist"""
        try:
            if hasattr(vevent, 'dtstart') and hasattr(vevent, 'dtend'):
                start = vevent.dtstart.value
                end = vevent.dtend.value
                
                if isinstance(start, date) and isinstance(end, date):
                    return True
                
                if isinstance(start, datetime) and isinstance(end, datetime):
                    # Prüfe ob es Mitternacht bis Mitternacht ist
                    return (start.hour == 0 and start.minute == 0 and 
                           end.hour == 0 and end.minute == 0)
            
            return False
        except:
            return False
    
    def get_calendar_list(self) -> List[str]:
        """Gibt Liste aller verfügbaren Kalender zurück"""
        if not self.calendars:
            if not self.connect():
                return []
        
        return [cal.name for cal in self.calendars]
    
    def get_today_info(self) -> Dict:
        """Gibt Informationen über heute zurück (Datum, Wochentag, etc.)"""
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


def create_calendar_manager() -> Optional[NextcloudCalendarManager]:
    """Erstellt Kalender-Manager aus Umgebungsvariablen oder Konfiguration"""
    try:
        # Konfiguration aus .env Datei
        nextcloud_url = os.getenv('NEXTCLOUD_URL')
        username = os.getenv('NEXTCLOUD_USERNAME')
        password = os.getenv('NEXTCLOUD_PASSWORD')
        
        if not all([nextcloud_url, username, password]):
            logger.error("Missing Nextcloud configuration in .env file")
            return None
        
        manager = NextcloudCalendarManager(nextcloud_url, username, password)
        return manager
        
    except Exception as e:
        logger.error(f"Error creating calendar manager: {e}")
        return None


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    manager = create_calendar_manager()
    if manager:
        print("Kalender-Manager erstellt")
        print(f"Verfügbare Kalender: {manager.get_calendar_list()}")
        print(f"Heute ist: {manager.get_today_info()}")
        print(f"Heutige Ereignisse: {len(manager.get_events_today())}")
