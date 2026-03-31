import logging
from typing import List, Dict, Optional
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET


class NextcloudSearchClient:
    """Client for Nextcloud Unified Search API integration"""

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize Search API client

        Args:
            url: Nextcloud server URL (e.g., https://cloud.example.com)
            username: Nextcloud username
            password: Nextcloud password or app password
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.logger = logging.getLogger(__name__)

        # OCS API headers
        self.ocs_headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        # WebDAV namespaces for SEARCH method
        self.namespaces = {
            'd': 'DAV:',
            'oc': 'http://owncloud.org/ns',
            'nc': 'http://nextcloud.org/ns'
        }

    def test_connection(self) -> bool:
        """
        Test Search API connection to Nextcloud

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Test OCS API endpoint
            url = f"{self.url}/ocs/v2.php/search"
            self.logger.info(f"Testing Search API connection to: {url}")

            response = self.session.get(url, headers=self.ocs_headers, timeout=10)

            self.logger.info(f"Search API connection test response status: {response.status_code}")

            if response.status_code in [200, 207]:
                self.logger.info("Search API connection successful")
                return True
            elif response.status_code == 401:
                self.logger.error("Search API authentication failed - check username/password")
                return False
            else:
                self.logger.error(f"Search API unexpected status code: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("Search API connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("Search API connection error - check URL and network")
            return False
        except Exception as e:
            self.logger.error(f"Search API connection failed: {str(e)}")
            return False

    def get_search_providers(self) -> List[Dict]:
        """
        Get available search providers in Nextcloud

        Returns:
            List of search provider dictionaries
        """
        providers = []

        try:
            url = f"{self.url}/ocs/v2.php/search/providers"

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                ocs_data = data.get('ocs', {})
                providers_data = ocs_data.get('data', [])

                for provider in providers_data:
                    providers.append({
                        'id': provider.get('id', ''),
                        'name': provider.get('name', ''),
                        'order': provider.get('order', 0)
                    })

                self.logger.info(f"Found {len(providers)} search providers")
            else:
                self.logger.error(f"Failed to get search providers: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error getting search providers: {str(e)}")

        return providers

    def search(self, query: str, provider: str = None, limit: int = 25, cursor: int = None) -> Dict:
        """
        Perform unified search across Nextcloud

        Args:
            query: Search query string
            provider: Specific provider to search (e.g., 'files', 'contacts', 'calendar')
                     If None, searches all providers
            limit: Maximum number of results per provider (default: 25)
            cursor: Pagination cursor for next page

        Returns:
            Dictionary with search results by provider
        """
        try:
            # Build base URL
            if provider:
                url = f"{self.url}/ocs/v2.php/search/providers/{provider}/search"
            else:
                url = f"{self.url}/ocs/v2.php/search"

            # Build parameters
            params = {
                'term': query,
                'limit': limit
            }

            if cursor is not None:
                params['cursor'] = cursor

            response = self.session.get(
                url,
                headers=self.ocs_headers,
                params=params,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                ocs_data = data.get('ocs', {})
                search_data = ocs_data.get('data', {})

                results = {
                    'query': query,
                    'results': [],
                    'cursor': search_data.get('cursor', None)
                }

                # Handle different response formats
                if isinstance(search_data, dict):
                    # Single provider search
                    if 'entries' in search_data:
                        entries = search_data.get('entries', [])
                        results['results'] = self._format_search_results(entries, provider)
                    # Multi-provider search
                    else:
                        for prov_id, prov_data in search_data.items():
                            if isinstance(prov_data, dict) and 'entries' in prov_data:
                                entries = prov_data.get('entries', [])
                                formatted = self._format_search_results(entries, prov_id)
                                results['results'].extend(formatted)

                self.logger.info(f"Search for '{query}' found {len(results['results'])} results")
                return results
            else:
                self.logger.error(f"Search failed: {response.status_code}")
                return {'query': query, 'results': [], 'cursor': None}

        except Exception as e:
            self.logger.error(f"Error performing search: {str(e)}")
            return {'query': query, 'results': [], 'cursor': None}

    def _format_search_results(self, entries: List, provider: str = None) -> List[Dict]:
        """
        Format search result entries into a consistent structure

        Args:
            entries: List of raw search entries
            provider: Provider ID

        Returns:
            List of formatted result dictionaries
        """
        formatted = []

        for entry in entries:
            result = {
                'provider': provider or entry.get('provider', 'unknown'),
                'title': entry.get('title', ''),
                'subline': entry.get('subline', ''),
                'resource_url': entry.get('resourceUrl', ''),
                'icon': entry.get('icon', ''),
                'rounded': entry.get('rounded', False),
                'thumbnailUrl': entry.get('thumbnailUrl', ''),
                'attributes': entry.get('attributes', {})
            }
            formatted.append(result)

        return formatted

    def search_files(self, query: str, limit: int = 25) -> List[Dict]:
        """
        Search specifically for files

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of file results
        """
        results = self.search(query, provider='files', limit=limit)
        return results.get('results', [])

    def search_contacts(self, query: str, limit: int = 25) -> List[Dict]:
        """
        Search specifically for contacts

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of contact results
        """
        results = self.search(query, provider='contacts', limit=limit)
        return results.get('results', [])

    def search_calendar(self, query: str, limit: int = 25) -> List[Dict]:
        """
        Search specifically for calendar events

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of calendar event results
        """
        results = self.search(query, provider='calendar', limit=limit)
        return results.get('results', [])

    def search_tasks(self, query: str, limit: int = 25) -> List[Dict]:
        """
        Search specifically for tasks

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of task results
        """
        results = self.search(query, provider='tasks', limit=limit)
        return results.get('results', [])

    def search_files_webdav(self, query: str, path: str = '/', limit: int = 100) -> List[Dict]:
        """
        Search files using WebDAV SEARCH method (alternative to OCS API)

        Args:
            query: Search query
            path: Path to search in (default: root)
            limit: Maximum results

        Returns:
            List of file dictionaries
        """
        files = []

        try:
            url = f"{self.url}/remote.php/dav/files/{self.username}{path}"

            # SEARCH request body
            search_body = f'''<?xml version="1.0" encoding="UTF-8"?>
<d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
    <d:basicsearch>
        <d:select>
            <d:prop>
                <d:displayname/>
                <d:getcontenttype/>
                <d:getetag/>
                <d:getlastmodified/>
                <oc:size/>
            </d:prop>
        </d:select>
        <d:from>
            <d:scope>
                <d:href>{url}</d:href>
                <d:depth>infinity</d:depth>
            </d:scope>
        </d:from>
        <d:where>
            <d:like>
                <d:prop>
                    <d:displayname/>
                </d:prop>
                <d:literal>%{query}%</d:literal>
            </d:like>
        </d:where>
        <d:orderby/>
    </d:basicsearch>
</d:searchrequest>'''

            headers = {
                'Content-Type': 'application/xml; charset=utf-8',
                'Depth': 'infinity'
            }

            response = self.session.request(
                'SEARCH',
                url,
                headers=headers,
                data=search_body.encode('utf-8'),
                timeout=60
            )

            if response.status_code in [200, 207]:
                root = ET.fromstring(response.text)

                for response_elem in root.findall('.//d:response', self.namespaces):
                    href_elem = response_elem.find('d:href', self.namespaces)
                    if href_elem is None:
                        continue

                    href = href_elem.text

                    # Extract properties
                    propstat = response_elem.find('d:propstat', self.namespaces)
                    if propstat is None:
                        continue

                    prop = propstat.find('d:prop', self.namespaces)
                    if prop is None:
                        continue

                    displayname_elem = prop.find('d:displayname', self.namespaces)
                    displayname = displayname_elem.text if displayname_elem is not None else href.split('/')[-1]

                    size_elem = prop.find('oc:size', self.namespaces)
                    size = int(size_elem.text) if size_elem is not None and size_elem.text else 0

                    modified_elem = prop.find('d:getlastmodified', self.namespaces)
                    modified = modified_elem.text if modified_elem is not None else ""

                    contenttype_elem = prop.find('d:getcontenttype', self.namespaces)
                    contenttype = contenttype_elem.text if contenttype_elem is not None else ""

                    files.append({
                        'name': displayname,
                        'path': href.replace(f"/remote.php/dav/files/{self.username}", ''),
                        'size': size,
                        'modified': modified,
                        'content_type': contenttype,
                        'url': f"{self.url}{href}"
                    })

                    if len(files) >= limit:
                        break

                self.logger.info(f"WebDAV search for '{query}' found {len(files)} files")
            else:
                self.logger.error(f"WebDAV search failed: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error performing WebDAV search: {str(e)}")

        return files
