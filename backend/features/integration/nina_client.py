"""
NINA (Bundesamt fuer Bevoelkerungsschutz) API Client
Public API for civil protection warnings.
"""

import logging
import time
import re
from typing import Dict, Any, Optional, List
import requests
from .api_registry import APIClient


class NINAClient(APIClient):
    """Client for the NINA public API"""

    DEFAULT_BASE_URL = "https://warnung.bund.de/api31"
    DEFAULT_REGIONAL_KEYS_URL = (
        "https://www.xrepository.de/api/xrepository/"
        "urn:de:bund:destatis:bevoelkerungsstatistik:schluessel:rs_2021-07-31/"
        "download/Regionalschl_ssel_2021-07-31.json"
    )
    DEFAULT_REGIONAL_KEYS_TTL = 60 * 60 * 24
    _regional_keys_cache = None
    _regional_keys_cached_at = 0.0

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.base_url = (config.get('base_url') or self.DEFAULT_BASE_URL).rstrip('/')
        self.timeout = int(config.get('timeout', 10))
        self.ars = str(config.get('ars', '')).strip()
        self.regional_keys_url = config.get('regional_keys_url') or self.DEFAULT_REGIONAL_KEYS_URL
        self.regional_keys_cache_ttl = int(
            config.get('regional_keys_cache_ttl', self.DEFAULT_REGIONAL_KEYS_TTL)
        )

    @classmethod
    def requires_config(cls) -> bool:
        return False

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            'base_url': cls.DEFAULT_BASE_URL,
            'timeout': 10,
            'ars': '',
            'regional_keys_url': cls.DEFAULT_REGIONAL_KEYS_URL,
            'regional_keys_cache_ttl': cls.DEFAULT_REGIONAL_KEYS_TTL
        }

    def get_api_name(self) -> str:
        return "nina"

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'base_url': {
                'type': 'string',
                'required': False,
                'description': 'NINA API base URL',
                'example': self.DEFAULT_BASE_URL,
                'default': self.DEFAULT_BASE_URL
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'description': 'Request timeout in seconds',
                'default': 10
            },
            'ars': {
                'type': 'string',
                'required': False,
                'description': 'Amtlicher Regionalschluessel (ARS) fuer Standard-Warnungen',
                'example': '091620000000'
            },
            'regional_keys_url': {
                'type': 'string',
                'required': False,
                'description': 'Quelle fuer ARS-Regionalschluessel',
                'example': self.DEFAULT_REGIONAL_KEYS_URL,
                'default': self.DEFAULT_REGIONAL_KEYS_URL
            },
            'regional_keys_cache_ttl': {
                'type': 'number',
                'required': False,
                'description': 'Cache TTL fuer Regionalschluessel (Sekunden)',
                'example': self.DEFAULT_REGIONAL_KEYS_TTL,
                'default': self.DEFAULT_REGIONAL_KEYS_TTL
            }
        }

    def test_connection(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}/appdata/gsb/eventCodes/eventCodes.json",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True
            self.logger.error("NINA connection failed: %s", response.status_code)
            return False
        except requests.exceptions.Timeout:
            self.logger.error("NINA connection timeout")
            return False
        except Exception as exc:
            self.logger.error("NINA connection error: %s", exc)
            return False

    def get_dashboard(self, ars: str) -> Dict[str, Any]:
        return self._get_json(f"/dashboard/{ars}.json")

    def get_dashboard_with_fallback(self, ars: str) -> Dict[str, Any]:
        """Get dashboard data and automatically try broader ARS keys on 404."""
        normalized = self._normalize_ars(ars)
        if not normalized:
            raise ValueError('ARS is required')

        candidates = self._build_ars_fallbacks(normalized)
        last_error = None

        for candidate in candidates:
            try:
                data = self.get_dashboard(candidate)
                return {
                    'ars_requested': normalized,
                    'ars_used': candidate,
                    'fallback_used': candidate != normalized,
                    'data': data
                }
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                # Try next broader ARS only for 404. Other statuses should fail fast.
                if status == 404:
                    last_error = exc
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError('No ARS fallback candidates available')

    def get_regional_keys(self, query: str = '', limit: int = 200) -> Dict[str, Any]:
        """Fetch and normalize regional keys (ARS) list."""
        normalized = self._get_cached_regional_keys()

        if query:
            lowered = query.lower()
            query_norm = self._normalize_text(query)
            ranked = []
            for entry in normalized:
                ars = str(entry.get('ars', ''))
                name = str(entry.get('name', ''))
                hint = str(entry.get('hint', ''))

                if lowered not in ars.lower() and lowered not in name.lower() and lowered not in hint.lower():
                    continue

                score = 0
                if query_norm:
                    name_norm = self._normalize_text(name)
                    hint_norm = self._normalize_text(hint)
                    score = max(score, self._score_match(query_norm, name_norm))
                    score = max(score, int(self._score_match(query_norm, hint_norm) * 0.9))

                    # Prefer exact word matches (e.g. "berlin" in "berlin stadt") over partials (e.g. "berlingen").
                    name_tokens = [token for token in name_norm.split(' ') if token]
                    if query_norm in name_tokens:
                        score = max(score, 108)
                    elif name_norm.startswith(f"{query_norm} "):
                        score = max(score, 102)

                if lowered == ars.lower():
                    score = max(score, 110)
                elif ars.lower().startswith(lowered):
                    score = max(score, 95)

                ranked.append((score, entry))

            ranked.sort(key=lambda item: item[0], reverse=True)
            normalized = [entry for _, entry in ranked]

        if limit > 0:
            normalized = normalized[:limit]

        return {
            'total': len(normalized),
            'items': normalized
        }

    def resolve_ars_for_places(self, place_names: List[str]) -> Optional[Dict[str, Any]]:
        """Resolve the best matching ARS entry for a list of place names."""
        candidates = [self._normalize_text(name) for name in place_names if name]
        candidates = [entry for entry in candidates if entry]
        if not candidates:
            return None

        entries = self._get_cached_regional_keys()
        best = None
        best_score = 0

        for entry in entries:
            entry_name = self._normalize_text(entry.get('name', ''))
            entry_hint = self._normalize_text(entry.get('hint', ''))
            if not entry_name:
                continue

            score = 0
            for candidate in candidates:
                score = max(score, self._score_match(candidate, entry_name))
                if entry_hint:
                    score = max(score, int(self._score_match(candidate, entry_hint) * 0.85))

            if score > best_score:
                best_score = score
                best = entry

        if best and best_score >= 60:
            resolved = dict(best)
            resolved['score'] = best_score
            return resolved

        return None

    def _get_cached_regional_keys(self) -> list:
        now = time.time()
        ttl = self.regional_keys_cache_ttl
        cache = self.__class__._regional_keys_cache
        cached_at = self.__class__._regional_keys_cached_at

        if cache is not None and ttl > 0 and (now - cached_at) < ttl:
            return cache

        response = requests.get(self.regional_keys_url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        normalized = self._normalize_regional_keys(data)

        self.__class__._regional_keys_cache = normalized
        self.__class__._regional_keys_cached_at = now
        return normalized

    def get_warning(self, identifier: str) -> Dict[str, Any]:
        return self._get_json(f"/warnings/{identifier}.json")

    def get_warning_geojson(self, identifier: str) -> Dict[str, Any]:
        return self._get_json(f"/warnings/{identifier}.geojson")

    def get_map_data(self, source: str) -> Dict[str, Any]:
        return self._get_json(f"/{source}/mapData.json")

    def get_mowas_rss(self, ars: str) -> str:
        return self._get_text(f"/mowas/rss/{ars}.rss")

    def get_covid_rules(self, ars: str) -> Dict[str, Any]:
        return self._get_json(f"/appdata/covid/covidrules/DE/{ars}.json")

    def get_covid_infos(self) -> Dict[str, Any]:
        return self._get_json("/appdata/covid/covidinfos/DE/covidinfos.json")

    def get_covid_ticker(self) -> Dict[str, Any]:
        return self._get_json("/appdata/covid/covidticker/DE/covidticker.json")

    def get_covid_ticker_message(self, message_id: str) -> Dict[str, Any]:
        return self._get_json(f"/appdata/covid/covidticker/DE/tickermeldungen/{message_id}.json")

    def get_covid_map(self) -> Dict[str, Any]:
        return self._get_json("/appdata/covid/covidmap/DE/covidmap.json")

    def get_logos(self) -> Dict[str, Any]:
        return self._get_json("/appdata/gsb/logos/logos.json")

    def get_event_codes(self) -> Dict[str, Any]:
        return self._get_json("/appdata/gsb/eventCodes/eventCodes.json")

    def get_emergency_tips(self) -> Dict[str, Any]:
        return self._get_json("/appdata/gsb/notfalltipps/DE/notfalltipps.json")

    def get_faqs(self) -> Dict[str, Any]:
        return self._get_json("/appdata/gsb/faqs/DE/faq.json")

    def get_data_version(self) -> Dict[str, Any]:
        return self._get_json("/dynamic/version/dataVersion.json")

    def get_archive_mowas_mapping(self, identifier: str) -> Dict[str, Any]:
        return self._get_json(f"/archive.mowas/{identifier}-mapping.json")

    def get_archive_mowas(self, identifier: str) -> Dict[str, Any]:
        return self._get_json(f"/archive.mowas/{identifier}.json")

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _get_text(self, path: str, params: Optional[Dict[str, Any]] = None) -> str:
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _normalize_regional_keys(self, payload: Any) -> list:
        """Normalize regional keys to a list of dicts with ars, name, hint."""
        if isinstance(payload, dict):
            data = payload.get('daten') or payload.get('data') or payload.get('items')
        else:
            data = payload

        if not isinstance(data, list):
            return []

        normalized = []
        for entry in data:
            if isinstance(entry, list) and len(entry) >= 2:
                ars = str(entry[0]).strip()
                name = str(entry[1]).strip()
                hint = str(entry[2]).strip() if len(entry) > 2 and entry[2] is not None else ''
            elif isinstance(entry, dict):
                ars = str(entry.get('ARS') or entry.get('ars') or entry.get('RS') or entry.get('rs') or '').strip()
                name = str(entry.get('Name') or entry.get('name') or entry.get('Gemeinde') or '').strip()
                hint = str(entry.get('Hinweis') or entry.get('hint') or '').strip()
            else:
                continue

            if not ars or not name:
                continue

            normalized.append({
                'ars': ars,
                'name': name,
                'hint': hint
            })

        return normalized

    def _normalize_text(self, value: str) -> str:
        if not value:
            return ''
        cleaned = re.sub(r"[^\w\s-]", " ", str(value).lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _score_match(self, query: str, target: str) -> int:
        if not query or not target:
            return 0
        if query == target:
            return 100
        if target.startswith(query) or query.startswith(target):
            return 85
        if query in target:
            return 70
        return 0

    def _normalize_ars(self, ars: Any) -> str:
        if ars is None:
            return ''
        cleaned = re.sub(r"\D", "", str(ars))
        if len(cleaned) >= 12:
            return cleaned[:12]
        return cleaned

    def _build_ars_fallbacks(self, ars: str) -> List[str]:
        if not ars:
            return []

        # The NINA dashboard is not available for every municipality-level ARS.
        # Try broader administrative levels by zeroing trailing segments.
        fallbacks = [
            ars,
            ars[:8] + '0000',
            ars[:6] + '000000',
            ars[:5] + '0000000',
            ars[:3] + '000000000',
            ars[:2] + '0000000000',
        ]

        seen = set()
        unique = []
        for candidate in fallbacks:
            if len(candidate) == 12 and candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)
        return unique
