import sqlite3
import logging
import sys
import os
from typing import List, Dict
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from backend.core.database import KnowledgeDatabase

logger = logging.getLogger(__name__)

class SimpleSearchEngine:
    """Lightweight search engine using SQLite FTS without heavy ML models"""
    
    def __init__(self, db_path: str = "knowledge_base.db"):
        self.db = KnowledgeDatabase(db_path)
        logger.info("Simple search engine initialized")

    def add_chunks_to_index(self, chunks: List[Dict]) -> None:
        """Compatibility no-op: chunks are already persisted in SQLite via KnowledgeDatabase."""
        logger.info(f"Received {len(chunks)} chunks for index update (SQLite FTS uses DB directly)")

    def _save_index(self) -> None:
        """Compatibility no-op for interface parity with semantic engine."""
        logger.debug("Skipping index save for SQLite FTS backend")
    
    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Perform search using SQLite FTS with improved query processing"""
        try:
            if not query or len(query.strip()) < 2:
                return []
            
            logger.info(f"Searching for: {query}")
            
            # Try multiple search strategies
            all_results = []
            
            # 1. Original query
            fts_results = self.db.search_fulltext(query, limit=k)
            logger.info(f"FTS results for '{query}': {len(fts_results)}")
            all_results.extend(fts_results)
            
            # 2. If no results, try keywords
            if len(fts_results) < k:
                keywords = self._extract_keywords(query)
                logger.info(f"Keywords extracted: {keywords}")
                
                for keyword in keywords[:3]:  # Limit to avoid too many results
                    if len(keyword) > 2:  # Skip very short keywords
                        keyword_results = self.db.search_fulltext(keyword, limit=k//2)
                        logger.info(f"Keyword '{keyword}' results: {len(keyword_results)}")
                        all_results.extend(keyword_results)
            
            # Remove duplicates and sort by relevance
            seen_ids = set()
            unique_results = []
            for result in all_results:
                if result['id'] not in seen_ids:
                    seen_ids.add(result['id'])
                    unique_results.append(result)
            
            # Convert to expected format
            results = []
            for result in unique_results[:k]:
                results.append({
                    'content': result['content'],
                    'distance': 0.5,  # Neutral distance
                    'source': result.get('doc_name', 'Unknown'),
                    'path': result.get('doc_path', ''),
                    'similarity_score': 0.5,
                    'search_type': 'fulltext',
                    'chunk_id': result['id']
                })
            
            logger.info(f"Final results: {len(results)} for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query"""
        import re
        
        # Remove common German stop words
        stop_words = {
            'der', 'die', 'das', 'ist', 'sind', 'war', 'waren', 'haben', 'hat', 'hatten',
            'werden', 'wird', 'wurde', 'wurden', 'können', 'kann', 'konnte', 'konnten',
            'müssen', 'muss', 'musste', 'mussten', 'sollen', 'soll', 'sollte', 'sollten',
            'wollen', 'will', 'wollte', 'wollten', 'dürfen', 'darf', 'durfte', 'durften',
            'mögen', 'mag', 'mochte', 'mochten', 'ein', 'eine', 'einer', 'eines', 'einem',
            'einen', 'oder', 'und', 'aber', 'auf', 'in', 'an', 'für', 'mit', 'zu', 'bei',
            'von', 'nach', 'über', 'unter', 'durch', 'gegen', 'ohne', 'um', 'bis', 'seit',
            'als', 'wie', 'wenn', 'dann', 'dass', 'weil', 'damit', 'dadurch', 'deshalb',
            'daher', 'dafür', 'dagegen', 'davor', 'danach', 'davor', 'hier', 'dort',
            'dieser', 'diese', 'dieses', 'jener', 'jene', 'jenes', 'welcher', 'welche',
            'welches', 'mein', 'dein', 'sein', 'ihr', 'unser', 'euer', 'ich', 'du',
            'er', 'sie', 'es', 'wir', 'ihr', 'sie', 'mich', 'dich', 'ihn', 'ihr',
            'es', 'uns', 'euch', 'sie', 'mir', 'dir', 'ihm', 'ihr', 'ihnen', 'was',
            'wie', 'wo', 'wann', 'warum', 'weshalb', 'wieso', 'woher', 'wohin'
        }
        
        # Extract words and filter stop words
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def get_stats(self) -> Dict:
        """Get search statistics"""
        stats = self.db.get_document_stats()
        stats.update({
            'index_size': stats.get('chunks', 0),
            'model_name': 'SQLite FTS',
            'dimension': 0,
            'model_loaded': True,
            'search_type': 'fulltext'
        })
        return stats
