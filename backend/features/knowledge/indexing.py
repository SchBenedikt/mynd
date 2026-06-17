import threading
import time
import sys
import logging
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from backend.features.integration.nextcloud_client import NextcloudClient
from backend.features.documents.parser import DocumentParser

class IndexingStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class IndexingProgress:
    status: IndexingStatus
    current_file: str = ""
    processed_files: int = 0
    total_files: int = 0
    errors: list = None
    start_time: float = 0
    end_time: float = 0
    error_message: str = ""
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def progress_percentage(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100
    
    @property
    def elapsed_time(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        elif self.start_time > 0:
            return time.time() - self.start_time
        return 0.0

class IndexingManager:
    """Manager für Hintergrund-Indexierung von Dokumenten"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_progress = IndexingProgress(status=IndexingStatus.IDLE)
        self.indexing_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.progress_callbacks: list = []
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        self.config_file = os.path.join(project_root, 'backend', 'config', 'indexing_config.json')
        self.nextcloud_auth_config_file = os.path.join(project_root, 'backend', 'config', 'nextcloud_config.json')
        self.nextcloud_config: Dict = {}
        self.knowledge_cache_file = "knowledge_cache.json"
        self.max_workers = 8  # Erhöht für bessere Parallelität
        self.batch_size = 50  # Batch-Verarbeitung für bessere Performance
        self.last_indexing_start = 0
        self.last_indexing_end = 0
        self._periodic_thread: Optional[threading.Thread] = None
        self._periodic_stop_event = threading.Event()
        self._periodic_interval = 6 * 3600  # default: 6 Stunden
        
    def add_progress_callback(self, callback: Callable[[IndexingProgress], None]):
        """Fügt einen Callback für Fortschritts-Updates hinzu"""
        self.progress_callbacks.append(callback)
    
    def notify_progress(self):
        """Benachrichtigt alle Callbacks über den aktuellen Fortschritt"""
        for callback in self.progress_callbacks:
            try:
                callback(self.current_progress)
            except Exception as e:
                self.logger.error(f"Error in progress callback: {str(e)}")
    
    def save_nextcloud_config(self, url: str, username: str, password: str, remote_path: str = "/", exclude_paths: list = None):
        """Speichert Nextcloud-Konfiguration"""
        # Normalize path: empty or None -> '/', ensure leading '/'
        path = (remote_path or '/').strip()
        if not path:
            path = '/'
        if not path.startswith('/'):
            path = '/' + path

        self.nextcloud_config = {
            'url': url,
            'username': username,
            'password': password,
            'path': path,
            'exclude_paths': exclude_paths or ['/Fotosharing', '/Videos', '/Handys']  # Default excludes
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.nextcloud_config, f, indent=2)
            self.logger.info(f"Nextcloud configuration saved to {self.config_file}")
        except Exception as e:
            self.logger.error(f"Error saving config: {str(e)}")
    
    def load_nextcloud_config(self) -> bool:
        """Lädt Nextcloud-Konfiguration"""
        try:
            candidates = [self.config_file, self.nextcloud_auth_config_file]
            for candidate in candidates:
                if not os.path.exists(candidate):
                    continue

                with open(candidate, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)

                normalized = {
                    'url': str(loaded.get('url') or loaded.get('nextcloud_url') or '').strip(),
                    'username': str(loaded.get('username') or '').strip(),
                    'password': str(loaded.get('password') or '').strip(),
                    'path': str(loaded.get('path') or '/').strip() or '/',
                    'exclude_paths': loaded.get('exclude_paths', ['/Fotosharing', '/Videos', '/Handys'])
                }

                # Skip unusable entries and continue searching for valid credentials.
                if not normalized['url'] or not normalized['username']:
                    continue
                if not normalized['password']:
                    # Leeres Passwort ist OK wenn OAuth2-Konfiguration existiert
                    oauth_file = os.path.join(os.path.dirname(self.config_file), 'nextcloud_oauth2.json')
                    if not os.path.exists(oauth_file):
                        continue

                self.nextcloud_config = normalized

                # Keep canonical indexing config in sync with loginflow config.
                if candidate != self.config_file:
                    try:
                        self.save_nextcloud_config(
                            normalized['url'],
                            normalized['username'],
                            normalized['password'],
                            normalized['path']
                        )
                    except Exception:
                        pass

                self.logger.info("Nextcloud configuration loaded")
                return True
        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
        return False
    
    def start_indexing(self, nextcloud_config: Optional[Dict] = None) -> bool:
        """Startet die Indexierung im Hintergrund"""
        if self.current_progress.status == IndexingStatus.RUNNING:
            self.logger.warning("Indexing already running")
            return False
        
        if nextcloud_config:
            self.nextcloud_config = nextcloud_config
            # Konfiguration speichern
            try:
                # If config contains username, save per-account as well
                with open(self.config_file, 'w') as f:
                    json.dump(self.nextcloud_config, f)
                self.logger.info("Nextcloud configuration saved")
            except Exception as e:
                self.logger.error(f"Error saving config: {str(e)}")
        elif not self.nextcloud_config:
            self.logger.error("No Nextcloud configuration available")
            return False
        
        # Stop-Event zurücksetzen
        self.stop_event.clear()
        
        # Neuen Fortschritt initialisieren
        self.current_progress = IndexingProgress(
            status=IndexingStatus.RUNNING,
            start_time=time.time()
        )
        
        # Track last indexing start time
        self.last_indexing_start = time.time()
        
        # Indexierungsthread starten
        self.indexing_thread = threading.Thread(
            target=self._indexing_worker,
            daemon=True
        )
        self.indexing_thread.start()
        
        self.logger.info("Indexing started in background")
        return True
    
    def stop_indexing(self):
        """Stoppt die aktuelle Indexierung"""
        if self.current_progress.status == IndexingStatus.RUNNING:
            self.stop_event.set()
            self.logger.info("Indexing stop requested")
    
    def start_periodic_indexing(self, interval_hours: int = 6):
        """Startet periodische Hintergrund-Indexierung. Der erste Durchlauf startet sofort."""
        self._periodic_interval = max(1, interval_hours) * 3600
        if self._periodic_thread and self._periodic_thread.is_alive():
            self.logger.info("Periodic indexing already running")
            return
        self._periodic_stop_event.clear()
        self._periodic_thread = threading.Thread(
            target=self._periodic_worker,
            daemon=True,
            name="periodic-indexer"
        )
        self._periodic_thread.start()
        self.logger.info(f"Periodic indexing started (interval={interval_hours}h)")

    def stop_periodic_indexing(self):
        """Stoppt die periodische Hintergrund-Indexierung."""
        self._periodic_stop_event.set()
        self.stop_indexing()
        self.logger.info("Periodic indexing stopped")

    def _periodic_worker(self):
        """Worker-Loop: wartet Intervall, startet Indexierung, wiederholt sich."""
        while not self._periodic_stop_event.is_set():
            if self.nextcloud_config.get('url') and self.nextcloud_config.get('username'):
                self.logger.info("Periodic check: starting indexing run")
                self.start_indexing()
                while self.current_progress.status == IndexingStatus.RUNNING:
                    if self._periodic_stop_event.is_set():
                        self.stop_indexing()
                        break
                    time.sleep(5)
            else:
                self.logger.debug("Periodic indexing skipped – no Nextcloud config")

            if self._periodic_stop_event.wait(self._periodic_interval):
                break

    def _get_auth_provider(self):
        """Erzeugt AuthProvider aus OAuth2-Konfiguration falls vorhanden."""
        try:
            oauth_file = os.path.join(os.path.dirname(self.config_file), 'nextcloud_oauth2.json')
            if os.path.exists(oauth_file):
                with open(oauth_file) as f:
                    oauth = json.load(f)
                token = oauth.get('access_token')
                if token:
                    from backend.features.integration.oauth2_nextcloud import OAuth2NextcloudProvider
                    provider = OAuth2NextcloudProvider(oauth)
                    # Token frisch halten – bei Ablauf automatisch erneuern
                    try:
                        if provider.refresh_token:
                            provider.refresh_access_token()
                            # Persistiere aktualisierten Token
                            oauth.update(provider.to_config_dict())
                            with open(oauth_file, 'w') as f:
                                json.dump(oauth, f, indent=2)
                    except Exception:
                        pass
                    return provider
        except Exception as e:
            self.logger.warning(f"Could not load OAuth provider: {e}")
        return None

    def _indexing_worker(self):
        """Hintergrund-Worker für die Indexierung mit paralleler Verarbeitung"""
        try:
            # Nextcloud Client initialisieren
            auth_provider = self._get_auth_provider()
            if auth_provider:
                nc_client = NextcloudClient(
                    self.nextcloud_config['url'],
                    self.nextcloud_config['username'],
                    auth_provider=auth_provider
                )
            else:
                nc_client = NextcloudClient(
                    self.nextcloud_config['url'],
                    self.nextcloud_config['username'],
                    self.nextcloud_config['password']
                )
            
            self.logger.info("Testing Nextcloud connection...")
            if not nc_client.test_connection():
                raise Exception("Nextcloud connection failed - check URL, username, and password")
            
            self.logger.info("Connection successful, listing files...")
            # Get exclude paths from config
            exclude_paths = self.nextcloud_config.get('exclude_paths', [])
            if exclude_paths:
                self.logger.info(f"Excluding paths: {exclude_paths}")

            # Dateien im Hintergrund auflisten mit geteilter Liste für Live-Fortschritt
            progress_files = []
            listing_done = False
            def _do_listing():
                nonlocal progress_files, listing_done
                try:
                    nc_client.list_files(
                        self.nextcloud_config.get('path', '/'),
                        recursive=True,
                        exclude_paths=exclude_paths,
                        shared_files=progress_files
                    )
                except Exception as e:
                    self.logger.error(f"File listing error: {e}")
                finally:
                    listing_done = True
            listing_thread = threading.Thread(target=_do_listing, daemon=True)
            listing_thread.start()

            while not listing_done:
                self.current_progress.total_files = len(progress_files)
                self.current_progress.current_file = f"Scanning: {len(progress_files)} files found..."
                self.notify_progress()
                if self.stop_event.is_set():
                    self.logger.info("Indexing stopped during file listing")
                    self.current_progress.status = IndexingStatus.IDLE
                    self.current_progress.end_time = time.time()
                    self.notify_progress()
                    return
                time.sleep(2)

            files = progress_files
            self.current_progress.total_files = len(files)
            self.current_progress.current_file = ""
            self.notify_progress()
            
            if not files:
                self.logger.info("No files found")
                self.current_progress.status = IndexingStatus.COMPLETED
                self.current_progress.end_time = time.time()
                self.notify_progress()
                return

            # If database available, skip files that are already indexed (simple incremental behavior)
            try:
                from app import knowledge_base
                if getattr(knowledge_base, 'db', None):
                    try:
                        cursor = knowledge_base.db.connection.cursor()
                        cursor.execute("SELECT path FROM documents")
                        existing_paths = {row['path'] for row in cursor.fetchall()}
                        new_files = [f for f in files if f.get('path') not in existing_paths]
                        skipped = len(files) - len(new_files)
                        if skipped > 0:
                            self.logger.info(f"Skipping {skipped} already-indexed files")
                        files = new_files
                    except Exception:
                        pass
            except Exception:
                pass
            
            self.logger.info(f"Processing {len(files)} files with {self.max_workers} workers...")
            
            self.current_progress.total_files = len(files)
            self.notify_progress()
            
            # Dokumente verarbeiten mit optimiertem ThreadPoolExecutor
            all_chunks = []
            sources = []
            parser = DocumentParser()
            processed_count = 0
            
            # Batch-Verarbeitung für bessere Performance
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Dateien in Batches aufteilen
                file_batches = [files[i:i + self.batch_size] for i in range(0, len(files), self.batch_size)]
                
                for batch_idx, batch in enumerate(file_batches):
                    if self.stop_event.is_set():
                        self.logger.info("Indexing stopped by user")
                        break
                    
                    # Token alle 50 Batches auffrischen (lange Läufe)
                    if auth_provider and batch_idx > 0 and batch_idx % 50 == 0:
                        try:
                            auth_provider.refresh_access_token()
                            oauth_file = os.path.join(os.path.dirname(self.config_file), 'nextcloud_oauth2.json')
                            if os.path.exists(oauth_file):
                                with open(oauth_file) as f:
                                    oauth = json.load(f)
                                oauth.update(auth_provider.to_config_dict())
                                with open(oauth_file, 'w') as f:
                                    json.dump(oauth, f, indent=2)
                        except Exception:
                            pass
                    
                    self.logger.info(f"Processing batch {batch_idx + 1}/{len(file_batches)} with {len(batch)} files")
                    
                    # Futures für parallele Verarbeitung erstellen
                    future_to_file = {
                        executor.submit(self._process_single_file, nc_client, file_info, parser): file_info
                        for file_info in batch
                    }
                    
                    # Ergebnisse sammeln
                    batch_chunks = []
                    batch_sources = []
                    
                    for future in as_completed(future_to_file):
                        if self.stop_event.is_set():
                            break
                        
                        file_info = future_to_file[future]
                        self.current_progress.current_file = file_info['name']
                        
                        try:
                            file_chunks, file_sources = future.result()
                            if file_chunks:
                                batch_chunks.extend(file_chunks)
                                batch_sources.extend(file_sources)
                        except Exception as e:
                            error_msg = f"Error processing {file_info['name']}: {str(e)}"
                            self.logger.error(error_msg)
                            self.current_progress.errors.append(error_msg)
                        
                        processed_count += 1
                        self.current_progress.processed_files = processed_count
                    
                    # Batch-Ergebnisse hinzufügen
                    all_chunks.extend(batch_chunks)
                    sources.extend(batch_sources)
                    
                    # Fortschritt aktualisieren
                    self.notify_progress()
                    
                    # Kurze Pause zwischen Batches
                    time.sleep(0.1)
            
            # Abschluss
            if not self.stop_event.is_set():
                # Wissensbasis aktualisieren (global)
                from app import knowledge_base
                knowledge_base.knowledge_chunks = all_chunks
                knowledge_base.document_sources = sources
                
                # Cache speichern für schnelleren Neustart
                self._save_knowledge_cache(all_chunks, sources)
                
                # Automatisch Embeddings für neue Chunks erzeugen
                try:
                    from app import knowledge_base
                    if knowledge_base and knowledge_base.search_engine:
                        self.logger.info("Generating embeddings for new chunks...")
                        self.current_progress.status = IndexingStatus.EMBEDDING
                        self.notify_progress()
                        knowledge_base.search_engine.update_missing_embeddings()
                        self.logger.info("Embeddings generated successfully")
                except Exception as e:
                    self.logger.warning(f"Embedding generation failed: {e}")
                
                self.current_progress.status = IndexingStatus.COMPLETED
                self.logger.info(f"Indexing completed: {len(all_chunks)} chunks from {len(sources)} documents")
            else:
                self.current_progress.status = IndexingStatus.IDLE
            
        except Exception as e:
            self.current_progress.status = IndexingStatus.ERROR
            self.current_progress.error_message = str(e)
            self.logger.error(f"Indexing error: {str(e)}")
        
        finally:
            self.current_progress.end_time = time.time()
            self.current_progress.current_file = ""
            
            # Track last indexing end time
            self.last_indexing_end = time.time()
            
            self.notify_progress()
    
    def _split_text(self, text: str, chunk_size: int = 500) -> list:
        """Teilt Text in kleinere Chunks"""
        import re
        
        # Nach Absätzen aufteilen
        paragraphs = text.split('\n\n')
        chunks = []
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if len(paragraph) > chunk_size:
                # Lange Absätze weiter aufteilen
                sentences = re.split(r'[.!?]+', paragraph)
                current_chunk = ""
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(current_chunk + sentence) < chunk_size:
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                if paragraph:
                    chunks.append(paragraph)
        
        return chunks
    
    def _process_single_file(self, nc_client: NextcloudClient, file_info: Dict, parser: DocumentParser) -> tuple:
        """Verarbeitet eine einzelne Datei parallel"""
        try:
            # Datei-Inhalt parsen
            content = nc_client.parse_remote_file(file_info['path'])
            
            if content and len(content.strip()) > 20:
                # Text in Chunks aufteilen
                chunks = self._split_text(content)
                
                sources = [{
                    "file": file_info['name'],
                    "path": file_info['path'],
                    "type": file_info['extension']
                }] * len(chunks)
                
                return chunks, sources
            else:
                return [], []
                
        except Exception as e:
            self.logger.error(f"Error in _process_single_file for {file_info['name']}: {str(e)}")
            raise
    
    def _save_knowledge_cache(self, chunks: list, sources: list):
        """Speichert die verarbeiteten Daten in der Datenbank"""
        try:
            # Use the new database system instead of JSON
            from app import knowledge_base
            
            if knowledge_base.db:
                # Incremental save: only replace chunks for documents that were (re-)indexed
                conn = knowledge_base.db.connection
                cursor = conn.cursor()

                # Group chunks by document
                doc_chunks = {}
                for i, chunk in enumerate(chunks):
                    source = sources[i] if i < len(sources) else {'file': 'indexed', 'type': 'text'}
                    doc_key = source.get('path', source.get('file', f'doc_{i}'))

                    if doc_key not in doc_chunks:
                        doc_chunks[doc_key] = {
                            'chunks': [],
                            'source': source
                        }
                    doc_chunks[doc_key]['chunks'].append(chunk)

                # Add/update documents and their chunks
                total_chunks = 0
                for doc_key, doc_data in doc_chunks.items():
                    source = doc_data['source']
                    doc_chunks_list = doc_data['chunks']

                    path = source.get('path', doc_key)
                    name = source.get('file', os.path.basename(path))
                    file_type = source.get('type', 'text')
                    metadata = source
                    # Ensure owner metadata if available
                    try:
                        owner = self.nextcloud_config.get('username') if isinstance(self.nextcloud_config, dict) else None
                        if owner:
                            metadata = dict(metadata or {})
                            metadata['owner'] = owner
                    except Exception:
                        pass

                    # Check if document already exists
                    cursor.execute("SELECT id FROM documents WHERE path = ?", (path,))
                    existing = cursor.fetchone()

                    if existing:
                        # Remove existing chunks for this document before re-adding
                        doc_id = existing['id']
                        try:
                            cursor.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
                            cursor.execute("DELETE FROM chunks_fts WHERE document_id = ?", (doc_id,))
                            conn.commit()
                        except Exception:
                            conn.rollback()

                        # Update metadata/updated_at for the existing document
                        try:
                            cursor.execute(
                                """
                                UPDATE documents SET name = ?, file_type = ?, size = ?, updated_at = ?, metadata = ?
                                WHERE id = ?
                                """,
                                (name, file_type, 0, time.time(), json.dumps(metadata or {}), doc_id)
                            )
                            conn.commit()
                        except Exception:
                            conn.rollback()
                    else:
                        # Insert new document
                        doc_id = knowledge_base.db.add_document(
                            name=name,
                            path=path,
                            file_type=file_type,
                            metadata=metadata
                        )

                    # Add chunks for this document
                    try:
                        chunk_ids = knowledge_base.db.add_chunks(doc_id, doc_chunks_list)
                        total_chunks += len(chunk_ids)
                    except Exception as e:
                        self.logger.error(f"Error adding chunks for {path}: {str(e)}")

                # Update search engine index after DB changes
                if knowledge_base.search_engine:
                    try:
                        knowledge_base.search_engine.rebuild_index()
                    except Exception as e:
                        self.logger.error(f"Error rebuilding search index: {str(e)}")

                self.logger.info(f"Knowledge saved to database: {total_chunks} chunks from {len(doc_chunks)} documents")

                # Record indexing run stats if supported by DB
                try:
                    if hasattr(knowledge_base.db, 'record_index_run'):
                        knowledge_base.db.record_index_run(
                            started_at=self.last_indexing_start or time.time(),
                            ended_at=self.last_indexing_end or time.time(),
                            documents_count=len(doc_chunks),
                            chunks_count=total_chunks,
                            errors=json.dumps(self.current_progress.errors) if self.current_progress.errors else None,
                            scope=self.nextcloud_config.get('path', '/') if isinstance(self.nextcloud_config, dict) else None
                        )
                except Exception as e:
                    self.logger.error(f"Error recording index run: {str(e)}")
            else:
                # Fallback to JSON cache
                cache_data = {
                    'chunks': chunks,
                    'sources': sources,
                    'timestamp': time.time(),
                    'nextcloud_config': self.nextcloud_config
                }
                
                with open(self.knowledge_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    
                self.logger.info(f"Knowledge cache saved: {len(chunks)} chunks")
                
        except Exception as e:
            self.logger.error(f"Error saving knowledge: {str(e)}")
    
    def load_knowledge_cache(self) -> bool:
        """Lädt die Wissensbasis aus dem Cache"""
        try:
            if os.path.exists(self.knowledge_cache_file):
                with open(self.knowledge_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Prüfen ob Cache noch gültig (optional: Zeitprüfung)
                from app import knowledge_base
                knowledge_base.knowledge_chunks = cache_data.get('chunks', [])
                knowledge_base.document_sources = cache_data.get('sources', [])
                
                self.logger.info(f"Knowledge cache loaded: {len(knowledge_base.knowledge_chunks)} chunks")
                return True
        except Exception as e:
            self.logger.error(f"Error loading knowledge cache: {str(e)}")
        return False
    
    def get_progress(self) -> Dict:
        """Gibt den aktuellen Fortschritt zurück"""
        return {
            'status': self.current_progress.status.value,
            'current_file': self.current_progress.current_file,
            'processed_files': self.current_progress.processed_files,
            'total_files': self.current_progress.total_files,
            'progress_percentage': self.current_progress.progress_percentage,
            'errors': self.current_progress.errors,
            'elapsed_time': self.current_progress.elapsed_time,
            'error_message': self.current_progress.error_message,
            'is_running': self.current_progress.status == IndexingStatus.RUNNING,
            'last_indexing_start': self.last_indexing_start,
            'last_indexing_end': self.last_indexing_end,
            'last_indexing_duration': self.last_indexing_end - self.last_indexing_start if self.last_indexing_end > 0 and self.last_indexing_start > 0 else 0
        }
    
    def get_config(self, mask_password: bool = False) -> Dict:
        """Gibt die aktuelle Konfiguration zurück"""
        if not self.nextcloud_config:
            self.load_nextcloud_config()

        if self.nextcloud_config:
            config = self.nextcloud_config.copy()
            if mask_password:
                config['password'] = '***' if config.get('password') else ''
            return config
        return {}

# Globaler IndexingManager
indexing_manager = IndexingManager()
