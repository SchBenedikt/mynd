import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import calendar

logger = logging.getLogger(__name__)

class MetadataExtractor:
    """Extrahiert Metadaten wie Datum, Uhrzeit, Ort aus Text-Chunks"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Patterns für Datum/Zeit
        self.date_patterns = [
            r'(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})',  # DD.MM.YYYY
            r'(\d{1,2}\.\s*[A-Za-z]+\s*\d{4})',  # DD. Monat YYYY
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{1,2}\.\s*[A-Za-z]+\s*\d{2,4})',  # DD. Monat YY
            r'([A-Za-z]+\s+\d{1,2},\s*\d{4})',  # Monat DD, YYYY
        ]
        
        # Patterns für Uhrzeit
        self.time_patterns = [
            r'(\d{1,2}:\d{2}(?:\s*Uhr)?)',  # HH:MM oder HH:MM Uhr
            r'(\d{1,2}\s*Uhr\s*\d{2})',  # HH Uhr MM
            r'(\d{1,2}\.\d{2}\s*Uhr)',  # HH.MM Uhr
            r'(um\s*\d{1,2}:\d{2})',  # um HH:MM
        ]
        
        # Patterns für Orte
        self.location_patterns = [
            r'(?:in|am|bei|zur)\s+([A-Z][a-zA-ZäöüÄÖÜß\s-]+?)(?:\s|[,.!?]|$)',
            r'([A-Z][a-zA-ZäöüÄÖÜß]+\s*\d+(?:\s*[A-Z][a-z]*)?)',  # Stadt mit PLZ
            r'([A-Z][a-zA-ZäöüÄÖÜß]+(?:\s+[A-Z][a-zA-ZäöüÄÖÜß]+)*\s*(?:Straße|Str\.|Allee|Platz|Weg|Gasse))',
            r'(https?://[^\s]+\.(?:de|com|org|net|io))',  # URLs/Websites
        ]
        
        # Patterns für Ereignisse
        self.event_patterns = [
            r'(?:Veranstaltung|Konferenz|Meeting|Termin|Präsentation|Workshop|Seminar)',
            r'(?:Geburtstag|Feier|Party|Treffen|Besuch)',
            r'(?:Preisverleihung|Award|Ceremony)',
        ]
    
    def extract_metadata_from_chunk(self, chunk: str, file_path: str = "") -> Dict:
        """Extrahiert alle Metadaten aus einem Text-Chunk"""
        metadata = {
            'dates': [],
            'times': [],
            'locations': [],
            'events': [],
            'people': [],
            'organizations': [],
            'urls': [],
            'file_path': file_path,
            'confidence_score': 0.0
        }
        
        try:
            # Datum extrahieren
            for pattern in self.date_patterns:
                matches = re.findall(pattern, chunk, re.IGNORECASE)
                for match in matches:
                    normalized_date = self._normalize_date(match)
                    if normalized_date:
                        metadata['dates'].append({
                            'raw': match,
                            'normalized': normalized_date,
                            'type': 'date'
                        })
            
            # Uhrzeit extrahieren
            for pattern in self.time_patterns:
                matches = re.findall(pattern, chunk, re.IGNORECASE)
                for match in matches:
                    metadata['times'].append({
                        'raw': match,
                        'normalized': self._normalize_time(match),
                        'type': 'time'
                    })
            
            # Orte extrahieren
            for pattern in self.location_patterns:
                matches = re.findall(pattern, chunk, re.IGNORECASE)
                for match in matches:
                    if self._is_valid_location(match):
                        metadata['locations'].append({
                            'raw': match.strip(),
                            'type': 'location'
                        })
            
            # Personen extrahieren (einfache Version)
            people = self._extract_people(chunk)
            metadata['people'] = people
            
            # Organisationen extrahieren
            orgs = self._extract_organizations(chunk)
            metadata['organizations'] = orgs
            
            # URLs extrahieren
            urls = self._extract_urls(chunk)
            metadata['urls'] = urls
            
            # Ereignisse erkennen
            events = self._extract_events(chunk)
            metadata['events'] = events
            
            # Confidence Score berechnen
            metadata['confidence_score'] = self._calculate_confidence(metadata)
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {str(e)}")
        
        return metadata
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalisiert Datum zu einem einheitlichen Format"""
        try:
            # Verschiedene Formate zu parsen
            formats = [
                '%d.%m.%Y',
                '%d.%m.%y',
                '%d. %B %Y',
                '%d. %b %Y',
                '%Y-%m-%d',
                '%B %d, %Y'
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            return None
        except Exception:
            return None
    
    def _normalize_time(self, time_str: str) -> Optional[str]:
        """Normalisiert Uhrzeit"""
        try:
            # "Uhr" entfernen und normalisieren
            clean_time = re.sub(r'(?i)\s*Uhr', '', time_str).strip()
            
            # HH:MM Format
            if re.match(r'^\d{1,2}:\d{2}$', clean_time):
                return clean_time
            
            # HH Uhr MM Format
            match = re.match(r'^(\d{1,2})\s*Uhr\s*(\d{2})$', clean_time)
            if match:
                return f"{match.group(1).zfill(2)}:{match.group(2)}"
            
            return None
        except Exception:
            return None
    
    def _is_valid_location(self, location: str) -> bool:
        """Prüft ob es sich um einen gültigen Ort handelt"""
        location = location.strip()
        
        # Mindestlänge
        if len(location) < 2:
            return False
        
        # Stop-Wörter für Orte
        stop_words = {
            'der', 'die', 'das', 'und', 'oder', 'aber', 'mit', 'für', 'auf', 'in', 'an',
            'bei', 'zu', 'von', 'bis', 'durch', 'gegen', 'ohne', 'um', 'wenn', 'dann',
            'dass', 'weil', 'damit', 'deshalb', 'daher', 'dafür', 'dagegen', 'davor',
            'danach', 'hier', 'dort', 'dort', 'diese', 'dieser', 'dieses', 'jene', 'jener'
        }
        
        words = location.lower().split()
        if any(word in stop_words for word in words):
            return False
        
        # Zu generisch?
        generic_words = {'information', 'details', 'daten', 'text', 'inhalt', 'seite'}
        if location.lower() in generic_words:
            return False
        
        return True
    
    def _extract_people(self, text: str) -> List[Dict]:
        """Extrahiert Personennamen (einfache Version)"""
        people = []
        
        # Capitalisierte Wörter die wie Namen aussehen
        words = text.split()
        for i, word in enumerate(words):
            # Capitalisierte Wörter mit 2+ Buchstaben
            if word and word[0].isupper() and len(word) > 2:
                # Prüfen ob nächstes Wort auch capitalisiert ist (z.B. "Max Mustermann")
                if i + 1 < len(words) and words[i + 1][0].isupper():
                    full_name = f"{word} {words[i + 1]}"
                    # Keine Stop-Wörter
                    if not any(stop in full_name.lower() for stop in ['die', 'der', 'das', 'und', 'oder']):
                        people.append({
                            'raw': full_name,
                            'type': 'person'
                        })
        
        return people[:5]  # Limit auf 5 Personen
    
    def _extract_organizations(self, text: str) -> List[Dict]:
        """Extrahiert Organisationen"""
        orgs = []
        
        # Common organization patterns
        org_patterns = [
            r'\b([A-Z][a-zA-Z]+(?:\s+(?:GmbH|AG|KG|OHG|e\.V\.|Ltd\.|Inc\.|Corp\.))?)',
            r'\b([A-Z][a-zA-Z]+\s+(?:University|Hochschule|Schule|Institut|Akademie))',
            r'\b((?:Bundes|Landes|Stadt|Gemeinde)\s+[A-Z][a-zA-ZäöüÄÖÜß]+)',
        ]
        
        for pattern in org_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                orgs.append({
                    'raw': match,
                    'type': 'organization'
                })
        
        return orgs[:3]  # Limit auf 3 Organisationen
    
    def _extract_urls(self, text: str) -> List[Dict]:
        """Extrahiert URLs"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+(?=\s|$|[<>"{}|\\^`\[\]])'
        matches = re.findall(url_pattern, text)
        
        urls = []
        for match in matches:
            urls.append({
                'raw': match,
                'type': 'url'
            })
        
        return urls
    
    def _extract_events(self, text: str) -> List[Dict]:
        """Extrahiert Ereignisse"""
        events = []
        
        for pattern in self.event_patterns:
            # Finde Sätze mit Ereignis-Wörtern
            sentences = re.split(r'[.!?]+', text)
            for sentence in sentences:
                if re.search(pattern, sentence, re.IGNORECASE):
                    events.append({
                        'raw': sentence.strip(),
                        'type': 'event'
                    })
        
        return events[:3]  # Limit auf 3 Ereignisse
    
    def _calculate_confidence(self, metadata: Dict) -> float:
        """Berechtest Confidence Score basierend auf gefundenen Metadaten"""
        score = 0.0
        
        # Gewichtung für verschiedene Metadaten-Typen
        weights = {
            'dates': 0.3,
            'times': 0.2,
            'locations': 0.25,
            'people': 0.15,
            'organizations': 0.1
        }
        
        for key, weight in weights.items():
            count = len(metadata.get(key, []))
            if count > 0:
                score += weight * min(count / 3, 1.0)  # Max 1.0 pro Typ
        
        return min(score, 1.0)
    
    def enhance_context_with_metadata(self, context_results: List[Dict]) -> List[Dict]:
        """Verreichert Kontext-Ergebnisse mit Metadaten"""
        enhanced_results = []
        
        for result in context_results:
            content = result.get('content', '')
            file_path = result.get('path', '')
            
            # Metadaten extrahieren
            metadata = self.extract_metadata_from_chunk(content, file_path)
            
            # Ergebnis erweitern
            enhanced_result = result.copy()
            enhanced_result['metadata'] = metadata
            
            enhanced_results.append(enhanced_result)
        
        return enhanced_results
