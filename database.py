import sqlite3
import json
import time
import logging
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
            # Escape query properly for FTS5
            escaped_query = query.replace('"', '""')
            
            cursor.execute("""
                SELECT c.*, d.name as doc_name, d.path as doc_path, d.file_type
                FROM chunks_fts fts
                JOIN chunks c ON fts.rowid = c.id
                JOIN documents d ON c.document_id = d.id
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (escaped_query, limit))
            
            results = [dict(row) for row in cursor.fetchall()]
            execution_time = time.time() - start_time
            
            # Log search history
            self._log_search(query, len(results), execution_time)
            
            return results
            
        except Exception as e:
            logger.error(f"Full-text search error: {str(e)}")
            return []
    
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
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
