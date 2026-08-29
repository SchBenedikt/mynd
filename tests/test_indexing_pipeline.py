import json
import threading

import numpy as np
import pytest

from app import indexing_pipeline


def test_dav_location_accepts_instance_and_full_webdav_urls():
    assert indexing_pipeline._dav_location('https://cloud.example', 'user name') == (
        'https://cloud.example',
        '/remote.php/dav/files/user%20name',
    )
    assert indexing_pipeline._dav_location(
        'https://cloud.example/remote.php/dav/files/alice', 'ignored'
    ) == ('https://cloud.example', '/remote.php/dav/files/alice')


def test_pipeline_builds_real_chunks_and_embeddings(monkeypatch, tmp_path):
    def fake_sync(syncer, _cancel_event):
        source = syncer.local_dir / 'Documents' / 'note.txt'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('# Heading\n\nUseful content', encoding='utf-8')
        return {
            'stats': {'downloaded': 1, 'skipped': 0, 'errors': 0, 'parsed': 0},
            'files': [
                {
                    'path': 'Documents/note.txt',
                    'local_path': str(source),
                    'hash': 'hash',
                    'action': 'downloaded',
                }
            ],
        }

    monkeypatch.setattr(indexing_pipeline.NextcloudSyncer, 'full_sync', fake_sync)
    monkeypatch.setattr(
        indexing_pipeline,
        'embed',
        lambda texts, model=None: np.ones((len(texts), 4), dtype=np.float32),
    )
    chunks_path = tmp_path / 'chunks.json'
    embeddings_path = tmp_path / 'embeddings.npy'

    result = indexing_pipeline.index_nextcloud_documents(
        url='https://cloud.example',
        username='alice',
        password='secret',
        remote_path='/Documents',
        data_dir=tmp_path,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        embedding_model='embed-model',
        cancel_event=threading.Event(),
    )

    chunks = json.loads(chunks_path.read_text(encoding='utf-8'))
    embeddings = np.load(embeddings_path)
    assert result['documents'] == 1
    assert result['chunks'] == len(chunks) > 0
    assert chunks[0]['source'] == 'nextcloud://Documents/note.md'
    assert embeddings.shape == (len(chunks), 4)


def test_pipeline_rejects_relative_remote_path(tmp_path):
    with pytest.raises(ValueError, match='relative'):
        indexing_pipeline.index_nextcloud_documents(
            url='https://cloud.example',
            username='alice',
            password='secret',
            remote_path='../private',
            data_dir=tmp_path,
            chunks_path=tmp_path / 'chunks.json',
            embeddings_path=tmp_path / 'embeddings.npy',
            embedding_model='embed-model',
            cancel_event=threading.Event(),
        )
