import sqlite3
import json
import time
import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)

@dataclass
class Document:
    id: int
    name: str
    path: str
    file_type: str
    size: int
    created_at: float
    updated_at: float

@dataclass
class Chunk:
    id: int
    document_id: int
    content: str
    chunk_index: int
    embedding_id: Optional[int] = None

class KnowledgeDatabase:
    """SQLite database for structured knowledge storage"""
    
    def __init__(self, db_path: str = "knowledge_base.db"):
        self.db_path = db_path
        self.connection = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Create database schema with proper indexing"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrent access
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=NORMAL")
            self.connection.execute("PRAGMA cache_size=10000")
            self.connection.execute("PRAGMA temp_store=MEMORY")
            
            self._create_tables()
            self._create_indexes()
            
            logger.info(f"Database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise
    
    def _create_tables(self):
        """Create all necessary tables"""
        cursor = self.connection.cursor()
        
        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                metadata TEXT
            )
        """)
        
        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                embedding_id INTEGER,
                word_count INTEGER,
                created_at REAL NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        
        # Embeddings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL,
                vector_data BLOB NOT NULL,
                model_name TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (chunk_id) REFERENCES chunks (id) ON DELETE CASCADE
            )
        """)
        
        # Full-text search virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content,
                document_id,
                chunk_index,
                content='chunks',
                content_rowid='id'
            )
        """)
        
        # Search history for optimization
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                results_count INTEGER,
                execution_time REAL,
                created_at REAL NOT NULL
            )
        """)
        
        # Tasks table - für Nextcloud Todos Caching
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                completed INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                last_synced REAL NOT NULL,
                nextcloud_path TEXT
            )
        """)
        
        # Tasks sync status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks_sync_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_name TEXT NOT NULL UNIQUE,
                total_count INTEGER DEFAULT 0,
                loaded_count INTEGER DEFAULT 0,
                last_full_sync REAL,
                last_update REAL NOT NULL
            )
        """)
        
        self.connection.commit()
    
    def _create_indexes(self):
        """Create performance indexes"""
        cursor = self.connection.cursor()
        
        # Document indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(file_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at)")
        
        # Chunk indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks(embedding_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_created ON chunks(created_at)")
        
        # Embedding indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chunk ON embeddings(chunk_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model_name)")
        
        # Tasks indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_uid ON tasks(uid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at)")
        
        # Tasks sync status index
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_sync_list ON tasks_sync_status(list_name)")
        
        self.connection.commit()
    
    def add_document(self, name: str, path: str, file_type: str, size: int = 0, metadata: Dict = None) -> int:
        """Add a new document"""
        cursor = self.connection.cursor()
        current_time = time.time()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO documents 
                (name, path, file_type, size, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, path, file_type, size, current_time, current_time, json.dumps(metadata or {})))
            
            doc_id = cursor.lastrowid
            self.connection.commit()
            
            logger.info(f"Document added: {name} (ID: {doc_id})")
            return doc_id
            
        except sqlite3.IntegrityError as e:
            logger.error(f"Document already exists: {path}")
            # Return existing document ID
            cursor.execute("SELECT id FROM documents WHERE path = ?", (path,))
            result = cursor.fetchone()
            return result['id'] if result else None
    
    def add_chunks(self, document_id: int, chunks: List[str]) -> List[int]:
        """Add multiple chunks for a document"""
        cursor = self.connection.cursor()
        current_time = time.time()
        chunk_ids = []
        
        try:
            for i, content in enumerate(chunks):
                word_count = len(content.split())
                
                cursor.execute("""
                    INSERT INTO chunks (document_id, content, chunk_index, word_count, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (document_id, content, i, word_count, current_time))
                
                chunk_id = cursor.lastrowid
                chunk_ids.append(chunk_id)
                
                # Add to FTS table
                cursor.execute("""
                    INSERT INTO chunks_fts (rowid, content, document_id, chunk_index)
                    VALUES (?, ?, ?, ?)
                """, (chunk_id, content, document_id, i))
            
            self.connection.commit()
            logger.info(f"Added {len(chunks)} chunks for document {document_id}")
            
        except Exception as e:
            logger.error(f"Error adding chunks: {str(e)}")
            self.connection.rollback()
            raise
        
        return chunk_ids
    
    def add_embedding(self, chunk_id: int, vector_data: bytes, model_name: str) -> int:
        """Add embedding for a chunk"""
        cursor = self.connection.cursor()
        current_time = time.time()
        
        try:
            cursor.execute("""
                INSERT INTO embeddings (chunk_id, vector_data, model_name, created_at)
                VALUES (?, ?, ?, ?)
            """, (chunk_id, vector_data, model_name, current_time))
            
            embedding_id = cursor.lastrowid
            
            # Update chunk with embedding reference
            cursor.execute("UPDATE chunks SET embedding_id = ? WHERE id = ?", (embedding_id, chunk_id))
            
            self.connection.commit()
            return embedding_id
            
        except Exception as e:
            logger.error(f"Error adding embedding: {str(e)}")
            self.connection.rollback()
            raise
    
    def search_fulltext(self, query: str, limit: int = 10) -> List[Dict]:
        """Full-text search using FTS5"""
        cursor = self.connection.cursor()
        start_time = time.time()
        
        try:
            match_query = self._build_fts_match_query(query)
            if not match_query:
                return []
            
            cursor.execute("""
                SELECT c.*, d.name as doc_name, d.path as doc_path, d.file_type
                FROM chunks_fts fts
                JOIN chunks c ON fts.rowid = c.id
                JOIN documents d ON c.document_id = d.id
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (match_query, limit))
            
            results = [dict(row) for row in cursor.fetchall()]
            execution_time = time.time() - start_time
            
            # Log search history
            self._log_search(query, len(results), execution_time)
            
            return results
            
        except Exception as e:
            logger.error(f"Full-text search error: {str(e)}")
            return []

    def _build_fts_match_query(self, query: str) -> str:
        """Build a safe and effective FTS5 MATCH query from natural language input."""
        cleaned = (query or "").strip()
        if not cleaned:
            return ""

        # Keep word-like tokens only to avoid FTS parser errors on punctuation/operators.
        tokens = [token for token in re.findall(r"\w+", cleaned.lower(), flags=re.UNICODE) if len(token) > 1]

        if not tokens:
            return ""

        # Use prefix matching and OR-combination for robust recall with natural language queries.
        return " OR ".join(f'"{token}"*' for token in tokens)
    
    def get_chunks_without_embeddings(self, model_name: str, limit: int = 100) -> List[Dict]:
        """Get chunks that need embeddings"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT c.id, c.content
            FROM chunks c
            LEFT JOIN embeddings e ON c.embedding_id = e.id
            WHERE e.id IS NULL OR e.model_name != ?
            ORDER BY c.created_at DESC
            LIMIT ?
        """, (model_name, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[Dict]:
        """Get a specific chunk with document info"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT c.*, d.name as doc_name, d.path as doc_path, d.file_type
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.id = ?
        """, (chunk_id,))
        
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def get_document_stats(self) -> Dict:
        """Get database statistics"""
        cursor = self.connection.cursor()
        
        stats = {}
        
        # Document count
        cursor.execute("SELECT COUNT(*) as count FROM documents")
        stats['documents'] = cursor.fetchone()['count']
        
        # Chunk count
        cursor.execute("SELECT COUNT(*) as count FROM chunks")
        stats['chunks'] = cursor.fetchone()['count']
        
        # Embedding count
        cursor.execute("SELECT COUNT(*) as count FROM embeddings")
        stats['embeddings'] = cursor.fetchone()['count']
        
        # Total words
        cursor.execute("SELECT SUM(word_count) as total FROM chunks")
        result = cursor.fetchone()
        stats['total_words'] = result['total'] or 0
        
        # File types
        cursor.execute("SELECT file_type, COUNT(*) as count FROM documents GROUP BY file_type")
        stats['file_types'] = {row['file_type']: row['count'] for row in cursor.fetchall()}
        
        return stats
    
    def _log_search(self, query: str, results_count: int, execution_time: float):
        """Log search query for optimization analysis"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT INTO search_history (query, results_count, execution_time, created_at)
            VALUES (?, ?, ?, ?)
        """, (query, results_count, execution_time, time.time()))
        
        self.connection.commit()
    
    # ============ TASKS MANAGEMENT ============
    
    def add_tasks_batch(self, tasks: List[Dict], list_name: str = 'todo') -> int:
        """Speichert Batch von Tasks in Datenbank (für Nextcloud Sync)"""
        cursor = self.connection.cursor()
        current_time = time.time()
        added_count = 0
        
        try:
            for task in tasks:
                uid = task.get('uid', task.get('title', f'task_{current_time}'))
                
                cursor.execute("""
                    INSERT OR REPLACE INTO tasks 
                    (uid, title, description, due_date, completed, priority, created_at, updated_at, last_synced, nextcloud_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uid,
                    task.get('title', 'Untitled'),
                    task.get('description', ''),
                    task.get('due_date'),
                    1 if task.get('completed') else 0,
                    task.get('priority', 0),
                    current_time,
                    current_time,
                    current_time,
                    task.get('nextcloud_path', '')
                ))
                added_count += 1
            
            # Update sync status
            cursor.execute("""
                INSERT OR REPLACE INTO tasks_sync_status 
                (list_name, loaded_count, last_update)
                VALUES (?, ?, ?)
            """, (list_name, added_count, current_time))
            
            self.connection.commit()
            logger.info(f"✅ Added {added_count} tasks to database from list '{list_name}'")
            return added_count
            
        except Exception as e:
            logger.error(f"❌ Error adding tasks batch: {str(e)}")
            self.connection.rollback()
            return 0
    
    def get_tasks_from_db(self, completed_only: bool = False, limit: int = 100) -> List[Dict]:
        """Lädt Tasks aus Datenbank (ultra-schnell!)"""
        cursor = self.connection.cursor()
        
        completed_filter = "WHERE completed = 1" if completed_only else ""
        
        cursor.execute(f"""
            SELECT id, uid, title, description, due_date, completed, priority, updated_at
            FROM tasks
            {completed_filter}
            ORDER BY 
                completed ASC,
                due_date ASC,
                updated_at DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_open_tasks(self, limit: int = 20) -> List[Dict]:
        """Gibt nur offene (nicht abgehakte) Tasks zurück"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT id, uid, title, description, due_date, priority
            FROM tasks
            WHERE completed = 0
            ORDER BY due_date ASC, priority DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def complete_task_in_db(self, task_uid: str) -> bool:
        """Markiert Task als completed in DB"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                UPDATE tasks
                SET completed = 1, updated_at = ?
                WHERE uid = ?
            """, (time.time(), task_uid))
            
            self.connection.commit()
            logger.info(f"✅ Task marked completed: {task_uid}")
            return True
        except Exception as e:
            logger.error(f"❌ Error completing task: {str(e)}")
            return False
    
    def get_task_stats(self) -> Dict:
        """Gibt Statistiken über Tasks zurück"""
        cursor = self.connection.cursor()
        
        stats = {}
        
        # Total tasks
        cursor.execute("SELECT COUNT(*) as count FROM tasks")
        stats['total'] = cursor.fetchone()['count']
        
        # Open tasks
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE completed = 0")
        stats['open'] = cursor.fetchone()['count']
        
        # Completed tasks
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE completed = 1")
        stats['completed'] = cursor.fetchone()['count']
        
        # By priority
        cursor.execute("""
            SELECT priority, COUNT(*) as count 
            FROM tasks WHERE completed = 0
            GROUP BY priority
        """)
        stats['by_priority'] = {row['priority']: row['count'] for row in cursor.fetchall()}
        
        # Sync status
        cursor.execute("SELECT list_name, loaded_count, last_update FROM tasks_sync_status")
        stats['sync_status'] = [dict(row) for row in cursor.fetchall()]
        
        return stats
    
    def clear_tasks(self) -> bool:
        """Löscht alle Tasks aus der Datenbank (für Neustart/Neuload)"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("DELETE FROM tasks")
            cursor.execute("DELETE FROM tasks_sync_status")
            self.connection.commit()
            logger.info("✅ All tasks cleared from database")
            return True
        except Exception as e:
            logger.error(f"❌ Error clearing tasks: {str(e)}")
            return False
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
