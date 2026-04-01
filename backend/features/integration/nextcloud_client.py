import os
import sys
import logging
from typing import List, Dict, Optional, Union
import requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from backend.features.documents.parser import DocumentParser
from backend.features.integration.auth_provider import AuthProvider
from backend.features.integration.auth_manager import get_auth_manager

class NextcloudClient:
    """Client für Nextcloud-Integration über WebDAV"""

    def __init__(self, url: str, username: str = None, password: str = None, auth_provider: AuthProvider = None):
        """
        Initialize Nextcloud client

        Args:
            url: Nextcloud server URL
            username: Username (for backward compatibility with basic auth)
            password: Password (for backward compatibility with basic auth)
            auth_provider: AuthProvider instance (recommended)
        """
        self.url = url.rstrip('/')
        self.username = username
        self.parser = DocumentParser()
        self.logger = logging.getLogger(__name__)

        # Set up authentication
        if auth_provider:
            self.auth_provider = auth_provider
        elif username and password:
            # Backward compatibility: create basic auth provider
            auth_manager = get_auth_manager()
            self.auth_provider = auth_manager.create_basic_auth(username, password)
        else:
            raise ValueError("Either auth_provider or username/password must be provided")

        # Unterstützte Dateiformate - erweitert um mehr Formate
        self.supported_formats = {
            '.pdf', '.docx', '.doc', '.xlsx', '.xls',
            '.pptx', '.ppt', '.md', '.markdown',
            '.txt', '.html', '.htm', '.rtf', '.odt',
            '.ods', '.odp', '.csv', '.json', '.xml',
            '.epub', '.mobi', '.pages', '.numbers', '.key'
        }
    
    def test_connection(self) -> bool:
        """Testet die Verbindung zu Nextcloud mit verbesserter Fehlerbehandlung"""
        try:
            # Get username from auth provider config or fallback to self.username
            if not self.username:
                self.username = self.auth_provider.config.get('username', 'unknown')

            url = f"{self.url}/remote.php/dav/files/{self.username}/"
            self.logger.info(f"Testing connection to: {url}")

            response = requests.request('PROPFIND', url, auth=self.auth_provider.get_auth(), timeout=30)
            
            self.logger.info(f"Connection test response status: {response.status_code}")
            
            if response.status_code in [200, 207]:
                self.logger.info("Nextcloud connection successful")
                return True
            elif response.status_code == 401:
                self.logger.error("Authentication failed - check username/password")
                return False
            elif response.status_code == 404:
                self.logger.info("Connection successful (directory may be empty)")
                return True
            else:
                self.logger.error(f"Unexpected status code: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error("Connection timeout - check URL and network")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("Connection error - check URL and network connectivity")
            return False
        except Exception as e:
            self.logger.error(f"Nextcloud connection failed: {str(e)}")
            return False
    
    def list_files(self, remote_path: str = '/', recursive: bool = True) -> List[Dict]:
        """Listet Dateien in einem Nextcloud-Verzeichnis auf - verbesserte Erkennung"""
        files = []
        
        try:
            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            
            # PROPFIND request für Verzeichnisinhalt
            headers = {'Depth': '1' if not recursive else 'infinity'}
            response = requests.request('PROPFIND', url, auth=self.auth_provider.get_auth(), headers=headers, timeout=60)
            
            if response.status_code in [200, 207]:
                # XML-Verarbeitung mit besserer Fehlerbehandlung
                content = response.text
                import xml.etree.ElementTree as ET
                
                try:
                    # Versuche XML zu parsen
                    root = ET.fromstring(content)
                    
                    # Namespace für WebDAV
                    namespaces = {
                        'd': 'DAV:',
                        'oc': 'http://owncloud.org/ns',
                        'nc': 'http://nextcloud.org/ns'
                    }
                    
                    for response_elem in root.findall('.//d:response', namespaces):
                        href_elem = response_elem.find('d:href', namespaces)
                        if href_elem is not None:
                            href = href_elem.text
                            
                            # Überspringe das Verzeichnis selbst
                            if href == f"/remote.php/dav/files/{self.username}{remote_path.rstrip('/')}/":
                                continue
                            
                            # Dateiname und Extension extrahieren
                            file_name = href.split('/')[-1]
                            if not file_name or file_name.endswith('/'):
                                continue  # Überspringe Verzeichnisse
                                
                            file_ext = os.path.splitext(file_name)[1].lower()
                            
                            # Alle Dateien aufnehmen, nicht nur unterstützte Formate
                            # Filterung erfolgt später bei der Verarbeitung
                            files.append({
                                'path': href.replace(f"/remote.php/dav/files/{self.username}", ''),
                                'name': file_name,
                                'size': 0,  # Wird später geholt
                                'extension': file_ext
                            })
                            
                except ET.ParseError:
                    # Fallback auf Regex wenn XML fehlerhaft
                    import re
                    
                    # Finde alle Dateipfade
                    href_pattern = r'<d:href>([^<]+)</d:href>'
                    hrefs = re.findall(href_pattern, content)
                    
                    for href in hrefs:
                        if href != f"/remote.php/dav/files/{self.username}{remote_path}":
                            # Dateiname extrahieren
                            file_name = href.split('/')[-1]
                            if not file_name or file_name.endswith('/'):
                                continue
                                
                            file_ext = os.path.splitext(file_name)[1].lower()
                            
                            # Alle Dateien aufnehmen
                            files.append({
                                'path': href.replace(f"/remote.php/dav/files/{self.username}", ''),
                                'name': file_name,
                                'size': 0,
                                'extension': file_ext
                            })
                
                self.logger.info(f"Found {len(files)} total files in {remote_path}")
                
                # Logge gefundene Dateitypen für Analyse
                extensions = set()
                for f in files:
                    if f['extension']:
                        extensions.add(f['extension'])
                
                if extensions:
                    self.logger.info(f"File extensions found: {sorted(list(extensions))}")
            
        except Exception as e:
            self.logger.error(f"Error listing files in {remote_path}: {str(e)}")
        
        return files
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Lädt eine Datei von Nextcloud herunter mit verbesserter Fehlerbehandlung"""
        try:
            # Lokales Verzeichnis erstellen falls nötig
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)
            
            # Datei herunterladen
            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            self.logger.debug(f"Downloading {remote_path} to {local_path}")

            response = requests.get(url, auth=self.auth_provider.get_auth(), timeout=60)
            
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                self.logger.debug(f"Successfully downloaded {remote_path}")
                return True
            elif response.status_code == 401:
                self.logger.error(f"Authentication failed for {remote_path}")
                return False
            elif response.status_code == 404:
                self.logger.error(f"File not found: {remote_path}")
                return False
            else:
                self.logger.error(f"Download failed with status {response.status_code} for {remote_path}")
                return False
        
        except requests.exceptions.Timeout:
            self.logger.error(f"Download timeout for {remote_path}")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection error during download of {remote_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error downloading {remote_path}: {str(e)}")
            return False
    
    def parse_remote_file(self, remote_path: str) -> str:
        """Parst eine Remote-Datei ohne sie lokal zu speichern - mit verbessertem Caching"""
        try:
            # Prüfe ob Dateiformat unterstützt wird
            file_ext = os.path.splitext(remote_path)[1].lower()
            if file_ext not in self.supported_formats:
                self.logger.debug(f"Skipping unsupported file format: {file_ext}")
                return ""
            
            # Sicheren Dateinamen erstellen
            import hashlib
            safe_hash = hashlib.md5(remote_path.encode()).hexdigest()[:8]
            safe_filename = f"temp_{safe_hash}_{os.path.basename(remote_path).replace('/', '_').replace('%', '_')}"
            temp_file = safe_filename
            
            if self.download_file(remote_path, temp_file):
                # Datei parsen
                content = self.parser.parse_file(temp_file)
                
                # Temporäre Datei löschen
                try:
                    os.remove(temp_file)
                except:
                    pass
                
                return content
            else:
                return ""
        
        except Exception as e:
            self.logger.error(f"Error parsing remote file {remote_path}: {str(e)}")
            return ""
    
    def build_knowledge_base(self, remote_path: str = '/', max_files: int = 100) -> Dict:
        """Baut eine Wissensbasis aus Nextcloud-Dateien"""
        self.logger.info(f"Building knowledge base from {remote_path}")
        
        # Dateien auflisten
        files = self.list_files(remote_path, recursive=True)
        
        # Begrenze die Anzahl der Dateien
        if len(files) > max_files:
            files = files[:max_files]
            self.logger.warning(f"Limited to {max_files} files")
        
        knowledge_base = {
            'files_processed': 0,
            'total_size': 0,
            'documents': [],
            'errors': []
        }
        
        for file_info in files:
            try:
                self.logger.info(f"Processing: {file_info['name']}")
                
                # Datei-Inhalt parsen
                content = self.parse_remote_file(file_info['path'])
                
                if content and len(content.strip()) > 50:  # Mindestlänge
                    knowledge_base['documents'].append({
                        'path': file_info['path'],
                        'name': file_info['name'],
                        'content': content,
                        'size': file_info['size'],
                        'extension': file_info['extension']
                    })
                    knowledge_base['files_processed'] += 1
                    knowledge_base['total_size'] += file_info['size']
                else:
                    knowledge_base['errors'].append(f"Empty or short content: {file_info['name']}")
            
            except Exception as e:
                error_msg = f"Error processing {file_info['name']}: {str(e)}"
                self.logger.error(error_msg)
                knowledge_base['errors'].append(error_msg)
        
        self.logger.info(f"Knowledge base built: {knowledge_base['files_processed']} files processed")
        return knowledge_base

    # Write Operations (WebDAV)

    def upload_file(self, local_path: str, remote_path: str, overwrite: bool = True) -> bool:
        """
        Upload a file to Nextcloud via WebDAV PUT

        Args:
            local_path: Path to local file
            remote_path: Destination path in Nextcloud (e.g., '/Documents/file.txt')
            overwrite: Whether to overwrite existing files (default: True)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(local_path):
                self.logger.error(f"Local file not found: {local_path}")
                return False

            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            self.logger.info(f"Uploading {local_path} to {remote_path}")

            with open(local_path, 'rb') as f:
                file_data = f.read()

            headers = {}
            if not overwrite:
                headers['If-None-Match'] = '*'  # Only create if doesn't exist

            response = requests.put(
                url,
                auth=self.auth_provider.get_auth(),
                data=file_data,
                headers=headers,
                timeout=120
            )

            if response.status_code in [200, 201, 204]:
                self.logger.info(f"Successfully uploaded {remote_path}")
                return True
            elif response.status_code == 412:
                self.logger.error(f"File already exists and overwrite is disabled: {remote_path}")
                return False
            elif response.status_code == 401:
                self.logger.error("Authentication failed")
                return False
            else:
                self.logger.error(f"Upload failed with status {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error uploading file: {str(e)}")
            return False

    def upload_content(self, content: str, remote_path: str, overwrite: bool = True) -> bool:
        """
        Upload text content directly to Nextcloud without creating a local file

        Args:
            content: Text content to upload
            remote_path: Destination path in Nextcloud (e.g., '/Documents/file.txt')
            overwrite: Whether to overwrite existing files (default: True)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            self.logger.info(f"Uploading content to {remote_path}")

            headers = {'Content-Type': 'text/plain; charset=utf-8'}
            if not overwrite:
                headers['If-None-Match'] = '*'

            response = requests.put(
                url,
                auth=self.auth_provider.get_auth(),
                data=content.encode('utf-8'),
                headers=headers,
                timeout=60
            )

            if response.status_code in [200, 201, 204]:
                self.logger.info(f"Successfully uploaded content to {remote_path}")
                return True
            elif response.status_code == 412:
                self.logger.error(f"File already exists and overwrite is disabled: {remote_path}")
                return False
            else:
                self.logger.error(f"Upload failed with status {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error uploading content: {str(e)}")
            return False

    def create_folder(self, remote_path: str) -> bool:
        """
        Create a folder in Nextcloud via WebDAV MKCOL

        Args:
            remote_path: Path to folder to create (e.g., '/Documents/NewFolder')

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            self.logger.info(f"Creating folder: {remote_path}")

            response = requests.request(
                'MKCOL',
                url,
                auth=self.auth_provider.get_auth(),
                timeout=30
            )

            if response.status_code in [201, 405]:  # 201 = created, 405 = already exists
                self.logger.info(f"Folder created or already exists: {remote_path}")
                return True
            elif response.status_code == 401:
                self.logger.error("Authentication failed")
                return False
            elif response.status_code == 409:
                self.logger.error(f"Parent folder doesn't exist: {remote_path}")
                return False
            else:
                self.logger.error(f"Create folder failed with status {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error creating folder: {str(e)}")
            return False

    def delete_file(self, remote_path: str) -> bool:
        """
        Delete a file or folder in Nextcloud via WebDAV DELETE

        Args:
            remote_path: Path to file/folder to delete (e.g., '/Documents/file.txt')

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            self.logger.info(f"Deleting: {remote_path}")

            response = requests.delete(
                url,
                auth=self.auth_provider.get_auth(),
                timeout=30
            )

            if response.status_code in [200, 204]:
                self.logger.info(f"Successfully deleted: {remote_path}")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"File not found: {remote_path}")
                return False
            elif response.status_code == 401:
                self.logger.error("Authentication failed")
                return False
            else:
                self.logger.error(f"Delete failed with status {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error deleting file: {str(e)}")
            return False

    def move_file(self, source_path: str, destination_path: str, overwrite: bool = False) -> bool:
        """
        Move a file or folder in Nextcloud via WebDAV MOVE

        Args:
            source_path: Source path (e.g., '/Documents/old.txt')
            destination_path: Destination path (e.g., '/Documents/new.txt')
            overwrite: Whether to overwrite if destination exists (default: False)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            source_url = f"{self.url}/remote.php/dav/files/{self.username}{source_path}"
            dest_url = f"{self.url}/remote.php/dav/files/{self.username}{destination_path}"

            self.logger.info(f"Moving {source_path} to {destination_path}")

            headers = {
                'Destination': dest_url,
                'Overwrite': 'T' if overwrite else 'F'
            }

            response = requests.request(
                'MOVE',
                source_url,
                auth=self.auth_provider.get_auth(),
                headers=headers,
                timeout=30
            )

            if response.status_code in [201, 204]:
                self.logger.info(f"Successfully moved to {destination_path}")
                return True
            elif response.status_code == 412:
                self.logger.error(f"Destination already exists and overwrite is disabled")
                return False
            elif response.status_code == 404:
                self.logger.error(f"Source not found: {source_path}")
                return False
            else:
                self.logger.error(f"Move failed with status {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error moving file: {str(e)}")
            return False

    def copy_file(self, source_path: str, destination_path: str, overwrite: bool = False) -> bool:
        """
        Copy a file or folder in Nextcloud via WebDAV COPY

        Args:
            source_path: Source path (e.g., '/Documents/file.txt')
            destination_path: Destination path (e.g., '/Backup/file.txt')
            overwrite: Whether to overwrite if destination exists (default: False)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            source_url = f"{self.url}/remote.php/dav/files/{self.username}{source_path}"
            dest_url = f"{self.url}/remote.php/dav/files/{self.username}{destination_path}"

            self.logger.info(f"Copying {source_path} to {destination_path}")

            headers = {
                'Destination': dest_url,
                'Overwrite': 'T' if overwrite else 'F'
            }

            response = requests.request(
                'COPY',
                source_url,
                auth=self.auth_provider.get_auth(),
                headers=headers,
                timeout=30
            )

            if response.status_code in [201, 204]:
                self.logger.info(f"Successfully copied to {destination_path}")
                return True
            elif response.status_code == 412:
                self.logger.error(f"Destination already exists and overwrite is disabled")
                return False
            elif response.status_code == 404:
                self.logger.error(f"Source not found: {source_path}")
                return False
            else:
                self.logger.error(f"Copy failed with status {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error copying file: {str(e)}")
            return False

    def set_favorite(self, remote_path: str, favorite: bool = True) -> bool:
        """
        Mark a file or folder as favorite via WebDAV PROPPATCH

        Args:
            remote_path: Path to file/folder (e.g., '/Documents/important.txt')
            favorite: True to mark as favorite, False to unmark (default: True)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            self.logger.info(f"Setting favorite={favorite} for {remote_path}")

            favorite_value = '1' if favorite else '0'

            proppatch_body = f'''<?xml version="1.0"?>
<d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:set>
    <d:prop>
      <oc:favorite>{favorite_value}</oc:favorite>
    </d:prop>
  </d:set>
</d:propertyupdate>'''

            headers = {'Content-Type': 'application/xml; charset=utf-8'}

            response = requests.request(
                'PROPPATCH',
                url,
                auth=self.auth_provider.get_auth(),
                data=proppatch_body.encode('utf-8'),
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 207]:
                self.logger.info(f"Successfully set favorite for {remote_path}")
                return True
            elif response.status_code == 404:
                self.logger.error(f"File not found: {remote_path}")
                return False
            else:
                self.logger.error(f"Set favorite failed with status {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error setting favorite: {str(e)}")
            return False

    def list_favorites(self, remote_path: str = '/') -> List[Dict]:
        """
        List favorite files and folders via WebDAV REPORT

        Args:
            remote_path: Base path to search for favorites (default: '/')

        Returns:
            List of dictionaries containing favorite file information
        """
        try:
            url = f"{self.url}/remote.php/dav/files/{self.username}{remote_path}"
            self.logger.info(f"Listing favorites in {remote_path}")

            report_body = '''<?xml version="1.0"?>
<oc:filter-files xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
     <oc:filter-rules>
         <oc:favorite>1</oc:favorite>
     </oc:filter-rules>
     <d:prop>
        <d:getlastmodified/>
        <d:getetag/>
        <d:getcontenttype/>
        <d:resourcetype/>
        <oc:fileid/>
        <oc:permissions/>
        <oc:size/>
        <d:getcontentlength/>
        <oc:favorite/>
     </d:prop>
</oc:filter-files>'''

            headers = {'Content-Type': 'application/xml; charset=utf-8'}

            response = requests.request(
                'REPORT',
                url,
                auth=self.auth_provider.get_auth(),
                data=report_body.encode('utf-8'),
                headers=headers,
                timeout=60
            )

            favorites = []

            if response.status_code == 207:
                import xml.etree.ElementTree as ET

                root = ET.fromstring(response.text)
                namespaces = {
                    'd': 'DAV:',
                    'oc': 'http://owncloud.org/ns',
                    'nc': 'http://nextcloud.org/ns'
                }

                for response_elem in root.findall('.//d:response', namespaces):
                    href_elem = response_elem.find('d:href', namespaces)
                    if href_elem is not None:
                        href = href_elem.text
                        file_path = href.replace(f"/remote.php/dav/files/{self.username}", '')

                        # Get file properties
                        propstat = response_elem.find('.//d:propstat', namespaces)
                        if propstat is not None:
                            prop = propstat.find('d:prop', namespaces)
                            if prop is not None:
                                file_name = file_path.split('/')[-1]

                                # Check if it's a folder
                                resourcetype = prop.find('d:resourcetype', namespaces)
                                is_folder = resourcetype is not None and resourcetype.find('d:collection', namespaces) is not None

                                # Get size
                                size_elem = prop.find('oc:size', namespaces)
                                size = int(size_elem.text) if size_elem is not None and size_elem.text else 0

                                favorites.append({
                                    'path': file_path,
                                    'name': file_name,
                                    'is_folder': is_folder,
                                    'size': size
                                })

                self.logger.info(f"Found {len(favorites)} favorites")
            else:
                self.logger.error(f"List favorites failed with status {response.status_code}")

            return favorites

        except Exception as e:
            self.logger.error(f"Error listing favorites: {str(e)}")
            return []
