import threading
import time
import sys
import logging
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from backend.features.integration.email_client import EmailClient


class EmailIndexingStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class EmailIndexingProgress:
    status: EmailIndexingStatus
    current_folder: str = ""
    current_email: str = ""
    processed_emails: int = 0
    total_emails: int = 0
    errors: list = None
    start_time: float = 0
    end_time: float = 0
    error_message: str = ""
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def progress_percentage(self) -> float:
        if self.total_emails == 0:
            return 0.0
        return (self.processed_emails / self.total_emails) * 100
    
    @property
    def elapsed_time(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        elif self.start_time > 0:
            return time.time() - self.start_time
        return 0.0


class EmailIndexingManager:
    """Manager für Hintergrund-Indexierung von E-Mails"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_progress = EmailIndexingProgress(status=EmailIndexingStatus.IDLE)
        self.indexing_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.progress_callbacks: list = []
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        self.config_file = os.path.join(project_root, 'backend', 'config', 'email_indexing_config.json')
        self.email_config: Dict = {}
        self.max_workers = 4  # Reduziert für E-Mails (nicht so I/O intensiv)
        self.batch_size = 20
        self.last_indexing_start = 0
        self.last_indexing_end = 0
        self.chunk_size = 500  # Zeichen pro Chunk
        
    def add_progress_callback(self, callback: Callable[[EmailIndexingProgress], None]):
        """Fügt einen Callback für Fortschritts-Updates hinzu"""
        self.progress_callbacks.append(callback)
    
    def notify_progress(self):
        """Benachrichtigt alle Callbacks über den aktuellen Fortschritt"""
        for callback in self.progress_callbacks:
            try:
                callback(self.current_progress)
            except Exception as e:
                self.logger.error(f"Error in progress callback: {str(e)}")
    
    def save_email_config(self, imap_host: str, username: str, password: str, 
                         imap_port: int = 993, folders: str = "INBOX", 
                         max_emails: int = 50, use_ssl: bool = True):
        """Speichert E-Mail-Konfiguration"""
        self.email_config = {
            'imap_host': imap_host,
            'username': username,
            'password': password,
            'imap_port': imap_port,
            'folders': folders,
            'max_emails': max_emails,
            'use_ssl': use_ssl
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.email_config, f, indent=2)
            self.logger.info("Email configuration saved")
            return True
        except Exception as e:
            self.logger.error(f"Error saving email config: {str(e)}")
            return False
    
    def load_email_config(self) -> bool:
        """Lädt E-Mail-Konfiguration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.email_config = json.load(f)
                self.logger.info("Email configuration loaded")
                return bool(self.email_config.get('imap_host'))
        except Exception as e:
            self.logger.error(f"Error loading email config: {str(e)}")
        return False
    
    def get_config(self, mask_password: bool = False) -> Dict:
        """Gibt die aktuelle Konfiguration zurück"""
        config = dict(self.email_config)
        if mask_password and 'password' in config:
            config['password'] = '***' if config['password'] else ''
        return config
    
    def start_indexing(self, email_config: Optional[Dict] = None) -> bool:
        """Startet die E-Mail-Indexierung im Hintergrund"""
        if self.current_progress.status == EmailIndexingStatus.RUNNING:
            self.logger.warning("Email indexing already running")
            return False
        
        if email_config:
            self.email_config = email_config
            # Konfiguration speichern
            try:
                with open(self.config_file, 'w') as f:
                    json.dump(self.email_config, f)
                self.logger.info("Email configuration saved")
            except Exception as e:
                self.logger.error(f"Error saving config: {str(e)}")
        elif not self.email_config:
            self.logger.error("No email configuration available")
            return False
        
        # Stop-Event zurücksetzen
        self.stop_event.clear()
        
        # Neuen Fortschritt initialisieren
        self.current_progress = EmailIndexingProgress(
            status=EmailIndexingStatus.RUNNING,
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
        
        self.logger.info("Email indexing started in background")
        return True
    
    def stop_indexing(self):
        """Stoppt die aktuelle E-Mail-Indexierung"""
        self.stop_event.set()
        if self.indexing_thread:
            self.indexing_thread.join(timeout=5)
        self.logger.info("Email indexing stopped")
    
    def get_progress(self) -> Dict:
        """Gibt den aktuellen Fortschritt als Dict zurück"""
        return {
            'status': self.current_progress.status.value,
            'current_folder': self.current_progress.current_folder,
            'current_email': self.current_progress.current_email,
            'processed_emails': self.current_progress.processed_emails,
            'total_emails': self.current_progress.total_emails,
            'progress_percentage': self.current_progress.progress_percentage,
            'errors': self.current_progress.errors,
            'elapsed_time': self.current_progress.elapsed_time,
            'error_message': self.current_progress.error_message
        }
    
    def _split_text(self, text: str, chunk_size: int = None) -> list:
        """Teilt Text in kleinere Chunks"""
        if chunk_size is None:
            chunk_size = self.chunk_size
        
        if not text:
            return []
        
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size].strip()
            if chunk:  # Nur nicht-leere Chunks
                chunks.append(chunk)
        return chunks
    
    def _format_email_content(self, email_data: Dict) -> str:
        """Formatiert E-Mail-Daten für die Indexierung"""
        parts = []
        
        # Subject
        subject = email_data.get('subject', '(Kein Betreff)')
        parts.append(f"Betreff: {subject}")
        
        # From
        sender = email_data.get('from', '')
        if sender:
            parts.append(f"Von: {sender}")
        
        # Date
        date_str = email_data.get('date', '')
        if date_str:
            parts.append(f"Datum: {date_str}")
        
        # Body
        body = email_data.get('body', '')
        if body:
            parts.append("")
            parts.append("Inhalt:")
            parts.append(body)
        
        return "\n".join(parts)
    
    def _indexing_worker(self):
        """Hintergrund-Worker für die E-Mail-Indexierung"""
        try:
            # E-Mail-Client initialisieren
            email_client = EmailClient(self.email_config)
            
            # Verbindung testen
            try:
                email_client.test_connection()
            except Exception as e:
                self.logger.warning(f"Email connection may have issues: {str(e)}")
            
            # Ordner abrufen
            folders = self.email_config.get('folders', 'INBOX')
            if folders.upper() in ('ALL', '*'):
                try:
                    folder_list = email_client.list_folder_tree()
                    folders_to_process = [f.get('name') for f in folder_list]
                except Exception:
                    folders_to_process = ['INBOX']
            else:
                folders_to_process = [f.strip() for f in folders.split(',') if f.strip()]
            
            if not folders_to_process:
                folders_to_process = ['INBOX']
            
            all_chunks = []
            sources = []
            total_emails_to_process = 0
            
            # Schritt 1: Zähle E-Mails
            try:
                for folder in folders_to_process:
                    if self.stop_event.is_set():
                        break
                    self.current_progress.current_folder = folder
                    self.notify_progress()
                    
                    try:
                        # Anzahl der E-Mails in diesem Ordner
                        email_list = email_client.search_emails(
                            query='ALL',
                            folder=folder,
                            limit=self.email_config.get('max_emails', 50)
                        )
                        total_emails_to_process += len(email_list)
                    except Exception as e:
                        self.logger.warning(f"Error getting email count from {folder}: {str(e)}")
                
                self.current_progress.total_emails = total_emails_to_process
                self.notify_progress()
                
                # Schritt 2: Verarbeite E-Mails
                for folder in folders_to_process:
                    if self.stop_event.is_set():
                        break
                    
                    self.current_progress.current_folder = folder
                    self.notify_progress()
                    
                    try:
                        # E-Mails abrufen
                        email_list = email_client.search_emails(
                            query='ALL',
                            folder=folder,
                            limit=self.email_config.get('max_emails', 50)
                        )
                        
                        for email_data in email_list:
                            if self.stop_event.is_set():
                                break
                            
                            try:
                                subject = email_data.get('subject', '(Kein Betreff)')
                                self.current_progress.current_email = subject
                                
                                # E-Mail formatieren
                                content = self._format_email_content(email_data)
                                
                                # In Chunks aufteilen
                                chunks = self._split_text(content)
                                
                                if chunks:
                                    all_chunks.extend(chunks)
                                    
                                    # Source-Informationen erstellen
                                    source_info = {
                                        'file': subject,
                                        'folder': folder,
                                        'from': email_data.get('from', ''),
                                        'date': email_data.get('date', ''),
                                        'type': 'email'
                                    }
                                    sources.extend([source_info] * len(chunks))
                                
                                self.current_progress.processed_emails += 1
                                self.notify_progress()
                                
                            except Exception as e:
                                error_msg = f"Error processing email {subject}: {str(e)}"
                                self.logger.error(error_msg)
                                self.current_progress.errors.append(error_msg)
                    
                    except Exception as e:
                        error_msg = f"Error accessing folder {folder}: {str(e)}"
                        self.logger.error(error_msg)
                        self.current_progress.errors.append(error_msg)
                
                # Abschluss
                if not self.stop_event.is_set():
                    # Wissensbasis aktualisieren (global)
                    from app import knowledge_base
                    knowledge_base.knowledge_chunks = all_chunks
                    knowledge_base.document_sources = sources
                    
                    # Cache speichern
                    self._save_knowledge_cache(all_chunks, sources)
                    
                    self.current_progress.status = EmailIndexingStatus.COMPLETED
                    self.logger.info(f"Email indexing completed: {len(all_chunks)} chunks from {self.current_progress.processed_emails} emails")
                else:
                    self.current_progress.status = EmailIndexingStatus.IDLE
                
            except Exception as e:
                self.current_progress.status = EmailIndexingStatus.ERROR
                self.current_progress.error_message = str(e)
                self.logger.error(f"Email indexing error: {str(e)}")
        
        finally:
            self.current_progress.end_time = time.time()
            self.current_progress.current_folder = ""
            self.current_progress.current_email = ""
            self.notify_progress()
    
    def _save_knowledge_cache(self, chunks: list, sources: list):
        """Speichert die verarbeiteten E-Mail-Daten in der Datenbank"""
        try:
            from app import knowledge_base
            
            if knowledge_base.db:
                conn = knowledge_base.db.connection
                cursor = conn.cursor()
                
                # Gruppiere Chunks nach E-Mail
                doc_chunks = {}
                for i, chunk in enumerate(chunks):
                    source = sources[i] if i < len(sources) else {'file': 'email', 'type': 'email'}
                    doc_key = source.get('file', f'email_{i}')
                    
                    if doc_key not in doc_chunks:
                        doc_chunks[doc_key] = {
                            'chunks': [],
                            'source': source
                        }
                    doc_chunks[doc_key]['chunks'].append(chunk)
                
                # Speichere Dokumente und Chunks
                total_chunks = 0
                for doc_key, doc_data in doc_chunks.items():
                    source = doc_data['source']
                    doc_chunks_list = doc_data['chunks']
                    
                    path = f"email://{source.get('folder', 'INBOX')}/{doc_key}"
                    name = doc_key
                    file_type = 'email'
                    metadata = source
                    
                    # Prüfe ob Dokument bereits existiert
                    cursor.execute("SELECT id FROM documents WHERE path = ?", (path,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        doc_id = existing['id']
                        try:
                            cursor.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
                            cursor.execute("DELETE FROM chunks_fts WHERE document_id = ?", (doc_id,))
                            conn.commit()
                        except Exception:
                            conn.rollback()
                        
                        # Update metadata
                        try:
                            cursor.execute(
                                """
                                UPDATE documents SET name = ?, file_type = ?, updated_at = ?, metadata = ?
                                WHERE id = ?
                                """,
                                (name, file_type, time.time(), json.dumps(metadata or {}), doc_id)
                            )
                            conn.commit()
                        except Exception:
                            conn.rollback()
                    else:
                        # Neues Dokument einfügen
                        doc_id = knowledge_base.db.add_document(
                            name=name,
                            path=path,
                            file_type=file_type,
                            metadata=metadata
                        )
                    
                    # Chunks hinzufügen
                    try:
                        for chunk_text in doc_chunks_list:
                            knowledge_base.db.add_chunk(
                                document_id=doc_id,
                                content=chunk_text
                            )
                        total_chunks += len(doc_chunks_list)
                    except Exception as e:
                        self.logger.error(f"Error adding chunks: {str(e)}")
                
                self.logger.info(f"Saved {total_chunks} email chunks to database")
            
        except Exception as e:
            self.logger.error(f"Error saving email cache: {str(e)}")


# Globaler EmailIndexingManager
email_indexing_manager = EmailIndexingManager()
