#!/usr/bin/env python3
"""
Orchestrator: Sync → Parse → Ingest pipeline controller.
Manages the full flow from Nextcloud to LightRAG.
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates sync, parse, and ingest into a continuous pipeline."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.running = True
        
        # Determine project root
        self.project_root = config_path.parent
        
        # Paths
        self.scripts_dir = self.project_root / 'scripts'
        self.synced_dir = self.project_root / 'data' / 'synced_docs'
        self.parsed_dir = self.project_root / 'parsed_docs'
        self.data_dir = self.project_root / 'data'
        
        # Script paths
        self.sync_script = self.scripts_dir / 'sync_nextcloud.py'
        self.parse_script = self.scripts_dir / 'parse_docs.py'
        self.ingest_script = self.scripts_dir / 'ingest.py'
        
        # Config
        self.sync_interval = int(os.getenv('SYNC_INTERVAL_SECONDS', '300'))
        self.ingestion_interval = int(os.getenv('INGESTION_INTERVAL_SECONDS', '60'))
        
        # Statistics
        self.stats = {
            'syncs': 0,
            'parsed': 0,
            'ingested': 0,
            'errors': 0,
            'last_sync': None,
            'last_ingest': None,
        }
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def ensure_directories(self):
        """Create required directories."""
        for d in [self.synced_dir, self.parsed_dir, self.data_dir]:
            d.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directories: synced={self.synced_dir}, parsed={self.parsed_dir}, data={self.data_dir}")
    
    def run_sync(self) -> Dict:
        """Run the Nextcloud sync."""
        logger.info("Starting Nextcloud sync...")
        
        env = os.environ.copy()
        env['PARSED_DOCS_PATH'] = str(self.parsed_dir)
        env['SYNC_STATE_FILE'] = str(self.data_dir / 'sync_state.json')
        
        try:
            result = subprocess.run(
                [sys.executable, str(self.sync_script), '--once', '--parse'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    self.stats['syncs'] += 1
                    self.stats['last_sync'] = datetime.now().isoformat()
                    logger.info(f"Sync completed: {data.get('stats', {})}")
                    return data
                except json.JSONDecodeError:
                    logger.warning(f"Sync output not JSON: {result.stdout[:200]}")
                    return {'stats': {'downloaded': 0, 'skipped': 0, 'errors': 0}}
            else:
                logger.error(f"Sync failed: {result.stderr[:500]}")
                self.stats['errors'] += 1
                return {'stats': {'downloaded': 0, 'skipped': 0, 'errors': 1}}
                
        except subprocess.TimeoutExpired:
            logger.error("Sync timed out after 10 minutes")
            self.stats['errors'] += 1
            return {'stats': {'downloaded': 0, 'skipped': 0, 'errors': 1}}
        except Exception as e:
            logger.error(f"Sync error: {e}")
            self.stats['errors'] += 1
            return {'stats': {'downloaded': 0, 'skipped': 0, 'errors': 1}}
    
    def run_ingestion(self) -> Dict:
        """Run the LightRAG ingestion."""
        logger.info("Starting LightRAG ingestion...")
        
        env = os.environ.copy()
        env['LIGHTRAG_WORKING_DIR'] = str(self.data_dir / 'lightrag')
        
        try:
            result = subprocess.run(
                [sys.executable, str(self.ingest_script), 'ingest',
                 str(self.parsed_dir),
                 '--state', str(self.data_dir / 'ingestion_state.json'),
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    self.stats['ingested'] += data.get('ingested', 0)
                    self.stats['last_ingest'] = datetime.now().isoformat()
                    logger.info(f"Ingestion completed: {data}")
                    return data
                except json.JSONDecodeError:
                    logger.warning(f"Ingestion output not JSON: {result.stdout[:200]}")
                    return {'ingested': 0, 'skipped': 0, 'errors': 0}
            else:
                logger.error(f"Ingestion failed: {result.stderr[:500]}")
                self.stats['errors'] += 1
                return {'ingested': 0, 'skipped': 0, 'errors': 1}
                
        except subprocess.TimeoutExpired:
            logger.error("Ingestion timed out after 10 minutes")
            self.stats['errors'] += 1
            return {'ingested': 0, 'skipped': 0, 'errors': 1}
        except Exception as e:
            logger.error(f"Ingestion error: {e}")
            self.stats['errors'] += 1
            return {'ingested': 0, 'skipped': 0, 'errors': 1}
    
    def run_single_pass(self) -> Dict:
        """Run one full pass: sync → parse → ingest."""
        pass_stats = {'sync': {}, 'ingestion': {}}
        
        # Step 1: Sync from Nextcloud (includes parsing)
        sync_result = self.run_sync()
        pass_stats['sync'] = sync_result.get('stats', {})
        
        # Step 2: Ingest to LightRAG
        ingest_result = self.run_ingestion()
        pass_stats['ingestion'] = ingest_result
        
        # Cleanup orphaned
        try:
            subprocess.run(
                [sys.executable, str(self.ingest_script), 'cleanup',
                 str(self.parsed_dir),
                 '--state', str(self.data_dir / 'ingestion_state.json'),
                ],
                cwd=self.project_root,
                capture_output=True,
                timeout=120,
            )
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        return pass_stats
    
    def run_continuous(self):
        """Run the full pipeline continuously."""
        logger.info("Starting continuous pipeline...")
        self.ensure_directories()
        
        # Initial full pass
        self.run_single_pass()
        
        # Continuous loop
        while self.running:
            logger.info(f"Waiting {self.sync_interval}s until next pass...")
            
            # Wait in small increments to allow graceful shutdown
            for _ in range(self.sync_interval):
                if not self.running:
                    break
                time.sleep(1)
            
            if not self.running:
                break
            
            try:
                self.run_single_pass()
            except Exception as e:
                logger.error(f"Pipeline pass failed: {e}")
                self.stats['errors'] += 1
        
        logger.info("Pipeline stopped.")
        logger.info(f"Final statistics: {json.dumps(self.stats, indent=2)}")
    
    def view_stats(self):
        """Display current statistics."""
        print(json.dumps(self.stats, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Nextcloud LightRAG Pipeline Orchestrator')
    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')
    
    subparsers.add_parser('start', help='Start continuous pipeline')
    subparsers.add_parser('sync', help='Run single sync+parse pass')
    subparsers.add_parser('ingest', help='Run single ingestion pass')
    subparsers.add_parser('full', help='Run single full pass (sync+parse+ingest)')
    subparsers.add_parser('stats', help='View pipeline statistics')
    subparsers.add_parser('status', help='Check service status')
    
    args = parser.parse_args()
    
    config_path = Path(__file__).parent.parent / '.env'
    orchestrator = Orchestrator(config_path)
    
    if args.command == 'start':
        orchestrator.run_continuous()
    elif args.command == 'sync':
        result = orchestrator.run_sync()
        print(json.dumps(result, indent=2))
    elif args.command == 'ingest':
        result = orchestrator.run_ingestion()
        print(json.dumps(result, indent=2))
    elif args.command == 'full':
        result = orchestrator.run_single_pass()
        print(json.dumps(result, indent=2))
    elif args.command == 'stats':
        orchestrator.view_stats()
    elif args.command == 'status':
        import requests
        services = {
            'Ollama': 'http://localhost:11434/api/tags',
            'Qdrant': 'http://localhost:6333/health',
            'LightRAG': 'http://localhost:9621/health',
            'Open WebUI': 'http://localhost:3000/health',
        }
        statuses = {}
        for name, url in services.items():
            try:
                r = requests.get(url, timeout=3)
                statuses[name] = '✅ UP' if r.status_code == 200 else f'⚠️  {r.status_code}'
            except Exception as e:
                statuses[name] = f'❌ DOWN ({type(e).__name__})'
        
        print(f"\nNextcloud LightRAG Status ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print("=" * 50)
        for name, status in statuses.items():
            print(f"  {name:15s}  {status}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()