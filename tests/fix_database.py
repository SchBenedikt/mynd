import sqlite3
import logging

logger = logging.getLogger(__name__)

def fix_fts_synchronization():
    """Repariert die FTS-Synchronisation"""
    try:
        conn = sqlite3.connect('knowledge_base.db')
        cursor = conn.cursor()
        
        # FTS Tabelle neu aufbauen
        logger.info("Rebuilding FTS index...")
        
        # Alte FTS Tabelle löschen
        cursor.execute("DROP TABLE IF EXISTS chunks_fts")
        
        # Neue FTS Tabelle erstellen
        cursor.execute("""
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                content,
                document_id,
                chunk_index,
                content='chunks',
                content_rowid='id'
            )
        """)
        
        # Alle Daten in FTS Tabelle einfügen
        cursor.execute("""
            INSERT INTO chunks_fts(rowid, content, document_id, chunk_index)
            SELECT id, content, document_id, chunk_index FROM chunks
        """)
        
        conn.commit()
        
        # Testen
        cursor.execute("SELECT COUNT(*) FROM chunks_fts")
        fts_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunks_count = cursor.fetchone()[0]
        
        logger.info(f"FTS records: {fts_count}, Chunk records: {chunks_count}")
        
        # Test-Suche
        cursor.execute("SELECT content FROM chunks_fts WHERE content MATCH 'wiki' LIMIT 3")
        results = cursor.fetchall()
        
        logger.info(f"Test search for 'wiki' found {len(results)} results")
        for result in results:
            logger.info(f"  - {result[0][:100]}...")
        
        conn.close()
        logger.info("FTS synchronization fixed successfully!")
        
    except Exception as e:
        logger.error(f"Error fixing FTS: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fix_fts_synchronization()
