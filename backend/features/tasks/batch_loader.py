"""
BatchTaskLoader - Lädt Nextcloud Tasks in Batches/Chunks in die SQLite Datenbank
macht dann Chat ultra-schnell, da nur von DB gelesen wird (nicht WebDAV)
"""

import logging
import time
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)


class BatchTaskLoader:
    """Lädt Tasks von Nextcloud in Batches in die Datenbank"""
    
    def __init__(self, tasks_client, database, batch_size: int = 100):
        """
        tasks_client: SimpleNextcloudTasks instance
        database: KnowledgeDatabase instance
        batch_size: Wie viele Tasks pro Batch (default: 100)
        """
        self.tasks_client = tasks_client
        self.database = database
        self.batch_size = batch_size
        self.is_loading = False
        self.load_thread: Optional[threading.Thread] = None
        self.logger = logger
    
    def start_background_load(self, list_name: str = 'auto') -> bool:
        """Startet Background-Thread zum Laden von Tasks"""
        if self.is_loading:
            self.logger.warning("Load already in progress")
            return False
        
        self.is_loading = True
        self.load_thread = threading.Thread(
            target=self._background_load,
            args=(list_name,),
            daemon=True
        )
        self.load_thread.start()
        self.logger.info(f"🔄 Background task loading started for list '{list_name}'")
        
        return True
    
    def _background_load(self, list_name: str):
        """Background-Prozess zum Laden von Tasks"""
        try:
            start_time = time.time()
            self.logger.info(f"⏳ Loading tasks from Nextcloud in batches...")

            target_lists: List[str] = []
            if list_name and list_name != 'auto':
                target_lists = [list_name]
            else:
                try:
                    target_lists = self.tasks_client.get_task_lists()
                except Exception as e:
                    self.logger.warning(f"Could not discover task lists for auto sync: {e}")

            if not target_lists:
                target_lists = ['todo', 'tasks']

            # Legacy-Schutz: Falls explizit angeforderte Liste nicht existiert (404),
            # wechsle automatisch auf Discovery aller verfügbaren Listen.
            if len(target_lists) == 1 and list_name and list_name != 'auto':
                probe_paths = self._get_all_task_paths(target_lists[0])
                if not probe_paths:
                    try:
                        discovered_lists = self.tasks_client.get_task_lists()
                    except Exception as e:
                        self.logger.warning(f"Fallback discovery failed after missing list '{target_lists[0]}': {e}")
                        discovered_lists = []

                    if discovered_lists:
                        self.logger.warning(
                            f"List '{target_lists[0]}' not found/empty, falling back to discovered lists: {discovered_lists}"
                        )
                        target_lists = discovered_lists

            self.logger.info(f"📚 Syncing task lists: {target_lists}")

            total_loaded = 0
            seen_paths = set()
            for source_list in target_lists:
                ics_paths = self._get_all_task_paths(source_list)
                if not ics_paths:
                    self.logger.warning(f"No tasks found in '{source_list}'")
                    continue

                unique_paths = [p for p in ics_paths if p not in seen_paths]
                seen_paths.update(unique_paths)

                if not unique_paths:
                    continue

                self.logger.info(
                    f"📦 Found {len(unique_paths)} tasks in '{source_list}', loading in batches of {self.batch_size}..."
                )

                for batch_num, batch_paths in enumerate(self._chunk_list(unique_paths, self.batch_size)):
                    batch_start = time.time()
                    batch_tasks = self._load_task_batch(batch_paths)

                    if batch_tasks:
                        loaded_count = self.database.add_tasks_batch(batch_tasks, source_list)
                        total_loaded += loaded_count

                        batch_time = time.time() - batch_start
                        self.logger.info(
                            f"✅ [{source_list}] Batch {batch_num + 1}: "
                            f"Loaded {loaded_count}/{len(batch_paths)} tasks in {batch_time:.2f}s"
                        )

                    # Kurze Pause zwischen Batches um WebDAV nicht zu überlasten
                    time.sleep(0.2)
            
            elapsed = time.time() - start_time
            self.logger.info(
                f"🎉 DONE! Loaded {total_loaded} tasks in {elapsed:.2f}s "
                f"({elapsed/total_loaded:.2f}s pro Task durchschnittlich)"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error in background load: {str(e)}", exc_info=True)
        finally:
            self.is_loading = False
    
    def _get_all_task_paths(self, list_name: str) -> List[str]:
        """Holt alle ICS-Pfade vom Nextcloud (schnell, nur PROPFIND)"""
        try:
            import requests
            import xml.etree.ElementTree as ET
            
            url = f"{self.tasks_client.base_url}/calendars/{self.tasks_client.username}/{list_name}/"
            
            response = requests.request(
                'PROPFIND',
                url,
                auth=self.tasks_client.session.auth,
                headers={'Depth': '1'},
                timeout=10
            )
            
            if response.status_code not in [207, 200]:
                self.logger.warning(f"PROPFIND failed for '{list_name}': {response.status_code}")
                return []
            
            # Parse XML
            root = ET.fromstring(response.content)
            namespaces = {'d': 'DAV:'}
            
            ics_paths = []
            for response_elem in root.findall('.//d:response', namespaces):
                href_elem = response_elem.find('d:href', namespaces)
                if href_elem is not None and href_elem.text and href_elem.text.endswith('.ics'):
                    ics_paths.append(href_elem.text)
            
            return ics_paths
            
        except Exception as e:
            self.logger.error(f"Error getting task paths: {str(e)}")
            return []
    
    def _load_task_batch(self, ics_paths: List[str]) -> List[Dict]:
        """Lädt ein Batch von Tasks (mit 2 parallelen Workers)"""
        tasks = []
        
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(self.tasks_client._get_task_quick, path)
                    for path in ics_paths
                ]
                
                for future in futures:
                    try:
                        task = future.result(timeout=2)
                        if task:
                            tasks.append(task)
                    except Exception as e:
                        self.logger.debug(f"Task load error: {e}")
        
        except Exception as e:
            self.logger.error(f"Batch load error: {str(e)}")
        
        return tasks
    
    def _chunk_list(self, lst: List, chunk_size: int) -> List[List]:
        """Teilt Liste in Chunks"""
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]
    
    def get_load_status(self) -> Dict:
        """Gibt aktuellen Loading-Status zurück"""
        task_stats = self.database.get_task_stats()
        
        return {
            'is_loading': self.is_loading,
            'stats': task_stats,
            'total': task_stats.get('total', 0),
            'open': task_stats.get('open', 0),
            'completed': task_stats.get('completed', 0)
        }


class QuickTaskLoader:
    """Schnelle Loader-Variante für nur wenige Tasks (z.B. für Chat)"""
    
    def __init__(self, tasks_client, database):
        self.tasks_client = tasks_client
        self.database = database
        self.logger = logger
    
    def load_open_tasks_only(self, list_name: str = 'auto', max_tasks: int = 5) -> List[Dict]:
        """Lädt NUR wenige offene Tasks (schnell, für Chat)"""
        try:
            target_lists = [list_name] if list_name and list_name != 'auto' else []
            if not target_lists:
                try:
                    target_lists = self.tasks_client.get_task_lists()
                except Exception as e:
                    self.logger.warning(f"Could not discover task lists for quick load: {e}")
                    target_lists = []

            if not target_lists:
                target_lists = ['todo', 'tasks']

            seen_paths = set()
            ics_paths: List[str] = []
            for source_list in target_lists:
                for path in self._get_first_n_paths(source_list, max_tasks * 2):
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    ics_paths.append(path)
                    if len(ics_paths) >= max_tasks * 2:
                        break
                if len(ics_paths) >= max_tasks * 2:
                    break

            if not ics_paths:
                self.logger.warning(f"No tasks found in any list ({target_lists})")
                return []
            
            # Schnell 2-3 Tasks laden
            tasks = []
            for path in ics_paths[:max_tasks]:
                task = self.tasks_client._get_task_quick(path)
                if task and not task.get('completed'):
                    tasks.append(task)
                    if len(tasks) >= max_tasks:
                        break
            
            return tasks
            
        except Exception as e:
            self.logger.error(f"Error loading quick tasks: {str(e)}")
            return []
    
    def _get_first_n_paths(self, list_name: str, n: int) -> List[str]:
        """Holt nur erste N Task-Pfade (sehr schnell)"""
        try:
            import requests
            import xml.etree.ElementTree as ET
            
            url = f"{self.tasks_client.base_url}/calendars/{self.tasks_client.username}/{list_name}/"
            
            response = requests.request(
                'PROPFIND',
                url,
                auth=self.tasks_client.session.auth,
                headers={'Depth': '1'},
                timeout=5
            )
            
            if response.status_code not in [207, 200]:
                return []
            
            root = ET.fromstring(response.content)
            namespaces = {'d': 'DAV:'}
            
            ics_paths = []
            for response_elem in root.findall('.//d:response', namespaces):
                href_elem = response_elem.find('d:href', namespaces)
                if href_elem is not None and href_elem.text and href_elem.text.endswith('.ics'):
                    ics_paths.append(href_elem.text)
                    if len(ics_paths) >= n:
                        break
            
            return ics_paths
            
        except Exception as e:
            self.logger.error(f"Error getting task paths: {str(e)}")
            return []
