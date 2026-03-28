import threading
import time
import logging
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from nextcloud_client import NextcloudClient
from document_parser import DocumentParser

class IndexingStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
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
        self.config_file = "indexing_config.json"
        self.nextcloud_config: Dict = {}
        self.knowledge_cache_file = "knowledge_cache.json"
        self.max_workers = 8  # Erhöht für bessere Parallelität
        self.batch_size = 50  # Batch-Verarbeitung für bessere Performance
        
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
    
    def save_nextcloud_config(self, url: str, username: str, password: str, remote_path: str = "/"):
        """Speichert Nextcloud-Konfiguration"""
        self.nextcloud_config = {
            'url': url,
            'username': username,
            'password': password,
            'path': remote_path
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.nextcloud_config, f)
            self.logger.info("Nextcloud configuration saved")
        except Exception as e:
            self.logger.error(f"Error saving config: {str(e)}")
    
    def load_nextcloud_config(self) -> bool:
        """Lädt Nextcloud-Konfiguration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.nextcloud_config = json.load(f)
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
    
    def _indexing_worker(self):
        """Hintergrund-Worker für die Indexierung mit paralleler Verarbeitung"""
        try:
            # Nextcloud Client initialisieren
            nc_client = NextcloudClient(
                self.nextcloud_config['url'],
                self.nextcloud_config['username'],
                self.nextcloud_config['password']
            )
            
            self.logger.info("Testing Nextcloud connection...")
            if not nc_client.test_connection():
                raise Exception("Nextcloud connection failed - check URL, username, and password")
            
            self.logger.info("Connection successful, listing files...")
            # Dateien auflisten
            files = nc_client.list_files(self.nextcloud_config.get('path', '/'), recursive=True)
            
            if not files:
                self.logger.info("No files found")
                self.current_progress.status = IndexingStatus.COMPLETED
                self.current_progress.end_time = time.time()
                self.notify_progress()
                return
            
            # Alle Dateien verarbeiten mit parallelem Download
            self.logger.info(f"Processing all {len(files)} files with {self.max_workers} workers...")
            
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
                # Clear existing data from this indexing session
                knowledge_base.db.connection.execute("DELETE FROM chunks")
                knowledge_base.db.connection.execute("DELETE FROM documents")
                knowledge_base.db.connection.commit()
                
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
                
                # Add to database
                total_chunks = 0
                for doc_key, doc_data in doc_chunks.items():
                    source = doc_data['source']
                    doc_chunks_list = doc_data['chunks']
                    
                    doc_id = knowledge_base.db.add_document(
                        name=source.get('file', os.path.basename(doc_key)),
                        path=source.get('path', doc_key),
                        file_type=source.get('type', 'text'),
                        metadata=source
                    )
                    
                    chunk_ids = knowledge_base.db.add_chunks(doc_id, doc_chunks_list)
                    total_chunks += len(chunk_ids)
                
                # Update search engine
                if knowledge_base.search_engine:
                    knowledge_base.search_engine.rebuild_index()
                
                self.logger.info(f"Knowledge saved to database: {total_chunks} chunks from {len(doc_chunks)} documents")
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
            'is_running': self.current_progress.status == IndexingStatus.RUNNING
        }
    
    def get_config(self, mask_password: bool = False) -> Dict:
        """Gibt die aktuelle Konfiguration zurück"""
        if self.nextcloud_config:
            config = self.nextcloud_config.copy()
            if mask_password:
                config['password'] = '***' if config.get('password') else ''
            return config
        return {}

# Globaler IndexingManager
indexing_manager = IndexingManager()
