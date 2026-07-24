#!/usr/bin/env python3
"""
LightRAG Ingestion Pipeline
Ingests parsed documents into LightRAG with heading-aware chunking,
entity extraction, and graph construction.
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class IgestionState:
    """Tracks ingestion state for each document."""
    documents: dict[str, dict]  # doc_hash -> {path, hash, ingested_at, chunks, entities, relations}

    @classmethod
    def load(cls, path: Path) -> 'IgestionState':
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(**data)
        return cls(documents={})

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    def is_ingested(self, doc_hash: str) -> bool:
        return doc_hash in self.documents

    def mark_ingested(self, doc_hash: str, doc_info: dict):
        self.documents[doc_hash] = doc_info

    def remove(self, doc_hash: str):
        self.documents.pop(doc_hash, None)


class HeadingAwareChunker:
    """Chunk documents respecting heading hierarchy for better context."""

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, content: str, metadata: dict = None) -> list[dict]:
        """Split document into heading-aware chunks with metadata."""
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        current_heading_chain = []
        chunk_idx = 0

        def _flush_chunk():
            nonlocal chunk_idx, current_size
            if not current_chunk:
                return

            chunk_text = '\n'.join(current_chunk).strip()
            if not chunk_text:
                return

            chunk_info = {
                'id': f"{metadata.get('source', 'doc')}#chunk-{chunk_idx}",
                'content': chunk_text,
                'metadata': {
                    **metadata,
                    'headings': list(current_heading_chain),
                    'chunk_index': chunk_idx,
                    'total_chunks': None,  # filled later
                }
            }
            chunks.append(chunk_info)
            chunk_idx += 1

        for line in lines:
            # Detect headings
            heading_match = line.strip().startswith('#')
            if heading_match:
                heading_level = len(line) - len(line.lstrip('#'))
                heading_text = line.strip('#').strip()

                if heading_text:
                    # Update heading chain
                    current_heading_chain = [
                        h for h in current_heading_chain
                        if h['level'] < heading_level
                    ]
                    current_heading_chain.append({
                        'level': heading_level,
                        'text': heading_text
                    })

                    # Flush previous section
                    if current_size > self.chunk_size * 0.5:
                        _flush_chunk()
                        current_chunk = []
                        current_size = 0

            current_chunk.append(line)
            current_size += len(line)

            if current_size >= self.chunk_size:
                _flush_chunk()
                # Keep overlap: last chunk_size/5 chars
                overlap_size = 0
                overlap_lines = []
                for line_ in reversed(current_chunk):
                    if overlap_size >= self.chunk_overlap:
                        break
                    overlap_lines.insert(0, line_)
                    overlap_size += len(line_)
                current_chunk = overlap_lines
                current_size = overlap_size

        _flush_chunk()

        # Update total chunks
        for i, chunk in enumerate(chunks):
            chunk['metadata']['total_chunks'] = len(chunks)

        return chunks


class LightRAGHandler:
    """Handles communication with LightRAG API."""

    def __init__(self, base_url: str = "http://localhost:9621"):
        self.base_url = base_url.rstrip('/')
        self.session = None

    def _get_session(self):
        if self.session is None:
            import requests
            self.session = requests.Session()
        return self.session

    def health_check(self) -> bool:
        """Check if LightRAG is running."""
        try:
            session = self._get_session()
            response = session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"LightRAG health check failed: {e}")
            return False

    def insert_text(self, text: str, metadata: dict = None) -> dict:
        """Insert text into LightRAG."""
        import requests
        session = self._get_session()

        payload = {
            'text': text,
            'metadata': metadata or {},
        }

        try:
            response = session.post(
                f"{self.base_url}/insert_text",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning("LightRAG insert_text timed out, retrying...")
            time.sleep(5)
            response = session.post(
                f"{self.base_url}/insert_text",
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            return response.json()

    def insert_file(self, filepath: Path, metadata: dict = None) -> dict:
        """Insert a file into LightRAG."""
        session = self._get_session()

        with open(filepath, 'rb') as f:
            content = f.read()

        files = {'file': (filepath.name, content, 'text/markdown')}
        data = {'metadata': json.dumps(metadata or {})}

        response = session.post(
            f"{self.base_url}/upload_document",
            files=files,
            data=data,
            timeout=300
        )
        response.raise_for_status()
        return response.json()

    def query(self, question: str, mode: str = "hybrid", stream: bool = False) -> dict:
        """Query the LightRAG index."""
        session = self._get_session()

        payload = {
            'query': question,
            'mode': mode,
            'stream': stream,
        }

        response = session.post(
            f"{self.base_url}/query",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the index."""
        session = self._get_session()

        try:
            response = session.delete(
                f"{self.base_url}/delete_document/{doc_id}",
                timeout=30
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False


class DocmentIngestor:
    """Main ingestion pipeline: parses, chunks, and inserts into LightRAG."""

    def __init__(
        self,
        lightrag: LightRAGHandler,
        state_file: Path,
        parsed_dir: Path,
        chunk_size: int = 1200,
        chunk_overlap: int = 100,
    ):
        self.lightrag = lightrag
        self.state = IgestionState.load(state_file)
        self.state_file = state_file
        self.parsed_dir = parsed_dir
        self.chunker = HeadingAwareChunker(chunk_size, chunk_overlap)
        self.stats = {'ingested': 0, 'skipped': 0, 'errors': 0, 'deleted': 0}

    def compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def process_document(self, filepath: Path) -> bool:
        """Process a single parsed document."""
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return False

        try:
            content = filepath.read_text(encoding='utf-8')
            doc_hash = self.compute_hash(content)

            # Check if already ingested
            if self.state.is_ingested(doc_hash):
                self.stats['skipped'] += 1
                logger.debug(f"Already ingested: {filepath.name}")
                return True

            # Extract metadata from YAML frontmatter
            metadata = {'source_file': str(filepath)}
            if content.startswith('---'):
                end_idx = content.find('---', 3)
                if end_idx != -1:
                    frontmatter = content[3:end_idx].strip()
                    for line in frontmatter.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                    content = content[end_idx + 3:].strip()

            # Chunk the document
            chunks = self.chunker.chunk_document(content, metadata)

            # Insert each chunk into LightRAG
            for chunk in chunks:
                try:
                    self.lightrag.insert_text(
                        chunk['content'],
                        chunk['metadata']
                    )
                except Exception as e:
                    logger.error(f"Failed to insert chunk {chunk['id']}: {e}")
                    raise

            # Mark as ingested
            self.state.mark_ingested(doc_hash, {
                'path': str(filepath),
                'hash': doc_hash,
                'chunks': len(chunks),
                'ingested_at': datetime.now().isoformat(),
            })
            self.state.save(self.state_file)

            self.stats['ingested'] += 1
            logger.info(f"Ingested: {filepath.name} ({len(chunks)} chunks)")
            return True

        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            self.stats['errors'] += 1
            return False

    def process_directory(self, directory: Path, pattern: str = "*.md") -> dict:
        """Process all parsed documents in a directory."""
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return self.stats

        md_files = sorted(directory.rglob(pattern))
        logger.info(f"Processing {len(md_files)} documents from {directory}")

        for filepath in md_files:
            self.process_document(filepath)

        self.state.save(self.state_file)
        logger.info(f"Ingestion complete: {self.stats}")
        return self.stats

    def watch_directory(self, directory: Path, interval: int = 60):
        """Watch directory for new/changed files and ingest them."""
        logger.info(f"Watching {directory} for changes (interval: {interval}s)...")

        while True:
            try:
                self.process_directory(directory)
            except KeyboardInterrupt:
                logger.info("Watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Watcher error: {e}")

            time.sleep(interval)

    def get_orphaned_documents(self, directory: Path) -> list[str]:
        """Find documents in state that no longer exist on disk."""
        orphaned = []
        for doc_hash, doc_info in self.state.documents.items():
            doc_path = Path(doc_info['path'])
            if not doc_path.exists():
                orphaned.append(doc_hash)
        return orphaned

    def cleanup_orphaned(self, directory: Path):
        """Remove orphaned documents from state and LightRAG."""
        orphaned = self.get_orphaned_documents(directory)
        for doc_hash in orphaned:
            doc_info = self.state.documents[doc_hash]
            path = doc_info.get('path', '')
            logger.info(f"Removing orphaned: {path}")
            self.state.remove(doc_hash)
            self.stats['deleted'] += 1

        if orphaned:
            self.state.save(self.state_file)
        logger.info(f"Cleaned up {len(orphaned)} orphaned documents")


def main():
    parser = argparse.ArgumentParser(description='LightRAG Ingestion Pipeline')
    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')

    # Ingest sub-command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest documents')
    ingest_parser.add_argument('input', type=str, nargs='?', default='./parsed_docs',
                               help='Input file or directory')
    ingest_parser.add_argument('--state', type=str, default='./data/ingestion_state.json',
                               help='State file path')
    ingest_parser.add_argument('--lightrag-url', type=str, default='http://localhost:9621',
                               help='LightRAG API URL')
    ingest_parser.add_argument('--chunk-size', type=int, default=1200,
                               help='Chunk size in tokens')
    ingest_parser.add_argument('--chunk-overlap', type=int, default=100,
                               help='Chunk overlap in tokens')

    # Watch sub-command
    watch_parser = subparsers.add_parser('watch', help='Watch directory for changes')
    watch_parser.add_argument('input', type=str, nargs='?', default='./parsed_docs',
                              help='Directory to watch')
    watch_parser.add_argument('--interval', type=int, default=60,
                              help='Watch interval in seconds')
    watch_parser.add_argument('--state', type=str, default='./data/ingestion_state.json',
                              help='State file path')
    watch_parser.add_argument('--lightrag-url', type=str, default='http://localhost:9621',
                               help='LightRAG API URL')
    watch_parser.add_argument('--chunk-size', type=int, default=1200,
                               help='Chunk size in tokens')

    # Query sub-command
    query_parser = subparsers.add_parser('query', help='Query the index')
    query_parser.add_argument('query', type=str, help='Query text')
    query_parser.add_argument('--lightrag-url', type=str, default='http://localhost:9621',
                              help='LightRAG API URL')
    query_parser.add_argument('--mode', type=str, default='hybrid',
                              choices=['local', 'global', 'hybrid', 'naive'],
                              help='Query mode')
    query_parser.add_argument('--stream', action='store_true', help='Stream response')

    # Cleanup sub-command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up orphaned documents')
    cleanup_parser.add_argument('--state', type=str, default='./data/ingestion_state.json',
                                help='State file path')
    cleanup_parser.add_argument('--lightrag-url', type=str, default='http://localhost:9621',
                                help='LightRAG API URL')
    cleanup_parser.add_argument('input', type=str, nargs='?', default='./parsed_docs',
                                help='Parsed documents directory')

    args = parser.parse_args()

    # Default to ingest if no command given
    if not args.command:
        args.command = 'ingest'
        args.input = './parsed_docs'
        args.state = './data/ingestion_state.json'
        args.lightrag_url = 'http://localhost:9621'
        args.chunk_size = 1200
        args.chunk_overlap = 100

    lightrag = LightRAGHandler(args.lightrag_url)

    # Wait for LightRAG to be ready
    if args.command in ['ingest', 'watch']:
        logger.info("Waiting for LightRAG to be ready...")
        for i in range(30):
            if lightrag.health_check():
                logger.info("LightRAG is ready!")
                break
            time.sleep(2)
        else:
            logger.error("LightRAG not ready after 60 seconds")
            sys.exit(1)

    parsed_dir = Path(getattr(args, 'input', './parsed_docs'))
    state_file = Path(getattr(args, 'state', './data/ingestion_state.json'))

    ingestor = DocmentIngestor(
        lightrag=lightrag,
        state_file=state_file,
        parsed_dir=parsed_dir,
        chunk_size=getattr(args, 'chunk_size', 1200),
        chunk_overlap=getattr(args, 'chunk_overlap', 100),
    )

    if args.command == 'ingest':
        input_path = Path(args.input)
        if input_path.is_file():
            ingestor.process_document(input_path)
        else:
            ingestor.process_directory(input_path)
        print(json.dumps(ingestor.stats, indent=2))

    elif args.command == 'watch':
        ingestor.watch_directory(Path(args.input), args.interval)

    elif args.command == 'query':
        result = lightrag.query(args.query, args.mode, args.stream)
        print(result.get('response', json.dumps(result, indent=2)))

    elif args.command == 'cleanup':
        ingestor.cleanup_orphaned(parsed_dir)


if __name__ == '__main__':
    main()
