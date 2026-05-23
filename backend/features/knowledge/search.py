import logging
import os
import re
from typing import Dict, List

import numpy as np

from backend.core.database import KnowledgeDatabase

logger = logging.getLogger(__name__)


class SimpleSearchEngine:
    """SQLite FTS search with embedding-based reranking."""

    def __init__(self, db_path: str = "knowledge_base.db"):
        self.db = KnowledgeDatabase(db_path)
        self.embedding_model_name = os.getenv('MYND_EMBEDDING_MODEL', 'nomic-embed-text')
        self.embedding_model = None
        self._embedding_model_loaded = False
        self._use_ollama = False
        logger.info("Simple search engine initialized")

    def _ensure_embedding_model_loaded(self) -> bool:
        """Lazy-load the embedding model and keep startup cheap if it is unavailable."""
        if self._embedding_model_loaded:
            return self.embedding_model is not None
        # First check if Ollama is available and prefer it as a remote embedder.
        try:
            from backend.core import app as core_app
            ollama = getattr(core_app, 'ollama_client', None)
            if ollama and ollama.check_connection():
                # Use Ollama as embedding provider (no local model loaded)
                self._use_ollama = True
                self.embedding_model = None
                self._embedding_model_loaded = True
                logger.info("Using Ollama as embedding provider: %s", ollama.base_url)
                return True
        except Exception:
            # ignore and fall back to local model attempt
            pass

        self._embedding_model_loaded = True
        try:
            from sentence_transformers import SentenceTransformer

            self.embedding_model = SentenceTransformer(self.embedding_model_name, device='cpu')
            logger.info("Embedding model loaded: %s", self.embedding_model_name)
            return True
        except Exception as exc:
            logger.warning("Embedding model unavailable, falling back to text search: %s", exc)
            self.embedding_model = None
            return False

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        """Encode texts as normalized float32 embeddings."""
        if not texts:
            return np.empty((0, 0), dtype='float32')

        if not self._ensure_embedding_model_loaded():
            # Try to use Ollama as a remote embedding provider if available
            try:
                # import here to avoid circular imports at module load time
                from backend.core import app as core_app
                ollama = getattr(core_app, 'ollama_client', None)
                if ollama and ollama.check_connection():
                    embeddings = ollama.embed(texts, model=self.embedding_model_name)
                    arr = np.asarray(embeddings, dtype='float32')
                    if arr.size == 0:
                        return np.empty((0, 0), dtype='float32')
                    norms = np.linalg.norm(arr, axis=1, keepdims=True)
                    arr = arr / np.clip(norms, 1e-12, None)
                    return arr
            except Exception as exc:
                logger.warning("Ollama embedding fallback failed: %s", exc)

            return np.empty((0, 0), dtype='float32')

        embeddings = self.embedding_model.encode(texts, batch_size=16, show_progress_bar=False)
        embeddings = np.asarray(embeddings, dtype='float32')
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.clip(norms, 1e-12, None)
        return embeddings

    def _merge_candidates(self, primary: List[Dict], fallback: List[Dict]) -> List[Dict]:
        """Merge result sets while keeping the original ranking order of the primary set."""
        merged = []
        seen_ids = set()

        for result in primary + fallback:
            chunk_id = result.get('id') or result.get('chunk_id')
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)
            merged.append(result)

        return merged

    def _format_results(self, results: List[Dict], search_type: str) -> List[Dict]:
        formatted = []
        for result in results:
            formatted.append({
                'content': result.get('content', ''),
                'distance': 1.0 - float(result.get('similarity_score', 0.5)),
                'source': result.get('doc_name', 'Unknown'),
                'path': result.get('doc_path', ''),
                'similarity_score': float(result.get('similarity_score', 0.5)),
                'search_type': result.get('search_type', search_type),
                'chunk_id': result.get('id') or result.get('chunk_id')
            })
        return formatted

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract a few meaningful keywords for fallback full-text queries."""
        stop_words = {
            'der', 'die', 'das', 'ist', 'sind', 'war', 'waren', 'haben', 'hat', 'hatten',
            'werden', 'wird', 'wurde', 'wurden', 'können', 'kann', 'konnte', 'konnten',
            'müssen', 'muss', 'musste', 'mussten', 'sollen', 'soll', 'sollte', 'sollten',
            'wollen', 'will', 'wollte', 'wollten', 'dürfen', 'darf', 'durfte', 'durften',
            'mögen', 'mag', 'mochte', 'mochten', 'ein', 'eine', 'einer', 'eines', 'einem',
            'einen', 'oder', 'und', 'aber', 'auf', 'in', 'an', 'für', 'mit', 'zu', 'bei',
            'von', 'nach', 'über', 'unter', 'durch', 'gegen', 'ohne', 'um', 'bis', 'seit',
            'als', 'wie', 'wenn', 'dann', 'dass', 'weil', 'damit', 'dadurch', 'deshalb',
            'daher', 'dafür', 'dagegen', 'davor', 'danach', 'hier', 'dort', 'dieser', 'diese',
            'dieses', 'jener', 'jene', 'jenes', 'welcher', 'welche', 'welches', 'mein', 'dein',
            'sein', 'ihr', 'unser', 'euer', 'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'mich',
            'dich', 'ihn', 'uns', 'euch', 'mir', 'dir', 'ihm', 'ihnen', 'was', 'wie', 'wo',
            'wann', 'warum', 'weshalb', 'wieso', 'woher', 'wohin'
        }

        words = re.findall(r'\b\w+\b', (query or '').lower())
        return [word for word in words if word not in stop_words and len(word) > 2]

    def add_chunks_to_index(self, chunks: List[Dict]) -> None:
        """Generate and persist embeddings for chunks so reranking has cached vectors."""
        if not chunks:
            return

        if not self._ensure_embedding_model_loaded():
            logger.info("Skipping embedding persistence because the model is unavailable")
            return

        texts = [str(chunk.get('content', '') or '') for chunk in chunks]
        embeddings = self._encode_texts(texts)
        if embeddings.size == 0:
            return

        stored = 0
        for chunk, vector in zip(chunks, embeddings):
            chunk_id = chunk.get('id')
            if chunk_id is None:
                continue
            self.db.add_embedding(chunk_id, vector.tobytes(), self.embedding_model_name)
            stored += 1

        logger.info("Stored embeddings for %s chunks", stored)

    def update_missing_embeddings(self, batch_size: int = 50):
        """Backfill missing embeddings for recently indexed chunks."""
        try:
            chunks = self.db.get_chunks_without_embeddings(self.embedding_model_name, batch_size)
            if not chunks:
                logger.info("No missing embeddings found")
                return

            logger.info("Generating embeddings for %s missing chunks", len(chunks))
            self.add_chunks_to_index(chunks)
            self._save_index()
        except Exception as exc:
            logger.error("Embedding update error: %s", exc)
            raise

    def rebuild_index(self):
        """Rebuild cached embeddings for all chunks that do not yet have the active model."""
        try:
            while True:
                chunks = self.db.get_chunks_without_embeddings(self.embedding_model_name, 500)
                if not chunks:
                    break
                self.add_chunks_to_index(chunks)

            self._save_index()
            logger.info("Embedding cache rebuild completed")
        except Exception as exc:
            logger.error("Embedding cache rebuild error: %s", exc)
            raise

    def _save_index(self) -> None:
        """Compatibility no-op for interface parity with semantic engine."""
        logger.debug("Skipping index save for SQLite FTS backend")

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Perform search using SQLite FTS plus embedding reranking."""
        return self.hybrid_search(query, k=k)

    def hybrid_search(self, query: str, k: int = 5, semantic_weight: float = 0.7) -> List[Dict]:
        """Rerank search candidates with semantic similarity and full-text relevance."""
        try:
            if not query or len(query.strip()) < 2:
                return []

            logger.info("Searching for: %s", query)

            candidate_limit = max(k * 6, 20)
            fts_results = self.db.search_fulltext(query, limit=candidate_limit)

            keyword_results = []
            if len(fts_results) < k:
                for keyword in self._extract_keywords(query)[:3]:
                    if len(keyword) > 2:
                        keyword_results.extend(self.db.search_fulltext(keyword, limit=max(2, k // 2)))

            candidate_results = self._merge_candidates(fts_results, keyword_results)

            if len(candidate_results) < k:
                fallback_candidates = self.db.get_chunks_with_documents(limit=max(candidate_limit, 100))
                candidate_results = self._merge_candidates(candidate_results, fallback_candidates)

            logger.info("Candidate results for '%s': %s", query, len(candidate_results))

            if not candidate_results:
                return []

            if not self._ensure_embedding_model_loaded():
                return self._format_results(candidate_results[:k], 'fulltext')

            query_embedding = self._encode_texts([query])
            if query_embedding.size == 0:
                return self._format_results(candidate_results[:k], 'fulltext')

            candidate_texts = [str(result.get('content', '') or '') for result in candidate_results]
            candidate_embeddings = self._encode_texts(candidate_texts)
            if candidate_embeddings.size == 0:
                return self._format_results(candidate_results[:k], 'fulltext')

            semantic_scores = candidate_embeddings @ query_embedding[0]
            total_candidates = max(len(candidate_results), 1)

            scored_results = []
            for index, result in enumerate(candidate_results):
                text_score = 1.0 - (index / max(total_candidates - 1, 1))
                semantic_score = float(semantic_scores[index])
                final_score = (semantic_weight * semantic_score) + ((1.0 - semantic_weight) * text_score)

                enriched = dict(result)
                enriched['semantic_score'] = semantic_score
                enriched['text_score'] = text_score
                enriched['similarity_score'] = final_score
                enriched['search_type'] = 'hybrid'
                scored_results.append(enriched)

            scored_results.sort(key=lambda item: item.get('similarity_score', 0.0), reverse=True)

            results = self._format_results(scored_results[:k], 'hybrid')
            logger.info("Final results: %s for query: %s...", len(results), query[:50])
            return results

        except Exception as exc:
            logger.error("Search error: %s", exc)
            import traceback
            traceback.print_exc()
            return []

    def get_stats(self) -> Dict:
        """Get search statistics"""
        stats = self.db.get_document_stats()
        embedding_coverage = self.db.get_embedding_coverage(self.embedding_model_name)
        stats.update({
            'index_size': stats.get('chunks', 0),
            'model_name': self.embedding_model_name,
            'dimension': 384,
            'model_loaded': self.embedding_model is not None,
            'search_type': 'hybrid' if self.embedding_model is not None else 'fulltext',
            'embedding_coverage': embedding_coverage,
        })
        return stats
