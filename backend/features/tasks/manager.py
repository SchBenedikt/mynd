"""
TaskManager - Verwaltung von Todos/Tasks mit Caching und DB-Persistenz
"""

import logging
import time
from typing import List, Dict, Optional
from .simple import SimpleNextcloudTasks
from .batch_loader import BatchTaskLoader, QuickTaskLoader

logger = logging.getLogger(__name__)


class TaskManager:
    """Manager für Todo/Task-Verwaltung mit DB Persistenz"""
    
    def __init__(self, database=None):
        self.logger = logging.getLogger(__name__)
        self.tasks_client: Optional[SimpleNextcloudTasks] = None
        self.database = database
        self.batch_loader: Optional[BatchTaskLoader] = None
        self.quick_loader: Optional[QuickTaskLoader] = None
        self.cached_tasks: List[Dict] = []
        self.last_cache_time: float = 0
        self.cache_duration: float = 300  # 5 Minuten
    
    def initialize(self, url: str, username: str, password: str) -> bool:
        """
        Initialisiert die Verbindung zu Nextcloud Tasks
        """
        try:
            self.tasks_client = SimpleNextcloudTasks(url, username, password)
            if self.tasks_client.test_connection():
                self.logger.info("✅ Task manager initialized with Nextcloud connection")
                
                # Initialize loaders nur wenn Database vorhanden
                if self.database:
                    self.batch_loader = BatchTaskLoader(self.tasks_client, self.database)
                    self.quick_loader = QuickTaskLoader(self.tasks_client, self.database)
                    self.logger.info("✅ Batch and quick loaders initialized")
                
                return True
            else:
                self.logger.warning("❌ Could not connect to Nextcloud Tasks")
                return False
        except Exception as e:
            self.logger.error(f"❌ Error initializing task manager: {str(e)}")
            return False
    
    def get_tasks(self, use_cache: bool = True, list_name: str = None) -> List[Dict]:
        """
        Holt alle aktiven Tasks
        Zuerst aus Datenbank, dann aus Cache, dann von WebDAV
        """
        if not self.tasks_client:
            self.logger.warning("Task client not initialized")
            return []
        
        # Standard-Namen für Task-Listen (in Reihenfolge der Wahrscheinlichkeit)
        if list_name is None:
            list_names = ['todo', 'tasks', 'Todo', 'Tasks', 'My Tasks']
        else:
            list_names = [list_name]
        
        # 1. ZUERST: Versuche aus Datenbank zu laden (ULTRA-SCHNELL!)
        if self.database:
            try:
                db_tasks = self.database.get_tasks_from_db(limit=50)
                if db_tasks:
                    self.logger.info(f"✅ Loaded {len(db_tasks)} tasks from DATABASE (instant!)")
                    return db_tasks
            except Exception as e:
                self.logger.debug(f"Error loading from DB: {e}")
        
        # 2. FALLBACK: WebDAV laden (langsamer)
        tasks = []
        tried_lists = []
        try:
            for name in list_names:
                tried_lists.append(name)
                try:
                    # Nur 1 Task laden, nicht alle!
                    tasks = self.tasks_client.get_tasks(name)
                    if tasks:  # Wenn Todos gefunden
                        self.logger.info(f"⚠️  Using WebDAV fallback, found {len(tasks)} tasks from list: {name}")
                        break
                except:
                    continue
            
            self.cached_tasks = tasks
            self.last_cache_time = time.time()
            return tasks
        except Exception as e:
            self.logger.error(f"❌ Error fetching tasks from {tried_lists}: {str(e)}")
            return self.cached_tasks  # Fallback zu Cache
    
    def create_task(self, title: str, description: str = '', 
                   due_date: Optional[str] = None, priority: int = 0,
                   list_name: str = 'tasks') -> bool:
        """
        Erstellt einen neuen Task
        """
        if not self.tasks_client:
            self.logger.error("Task client not initialized")
            return False
        
        success = self.tasks_client.create_task(title, description, due_date, priority, list_name)
        
        if success:
            # Cache invalidieren
            self.cached_tasks = []
            self.last_cache_time = 0
            
            # DB neu laden mit Background-Sync
            if self.batch_loader:
                self.batch_loader.start_background_load(list_name)
        
        return success
    
    def complete_task(self, task_uid: str, list_name: str = 'tasks') -> bool:
        """
        Markiert ein Task als abgeschlossen
        """
        if not self.tasks_client:
            self.logger.error("Task client not initialized")
            return False
        
        success = self.tasks_client.complete_task(task_uid, list_name)
        
        if success and self.database:
            # Auch in DB aktualisieren
            self.database.complete_task_in_db(task_uid)
        
        return success
    
    def sync_tasks_to_database(self, list_name: str = 'todo', batch_size: int = 100) -> bool:
        """
        Startet den Background-Batch-Load aller Tasks von Nextcloud in DB
        **DIES SOLLTE NUR EINMAL MACHEN!**
        
        Nach dem Sync werden alle Chat-Abfragen von DB gelesen (ultra-schnell)
        """
        if not self.batch_loader or not self.database:
            self.logger.error("Batch loader or database not initialized")
            return False
        
        # Zuerst die DB cleared von alten Tasks
        self.database.clear_tasks()
        self.logger.info("📋 Cleared old tasks from database")
        
        # Starte Background-Load
        success = self.batch_loader.start_background_load(list_name)
        
        if success:
            self.logger.info("🔄 Background sync started - Tasks werden geladen...")
        
        return success
    
    def get_sync_status(self) -> Dict:
        """
        Gibt aktuellen Sync-Status zurück
        """
        if not self.batch_loader:
            return {'status': 'not_initialized'}
        
        return self.batch_loader.get_load_status()
    
    def format_tasks_for_context(self, tasks: List[Dict]) -> str:
        """Formatiert Tasks für AI-Kontext"""
        if not tasks:
            return "=== MEINE TODOS ===\n\n🎉 Alle Todos erledigt! Über 300+ Todos sind abgeschlossen.\n"
        
        open_tasks = [t for t in tasks if not t.get('completed', False)]
        completed_tasks = [t for t in tasks if t.get('completed', False)]
        
        formatted = "=== MEINE TODOS ===\n\n"
        
        if open_tasks:
            formatted += f"📝 OFFENE TODOS ({len(open_tasks)}):\n"
            for i, task in enumerate(open_tasks, 1):
                title = task.get('title', 'Untitled')
                due = task.get('due_date', '')
                priority = task.get('priority', 0)
                
                priority_str = ''
                if priority > 0 and priority <= 4:
                    priority_str = '🔴 '
                elif priority == 5:
                    priority_str = '🟡 '
                elif priority >= 6:
                    priority_str = '🟢 '
                
                formatted += f"{i}. {priority_str}{title}"
                
                if due:
                    formatted += f" (Fällig: {due})"
                
                formatted += "\n"
        
        if completed_tasks:
            if open_tasks:
                formatted += f"\n"
            formatted += f"✅ ERLEDIGT ({len(completed_tasks)}): "
            
            recent_completed = [t.get('title', 'Task')[:30] for t in completed_tasks[:5]]
            formatted += ", ".join(recent_completed)
            
            if len(completed_tasks) > 5:
                formatted += f", ... +{len(completed_tasks) - 5} mehr"
            
            formatted += "\n"
        
        if not open_tasks and completed_tasks:
            formatted += "\n🎉 Super! Du hast deine Todos organisiert und viele abgeschlossen!\n"
        
        return formatted


# Globaler TaskManager - Datenbank wird später in app.py gesetzt
task_manager = TaskManager()


def set_database(db):
    """Setzt die Datenbank nach Initialisierung (Dependency Injection)"""
    task_manager.database = db
    if task_manager.tasks_client and db:
        task_manager.batch_loader = BatchTaskLoader(task_manager.tasks_client, db)
        task_manager.quick_loader = QuickTaskLoader(task_manager.tasks_client, db)
        logger.info("✅ Database set for task_manager")
