#!/usr/bin/env python3
"""
Nextcloud WebDAV Sync Script
Syncs files from Nextcloud to local parsed_docs directory with SHA256 deduplication.
Supports .md, .txt, .docx, .pdf files.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.parse_docs import parse_document

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SyncState:
    """Tracks sync state for each file."""
    files: dict[str, dict]  # path -> {hash, size, modified, parsed_hash, last_synced}
    last_full_sync: str | None = None

    @classmethod
    def load(cls, path: Path) -> 'SyncState':
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(**data)
        return cls(files={})

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    def get_file_state(self, rel_path: str) -> dict | None:
        return self.files.get(rel_path)

    def update_file_state(self, rel_path: str, state: dict):
        self.files[rel_path] = state

    def remove_file_state(self, rel_path: str):
        self.files.pop(rel_path, None)


class NextcloudWebDAVClient:
    """WebDAV client for Nextcloud."""

    def __init__(self, base_url: str, username: str, password: str, webdav_path: str = ""):
        self.base_url = base_url.rstrip('/')
        self.webdav_path = webdav_path.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({'Depth': '1'})

    def _get_webdav_url(self, path: str = "") -> str:
        path = path.lstrip('/')
        if self.webdav_path:
            return f"{self.base_url}{self.webdav_path}/{path}"
        return f"{self.base_url}/{path}"

    def list_folder(self, path: str = "") -> list[dict]:
        """List files in a WebDAV folder."""
        url = self._get_webdav_url(path)
        headers = {'Depth': '1'}

        response = self.session.request('PROPFIND', url, headers=headers)
        response.raise_for_status()

        # Parse XML response
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)

        files = []
        ns = {'d': 'DAV:'}

        for response_elem in root.findall('.//d:response', ns):
            href_elem = response_elem.find('d:href', ns)
            if href_elem is None:
                continue

            href = href_elem.text
            # Extract relative path from href
            if self.webdav_path:
                prefix = f"{self.webdav_path}/"
                if href.startswith(prefix):
                    rel_path = href[len(prefix):]
                else:
                    continue
            else:
                rel_path = href.lstrip('/')

            # Skip the folder itself
            if not rel_path or rel_path == path:
                continue

            propstat = response_elem.find('.//d:propstat[d:status[contains(., "200")]]/d:prop', ns)
            if propstat is None:
                continue

            is_collection = propstat.find('d:resourcetype/d:collection', ns) is not None
            content_length = propstat.find('d:getcontentlength', ns)
            last_modified = propstat.find('d:getlastmodified', ns)
            etag = propstat.find('d:getetag', ns)

            file_info = {
                'path': rel_path,
                'is_dir': is_collection,
                'size': int(content_length.text) if content_length is not None else 0,
                'modified': last_modified.text if last_modified is not None else None,
                'etag': etag.text.strip('"') if etag is not None else None,
            }
            files.append(file_info)

        return files

    def download_file(self, rel_path: str, local_path: Path) -> bool:
        """Download a file from WebDAV."""
        url = self._get_webdav_url(rel_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self.session.get(url, stream=True) as response:
                response.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Failed to download {rel_path}: {e}")
            return False

    def get_file_hash(self, rel_path: str) -> str | None:
        """Get SHA256 hash of a remote file without downloading full content."""
        url = self._get_webdav_url(rel_path)
        try:
            # Try to get ETag first (often contains hash)
            response = self.session.head(url)
            response.raise_for_status()
            etag = response.headers.get('ETag', '').strip('"')
            if etag and len(etag) >= 32:  # Likely a hash
                return etag
        except Exception:
            pass
        return None


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


class NextcloudSyncer:
    """Syncs Nextcloud files to local directory with deduplication."""

    def __init__(
        self,
        client: NextcloudWebDAVClient,
        local_dir: Path,
        state_file: Path,
        allowed_extensions: set[str],
        sync_folders: list[str],
    ):
        self.client = client
        self.local_dir = local_dir
        self.state_file = state_file
        self.allowed_extensions = allowed_extensions
        self.sync_folders = sync_folders
        self.state = SyncState.load(state_file)
        self.stats = {'downloaded': 0, 'skipped': 0, 'errors': 0, 'parsed': 0}

    def _should_sync(self, rel_path: str) -> bool:
        """Check if file should be synced based on extension and folder."""
        path = Path(rel_path)
        if path.suffix.lower() not in self.allowed_extensions:
            return False

        if self.sync_folders:
            folder = path.parts[0] if path.parts else ""
            if folder not in self.sync_folders:
                return False

        return True

    def _is_file_changed(self, rel_path: str, remote_info: dict) -> bool:
        """Check if file has changed since last sync."""
        local_path = self.local_dir / rel_path
        if not local_path.exists():
            return True

        state = self.state.get_file_state(rel_path)
        if not state:
            return True

        # Check size and modified time
        if state.get('size') != remote_info.get('size'):
            return True
        if state.get('modified') != remote_info.get('modified'):
            return True

        # Verify local hash matches
        try:
            local_hash = compute_sha256(local_path)
            if state.get('hash') != local_hash:
                return True
        except Exception:
            return True

        return False

    def sync_folder(self, folder: str = "") -> list[dict]:
        """Sync a single folder recursively."""
        synced_files = []

        try:
            items = self.client.list_folder(folder)
        except Exception as e:
            logger.error(f"Failed to list folder {folder}: {e}")
            self.stats['errors'] += 1
            return synced_files

        for item in items:
            rel_path = item['path']

            if item['is_dir']:
                # Recurse into subdirectories
                synced_files.extend(self.sync_folder(rel_path))
            elif self._should_sync(rel_path):
                if self._is_file_changed(rel_path, item):
                    local_path = self.local_dir / rel_path
                    if self.client.download_file(rel_path, local_path):
                        file_hash = compute_sha256(local_path)
                        self.state.update_file_state(rel_path, {
                            'hash': file_hash,
                            'size': item['size'],
                            'modified': item['modified'],
                            'parsed_hash': None,
                            'last_synced': datetime.now().isoformat(),
                        })
                        synced_files.append({
                            'path': rel_path,
                            'local_path': str(local_path),
                            'hash': file_hash,
                            'action': 'downloaded',
                        })
                        self.stats['downloaded'] += 1
                        logger.info(f"Downloaded: {rel_path}")
                    else:
                        self.stats['errors'] += 1
                else:
                    self.stats['skipped'] += 1
                    logger.debug(f"Skipped (unchanged): {rel_path}")

        return synced_files

    def full_sync(self) -> dict:
        """Perform full sync of all configured folders."""
        logger.info("Starting full sync...")
        self.stats = {'downloaded': 0, 'skipped': 0, 'errors': 0, 'parsed': 0}
        all_synced = []

        for folder in self.sync_folders:
            logger.info(f"Syncing folder: {folder}")
            all_synced.extend(self.sync_folder(folder))

        # Clean up deleted files
        self._cleanup_deleted(all_synced)

        self.state.last_full_sync = datetime.now().isoformat()
        self.state.save(self.state_file)

        logger.info(f"Sync complete: {self.stats}")
        return {
            'stats': self.stats,
            'files': all_synced,
        }

    def _cleanup_deleted(self, current_files: list[dict]):
        """Remove local files that no longer exist in Nextcloud."""
        current_paths = {f['path'] for f in current_files}
        tracked_paths = set(self.state.files.keys())

        for deleted_path in tracked_paths - current_paths:
            if self._should_sync(deleted_path):
                local_path = self.local_dir / deleted_path
                parsed_path = Path(str(local_path).replace(str(self.local_dir), str(self.local_dir.parent / 'parsed_docs'))).with_suffix('.md')

                if local_path.exists():
                    local_path.unlink()
                    logger.info(f"Deleted local file: {deleted_path}")

                if parsed_path.exists():
                    parsed_path.unlink()
                    logger.info(f"Deleted parsed file: {parsed_path}")

                self.state.remove_file_state(deleted_path)

        self.state.save(self.state_file)


def main():
    parser = argparse.ArgumentParser(description='Nextcloud WebDAV Sync')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=300, help='Sync interval in seconds')
    parser.add_argument('--config', type=str, default='.env', help='Path to config file')
    parser.add_argument('--folders', type=str, help='Comma-separated folders to sync')
    parser.add_argument('--extensions', type=str, help='Comma-separated file extensions')
    parser.add_argument('--parse', action='store_true', help='Parse documents after sync')
    args = parser.parse_args()

    # Load config
    from dotenv import load_dotenv
    load_dotenv(args.config)

    nextcloud_url = os.getenv('NEXTCLOUD_URL')
    username = os.getenv('NEXTCLOUD_USERNAME')
    password = os.getenv('NEXTCLOUD_PASSWORD')
    webdav_path = os.getenv('NEXTCLOUD_WEBDAV_PATH', '')

    if not all([nextcloud_url, username, password]):
        logger.error("Missing Nextcloud credentials in config")
        sys.exit(1)

    sync_folders = (args.folders or os.getenv('SYNC_FOLDERS', 'Documents,Notes,Projects')).split(',')
    sync_folders = [f.strip() for f in sync_folders if f.strip()]
    allowed_extensions = set((args.extensions or os.getenv('SYNC_FILE_EXTENSIONS', '.md,.txt,.docx,.pdf')).split(','))

    local_dir = Path(os.getenv('PARSED_DOCS_PATH', './parsed_docs')).parent / 'synced_docs'
    state_file = Path(os.getenv('SYNC_STATE_FILE', './data/sync_state.json'))

    client = NextcloudWebDAVClient(nextcloud_url, username, password, webdav_path)
    syncer = NextcloudSyncer(client, local_dir, state_file, allowed_extensions, sync_folders)

    if args.once:
        result = syncer.full_sync()

        if args.parse and result['files']:
            logger.info("Parsing downloaded documents...")
            for file_info in result['files']:
                try:
                    parse_document(Path(file_info['local_path']), local_dir)
                    syncer.stats['parsed'] += 1
                except Exception as e:
                    logger.error(f"Failed to parse {file_info['path']}: {e}")

        print(json.dumps(result, indent=2))
    else:
        # Continuous sync mode
        import time
        logger.info(f"Starting continuous sync (interval: {args.interval}s)")
        while True:
            try:
                syncer.full_sync()
            except KeyboardInterrupt:
                logger.info("Sync stopped by user")
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")

            time.sleep(args.interval)


if __name__ == '__main__':
    main()
