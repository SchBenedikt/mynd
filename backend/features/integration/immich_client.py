import os
import sys
import logging
import re
from typing import List, Dict, Optional, Any, Tuple
import requests
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

class ImmichClient:
    """Client für Immich-Integration über REST API"""

    def __init__(self, url: str, api_key: str, timeout_short: int = 15, timeout_long: int = 45):
        self.url = self._normalize_url(url)
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.last_error: Optional[str] = None
        # Configurable timeouts
        self.timeout_short = timeout_short  # For quick operations like ping, asset info
        self.timeout_long = timeout_long    # For heavy operations like search, get people

    def _normalize_url(self, url: str) -> str:
        """Stellt sicher, dass die URL ein gültiges Schema hat."""
        normalized = (url or '').strip()
        if not normalized:
            return normalized
        if not normalized.startswith(('http://', 'https://')):
            normalized = f"https://{normalized}"
        return normalized.rstrip('/')

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key"""
        return {
            'X-Api-Key': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> bool:
        """Testet die Verbindung zu Immich"""
        self.last_error = None
        try:
            # Unterschiedliche Immich-Versionen verwenden verschiedene Ping-Endpunkte.
            ping_paths = [
                '/api/server/ping',
                '/api/server-info/ping',
            ]
            errors = []

            for path in ping_paths:
                url = f"{self.url}{path}"
                self.logger.info(f"Testing connection to: {url}")
                response = requests.get(url, headers=self._get_headers(), timeout=self.timeout_short)
                self.logger.info(f"Connection test response status ({path}): {response.status_code}")

                if response.status_code == 200:
                    data = response.json() if response.content else {}
                    # Immich antwortet typischerweise mit {"res":"pong"}, wir akzeptieren aber auch 200 ohne res.
                    if not data or data.get('res') == 'pong' or data.get('status') == 'ok':
                        self.logger.info("Immich connection successful")
                        return True

                response_preview = (response.text or '').strip().replace('\n', ' ')[:200]
                errors.append(f"{path}: HTTP {response.status_code}" + (f" ({response_preview})" if response_preview else ""))

                # Bei Auth-Fehlern direkt abbrechen, da Endpoint existiert und Credentials relevant sind.
                if response.status_code in (401, 403):
                    self.last_error = f"Authentication failed on {url}: HTTP {response.status_code}"
                    self.logger.error(self.last_error)
                    return False

            self.last_error = "No compatible Immich ping endpoint succeeded. " + " | ".join(errors)
            self.logger.error(f"Unexpected responses: {self.last_error}")
            return False

        except requests.exceptions.Timeout:
            self.last_error = f"Connection timeout to {self.url}"
            self.logger.error("Connection timeout - check URL and network")
            return False
        except requests.exceptions.ConnectionError as e:
            self.last_error = f"Connection error to {self.url}: {str(e)}"
            self.logger.error("Connection error - check URL and network connectivity")
            return False
        except Exception as e:
            self.last_error = f"Immich request failed: {str(e)}"
            self.logger.error(f"Immich connection failed: {str(e)}")
            return False

    def get_all_assets(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Holt alle Assets (Fotos und Videos) von Immich über Search-Endpoint"""
        try:
            # Use search/metadata with empty query to get all assets
            url = f"{self.url}/api/search/metadata"
            payload = {
                'take': limit,
                'skip': skip
            }

            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=self.timeout_long)

            if response.status_code == 200:
                result = response.json()
                assets = result.get('assets', {}).get('items', [])
                self.logger.info(f"Retrieved {len(assets)} assets from Immich")
                return assets
            else:
                self.logger.error(f"Failed to get assets: {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"Error getting assets: {str(e)}")
            return []

    def search_assets(self, query: str = None, person_ids: List[str] = None,
                     date_from: str = None, date_to: str = None,
                     limit: int = 20) -> List[Dict[str, Any]]:
        """
        Sucht nach Assets in Immich

        Args:
            query: Suchtext (für Smart Search wenn verfügbar)
            person_ids: Liste von Personen-IDs
            date_from: Startdatum (ISO format)
            date_to: Enddatum (ISO format)
            limit: Maximale Anzahl Ergebnisse
        """
        try:
            # Verwende den Search Metadata API endpoint
            url = f"{self.url}/api/search/metadata"

            payload = {
                'take': limit
            }

            if query:
                payload['query'] = query

            if person_ids:
                payload['personIds'] = person_ids

            if date_from:
                payload['takenAfter'] = date_from

            if date_to:
                payload['takenBefore'] = date_to

            self.logger.info(f"Searching Immich metadata with payload: {payload}")

            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=self.timeout_long)

            if response.status_code == 200:
                result = response.json()
                # Response structure: {"assets": {"total": X, "items": [...]}}
                assets = result.get('assets', {}).get('items', [])
                self.logger.info(f"Found {len(assets)} assets matching search criteria")
                return assets
            else:
                self.logger.error(f"Search failed: {response.status_code} - {response.text[:200]}")
                return []

        except Exception as e:
            self.logger.error(f"Error searching assets: {str(e)}")
            return []

    def search_smart(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Verwendet Immich Smart Search (CLIP-basiert) falls verfügbar
        """
        try:
            url = f"{self.url}/api/search/smart"

            payload = {
                'query': query,
                'take': limit
            }

            self.logger.info(f"Smart searching Immich for: {query}")

            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=self.timeout_long)

            if response.status_code == 200:
                result = response.json()
                # Immich response can be {"items": [...]} or {"assets": {"items": [...]}}
                assets = result.get('items', [])
                if not assets:
                    assets = result.get('assets', {}).get('items', [])
                if limit and len(assets) > limit:
                    assets = assets[:limit]
                self.logger.info(f"Smart search found {len(assets)} assets")
                return assets
            else:
                self.logger.warning(f"Smart search not available or failed: {response.status_code}")
                # Fallback auf normale Suche
                return self.search_assets(query=query, limit=limit)

        except Exception as e:
            self.logger.error(f"Error in smart search: {str(e)}")
            # Fallback auf normale Suche
            return self.search_assets(query=query, limit=limit)

    def get_people(self) -> List[Dict[str, Any]]:
        """Holt alle erkannten Personen von Immich"""
        try:
            url = f"{self.url}/api/people"

            response = requests.get(url, headers=self._get_headers(), timeout=self.timeout_long)

            if response.status_code == 200:
                data = response.json()
                # The /api/people endpoint returns either a list directly or an object with 'people' key
                if isinstance(data, list):
                    people = data
                else:
                    people = data.get('people', [])
                self.logger.info(f"Retrieved {len(people)} people from Immich")
                return people
            else:
                self.logger.error(f"Failed to get people: {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"Error getting people: {str(e)}")
            return []

    def _extract_relevant_terms(self, query: str) -> List[str]:
        """Extrahiert relevante Suchbegriffe aus natürlicher Sprache."""
        words = re.findall(r"[\wäöüÄÖÜß]+", (query or "").lower())
        stop_words = {
            'zeig', 'zeige', 'mir', 'ein', 'eine', 'einem', 'einen', 'einer', 'von', 'vom',
            'im', 'in', 'aus', 'dem', 'der', 'die', 'das', 'den', 'des', 'und', 'oder', 'mit',
            'foto', 'fotos', 'bild', 'bilder', 'photo', 'photos', 'image', 'images',
            'bitte', 'kannst', 'kann', 'suche', 'finde', 'find', 'show', 'me', 'all',
            'jahr', 'jahren', 'monat', 'monaten', 'tag', 'tagen', 'heute', 'gestern', 'morgen'
        }

        terms = [w for w in words if len(w) >= 3 and w not in stop_words]
        # Preserve order while removing duplicates
        return list(dict.fromkeys(terms))

    def _expand_terms_with_synonyms(self, terms: List[str]) -> List[str]:
        """Erweitert Suchbegriffe um einfache DE/EN-Synonyme."""
        synonyms = {
            'hund': ['dog', 'hunde'],
            'hunde': ['hund', 'dog'],
            'dog': ['hund', 'hunde'],
            'katze': ['cat', 'katzen'],
            'katzen': ['katze', 'cat'],
            'cat': ['katze', 'katzen'],
            'baum': ['tree', 'bäume'],
            'bäume': ['baum', 'tree'],
            'tree': ['baum', 'bäume'],
            'auto': ['car', 'autos'],
            'autos': ['auto', 'car'],
            'car': ['auto', 'autos'],
            'haus': ['home', 'häuser'],
            'häuser': ['haus', 'home'],
            'home': ['haus', 'häuser'],
            'mensch': ['person', 'menschen'],
            'menschen': ['mensch', 'person'],
            'person': ['mensch', 'menschen'],
        }

        expanded = []
        for term in terms:
            expanded.append(term)
            expanded.extend(synonyms.get(term, []))

        return list(dict.fromkeys(expanded))

    def _detect_people_in_query(self, query: str, people: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Erkennt genannte Personen aus der Query anhand der Immich-Personenliste."""
        query_lower = (query or '').lower()
        matches = []

        for person in people:
            name = (person.get('name') or '').strip()
            if not name:
                continue

            name_lower = name.lower()
            if name_lower in query_lower:
                matches.append(person)
                continue

            # Match on word boundaries for first/last name parts
            name_parts = [part for part in re.findall(r"[\wäöüÄÖÜß]+", name_lower) if len(part) >= 3]
            if any(re.search(rf"\b{re.escape(part)}\b", query_lower) for part in name_parts):
                matches.append(person)

        # Deduplicate by id
        unique = {}
        for p in matches:
            pid = p.get('id')
            if pid and pid not in unique:
                unique[pid] = p
        return list(unique.values())

    def search_by_person_name(self, person_name: str, limit: int = 20,
                              date_from: str = None, date_to: str = None) -> List[Dict[str, Any]]:
        """Sucht Fotos einer bestimmten Person nach Name"""
        try:
            # Erst alle Personen holen
            people = self.get_people()

            # Person nach Name finden (case-insensitive)
            matching_people = [
                p for p in people
                if p.get('name', '').lower().find(person_name.lower()) >= 0
            ]

            if not matching_people:
                self.logger.info(f"No person found matching: {person_name}")
                return []

            # IDs der gefundenen Personen
            person_ids = [p['id'] for p in matching_people]
            matching_people_names = {p['id']: p.get('name', 'Unknown') for p in matching_people}
            self.logger.info(f"Found {len(person_ids)} people matching '{person_name}': {[p.get('name') for p in matching_people]}")

            # Suche je Person-ID und merge als OR (statt AND-Verhalten vieler Immich-Setups)
            assets = []
            seen_ids = set()
            for pid in person_ids:
                person_assets = self.search_assets(person_ids=[pid], date_from=date_from, date_to=date_to, limit=limit)
                for asset in person_assets:
                    asset_id = asset.get('id')
                    if asset_id and asset_id not in seen_ids:
                        seen_ids.add(asset_id)
                        assets.append(asset)
                    if len(assets) >= limit:
                        break
                if len(assets) >= limit:
                    break
            
            # Enrich assets with people info (Immich doesn't always return this)
            for asset in assets:
                # Add people names if not already there
                if not asset.get('people'):
                    asset['people'] = [{'id': pid, 'name': matching_people_names.get(pid, 'Unknown')} 
                                      for pid in person_ids]
            
            return assets

        except Exception as e:
            self.logger.error(f"Error searching by person name: {str(e)}")
            return []

    def get_asset_thumbnail_url(self, asset_id: str, size: str = 'preview') -> str:
        """
        Generiert die URL für ein Asset-Thumbnail

        Args:
            asset_id: Asset ID
            size: 'preview' oder 'thumbnail'
        """
        return f"{self.url}/api/assets/{asset_id}/thumbnail?size={size}"
    
    def _build_search_url_params(self, query: Optional[str] = None, 
                                   person_ids: Optional[List[str]] = None,
                                   date_from: Optional[str] = None,
                                   date_to: Optional[str] = None) -> str:
        """
        Erstellt URL-encodierte Search-Parameter für Immich UI URLs
        Format: {"query": "...", "takenAfter": "...", "takenBefore": "..."}
        """
        import json
        import urllib.parse
        
        search_params = {}
        
        if query:
            search_params['query'] = query
        if date_from:
            search_params['takenAfter'] = date_from
        if date_to:
            search_params['takenBefore'] = date_to
        if person_ids:
            search_params['personIds'] = person_ids
        
        # URL-encode the JSON
        json_str = json.dumps(search_params, separators=(',', ':'))
        return urllib.parse.quote(json_str)

    def get_asset_url(self, asset_id: str, search_query: Optional[str] = None,
                     date_from: Optional[str] = None, date_to: Optional[str] = None) -> str:
        """
        Generiert die URL zum Asset auf der Immich-UI (statt API)
        Mit Search-Kontext falls verfügbar
        """
        if search_query or date_from or date_to:
            # Generate UI search page URL with context
            params = self._build_search_url_params(search_query, None, date_from, date_to)
            return f"{self.url}/search/photos/{asset_id}?query={params}"
        else:
            # Fallback: Simple UI link without search context
            return f"{self.url}/photos/{asset_id}"

    def get_asset_info(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Holt detaillierte Informationen zu einem Asset"""
        try:
            url = f"{self.url}/api/assets/{asset_id}"

            response = requests.get(url, headers=self._get_headers(), timeout=self.timeout_short)

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to get asset info: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error getting asset info: {str(e)}")
            return None

    def format_asset_for_display(self, asset: Dict[str, Any], search_query: Optional[str] = None,
                                date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Formatiert ein Asset für die Anzeige im Frontend mit allen Details:
        - ID und Links (mit Such-Kontext wenn verfügbar)
        - Thumbnail-URL
        - Datum
        - Personen
        - Objekte/Tags (KI-Analyse)
        
        Args:
            asset: Das zu formatierende Asset
            search_query: Die ursprüngliche Suchanfrage (für URL-Kontext)
            date_from: Von-Datum für den Suchkontext
            date_to: Bis-Datum für den Suchkontext
        """
        asset_id = asset.get('id')
        
        # Extract people names - handle both dict and string formats
        people_list = asset.get('people', [])
        people_names = []
        for p in people_list:
            if isinstance(p, dict):
                people_names.append(p.get('name', 'Unbekannt'))
            elif isinstance(p, str):
                people_names.append(p)
        people_names = list(dict.fromkeys([name for name in people_names if name]))

        return {
            'id': asset_id,
            'original_file_name': asset.get('originalFileName', 'Unbekannt'),
            'type': asset.get('type', 'IMAGE'),
            'thumbnail_url': self.get_asset_thumbnail_url(asset_id, 'preview'),
            'asset_url': self.get_asset_url(asset_id, search_query, date_from, date_to),
            'created_at': asset.get('fileCreatedAt', asset.get('createdAt')),
            'location': self._format_location(asset.get('exifInfo', {})),
            'people': people_names,
            'objects': asset.get('smartInfo', {}).get('objects', []),
            'tags': asset.get('smartInfo', {}).get('tags', []),
            'description': asset.get('smartInfo', {}).get('description', ''),
        }

    def _format_location(self, exif_info: Dict) -> Optional[str]:
        """Formatiert Standort-Informationen aus EXIF-Daten"""
        if not exif_info:
            return None

        city = exif_info.get('city')
        state = exif_info.get('state')
        country = exif_info.get('country')

        location_parts = [p for p in [city, state, country] if p]
        return ', '.join(location_parts) if location_parts else None

    def _extract_date_range(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrahiert Datumsbereiche aus der Query
        Erkennt: heute, gestern, diese Woche, diesen Monat, dieses Jahr, etc.
        
        Returns:
            (date_from_iso, date_to_iso) oder (None, None)
        """
        today = date.today()
        query_lower = query.lower()

        # Spezifisches Jahr, z.B. "aus dem Jahr 2026" oder "von 2026"
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", query_lower)
        if year_match and any(token in query_lower for token in ['jahr', 'year', 'von', 'aus']):
            year = int(year_match.group(1))
            return f"{year:04d}-01-01", f"{year + 1:04d}-01-01"
        
        # Heute
        if any(word in query_lower for word in ['heute', 'today', 'von heute', 'from today']):
            return today.isoformat(), (today + timedelta(days=1)).isoformat()
        
        # Gestern
        elif any(word in query_lower for word in ['gestern', 'yesterday', 'von gestern']):
            yesterday = today - timedelta(days=1)
            return yesterday.isoformat(), today.isoformat()
        
        # Diese Woche
        elif any(word in query_lower for word in ['diese woche', 'this week', 'diese woche']):
            monday = today - timedelta(days=today.weekday())
            return monday.isoformat(), (today + timedelta(days=1)).isoformat()
        
        # Letzter Monat / Diesen Monat
        elif any(word in query_lower for word in ['diesen monat', 'this month', 'diesen monat']):
            first_day = today.replace(day=1)
            if today.month == 12:
                last_day = today.replace(year=today.year+1, month=1, day=1)
            else:
                last_day = today.replace(month=today.month+1, day=1)
            return first_day.isoformat(), last_day.isoformat()
        
        # Letzte 7 Tage
        elif any(word in query_lower for word in ['letzte 7 tage', 'last 7 days', 'letzte woche']):
            week_ago = today - timedelta(days=7)
            return week_ago.isoformat(), (today + timedelta(days=1)).isoformat()
        
        # Letzte 30 Tage
        elif any(word in query_lower for word in ['letzte 30 tage', 'last 30 days', 'letzter monat']):
            month_ago = today - timedelta(days=30)
            return month_ago.isoformat(), (today + timedelta(days=1)).isoformat()
        
        return None, None

    def search_photos_intelligent(self, query: str, limit: int = 20, max_parallel: int = 2) -> Dict[str, Any]:
        """
        Intelligente Suche die verschiedene Suchstrategien kombiniert

        Uses parallel execution to avoid timeout stacking

        Erkennt automatisch:
        - Personennamen
        - Objekte
        - Orte
        - Datumsbereiche
        - Allgemeine Beschreibungen
        """
        results = []

        # Extrahiere Datumsbereiche aus der Query
        date_from, date_to = self._extract_date_range(query)
        if date_from or date_to:
            self.logger.info(f"Extracted date range: {date_from} to {date_to}")

        # Erkenne genannte Personen robust anhand der Immich-Personenliste
        people = self.get_people()
        mentioned_people = self._detect_people_in_query(query, people)

        # Für Kontext-/Objektsuche gezielte Keywords statt ganzer Satz
        relevant_terms = self._extract_relevant_terms(query)
        context_queries = self._expand_terms_with_synonyms(relevant_terms)
        if not context_queries:
            context_queries = [query]
        self.logger.info(f"Context queries for '{query}': {context_queries[:4]}")

        try:
            # Use ThreadPoolExecutor for parallel execution to avoid sequential timeout stacking
            with ThreadPoolExecutor(max_workers=max_parallel) as executor:
                futures = {}
                person_futures = {}

                # Strategie 1: Personensuche für erkannte Immich-Personen
                if mentioned_people:
                    for i, person in enumerate(mentioned_people[:max_parallel]):
                        person_name = person.get('name', '')
                        person_future = executor.submit(
                            self.search_by_person_name,
                            person_name,
                            limit,
                            date_from,
                            date_to
                        )
                        person_futures[f'person_{i}_{person_name}'] = person_future
                        futures[f'person_{i}_{person_name}'] = person_future

                # Strategie 2: Smart Search auf Keywords/Synonyme statt vollem Satz
                for i, smart_query in enumerate(context_queries[:max_parallel]):
                    smart_future = executor.submit(self.search_smart, smart_query, limit)
                    futures[f'smart_{i}_{smart_query}'] = smart_future
                
                # Strategie 3: Metadata search mit Datums-Filter falls verfügbar
                if date_from or date_to:
                    metadata_query = context_queries[0] if context_queries else query
                    metadata_future = executor.submit(
                        self.search_assets, 
                        query=metadata_query,
                        person_ids=None,
                        date_from=date_from, 
                        date_to=date_to, 
                        limit=limit
                    )
                    futures['metadata_date'] = metadata_future
                
                # Strategie 4: Context search (Objekte/Tags)
                context_future = executor.submit(self.search_by_context, query, limit)
                futures['context'] = context_future

                # Sammle Ergebnisse mit timeout protection
                total_timeout = self.timeout_long + 10  # Add buffer to timeout
                
                # PRIORITÄT: Sammle Person-Resultate ZUERST
                for future_name, future in person_futures.items():
                    try:
                        result = future.result(timeout=total_timeout)
                        if result:
                            self.logger.info(f"Got {len(result)} results from {future_name}")
                            results.extend(result)
                    except FuturesTimeoutError:
                        self.logger.warning(f"Timeout getting results from {future_name}")
                    except Exception as e:
                        self.logger.error(f"Error getting results from {future_name}: {e}")
                
                # Dann andere Quellen (nur wenn noch nicht genug results)
                for future_name, future in futures.items():
                    if future_name in person_futures:
                        continue  # Skip person futures, already processed
                    if len(results) >= limit:
                        break
                    try:
                        result = future.result(timeout=total_timeout)
                        if result:
                            self.logger.info(f"Got {len(result)} results from {future_name}")
                            results.extend(result)
                    except FuturesTimeoutError:
                        self.logger.warning(f"Timeout getting results from {future_name}")
                    except Exception as e:
                        self.logger.error(f"Error getting results from {future_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error in parallel search execution: {e}")
            # Fallback to sequential search if parallel fails
            try:
                smart_results = self.search_smart(query, limit=limit)
                if smart_results:
                    results.extend(smart_results)
            except Exception as fallback_error:
                self.logger.error(f"Fallback search also failed: {fallback_error}")

        # Deduplizierung UND nur limit Ergebnisse nehmen (nicht alle formatieren!)
        seen_ids = set()
        unique_results = []
        for asset in results:
            if len(unique_results) >= limit:  # Stop early once we have enough
                break
            asset_id = asset.get('id')
            if asset_id and asset_id not in seen_ids:
                seen_ids.add(asset_id)
                unique_results.append(asset)

        # Formatiere nur die gewünschten Ergebnisse für Anzeige MIT Suchkontext
        formatted_results = [
            self.format_asset_for_display(asset, search_query=query, date_from=date_from, date_to=date_to) 
            for asset in unique_results
        ]

        return {
            'success': True,
            'query': query,
            'count': len(formatted_results),
            'results': formatted_results
        }

    def search_by_context(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Sucht nach Fotos basierend auf KI-analysierte Kontextinformationen
        (Objekte, Tags, Beschreibungen die Immich erkannt hat)
        
        Filtert die assets die smartInfo.objects oder smartInfo.tags enthalten,
        die mit der Query übereinstimmen
        """
        try:
            # Hol alle Assets und filtere nach Kontext
            all_assets = self.get_all_assets(limit=1000)  # Get more to allow filtering
            
            query_lower = query.lower()
            relevant_terms = self._extract_relevant_terms(query)
            if not relevant_terms:
                relevant_terms = [query_lower]
            relevant_terms = self._expand_terms_with_synonyms(relevant_terms)

            matching_assets = []
            
            for asset in all_assets:
                smart_info = asset.get('smartInfo', {})
                objects = [str(o).lower() for o in smart_info.get('objects', [])]
                tags = [str(t).lower() for t in smart_info.get('tags', [])]
                description = smart_info.get('description', '').lower()
                
                searchable = objects + tags + ([description] if description else [])

                # Match on any relevant term from the natural language query
                if any(
                    term in field
                    for term in relevant_terms
                    for field in searchable
                ):
                    matching_assets.append(asset)
                    
                    if len(matching_assets) >= limit:
                        break
            
            self.logger.info(f"Found {len(matching_assets)} assets matching context query: {query}")
            return matching_assets
            
        except Exception as e:
            self.logger.error(f"Error in context search: {str(e)}")
            return []
