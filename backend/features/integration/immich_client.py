import os
import sys
import logging
from typing import List, Dict, Optional, Any
import requests
from datetime import datetime, date

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

class ImmichClient:
    """Client für Immich-Integration über REST API"""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key"""
        return {
            'X-Api-Key': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> bool:
        """Testet die Verbindung zu Immich"""
        try:
            # Test mit /api/server-info/ping endpoint
            url = f"{self.url}/api/server-info/ping"
            self.logger.info(f"Testing connection to: {url}")

            response = requests.get(url, headers=self._get_headers(), timeout=10)

            self.logger.info(f"Connection test response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get('res') == 'pong':
                    self.logger.info("Immich connection successful")
                    return True

            self.logger.error(f"Unexpected response: {response.status_code}")
            return False

        except requests.exceptions.Timeout:
            self.logger.error("Connection timeout - check URL and network")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("Connection error - check URL and network connectivity")
            return False
        except Exception as e:
            self.logger.error(f"Immich connection failed: {str(e)}")
            return False

    def get_all_assets(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Holt alle Assets (Fotos und Videos) von Immich"""
        try:
            url = f"{self.url}/api/asset"
            params = {
                'take': limit,
                'skip': skip
            }

            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)

            if response.status_code == 200:
                assets = response.json()
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
            # Verwende den Search API endpoint
            url = f"{self.url}/api/search/metadata"

            payload = {}

            if query:
                payload['query'] = query

            if person_ids:
                payload['personIds'] = person_ids

            if date_from:
                payload['takenAfter'] = date_from

            if date_to:
                payload['takenBefore'] = date_to

            # Setze Limit
            payload['take'] = limit

            self.logger.info(f"Searching Immich with payload: {payload}")

            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                assets = result.get('assets', {}).get('items', [])
                self.logger.info(f"Found {len(assets)} assets matching search criteria")
                return assets
            else:
                self.logger.error(f"Search failed: {response.status_code} - {response.text}")
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

            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                assets = result.get('items', [])
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
            url = f"{self.url}/api/person"

            response = requests.get(url, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                people = response.json()
                self.logger.info(f"Retrieved {len(people.get('people', []))} people from Immich")
                return people.get('people', [])
            else:
                self.logger.error(f"Failed to get people: {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"Error getting people: {str(e)}")
            return []

    def search_by_person_name(self, person_name: str, limit: int = 20) -> List[Dict[str, Any]]:
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
            self.logger.info(f"Found {len(person_ids)} people matching '{person_name}': {[p.get('name') for p in matching_people]}")

            # Suche nach Assets dieser Personen
            return self.search_assets(person_ids=person_ids, limit=limit)

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
        return f"{self.url}/api/asset/thumbnail/{asset_id}?size={size}"

    def get_asset_url(self, asset_id: str) -> str:
        """Generiert die URL zum vollständigen Asset"""
        return f"{self.url}/api/asset/file/{asset_id}"

    def get_asset_info(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Holt detaillierte Informationen zu einem Asset"""
        try:
            url = f"{self.url}/api/asset/assetById/{asset_id}"

            response = requests.get(url, headers=self._get_headers(), timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to get asset info: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error getting asset info: {str(e)}")
            return None

    def format_asset_for_display(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formatiert ein Asset für die Anzeige im Frontend
        """
        asset_id = asset.get('id')

        return {
            'id': asset_id,
            'original_file_name': asset.get('originalFileName', 'Unbekannt'),
            'type': asset.get('type', 'IMAGE'),
            'thumbnail_url': self.get_asset_thumbnail_url(asset_id, 'preview'),
            'asset_url': self.get_asset_url(asset_id),
            'created_at': asset.get('fileCreatedAt', asset.get('createdAt')),
            'location': self._format_location(asset.get('exifInfo', {})),
            'people': [p.get('name', 'Unbekannt') for p in asset.get('people', [])],
            'objects': asset.get('smartInfo', {}).get('objects', []),
            'tags': asset.get('smartInfo', {}).get('tags', []),
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

    def search_photos_intelligent(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """
        Intelligente Suche die verschiedene Suchstrategien kombiniert

        Erkennt automatisch:
        - Personennamen
        - Objekte
        - Orte
        - Datumsbereiche
        - Allgemeine Beschreibungen
        """
        results = []

        # Strategie 1: Versuche Smart Search (CLIP-basiert)
        smart_results = self.search_smart(query, limit=limit)
        if smart_results:
            results.extend(smart_results)

        # Strategie 2: Falls noch Platz, versuche Personensuche
        # Extrahiere potentielle Namen aus Query (Wörter mit Großbuchstaben)
        words = query.split()
        potential_names = [w for w in words if w and w[0].isupper()]

        if potential_names and len(results) < limit:
            for name in potential_names:
                person_results = self.search_by_person_name(name, limit=limit-len(results))
                results.extend(person_results)
                if len(results) >= limit:
                    break

        # Deduplizierung
        seen_ids = set()
        unique_results = []
        for asset in results:
            asset_id = asset.get('id')
            if asset_id and asset_id not in seen_ids:
                seen_ids.add(asset_id)
                unique_results.append(asset)

        # Formatiere für Anzeige
        formatted_results = [self.format_asset_for_display(asset) for asset in unique_results[:limit]]

        return {
            'success': True,
            'query': query,
            'count': len(formatted_results),
            'results': formatted_results
        }
