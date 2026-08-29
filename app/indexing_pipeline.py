import json
import os
import tempfile
import threading
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import numpy as np

from core.embed import embed
from scripts.ingest import HeadingAwareChunker
from scripts.parse_docs import parse_document
from scripts.sync_nextcloud import NextcloudSyncer, NextcloudWebDAVClient

NEXTCLOUD_SOURCE_PREFIX = 'nextcloud://'


def _dav_location(url: str, username: str) -> tuple[str, str]:
    normalized = url.rstrip('/')
    marker = '/remote.php/'
    if marker in normalized:
        base_url, suffix = normalized.split(marker, 1)
        return base_url, f'/remote.php/{suffix}'.rstrip('/')
    return normalized, f'/remote.php/dav/files/{quote(username, safe="")}'


def _load_existing_index(chunks_path: Path, embeddings_path: Path) -> tuple[list[dict], np.ndarray]:
    if not chunks_path.exists() and not embeddings_path.exists():
        return [], np.array([], dtype=np.float32).reshape(0, 0)
    if not chunks_path.exists() or not embeddings_path.exists():
        raise RuntimeError('Der bestehende Wissensindex ist unvollständig; Chunks und Embeddings müssen gemeinsam vorliegen.')
    chunks = json.loads(chunks_path.read_text(encoding='utf-8'))
    embeddings = np.load(embeddings_path)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(chunks):
        raise RuntimeError('Der bestehende Wissensindex ist inkonsistent; bitte den Index reparieren oder neu aufbauen.')
    return chunks, embeddings.astype(np.float32, copy=False)


def _atomic_write_index(chunks_path: Path, embeddings_path: Path, chunks: list[dict], embeddings: np.ndarray) -> None:
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    chunks_fd, chunks_tmp = tempfile.mkstemp(prefix='.chunks.', dir=chunks_path.parent)
    embeddings_fd, embeddings_tmp = tempfile.mkstemp(prefix='.embeddings.', dir=embeddings_path.parent)
    try:
        with os.fdopen(chunks_fd, 'w', encoding='utf-8') as handle:
            json.dump(chunks, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        with os.fdopen(embeddings_fd, 'wb') as handle:
            np.save(handle, embeddings)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(chunks_tmp, chunks_path)
        os.replace(embeddings_tmp, embeddings_path)
    finally:
        for temporary in (chunks_tmp, embeddings_tmp):
            if os.path.exists(temporary):
                os.unlink(temporary)


def index_nextcloud_documents(
    *,
    url: str,
    username: str,
    password: str,
    remote_path: str,
    data_dir: Path,
    chunks_path: Path,
    embeddings_path: Path,
    embedding_model: str | None,
    cancel_event: threading.Event,
    progress_callback=None,
) -> dict:
    """Synchronize Nextcloud documents and atomically replace their part of the local index."""
    base_url, webdav_path = _dav_location(url, username)
    synced_dir = data_dir / 'nextcloud_synced'
    parsed_dir = data_dir / 'nextcloud_parsed'
    selected_path = remote_path.strip().strip('/')
    selected_parts = PurePosixPath(selected_path).parts if selected_path else ()
    if any(part in ('.', '..') for part in selected_parts):
        raise ValueError('Der Nextcloud-Pfad darf keine relativen Segmente enthalten.')
    selected_path = PurePosixPath(*selected_parts).as_posix() if selected_parts else ''
    folders = [selected_path] if selected_path else ['']
    extensions = {'.md', '.markdown', '.txt', '.text', '.docx', '.pdf'}

    client = NextcloudWebDAVClient(base_url, username, password, webdav_path)
    syncer = NextcloudSyncer(
        client,
        synced_dir,
        data_dir / 'nextcloud_sync_state.json',
        extensions,
        folders,
        parsed_dir=parsed_dir,
    )
    sync_result = syncer.full_sync(cancel_event)
    files = sync_result.get('files', [])
    if cancel_event.is_set():
        return {'cancelled': True, 'documents': 0, 'chunks': 0, 'files': len(files), 'sync': sync_result['stats']}
    if int(sync_result.get('stats', {}).get('errors', 0)) > 0:
        raise RuntimeError('Die Nextcloud-Synchronisierung war unvollständig; der bestehende Index wurde nicht verändert.')

    total_files = len(files)
    parsed_count = 0
    for index, file_info in enumerate(files, start=1):
        if cancel_event.is_set():
            return {'cancelled': True, 'documents': parsed_count, 'chunks': 0, 'files': total_files, 'sync': sync_result['stats']}
        source_path = Path(file_info['local_path'])
        output_path = (parsed_dir / Path(file_info['path'])).with_suffix('.md')
        if file_info.get('action') == 'downloaded' or not output_path.exists():
            parse_document(source_path, parsed_dir, relative_base=synced_dir)
        parsed_count += 1
        if progress_callback:
            progress_callback(
                processed_files=index,
                total_files=total_files,
                current_file=file_info['path'],
                progress=min(75, round(index / max(total_files, 1) * 75)),
            )

    existing_chunks, existing_embeddings = _load_existing_index(chunks_path, embeddings_path)
    preserved_indices = [
        index
        for index, chunk in enumerate(existing_chunks)
        if not str(chunk.get('source') or '').startswith(NEXTCLOUD_SOURCE_PREFIX)
    ]
    preserved_chunks = [existing_chunks[index] for index in preserved_indices]
    preserved_embeddings = (
        existing_embeddings[preserved_indices]
        if preserved_indices
        else np.array([], dtype=np.float32).reshape(0, existing_embeddings.shape[1] if existing_embeddings.ndim == 2 else 0)
    )

    chunker = HeadingAwareChunker()
    nextcloud_chunks = []
    for parsed_path in sorted(parsed_dir.rglob('*.md')):
        if cancel_event.is_set():
            return {'cancelled': True, 'documents': parsed_count, 'chunks': 0, 'files': total_files, 'sync': sync_result['stats']}
        relative_source = parsed_path.relative_to(parsed_dir).as_posix()
        content = parsed_path.read_text(encoding='utf-8')
        for chunk in chunker.chunk_document(content, {'source': f'{NEXTCLOUD_SOURCE_PREFIX}{relative_source}'}):
            nextcloud_chunks.append(
                {
                    'text': chunk['content'],
                    'source': chunk['metadata']['source'],
                    'headings': chunk['metadata'].get('headings', []),
                }
            )

    vectors: list[np.ndarray] = []
    texts = [chunk['text'] for chunk in nextcloud_chunks]
    for offset in range(0, len(texts), 32):
        if cancel_event.is_set():
            return {'cancelled': True, 'documents': parsed_count, 'chunks': len(vectors), 'files': total_files, 'sync': sync_result['stats']}
        batch = texts[offset:offset + 32]
        batch_vectors = np.asarray(embed(batch, model=embedding_model or None), dtype=np.float32)
        if batch_vectors.ndim != 2 or batch_vectors.shape[0] != len(batch):
            raise RuntimeError('Das Embedding-Modell hat eine ungültige Antwort geliefert.')
        vectors.append(batch_vectors)
        if progress_callback:
            progress_callback(
                processed_files=total_files,
                total_files=total_files,
                current_file='Embeddings werden erstellt',
                progress=75 + round((offset + len(batch)) / max(len(texts), 1) * 24),
            )

    if vectors:
        nextcloud_embeddings = np.vstack(vectors)
    else:
        dimension = preserved_embeddings.shape[1] if preserved_embeddings.ndim == 2 else 0
        nextcloud_embeddings = np.array([], dtype=np.float32).reshape(0, dimension)
    if preserved_embeddings.size and nextcloud_embeddings.size and preserved_embeddings.shape[1] != nextcloud_embeddings.shape[1]:
        raise RuntimeError('Das konfigurierte Embedding-Modell ist nicht mit dem bestehenden Index kompatibel.')
    if preserved_embeddings.size and nextcloud_embeddings.size:
        combined_embeddings = np.vstack([preserved_embeddings, nextcloud_embeddings])
    elif preserved_embeddings.size:
        combined_embeddings = preserved_embeddings
    else:
        combined_embeddings = nextcloud_embeddings
    combined_chunks = preserved_chunks + nextcloud_chunks
    _atomic_write_index(chunks_path, embeddings_path, combined_chunks, combined_embeddings)
    return {
        'cancelled': False,
        'documents': parsed_count,
        'chunks': len(nextcloud_chunks),
        'files': total_files,
        'sync': sync_result['stats'],
    }
