import numpy as np
import faiss
import logging
import time
from typing import List, Dict, Optional, Tuple
from sentence_transformers import SentenceTransformer
from database import KnowledgeDatabase
import pickle
import os

logger = logging.getLogger(__name__)

class SemanticSearchEngine:
    """High-performance semantic search engine using FAISS"""
    
    def __init__(self, db_path: str = "knowledge_base.db"):
        self.db_path = db_path
        self.db = None
        self.model = None
        self.index = None
        self.dimension = 384  # MiniLM-L6 dimension
        self.index_path = "faiss_index.bin"
        self.mapping_path = "chunk_mapping.pkl"
        
        # Initialize database first
        self.db = KnowledgeDatabase(db_path)
        
        # Initialize model and index later (lazy loading)
        self.model_loaded = False
        logger.info("Semantic search engine initialized (lazy loading)")
    
    def _ensure_model_loaded(self):
        """Ensure model is loaded (lazy loading)"""
        if not self.model_loaded:
            self._load_model()
            self._load_or_create_index()
            self.model_loaded = True
    
    def _load_model(self):
        """Load sentence transformer model"""
        try:
            logger.info("Loading sentence transformer model...")
            # Use a much smaller model to avoid segfaults
            self.model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            self.dimension = 384  # L6 dimension
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            # Fallback: disable semantic search
            self.model = None
            self.model_loaded = False
            raise
    
    def _load_or_create_index(self):
        """Load existing FAISS index or create new one"""
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.mapping_path):
                self._load_index()
                logger.info("Loaded existing FAISS index")
            else:
                self._create_index()
                logger.info("Created new FAISS index")
        except Exception as e:
            logger.error(f"Index initialization error: {str(e)}")
            self._create_index()
    
    def _create_index(self):
        """Create new FAISS index"""
        # Using Inner Product (IP) for cosine similarity
        self.index = faiss.IndexFlatIP(self.dimension)
        self.chunk_mapping = []
    
    def _load_index(self):
        """Load existing FAISS index and mapping"""
        self.index = faiss.read_index(self.index_path)
        
        with open(self.mapping_path, 'rb') as f:
            self.chunk_mapping = pickle.load(f)
    
    def _save_index(self):
        """Save FAISS index and mapping"""
        try:
            faiss.write_index(self.index, self.index_path)
            
            with open(self.mapping_path, 'wb') as f:
                pickle.dump(self.chunk_mapping, f)
            
            logger.info("FAISS index saved")
        except Exception as e:
            logger.error(f"Failed to save index: {str(e)}")
    
    def encode_text(self, texts: List[str]) -> np.ndarray:
        """Encode texts to embeddings"""
        self._ensure_model_loaded()
        try:
            embeddings = self.model.encode(texts, batch_size=32, show_progress_bar=False)
            # Normalize for cosine similarity
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            return embeddings.astype('float32')
        except Exception as e:
            logger.error(f"Encoding error: {str(e)}")
            raise
    
    def add_chunks_to_index(self, chunks: List[Dict]):
        """Add chunks to FAISS index"""
        if not chunks:
            return
        
        try:
            texts = [chunk['content'] for chunk in chunks]
            embeddings = self.encode_text(texts)
            
            # Add to index
            start_idx = self.index.ntotal
            self.index.add(embeddings)
            
            # Update mapping
            for i, chunk in enumerate(chunks):
                self.chunk_mapping.append({
                    'chunk_id': chunk['id'],
                    'content': chunk['content'],
                    'doc_name': chunk.get('doc_name', ''),
                    'doc_path': chunk.get('doc_path', ''),
                    'file_type': chunk.get('file_type', '')
                })
            
            # Save embeddings to database
            cursor = self.db.connection.cursor()
            for i, chunk in enumerate(chunks):
                embedding_bytes = embeddings[i].tobytes()
                self.db.add_embedding(chunk['id'], embedding_bytes, 'all-MiniLM-L6-v2')
            
            logger.info(f"Added {len(chunks)} chunks to index")
            
        except Exception as e:
            logger.error(f"Error adding chunks to index: {str(e)}")
            raise
    
    def semantic_search(self, query: str, k: int = 5, min_similarity: float = 0.3) -> List[Dict]:
        """Perform semantic search"""
        self._ensure_model_loaded()
        try:
            if self.index.ntotal == 0:
                logger.warning("Empty index - no search results")
                return []
            
            # Encode query
            query_embedding = self.encode_text([query])
            
            # Search in FAISS
            similarities, indices = self.index.search(query_embedding, min(k, self.index.ntotal))
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx >= 0 and idx < len(self.chunk_mapping):
                    similarity = float(similarities[0][i])
                    
                    if similarity >= min_similarity:
                        chunk_info = self.chunk_mapping[idx].copy()
                        chunk_info['similarity_score'] = similarity
                        chunk_info['search_type'] = 'semantic'
                        results.append(chunk_info)
            
            logger.info(f"Semantic search: {len(results)} results for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search error: {str(e)}")
            return []
    
    def hybrid_search(self, query: str, k: int = 5, semantic_weight: float = 0.7) -> List[Dict]:
        """Hybrid search combining semantic and full-text search"""
        try:
            # Get semantic results
            semantic_results = self.semantic_search(query, k=k*2)
            
            # Get full-text results
            text_results = self.db.search_fulltext(query, limit=k*2)
            
            # Convert text results to same format
            formatted_text_results = []
            for result in text_results:
                formatted_text_results.append({
                    'chunk_id': result['id'],
                    'content': result['content'],
                    'doc_name': result['doc_name'],
                    'doc_path': result['doc_path'],
                    'file_type': result['file_type'],
                    'similarity_score': 0.5,  # Default score for text search
                    'search_type': 'fulltext'
                })
            
            # Combine and deduplicate
            all_results = semantic_results + formatted_text_results
            seen_chunks = set()
            unique_results = []
            
            for result in all_results:
                chunk_id = result['chunk_id']
                if chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    unique_results.append(result)
            
            # Sort by combined score
            for result in unique_results:
                if result['search_type'] == 'semantic':
                    result['final_score'] = result['similarity_score'] * semantic_weight
                else:
                    result['final_score'] = result['similarity_score'] * (1 - semantic_weight)
            
            unique_results.sort(key=lambda x: x['final_score'], reverse=True)
            
            return unique_results[:k]
            
        except Exception as e:
            logger.error(f"Hybrid search error: {str(e)}")
            return []
    
    def rebuild_index(self):
        """Rebuild entire index from database"""
        try:
            logger.info("Rebuilding FAISS index...")
            
            # Create new index
            self._create_index()
            
            # Get all chunks with embeddings
            cursor = self.db.connection.cursor()
            cursor.execute("""
                SELECT c.id, c.content, d.name as doc_name, d.path as doc_path, d.file_type
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.embedding_id IS NOT NULL
                ORDER BY c.id
            """)
            
            chunks = [dict(row) for row in cursor.fetchall()]
            
            if chunks:
                # Process in batches to avoid memory issues
                batch_size = 100
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i+batch_size]
                    self.add_chunks_to_index(batch)
                    
                    if (i + batch_size) % 500 == 0:
                        logger.info(f"Processed {i + batch_size} chunks")
            
            self._save_index()
            logger.info(f"Index rebuilt with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Index rebuild error: {str(e)}")
            raise
    
    def update_missing_embeddings(self, batch_size: int = 50):
        """Generate embeddings for chunks that don't have them"""
        try:
            chunks = self.db.get_chunks_without_embeddings(self.model_name, batch_size)
            
            if not chunks:
                logger.info("No missing embeddings found")
                return
            
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            
            # Process in smaller batches
            for i in range(0, len(chunks), 10):
                batch = chunks[i:i+10]
                self.add_chunks_to_index(batch)
            
            self._save_index()
            logger.info(f"Updated embeddings for {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Embedding update error: {str(e)}")
            raise
    
    def get_stats(self) -> Dict:
        """Get search engine statistics"""
        stats = self.db.get_document_stats()
        stats.update({
            'index_size': self.index.ntotal if self.index and self.model_loaded else 0,
            'model_name': 'all-MiniLM-L6-v2',
            'dimension': self.dimension,
            'model_loaded': self.model_loaded
        })
        return stats
    
    def close(self):
        """Clean up resources"""
        try:
            self._save_index()
            self.db.close()
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
