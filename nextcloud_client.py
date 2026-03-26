import os
import logging
from document_parser import DocumentParser
from typing import List, Dict, Optional
import requests
from requests.auth import HTTPBasicAuth

class NextcloudClient:
    """Client für Nextcloud-Integration über WebDAV"""
    
    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.parser = DocumentParser()
        self.logger = logging.getLogger(__name__)
        
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
            url = f"{self.url}/remote.php/dav/files/{self.username}/"
            self.logger.info(f"Testing connection to: {url}")
            
            response = requests.request('PROPFIND', url, auth=HTTPBasicAuth(self.username, self.password), timeout=30)
            
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
            response = requests.request('PROPFIND', url, auth=HTTPBasicAuth(self.username, self.password), headers=headers, timeout=60)
            
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
            
            response = requests.get(url, auth=HTTPBasicAuth(self.username, self.password), timeout=60)
            
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
