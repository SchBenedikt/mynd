import logging
from typing import List, Dict, Optional
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET


class NextcloudCardDAVClient:
    """Client for Nextcloud CardDAV integration to manage contacts"""

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize CardDAV client

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

        # CardDAV XML namespaces
        self.namespaces = {
            'd': 'DAV:',
            'card': 'urn:ietf:params:xml:ns:carddav',
            'oc': 'http://owncloud.org/ns',
            'nc': 'http://nextcloud.org/ns'
        }

    def test_connection(self) -> bool:
        """
        Test CardDAV connection to Nextcloud

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            url = f"{self.url}/remote.php/dav/addressbooks/users/{self.username}/"
            self.logger.info(f"Testing CardDAV connection to: {url}")

            response = self.session.request('PROPFIND', url, timeout=10)

            self.logger.info(f"CardDAV connection test response status: {response.status_code}")

            if response.status_code in [200, 207]:
                self.logger.info("CardDAV connection successful")
                return True
            elif response.status_code == 401:
                self.logger.error("CardDAV authentication failed - check username/password")
                return False
            elif response.status_code == 404:
                self.logger.warning("CardDAV endpoint not found - may not be enabled")
                return False
            else:
                self.logger.error(f"CardDAV unexpected status code: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("CardDAV connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("CardDAV connection error - check URL and network")
            return False
        except Exception as e:
            self.logger.error(f"CardDAV connection failed: {str(e)}")
            return False

    def get_addressbooks(self) -> List[Dict]:
        """
        Get all addressbooks for the user

        Returns:
            List of addressbook dictionaries with keys: name, url, display_name
        """
        addressbooks = []

        try:
            url = f"{self.url}/remote.php/dav/addressbooks/users/{self.username}/"
            headers = {
                'Depth': '1',
                'Content-Type': 'application/xml; charset=utf-8'
            }

            # PROPFIND body to request addressbook properties
            propfind_body = '''<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
    <d:prop>
        <d:displayname />
        <d:resourcetype />
        <card:addressbook-description />
    </d:prop>
</d:propfind>'''

            response = self.session.request(
                'PROPFIND',
                url,
                headers=headers,
                data=propfind_body.encode('utf-8'),
                timeout=30
            )

            if response.status_code == 207:
                root = ET.fromstring(response.text)

                for response_elem in root.findall('.//d:response', self.namespaces):
                    href_elem = response_elem.find('d:href', self.namespaces)
                    if href_elem is None:
                        continue

                    href = href_elem.text

                    # Check if this is an addressbook (not the parent collection)
                    resourcetype = response_elem.find('.//d:resourcetype', self.namespaces)
                    if resourcetype is not None:
                        is_addressbook = resourcetype.find('card:addressbook', self.namespaces) is not None
                        if not is_addressbook:
                            continue

                    # Extract displayname
                    displayname_elem = response_elem.find('.//d:displayname', self.namespaces)
                    displayname = displayname_elem.text if displayname_elem is not None else href.split('/')[-2]

                    # Extract description
                    desc_elem = response_elem.find('.//card:addressbook-description', self.namespaces)
                    description = desc_elem.text if desc_elem is not None else ""

                    addressbooks.append({
                        'name': href.split('/')[-2] if href.endswith('/') else href.split('/')[-1],
                        'url': href,
                        'display_name': displayname,
                        'description': description
                    })

                self.logger.info(f"Found {len(addressbooks)} addressbooks")
            else:
                self.logger.error(f"Failed to get addressbooks: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error getting addressbooks: {str(e)}")

        return addressbooks

    def get_contacts(self, addressbook_name: str = None) -> List[Dict]:
        """
        Get contacts from an addressbook

        Args:
            addressbook_name: Name of addressbook (default: contacts)

        Returns:
            List of contact dictionaries with parsed vCard data
        """
        if addressbook_name is None:
            addressbook_name = "contacts"

        contacts = []

        try:
            url = f"{self.url}/remote.php/dav/addressbooks/users/{self.username}/{addressbook_name}/"
            headers = {
                'Depth': '1',
                'Content-Type': 'application/xml; charset=utf-8'
            }

            # PROPFIND to get all vCards
            propfind_body = '''<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
    <d:prop>
        <d:getetag />
        <card:address-data />
    </d:prop>
</d:propfind>'''

            response = self.session.request(
                'PROPFIND',
                url,
                headers=headers,
                data=propfind_body.encode('utf-8'),
                timeout=60
            )

            if response.status_code == 207:
                root = ET.fromstring(response.text)

                for response_elem in root.findall('.//d:response', self.namespaces):
                    href_elem = response_elem.find('d:href', self.namespaces)
                    if href_elem is None:
                        continue

                    href = href_elem.text

                    # Skip the addressbook itself
                    if href.endswith(f'/{addressbook_name}/'):
                        continue

                    # Get vCard data
                    address_data_elem = response_elem.find('.//card:address-data', self.namespaces)
                    if address_data_elem is not None and address_data_elem.text:
                        vcard_data = address_data_elem.text
                        contact = self._parse_vcard(vcard_data)
                        if contact:
                            contact['url'] = href
                            contact['id'] = href.split('/')[-1].replace('.vcf', '')
                            contacts.append(contact)

                self.logger.info(f"Found {len(contacts)} contacts in {addressbook_name}")
            else:
                self.logger.error(f"Failed to get contacts: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Error getting contacts: {str(e)}")

        return contacts

    def _parse_vcard(self, vcard_text: str) -> Optional[Dict]:
        """
        Parse vCard text into a dictionary

        Args:
            vcard_text: Raw vCard text

        Returns:
            Dictionary with contact information
        """
        try:
            contact = {
                'full_name': '',
                'given_name': '',
                'family_name': '',
                'organization': '',
                'email': [],
                'phone': [],
                'address': [],
                'note': '',
                'raw_vcard': vcard_text
            }

            lines = vcard_text.split('\n')
            for line in lines:
                line = line.strip()

                if line.startswith('FN:'):
                    contact['full_name'] = line[3:]
                elif line.startswith('N:'):
                    # Format: family;given;additional;prefix;suffix
                    name_parts = line[2:].split(';')
                    if len(name_parts) >= 2:
                        contact['family_name'] = name_parts[0]
                        contact['given_name'] = name_parts[1]
                elif line.startswith('ORG:'):
                    contact['organization'] = line[4:]
                elif line.startswith('EMAIL'):
                    email = line.split(':', 1)[1] if ':' in line else ''
                    if email:
                        contact['email'].append(email)
                elif line.startswith('TEL'):
                    phone = line.split(':', 1)[1] if ':' in line else ''
                    if phone:
                        contact['phone'].append(phone)
                elif line.startswith('ADR'):
                    address = line.split(':', 1)[1] if ':' in line else ''
                    if address:
                        contact['address'].append(address)
                elif line.startswith('NOTE:'):
                    contact['note'] = line[5:]

            # Only return if we have at least a name
            if contact['full_name'] or contact['given_name'] or contact['family_name']:
                return contact

            return None

        except Exception as e:
            self.logger.error(f"Error parsing vCard: {str(e)}")
            return None

    def search_contacts(self, query: str, addressbook_name: str = None) -> List[Dict]:
        """
        Search for contacts by name, email, or organization

        Args:
            query: Search query string
            addressbook_name: Name of addressbook to search (default: contacts)

        Returns:
            List of matching contacts
        """
        if addressbook_name is None:
            addressbook_name = "contacts"

        try:
            # Get all contacts and filter locally
            all_contacts = self.get_contacts(addressbook_name)
            query_lower = query.lower()

            matching_contacts = []
            for contact in all_contacts:
                # Search in name, email, organization
                searchable_text = ' '.join([
                    contact.get('full_name', ''),
                    contact.get('given_name', ''),
                    contact.get('family_name', ''),
                    contact.get('organization', ''),
                    ' '.join(contact.get('email', [])),
                    ' '.join(contact.get('phone', []))
                ]).lower()

                if query_lower in searchable_text:
                    matching_contacts.append(contact)

            self.logger.info(f"Found {len(matching_contacts)} contacts matching '{query}'")
            return matching_contacts

        except Exception as e:
            self.logger.error(f"Error searching contacts: {str(e)}")
            return []

    def get_contact_by_id(self, contact_id: str, addressbook_name: str = None) -> Optional[Dict]:
        """
        Get a specific contact by ID

        Args:
            contact_id: Contact ID (filename without .vcf)
            addressbook_name: Name of addressbook (default: contacts)

        Returns:
            Contact dictionary or None if not found
        """
        if addressbook_name is None:
            addressbook_name = "contacts"

        try:
            url = f"{self.url}/remote.php/dav/addressbooks/users/{self.username}/{addressbook_name}/{contact_id}.vcf"

            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                vcard_data = response.text
                contact = self._parse_vcard(vcard_data)
                if contact:
                    contact['url'] = url
                    contact['id'] = contact_id
                    return contact
            else:
                self.logger.error(f"Contact not found: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error getting contact by ID: {str(e)}")
            return None
