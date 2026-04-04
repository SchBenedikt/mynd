import os
import json
import sys
import html
import requests
import numpy as np
import threading
from flask import Flask, request, jsonify, redirect, url_for, session, Response
from dotenv import load_dotenv
import re
import logging
from datetime import datetime, timedelta, date
import time
import secrets
from urllib.parse import urljoin
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import package side effects to register all API clients in APIRegistry.
import backend.features.integration  # noqa: F401

from backend.features.documents.parser import DocumentParser
from backend.features.integration.nextcloud_client import NextcloudClient
from backend.features.integration.activity_client import NextcloudActivityClient
from backend.features.integration.notifications_client import NextcloudNotificationsClient
from backend.features.integration.search_client import NextcloudSearchClient
from backend.features.integration.auth_manager import get_auth_manager, AuthManager
from backend.features.integration.oauth2_nextcloud import OAuth2NextcloudProvider
from backend.features.integration.auth_nextcloud_direct import DirectNextcloudProvider
from backend.features.integration.api_registry import get_api_registry
from backend.features.integration.carddav_client import NextcloudCardDAVClient
from backend.features.integration.homeassistant_client import HomeAssistantClient
from backend.features.integration.uptimekuma_client import UptimeKumaClient
from backend.features.integration.email_client import EmailClient
from backend.features.knowledge.indexing import indexing_manager, IndexingProgress
# from backend.features.knowledge.engine import SemanticSearchEngine
# Temporär deaktiviert wegen faiss Problemen
class SemanticSearchEngine:
    def __init__(self):
        pass
from backend.features.knowledge.search import SimpleSearchEngine
from backend.features.training.manager import TrainingManager
from backend.features.knowledge.metadata import MetadataExtractor
# from backend.features.calendar.manager import create_calendar_manager
# Temporär deaktiviert wegen caldav Problemen
def create_calendar_manager():
    return None
from backend.features.calendar.simple import create_simple_calendar_manager
from backend.features.tasks.manager import task_manager, set_database
from backend.core.context.gatherers import (
    gather_photo_context, gather_file_context, gather_weather_context,
    gather_security_context, gather_activity_context, gather_calendar_context,
    gather_todo_context, gather_nextcloud_search_context, gather_email_context,
    _build_email_query_profile,
    combine_contexts,
    build_system_message as build_agent_system_message
)
from backend.core.autonomous.agent import AutonomousAgent
import xml.etree.ElementTree as ET

load_dotenv()

NEXTCLOUD_LOGINFLOW_USER_AGENT = 'MYND Assistant'

# Define base directories BEFORE Flask app creation
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONFIG_DIR = os.path.join(BASE_DIR, 'backend', 'config')
DATA_DIR = os.path.join(BASE_DIR, 'data')
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
TEMPLATES_DIR = os.path.join(BACKEND_DIR, 'templates')
DB_PATH = os.path.join(BASE_DIR, 'knowledge_base.db')
BRIEFING_STORE_FILE = os.path.join(DATA_DIR, 'assistant_briefings.json')
BRIEFING_MORNING_HOUR = int(os.getenv('BRIEFING_MORNING_HOUR', '7'))
BRIEFING_DAILY_ENABLED_DEFAULT = os.getenv('BRIEFING_DAILY_ENABLED', 'true').lower() in ('true', '1', 'yes')
BRIEFING_WEEKLY_ENABLED_DEFAULT = os.getenv('BRIEFING_WEEKLY_ENABLED', 'true').lower() in ('true', '1', 'yes')

# Setup directories
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Create Flask app with correct template folder
app = Flask(__name__, template_folder=TEMPLATES_DIR)

# Konfiguriere Session für OAuth2 State Management
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_briefing_lock = threading.Lock()
_briefing_scheduler_started = False


def _load_briefing_store() -> Dict[str, Any]:
    """Load persisted briefing items from disk."""
    try:
        if not os.path.exists(BRIEFING_STORE_FILE):
            return {'items': {}}
        with open(BRIEFING_STORE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {'items': {}}
        items = data.get('items')
        if not isinstance(items, dict):
            data['items'] = {}
        return data
    except Exception as exc:
        logger.warning('Could not load briefing store: %s', exc)
        return {'items': {}}


def _save_briefing_store(store: Dict[str, Any]) -> None:
    """Persist briefing items to disk."""
    try:
        os.makedirs(os.path.dirname(BRIEFING_STORE_FILE), exist_ok=True)
        with open(BRIEFING_STORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning('Could not save briefing store: %s', exc)


def _get_briefing_settings() -> Dict[str, Any]:
    """Load briefing settings from ai_config with env-based defaults."""
    settings = {
        'daily_enabled': BRIEFING_DAILY_ENABLED_DEFAULT,
        'weekly_enabled': BRIEFING_WEEKLY_ENABLED_DEFAULT,
        'morning_hour': int(BRIEFING_MORNING_HOUR),
    }

    try:
        if os.path.exists(AI_CONFIG_FILE):
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            settings['daily_enabled'] = bool(cfg.get('briefing_daily_enabled', settings['daily_enabled']))
            settings['weekly_enabled'] = bool(cfg.get('briefing_weekly_enabled', settings['weekly_enabled']))
            settings['morning_hour'] = int(cfg.get('briefing_morning_hour', settings['morning_hour']))
    except Exception as exc:
        logger.debug('Could not load briefing settings from config: %s', exc)

    settings['morning_hour'] = max(0, min(23, int(settings['morning_hour'])))
    return settings


def _calendar_events_for_today(limit: int = 8) -> List[Dict[str, Any]]:
    """Fetch today's calendar events in a robust way."""
    if not simple_calendar_manager:
        refresh_simple_calendar_manager()
    if not simple_calendar_manager:
        return []

    try:
        if hasattr(simple_calendar_manager, 'get_events_today'):
            events = simple_calendar_manager.get_events_today() or []
        else:
            events = []
        return [event for event in events if isinstance(event, dict)][:limit]
    except Exception as exc:
        logger.debug('Could not load today events for briefing: %s', exc)
        return []


def _calendar_events_for_week(limit: int = 12) -> List[Dict[str, Any]]:
    """Fetch current week calendar events in a robust way."""
    if not simple_calendar_manager:
        refresh_simple_calendar_manager()
    if not simple_calendar_manager:
        return []

    try:
        if hasattr(simple_calendar_manager, 'get_events_this_week'):
            events = simple_calendar_manager.get_events_this_week() or []
        else:
            events = []
        return [event for event in events if isinstance(event, dict)][:limit]
    except Exception as exc:
        logger.debug('Could not load week events for briefing: %s', exc)
        return []


def _build_daily_briefing() -> Dict[str, Any]:
    """Build the daily morning briefing payload."""
    today = date.today()
    weather = get_local_weather_status()
    security = get_local_security_status()
    todo_data = get_todo_data('heute')

    tasks = todo_data.get('tasks', []) or []
    overdue = 0
    due_today = 0
    for task in tasks:
        due = _parse_task_due_date(task.get('due_date'))
        if not due:
            continue
        if due < today:
            overdue += 1
        elif due == today:
            due_today += 1

    calendar_events = _calendar_events_for_today(limit=6)

    email_results = []
    try:
        email_client = get_email_client()
        if email_client:
            email_results = email_client.fetch_emails(
                limit=5,
                folder_focus='inbox',
                since=today,
                until=today,
                unread=None,
            ) or []
    except Exception as exc:
        logger.debug('Could not load emails for daily briefing: %s', exc)

    lines = [
        f"Guten Morgen. Hier ist dein Briefing für {today.strftime('%d.%m.%Y')}:",
        "",
        f"• Wetter: {weather.get('summary') or 'Nicht verfügbar.'}",
        f"• Sicherheitslage: {security.get('headline') or 'Keine Daten.'}",
        f"• Aufgaben: {len(tasks)} offen ({overdue} überfällig, {due_today} heute fällig).",
        f"• Termine heute: {len(calendar_events)}",
        f"• Neue E-Mails heute: {len(email_results)}",
        "",
    ]

    if calendar_events:
        lines.append("Top-Termine heute:")
        for idx, event in enumerate(calendar_events[:3], 1):
            title = str(event.get('summary') or event.get('title') or 'Termin').strip()
            start = str(event.get('start') or '').strip()
            lines.append(f"{idx}. {title}" + (f" ({start})" if start else ""))
        lines.append("")

    if email_results:
        lines.append("Wichtige neue Mails:")
        for idx, mail in enumerate(email_results[:3], 1):
            subject = str(mail.get('subject') or '(kein Betreff)').strip()
            sender = str(mail.get('sender') or '').strip()
            lines.append(f"{idx}. {subject}" + (f" — {sender}" if sender else ""))

    return {
        'kind': 'daily',
        'title': f"Tagesbriefing • {today.strftime('%d.%m.%Y')}",
        'content': '\n'.join(lines).strip(),
        'stats': {
            'tasks_open': len(tasks),
            'tasks_overdue': overdue,
            'tasks_today': due_today,
            'events_today': len(calendar_events),
            'emails_today': len(email_results),
            'warnings': int(security.get('nina_warning_count') or 0),
        }
    }


def _build_weekly_briefing() -> Dict[str, Any]:
    """Build the Monday weekly kickoff briefing payload."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_no = today.isocalendar()[1]

    week_events = _calendar_events_for_week(limit=10)
    todo_data = get_todo_data('diese woche')
    tasks = todo_data.get('tasks', []) or []

    due_this_week = 0
    overdue = 0
    for task in tasks:
        due = _parse_task_due_date(task.get('due_date'))
        if not due:
            continue
        if due < today:
            overdue += 1
        if week_start <= due <= week_end:
            due_this_week += 1

    lines = [
        f"Wochenstart-Briefing (KW {week_no}) für {week_start.strftime('%d.%m.')} bis {week_end.strftime('%d.%m.%Y')}.",
        "",
        f"• Termine diese Woche: {len(week_events)}",
        f"• Aufgaben mit Fälligkeit diese Woche: {due_this_week}",
        f"• Überfällige Aufgaben: {overdue}",
        "",
    ]

    if week_events:
        lines.append("Wichtige Termine:")
        for idx, event in enumerate(week_events[:5], 1):
            title = str(event.get('summary') or event.get('title') or 'Termin').strip()
            start = str(event.get('start') or '').strip()
            lines.append(f"{idx}. {title}" + (f" ({start})" if start else ""))

    return {
        'kind': 'weekly',
        'title': f"Wochenstart • KW {week_no}",
        'content': '\n'.join(lines).strip(),
        'stats': {
            'events_week': len(week_events),
            'tasks_due_week': due_this_week,
            'tasks_overdue': overdue,
            'week_number': week_no,
        }
    }


def _get_briefing_storage_key(kind: str) -> str:
    today = date.today()
    if kind == 'weekly':
        week = today.isocalendar()[1]
        return f"weekly:{today.year}-W{week:02d}"
    return f"daily:{today.isoformat()}"


def generate_proactive_briefing(kind: str = 'daily', force: bool = False) -> Dict[str, Any]:
    """Generate (or reuse) a proactive briefing payload for daily or weekly cadence."""
    normalized_kind = 'weekly' if str(kind).lower() == 'weekly' else 'daily'
    key = _get_briefing_storage_key(normalized_kind)

    with _briefing_lock:
        store = _load_briefing_store()
        items = store.setdefault('items', {})
        existing = items.get(key)
        if existing and not force:
            return existing

        built = _build_weekly_briefing() if normalized_kind == 'weekly' else _build_daily_briefing()
        item = {
            'key': key,
            'kind': normalized_kind,
            'title': built.get('title', ''),
            'content': built.get('content', ''),
            'stats': built.get('stats', {}),
            'generated_at': int(time.time()),
        }

        items[key] = item
        _save_briefing_store(store)
        return item


def _briefing_scheduler_loop() -> None:
    """Background loop generating morning and Monday briefings automatically."""
    logger.info('⏰ Proactive briefing scheduler started (daily + weekly)')
    while True:
        try:
            now = datetime.now()
            briefing_settings = _get_briefing_settings()
            if briefing_settings.get('daily_enabled') and now.hour >= int(briefing_settings.get('morning_hour', BRIEFING_MORNING_HOUR)):
                generate_proactive_briefing('daily', force=False)
                if briefing_settings.get('weekly_enabled') and now.weekday() == 0:
                    generate_proactive_briefing('weekly', force=False)
        except Exception as exc:
            logger.warning('Briefing scheduler loop error: %s', exc)
        time.sleep(60)


def start_briefing_scheduler() -> None:
    """Start the proactive briefing scheduler once per process."""
    global _briefing_scheduler_started
    if _briefing_scheduler_started:
        return
    _briefing_scheduler_started = True
    thread = threading.Thread(target=_briefing_scheduler_loop, daemon=True)
    thread.start()


@app.route('/api/assistant/briefing/current', methods=['GET'])
def get_current_proactive_briefing():
    """Return the current daily briefing and Monday weekly briefing."""
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        include_weekly = request.args.get('include_weekly', 'true').lower() != 'false'

        briefing_settings = _get_briefing_settings()
        items = []
        if briefing_settings.get('daily_enabled'):
            items.append(generate_proactive_briefing('daily', force=force))
        if include_weekly and briefing_settings.get('weekly_enabled') and date.today().weekday() == 0:
            items.append(generate_proactive_briefing('weekly', force=force))

        return jsonify({
            'success': True,
            'items': items,
            'count': len(items)
        })
    except Exception as exc:
        logger.error('Failed to build proactive briefing: %s', exc)
        return jsonify({'success': False, 'error': 'Briefing konnte nicht geladen werden.'}), 500

AI_CONFIG_FILE = os.path.join(CONFIG_DIR, "ai_config.json")
CALENDAR_CONFIG_FILE = os.path.join(CONFIG_DIR, "calendar_config.json")


def load_calendar_config() -> Dict:
    """Lädt Kalender-Konfiguration (z.B. Standard-Kalender) aus Datei."""
    config = {
        'default_calendar_name': ''
    }

    if os.path.exists(CALENDAR_CONFIG_FILE):
        try:
            with open(CALENDAR_CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)

            config['default_calendar_name'] = str(file_config.get('default_calendar_name', '')).strip()
        except Exception as e:
            logger.warning(f"Konnte Kalender-Konfiguration nicht laden: {str(e)}")

    return config


def save_calendar_config(default_calendar_name: str) -> None:
    """Speichert Kalender-Konfiguration persistent in einer lokalen JSON-Datei."""
    config = {
        'default_calendar_name': str(default_calendar_name or '').strip()
    }

    with open(CALENDAR_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

class KnowledgeBase:
    def __init__(self, knowledge_file=None):
        if knowledge_file is None:
            knowledge_file = os.path.join(DATA_DIR, "user_knowledge.txt")
        self.knowledge_file = knowledge_file
        self.knowledge_chunks = []
        self.document_sources = []
        self.parser = DocumentParser()
        self.search_engine = None
        self.db = None
        self._initialize_semantic_search()
        
    def _initialize_semantic_search(self):
        """Initialize search engine (start with simple to avoid segfaults)"""
        try:
            # Start with simple search first
            self.search_engine = SimpleSearchEngine(DB_PATH)
            self.db = self.search_engine.db
            logger.info("Simple search engine initialized")
        except Exception as e:
            logger.error(f"Simple search failed: {str(e)}")
            self.search_engine = None
            self.db = None
    
    def load_knowledge(self):
        """Lädt und verarbeitet die Wissensdatei"""
        if not os.path.exists(self.knowledge_file):
            # Create empty knowledge file if it doesn't exist
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                f.write("")
            
        with open(self.knowledge_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Text in Chunks aufteilen
        chunks = self.split_text(content)
        
        # Store in database if available
        if self.db:
            try:
                doc_id = self.db.add_document(
                    name=os.path.basename(self.knowledge_file),
                    path=self.knowledge_file,
                    file_type='.txt',
                    metadata={'source': 'user_knowledge'}
                )
                chunk_ids = self.db.add_chunks(doc_id, chunks)
                
                # Update search engine
                chunks_data = []
                for i, chunk_id in enumerate(chunk_ids):
                    chunk_info = self.db.get_chunk_by_id(chunk_id)
                    if chunk_info:
                        chunks_data.append(chunk_info)
                
                if chunks_data and self.search_engine:
                    self.search_engine.add_chunks_to_index(chunks_data)
                    self.search_engine._save_index()
                
                logger.info(f"Loaded {len(chunks)} chunks into database")
            except Exception as e:
                logger.error(f"Database loading error: {str(e)}")
                # Fallback to memory
                self.knowledge_chunks = chunks
        else:
            self.knowledge_chunks = chunks
            
        self.document_sources = [{"file": self.knowledge_file, "type": "text"}]
    
    def load_from_nextcloud(self, nextcloud_url, username, password, remote_path="/"):
        """Lädt Dokumente von Nextcloud und verarbeitet sie"""
        try:
            # Nextcloud Client initialisieren
            nc_client = NextcloudClient(nextcloud_url, username, password)
            
            if not nc_client.test_connection():
                raise Exception("Nextcloud Verbindung fehlgeschlagen")
            
            # Wissensbasis aufbauen
            knowledge_data = nc_client.build_knowledge_base(remote_path)
            
            # Dokumente verarbeiten
            all_chunks = []
            sources = []
            
            for doc in knowledge_data['documents']:
                chunks = self.split_text(doc['content'])
                for chunk in chunks:
                    all_chunks.append(chunk)
                    sources.append({
                        "file": doc['name'],
                        "path": doc['path'],
                        "type": doc['extension']
                    })
            
            self.knowledge_chunks = all_chunks
            self.document_sources = sources
            
            logger.info(f"Loaded {len(all_chunks)} chunks from {len(knowledge_data['documents'])} documents")
            
            return {
                'status': 'success',
                'chunks_loaded': len(all_chunks),
                'documents_processed': knowledge_data['files_processed'],
                'errors': knowledge_data['errors']
            }
            
        except Exception as e:
            logger.error(f"Error loading from Nextcloud: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def load_local_documents(self, directory_path):
        """Lädt Dokumente aus einem lokalen Verzeichnis"""
        try:
            all_chunks = []
            sources = []
            
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Datei parsen
                    content = self.parser.parse_file(file_path)
                    
                    if content and len(content.strip()) > 50:
                        chunks = self.split_text(content)
                        for chunk in chunks:
                            all_chunks.append(chunk)
                            sources.append({
                                "file": file,
                                "path": file_path,
                                "type": os.path.splitext(file)[1].lower()
                            })
            
            self.knowledge_chunks = all_chunks
            self.document_sources = sources
            
            logger.info(f"Loaded {len(all_chunks)} chunks from local directory")
            
            return {
                'status': 'success',
                'chunks_loaded': len(all_chunks),
                'documents_processed': len(sources)
            }
            
        except Exception as e:
            logger.error(f"Error loading local documents: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def split_text(self, text, chunk_size=500):
        """Teilt Text in kleinere Chunks"""
        # Nach Absätzen aufteilen
        paragraphs = text.split('\n\n')
        chunks = []
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if len(paragraph) > chunk_size:
                # Lange Absätze weiter aufteilen
                sentences = re.split(r'[.!?]+', paragraph)
                current_chunk = ""
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(current_chunk + sentence) < chunk_size:
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                if paragraph:
                    chunks.append(paragraph)
        
        return chunks
    
    def search_knowledge(self, query, k=3):
        """High-performance search using available engine"""
        if not query or len(query.strip()) < 2:
            return []
        
        # Use search engine if available
        if self.search_engine:
            try:
                if hasattr(self.search_engine, 'hybrid_search'):
                    results = self.search_engine.hybrid_search(query, k=k)
                else:
                    results = self.search_engine.search(query, k=k)
                
                # Convert to expected format
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        'content': result['content'],
                        'distance': 1.0 - result.get('similarity_score', 0.5),  # Convert to distance
                        'source': result.get('source') or result.get('doc_name') or 'Knowledge Base',
                        'path': result.get('path') or result.get('doc_path', ''),
                        'similarity_score': result.get('similarity_score', 0.5),
                        'search_type': result.get('search_type', 'search'),
                        'chunk_id': result.get('chunk_id') or result.get('id')
                    })
                
                logger.info(f"Search: {len(formatted_results)} results for query: {query[:50]}...")
                return formatted_results
                
            except Exception as e:
                logger.error(f"Search error: {str(e)}")
                # Fallback to simple search
        
        # Fallback to simple text search
        return self._simple_search(query, k)
    
    def _simple_search(self, query, k=3):
        """Fallback simple text search"""
        if not self.knowledge_chunks:
            return []
        
        query_lower = query.lower()
        relevant_chunks = []
        
        # Search through chunks
        for chunk in self.knowledge_chunks[:500]:  # Limit for performance
            if query_lower in chunk.lower():
                relevant_chunks.append({
                    'content': chunk,
                    'distance': 1.0,
                    'source': 'fallback_search',
                    'search_type': 'simple'
                })
                
                if len(relevant_chunks) >= k:
                    break
        
        return relevant_chunks[:k]

class OllamaClient:
    def __init__(self, base_url=None, model=None):
        self.base_url = (base_url or os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')).rstrip('/')
        self.model = model or os.getenv('OLLAMA_MODEL', 'gemma3:latest')

    def update_config(self, base_url: str, model: str):
        """Aktualisiert die Laufzeit-Konfiguration des Ollama-Clients."""
        self.base_url = base_url.rstrip('/')
        self.model = model

    def _messages_to_prompt(self, messages):
        """Konvertiert Chat-Nachrichten in einen Prompt für /api/generate Fallback."""
        lines = []
        for msg in messages:
            role = str(msg.get('role', 'user')).strip().lower()
            content = str(msg.get('content', '')).strip()

            if not content:
                continue

            if role == 'system':
                lines.append(f"System: {content}")
            elif role == 'assistant':
                lines.append(f"Assistant: {content}")
            else:
                lines.append(f"User: {content}")

        lines.append("Assistant:")
        return "\n\n".join(lines)
    
    def chat(self, messages, context=None):
        """Sendet eine Chat-Anfrage an Ollama mit verbessertem Training-Manager"""
        url = f"{self.base_url}/api/chat"
        
        # Nutze Training Manager für besseren Kontext
        if context and messages:
            # Extrahiere Query aus User-Nachricht
            user_message = ""
            for msg in messages:
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')
                    break
            
            # Erstelle verbesserten Kontext mit Training Manager
            enhanced_context = training_manager.create_enhanced_context_for_ai(user_message, context)
            
            # Intelligente Tool-Selection
            should_use_cal = should_use_calendar(user_message)
            should_use_task = should_use_tasks(user_message)
            
            # Erweiterter System-Prompt mit intelligenter Reasoning-Fähigkeit
            system_prompt = f"""Du bist ein hochintelligenter KI-Assistent mit Zugang zu einer Wissensdatenbank, einem Kalender-System und einer TODO-Liste. Du arbeitest präzise, analytisch und kontextbewusst.

=== DEINE KERNKOMPETENZEN ===
1. INTELLIGENTE ANALYSE: Verstehe die Absicht hinter der Anfrage, nicht nur die Wörter
2. KONTEXTUELLES DENKEN: Verknüpfe Informationen aus verschiedenen Quellen intelligent
3. RELEVANZFILTERUNG: Fokussiere auf die wichtigsten und relevantesten Informationen
4. PRÄZISE KOMMUNIKATION: Antworte konkret, strukturiert und mit klaren Quellenangaben
5. SMARTE TOOL-AUSWAHL: Entscheide professionell und intelligent welche Tools du nutzen solltest

=== INFORMATIONSQUELLEN-STRATEGIE (INTELLIGENTE PRIORISIERUNG) ===
Du hast Zugang zu drei Hauptquellen:
• WISSENSDATENBANK: Dokumente, Notizen, technische Informationen, persönliche Daten
• KALENDER: Termine, Events, zeitliche Planungen, Verfügbarkeiten
• TODO-LISTE: Aufgaben mit Fälligkeitsdaten und Prioritäten

ENTSCHEIDUNGSLOGIK FÜR TOOL-NUTZUNG:
1. Bei Fragen nach AUFGABEN/TODOS/TASKS/VERPFLICHTUNGEN {"[NUTZE TODO-TOOL]" if should_use_task else ""}:
   → Nutze IMMER die TODO-Liste als primäre Quelle
   → Zeige konkrete Einträge mit Status, Fälligkeit und Priorität
   → Sortiere nach: heute > überfällig > diese Woche > später
   → Erkenne auch indirekte Aufgaben-Anfragen ("was muss ich noch...", "was habe ich zu tun...")

2. Bei Fragen nach TERMINEN/EVENTS/ZEITPLÄNEN/VERFÜGBARKEIT {"[NUTZE KALENDER-TOOL]" if should_use_cal else ""}:
   → Nutze primär Kalender-Kontext
   → Berücksichtige zeitliche Nähe, Bedeutsamkeit und Überschneidungen
   → Bei Planung: Zeige verfügbare Zeitfenster
   → Erkenne Verfügbarkeitsfragen ("bin ich verfügbar...", "habe ich zeit...")

3. Bei KOMBINIERTEN FRAGEN (Aufgaben UND Zeitplanung):
   → Nutze BEIDE Quellen intelligent
   → Zeige zeitlich sortierte Übersicht von Aufgaben mit Kalender-Kontext
   → Beispiel: "Heute noch zu tun: [Aufgabe1 um 14:00] [Aufgabe2 vor 17:00]"

4. Bei Fragen nach WISSEN/FAKTEN/DOKUMENTEN:
   → Durchsuche Wissensdatenbank mit Relevanz-Scoring
   → Kombiniere Informationen aus mehreren Quellen intelligent
   → Gib Quellenangaben mit Relevanz-Score an

5. Bei PERSÖNLICHEN FRAGEN ohne gefundene Quellen:
    → Nutze bei öffentlich bekannten Fakten allgemeines Modellwissen
    → Kennzeichne dies transparent mit "Nach meinem allgemeinen Wissen ..."
    → Erfinde keine persönlichen oder nutzerspezifischen Details
    → Frage nach zusätzlichem Kontext, wenn die Frage unklar ist

=== PROFESSIONELLE TOOL-AUSWAHL-REGELN ===
⚠ KEINE Kalender-Tool Nutzung für: allgemeine Wissens-Fragen, Konzept-Erklärungen, generelle Informationen
✓ NUTZE Kalender-Tool für: "Wann bin ich...", "Termin erstellen", "Habe ich einen Termin zu...", "Was steht diese Woche an..."
✓ NUTZE TODO-Tool für: "Was muss ich noch...", "Meine offenen Aufgaben", "Verbleibende Aufgaben", "Erledigung-Status"
⚠ NICHT zufällig Tools nutzen - nur wenn wirklich relevant!

=== REASONING-PROZESS ===
Für jede Anfrage IMMER:
1. VERSTEHEN: Was ist die echte Absicht? (nicht nur Wörter lesen)
2. BEWERTEN: Ist eine Tool-Nutzung nötig? (oder nur Allgemeinwissen?)
3. IDENTIFIZIEREN: Welche Informationsquelle(n) sind optimal?
4. PRIORISIEREN: Welche Informationen sind am wichtigsten?
5. SYNTHESTISIEREN: Wie kombiniere ich die Informationen optimal?
6. ANTWORTEN: Präsentiere strukturiert mit Quellenangaben

=== ANTWORTQUALITÄT & FORMATIERUNG ===
• Nutze klare Strukturierung (Listen, Absätze, Hervorhebungen)
• Gib konkrete Quellenangaben, wenn Quellen im Kontext vorhanden sind
• Wenn keine passenden Quellen vorhanden sind, antworte transparent mit allgemeinem Wissen
• Vermeide Wiederholungen und unnötige Füllwörter
• Bei mehreren Infos: Sortiere nach Relevanz und zeitlicher Nähe
• Bei zeitbezogenen Fragen: Beachte Aktualität, Fälligkeitsdaten und Zeitpunkte
• Bei Listen: Formatiere kompakt und präzise

=== VERFÜGBARER KONTEXT ===
{enhanced_context}

=== KRITISCHE RULES FÜR BESTE QUALITÄT ===
⚠ Bei TODO-Anfragen: Zeige IMMER die konkreten Einträge mit Fälligkeitsdatum
⚠ Bei Kalender-Anfragen: Zeige IMMER spezifische Termine und Zeiten
⚠ Bei fehlenden Infos: Gib dies klar zu, erfinde NICHTS
⚠ Bei widersprüchlichen Infos: Erwähne dies und priorisiere nach Relevanz
⚠ NICHT mit unnötigen Werkzeugen spielen - nur intelligente, gezielte Nutzung!
⚠ Bleibe professionell und analytisch, nicht spekulativ

Beantworte die Anfrage mit maximaler Intelligenz, Präzision und eleganter Tool-Auswahl."""
            
            # System-Nachricht erstellen oder ersetzen
            if messages and messages[0].get('role') == 'system':
                messages[0]['content'] = system_prompt
            else:
                messages.insert(0, {'role': 'system', 'content': system_prompt})
        
        # Optimierte Parameter für intelligente und präzise Antworten
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2,      # Leicht erhöht für besseres Reasoning, aber noch faktentreu
                "top_p": 0.85,           # Verbesserte Balance zwischen Fokus und Vielfalt
                "top_k": 40,             # Erweiterte Token-Auswahl für präzisere Formulierungen
                "max_tokens": 3072,      # Mehr Tokens für komplexe Antworten mit Reasoning
                "repeat_penalty": 1.15,  # Stärkere Vermeidung von Wiederholungen
                "num_predict": 3072,     # Maximale Antwortlänge erhöht
                "num_ctx": 4096,         # Kontextfenster für besseres Verständnis
                "mirostat": 2,           # Aktiviere Mirostat für konsistente Qualität
                "mirostat_tau": 5.0,     # Ziel-Perplexität für kohärente Antworten
                "mirostat_eta": 0.1      # Lernrate für Mirostat-Anpassung
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=90)  # Noch längeres Timeout

            # Fallback für Ollama-Instanzen ohne /api/chat Support
            if response.status_code == 404:
                generate_url = f"{self.base_url}/api/generate"
                generate_payload = {
                    "model": self.model,
                    "prompt": self._messages_to_prompt(messages),
                    "stream": False,
                    "options": payload.get("options", {})
                }
                generate_response = requests.post(generate_url, json=generate_payload, timeout=90)
                generate_response.raise_for_status()
                generate_data = generate_response.json()

                return {
                    "message": {
                        "role": "assistant",
                        "content": generate_data.get("response", "")
                    }
                }

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Verbindung zu Ollama fehlgeschlagen: {str(e)}"}

    def generate(self, prompt, stream=False, options=None):
        """Generiert Text über /api/generate und liefert ein einheitliches Ergebnisformat."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": bool(stream),
            "options": options or {}
        }

        try:
            response = requests.post(url, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()
            return {
                "text": data.get("response", ""),
                "raw": data
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Verbindung zu Ollama fehlgeschlagen: {str(e)}"}
    
    def check_connection(self):
        """Prüft ob Ollama verfügbar ist"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def list_models(self):
        """Lädt verfügbare Modelle von Ollama."""
        response = requests.get(f"{self.base_url}/api/tags", timeout=8)
        response.raise_for_status()
        data = response.json()

        models = []
        for model in data.get('models', []):
            name = model.get('name')
            if name:
                models.append(name)

        return sorted(set(models))

def load_ai_config() -> dict:
    """Lädt AI-Konfiguration aus Datei (oder Defaults) und wendet sie an."""
    config = {
        'provider': 'ollama',
        'base_url': os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/'),
        'model': os.getenv('OLLAMA_MODEL', 'gemma3:latest'),
        'immich_url_default': '',
        'immich_api_key_default': '',
        'vector_db_enabled': True,
        'vector_db_provider': 'qdrant',
        'vector_db_path': './qdrant_data',
        'calendar_auto_reindex_hours': 6,
        'calendar_auto_reindex_past_days': 730,
        'calendar_auto_reindex_future_days': 365,
        'briefing_daily_enabled': BRIEFING_DAILY_ENABLED_DEFAULT,
        'briefing_weekly_enabled': BRIEFING_WEEKLY_ENABLED_DEFAULT,
        'briefing_morning_hour': int(BRIEFING_MORNING_HOUR),
    }

    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)

            config['base_url'] = str(file_config.get('base_url', config['base_url'])).rstrip('/')
            config['model'] = str(file_config.get('model', config['model']))
            config['immich_url_default'] = file_config.get('immich_url_default', '')
            config['immich_api_key_default'] = file_config.get('immich_api_key_default', '')
            config['vector_db_enabled'] = file_config.get('vector_db_enabled', True)
            config['vector_db_provider'] = file_config.get('vector_db_provider', 'qdrant')
            config['vector_db_path'] = file_config.get('vector_db_path', './qdrant_data')
            config['calendar_auto_reindex_hours'] = file_config.get('calendar_auto_reindex_hours', 6)
            config['calendar_auto_reindex_past_days'] = file_config.get('calendar_auto_reindex_past_days', 730)
            config['calendar_auto_reindex_future_days'] = file_config.get('calendar_auto_reindex_future_days', 365)
            config['briefing_daily_enabled'] = bool(file_config.get('briefing_daily_enabled', config['briefing_daily_enabled']))
            config['briefing_weekly_enabled'] = bool(file_config.get('briefing_weekly_enabled', config['briefing_weekly_enabled']))
            config['briefing_morning_hour'] = max(0, min(23, int(file_config.get('briefing_morning_hour', config['briefing_morning_hour']))))
        except Exception as e:
            logger.warning(f"Konnte AI-Konfiguration nicht laden: {str(e)}")

    ollama_client.update_config(config['base_url'], config['model'])
    return config


def save_ai_config(base_url: str, model: str) -> None:
    """Speichert AI-Konfiguration persistent in einer lokalen JSON-Datei."""
    config = {}
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {}

    config['provider'] = 'ollama'
    config['base_url'] = base_url.rstrip('/')
    config['model'] = model

    with open(AI_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_user_config(username: str) -> dict:
    """Lädt benutzerspezifische Konfiguration"""
    user_config_file = os.path.join(CONFIG_DIR, f"user_{username}.json")
    config = {}

    if os.path.exists(user_config_file):
        try:
            with open(user_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load user config for {username}: {str(e)}")

    return config

def save_user_config(username: str, config: dict) -> None:
    """Speichert benutzerspezifische Konfiguration"""
    user_config_file = os.path.join(CONFIG_DIR, f"user_{username}.json")

    try:
        with open(user_config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Could not save user config for {username}: {str(e)}")
        raise


# Initialisierung
knowledge_base = KnowledgeBase()
ollama_client = OllamaClient()
training_manager = TrainingManager()
metadata_extractor = MetadataExtractor()

# Database für TaskManager setzen
if knowledge_base.db:
    set_database(knowledge_base.db)
    logger.info("✅ Database connected to task_manager")

# AI-Konfiguration beim Start laden
load_ai_config()

# Kalender-Manager initialisieren
calendar_manager = create_calendar_manager()
simple_calendar_manager = create_simple_calendar_manager()
calendar_enabled = os.getenv('CALENDAR_ENABLED', 'False').lower() == 'true'


def refresh_simple_calendar_manager() -> bool:
    """Initialisiert den einfachen Kalender-Manager mit aktueller Nextcloud-Konfiguration neu."""
    global simple_calendar_manager

    try:
        indexing_manager.load_nextcloud_config()
        config = indexing_manager.get_config(mask_password=False) or {}
        url = str(config.get('url', '')).strip()
        username = str(config.get('username', '')).strip()
        password = str(config.get('password', '')).strip()

        if url and username and password:
            simple_calendar_manager = create_simple_calendar_manager(url, username, password)
        else:
            simple_calendar_manager = create_simple_calendar_manager()

        return simple_calendar_manager is not None
    except Exception as e:
        logger.error(f"Failed to refresh simple calendar manager: {e}")
        simple_calendar_manager = None
        return False

# Tasks/Todos Manager initialisieren
tasks_enabled = False
TASKS_AUTO_SYNC_ENABLED = os.getenv('TASKS_AUTO_SYNC_ENABLED', 'true').lower() == 'true'
TASKS_AUTO_SYNC_INTERVAL_SECONDS = int(os.getenv('TASKS_AUTO_SYNC_INTERVAL_SECONDS', '300'))
TASKS_AUTO_SYNC_LIST_NAME = os.getenv('TASKS_AUTO_SYNC_LIST_NAME', 'auto')

def initialize_tasks_from_config():
    """Initialisiert Task-Manager wenn Nextcloud-Config vorhanden"""
    global tasks_enabled
    logger.info("🔧 Starting tasks initialization...")
    try:
        # Versuche aus verschiedenen Quellen zu laden
        config = None
        
        # 1. Versuche indexing_manager
        try:
            config = indexing_manager.get_config(mask_password=False)
            if config and config.get('url'):
                logger.info("✓ Config from indexing_manager")
        except Exception as e:
            logger.info(f"✗ indexing_manager.get_config() failed: {e}")
            pass
        
        # 2. Fallback: Direkt JSON laden
        if not config or not config.get('url'):
            import json
            import os
            config_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'indexing_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    logger.info(f"✓ Config from {config_file}")
        
        if config and config.get('url') and config.get('username') and config.get('password'):
            success = task_manager.initialize(config['url'], config['username'], config['password'])
            tasks_enabled = success
            if success:
                logger.info(f"✅ Tasks manager initialized: tasks_enabled={tasks_enabled}")
                if TASKS_AUTO_SYNC_ENABLED:
                    auto_sync_list_name = TASKS_AUTO_SYNC_LIST_NAME or 'auto'

                    auto_sync_started = task_manager.start_auto_sync(
                        list_name=auto_sync_list_name,
                        interval_seconds=TASKS_AUTO_SYNC_INTERVAL_SECONDS
                    )
                    logger.info(
                        f"🔁 Task auto-sync {'enabled' if auto_sync_started else 'not started'} "
                        f"(list='{auto_sync_list_name}')"
                    )
            else:
                logger.warning(f"❌ Failed to initialize tasks manager: tasks_enabled={tasks_enabled}")
        else:
            logger.warning("❌ No valid config found for tasks initialization")
            tasks_enabled = False
    except Exception as e:
        logger.warning(f"❌ Could not initialize tasks: {str(e)}")
        tasks_enabled = False
    logger.info(f"📊 Final state: tasks_enabled={tasks_enabled}")

# Kalender-Caching für Performance
calendar_cache = {}
CACHE_DURATION = 300  # 5 Minuten Cache

def parse_relative_date(message: str) -> tuple:
    """Parst relative Datumangaben und gibt (start_date, end_date, description) zurück"""
    today = date.today()
    message_lower = message.lower()
    
    # "in X Tagen" Muster
    in_days_match = re.search(r'in (\d+) tagen', message_lower)
    if in_days_match:
        days = int(in_days_match.group(1))
        target_date = today + timedelta(days=days)
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        return start, end, f"in {days} Tagen ({target_date.strftime('%d.%m.%Y')})"
    
    # "übermorgen"
    if 'übermorgen' in message_lower:
        target_date = today + timedelta(days=2)
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        return start, end, f"übermorgen ({target_date.strftime('%d.%m.%Y')})"
    
    # "nächsten [Wochentag]"
    weekdays = ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']
    for i, weekday in enumerate(weekdays):
        pattern = f'nächsten {weekday}'
        if pattern in message_lower:
            days_ahead = (i - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7  # Nächste Woche, nicht heute
            target_date = today + timedelta(days=days_ahead)
            start = datetime.combine(target_date, datetime.min.time())
            end = datetime.combine(target_date, datetime.max.time())
            return start, end, f"nächsten {weekday.capitalize()} ({target_date.strftime('%d.%m.%Y')})"
    
    return None, None, None

def get_cached_calendar_events(cache_key: str) -> tuple:
    """Holt gecachte Kalendereignisse oder None"""
    if cache_key in calendar_cache:
        cached_data = calendar_cache[cache_key]
        if time.time() - cached_data['timestamp'] < CACHE_DURATION:
            return cached_data['events'], cached_data['description']
    return None, None

def is_todo_query(message: str) -> bool:
    """Prüft ob die Nachricht eine TODO-Frage ist"""
    message_lower = message.lower()
    todo_keywords = [
        'todo', 'todos', 'aufgabe', 'aufgaben', 'task', 'tasks',
        'zu tun', 'sache', 'sachen', 'erledigungen',
        'checklist', 'checkliste', 'reminders',
        'erinnerung', 'erinnerungen', 'erinnern',
        'muss ich', 'sollte ich', 'vergesse ich nicht',
        'was habe ich', 'was muss ich'
    ]
    return any(keyword in message_lower for keyword in todo_keywords)


def _parse_task_due_date(due_value) -> Optional[date]:
    """Konvertiert Task-Datum robust in ein date-Objekt."""
    if not due_value:
        return None

    try:
        if isinstance(due_value, date) and not isinstance(due_value, datetime):
            return due_value
        if isinstance(due_value, datetime):
            return due_value.date()

        due_str = str(due_value).strip()
        if not due_str:
            return None

        # Häufigster Fall: YYYY-MM-DD
        if len(due_str) >= 10:
            return datetime.strptime(due_str[:10], '%Y-%m-%d').date()

        # Fallback für kompakte Formate (z.B. YYYYMMDD)
        if len(due_str) == 8 and due_str.isdigit():
            return datetime.strptime(due_str, '%Y%m%d').date()
    except Exception:
        return None

    return None


def _filter_tasks_by_prompt(tasks: List[Dict], message: str) -> List[Dict]:
    """Filtert Tasks nach Zeitbezug in der Nutzeranfrage."""
    message_lower = message.lower()
    today = date.today()

    # Erinnerung = VALARM innerhalb VTODO. Falls vorhanden, nur Reminder-Tasks zeigen.
    if any(keyword in message_lower for keyword in ['erinnerung', 'erinnerungen', 'reminder', 'reminders']):
        alarm_tasks = [t for t in tasks if t.get('has_alarm')]
        if alarm_tasks:
            tasks = alarm_tasks

    def due_of(task: Dict) -> Optional[date]:
        return _parse_task_due_date(task.get('due_date'))

    if 'überfällig' in message_lower:
        return [t for t in tasks if due_of(t) and due_of(t) < today]

    if 'heute' in message_lower:
        return [t for t in tasks if due_of(t) == today]

    if 'morgen' in message_lower:
        target = today + timedelta(days=1)
        return [t for t in tasks if due_of(t) == target]

    if 'gestern' in message_lower:
        target = today - timedelta(days=1)
        return [t for t in tasks if due_of(t) == target]

    if 'diese woche' in message_lower or 'diesewoche' in message_lower:
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        return [t for t in tasks if due_of(t) and week_start <= due_of(t) <= week_end]

    if 'nächste woche' in message_lower or 'naechste woche' in message_lower:
        week_start = today - timedelta(days=today.weekday()) + timedelta(days=7)
        week_end = week_start + timedelta(days=6)
        return [t for t in tasks if due_of(t) and week_start <= due_of(t) <= week_end]

    if 'letzte woche' in message_lower:
        week_start = today - timedelta(days=today.weekday()) - timedelta(days=7)
        week_end = week_start + timedelta(days=6)
        return [t for t in tasks if due_of(t) and week_start <= due_of(t) <= week_end]

    # Standard: alle offenen Tasks
    return tasks


def _build_direct_todo_response(tasks: List[Dict], filtered_tasks: List[Dict], message: str) -> str:
    """Erzeugt eine direkte, verlässliche Antwort für Todo/Erinnerungsfragen."""
    today = date.today()
    message_lower = message.lower()
    is_reminder_query = any(k in message_lower for k in ['erinnerung', 'erinnerungen', 'reminder', 'reminders'])

    item_word = 'Erinnerungen' if is_reminder_query else 'Aufgaben'

    overdue_count = 0
    due_today_count = 0
    no_due_count = 0

    for task in tasks:
        due = _parse_task_due_date(task.get('due_date'))
        if not due:
            no_due_count += 1
        elif due < today:
            overdue_count += 1
        elif due == today:
            due_today_count += 1

    if not filtered_tasks:
        if 'überfällig' in message_lower:
            return f"Du hast aktuell keine überfälligen {item_word}."
        if 'heute' in message_lower:
            return f"Für heute hast du keine fälligen {item_word}."
        return f"Du hast aktuell keine offenen {item_word}."

    lines = []
    lines.append(f"Du hast {len(tasks)} offene {item_word}.")
    lines.append(f"Davon: {overdue_count} überfällig, {due_today_count} für heute, {no_due_count} ohne Datum.")
    lines.append("")
    lines.append(f"Relevante {item_word}:")

    # Sortierung: zuerst überfällig, dann heute, dann mit Datum, dann ohne Datum
    def sort_key(task: Dict):
        due = _parse_task_due_date(task.get('due_date'))
        if due is None:
            return (3, date.max)
        if due < today:
            return (0, due)
        if due == today:
            return (1, due)
        return (2, due)

    sorted_tasks = sorted(filtered_tasks, key=sort_key)

    for i, task in enumerate(sorted_tasks[:15], 1):
        title = (task.get('title') or 'Ohne Titel').strip()
        due = _parse_task_due_date(task.get('due_date'))

        if due is None:
            due_label = "ohne Datum"
        elif due < today:
            days_overdue = (today - due).days
            due_label = f"überfällig seit {due.strftime('%d.%m.%Y')} ({days_overdue} Tage)"
        elif due == today:
            due_label = "heute fällig"
        else:
            due_label = f"fällig am {due.strftime('%d.%m.%Y')}"

        lines.append(f"{i}. {title} ({due_label})")

    remaining = len(sorted_tasks) - min(len(sorted_tasks), 15)
    if remaining > 0:
        lines.append(f"… und {remaining} weitere.")

    return "\n".join(lines)


def get_todo_data(message: str) -> Dict:
    """Lädt offene Tasks und erzeugt gefilterten Todo-Kontext."""
    if not tasks_enabled or not task_manager.tasks_client:
        return {
            'enabled': False,
            'tasks': [],
            'filtered_tasks': [],
            'context': ''
        }

    try:
        tasks = task_manager.get_tasks(use_cache=True, list_name=None)
        open_tasks = [t for t in tasks if not t.get('completed', False)]
        filtered_tasks = _filter_tasks_by_prompt(open_tasks, message)

        context = task_manager.format_tasks_for_context(open_tasks)

        return {
            'enabled': True,
            'tasks': open_tasks,
            'filtered_tasks': filtered_tasks,
            'context': context
        }
    except Exception as e:
        logger.error(f"Error getting todo data: {str(e)}")
        return {
            'enabled': True,
            'tasks': [],
            'filtered_tasks': [],
            'context': ''
        }

def get_todo_context(message: str) -> str:
    """Holt Todo-Kontext basierend auf der Nachricht"""
    todo_data = get_todo_data(message)
    return todo_data.get('context', '')

def get_nextcloud_runtime_config() -> Dict:
    """Lädt Nextcloud-Zugangsdaten aus mehreren Quellen in stabiler Reihenfolge."""
    config = {}

    # 1) Bereits geladene Laufzeit-Konfiguration
    try:
        config = indexing_manager.get_config(mask_password=False)
        if config and all(config.get(k) for k in ['url', 'username', 'password']):
            return config
    except Exception as e:
        logger.debug(f"indexing_manager.get_config failed: {e}")

    # 2) Versuche explizit aus der vom IndexingManager genutzten Datei zu laden
    try:
        if hasattr(indexing_manager, 'load_nextcloud_config'):
            indexing_manager.load_nextcloud_config()
            config = indexing_manager.get_config(mask_password=False)
            if config and all(config.get(k) for k in ['url', 'username', 'password']):
                return config
    except Exception as e:
        logger.debug(f"indexing_manager.load_nextcloud_config failed: {e}")

    # 3) Fallback auf bekannte Konfig-Dateien im Backend
    config_candidates = [
        os.path.join(CONFIG_DIR, 'indexing_config.json'),
        os.path.join(CONFIG_DIR, 'nextcloud_config.json')
    ]
    for config_path in config_candidates:
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                if all(file_config.get(k) for k in ['url', 'username', 'password']):
                    return file_config
        except Exception as e:
            logger.debug(f"Could not read Nextcloud config from {config_path}: {e}")

    # 4) Letzter Fallback auf Environment
    env_config = {
        'url': os.getenv('NEXTCLOUD_URL'),
        'username': os.getenv('NEXTCLOUD_USERNAME'),
        'password': os.getenv('NEXTCLOUD_PASSWORD')
    }
    if all(env_config.get(k) for k in ['url', 'username', 'password']):
        return env_config

    return {}

def is_activity_query(message: str) -> bool:
    """Erkennt Fragen zu neuen Nextcloud-Aktivitäten."""
    message_lower = message.lower()
    activity_keywords = [
        'aktivität', 'aktivitäten', 'activity', 'activities', 'neuigkeiten',
        'was gibt es neues', 'was ist neu', 'nextcloud'
    ]
    return any(keyword in message_lower for keyword in activity_keywords)

def should_use_calendar(message: str) -> bool:
    """
    Intelligente Erkennung ob Kalender verwendet werden sollte.
    Basiert auf Schlüsselworten UND kontextuellem Verständnis.
    """
    message_lower = message.lower()
    
    # Explizite Kalender-Indikationen
    strong_calendar_keywords = [
        'termin', 'termine', 'erstelle', 'create', 'eintrag', 'event', 
        'meeting', 'termin erstellen', 'im kalender', 'kalender',
        'wann bin ich', 'habe ich einen termin', 'was steht an'
    ]
    
    if any(keyword in message_lower for keyword in strong_calendar_keywords):
        return True
    
    # Zeitbezogene Fragen die nach Verfügbarkeit oder Planung fragen
    time_context_keywords = ['wann', 'zeitpunkt', 'uhrzeit', 'um', 'heute', 'morgen', 'diese woche', 'nächste woche']
    if any(keyword in message_lower for keyword in time_context_keywords):
        # Wenn es ohne Kontext ist, könnte es eine normale Frage sein
        # Aber mit "habe ich", "bin ich", "steht an", etc. sollte Kalender genutzt werden
        activity_indicators = ['habe ich', 'bin ich', 'bin die', 'steht an', 'planung', 'geplant']
        if any(indicator in message_lower for indicator in activity_indicators):
            return True
    
    return False

def should_use_tasks(message: str) -> bool:
    """
    Intelligente Erkennung ob TODOs/Tasks verwendet werden sollten.
    """
    message_lower = message.lower()
    
    task_keywords = [
        'aufgabe', 'aufgaben', 'todo', 'todos', 'task', 'tasks',
        'erledigen', 'abhaken', 'fertig', 'erledigt',
        'was muss ich', 'noch zu tun', 'to do', 'meine aufgaben'
    ]
    
    if any(keyword in message_lower for keyword in task_keywords):
        return True
    
    # Auch "was muss ich tun" oder "was sollte ich machen" ohne explizites task-Wort
    action_indicators = ['was muss ich', 'was sollte ich', 'was habe ich']
    if any(indicator in message_lower for indicator in action_indicators):
        return True
    
    return False

def is_calendar_create_query(message: str) -> bool:
    """Erkennt Wunsch nach Termin-Erstellung."""
    message_lower = message.lower()
    create_keywords = ['erstelle', 'anlegen', 'create', 'eintragen', 'hinzufügen']
    calendar_keywords = ['termin', 'ereignis', 'kalender', 'event', 'appointment']
    return any(k in message_lower for k in create_keywords) and any(k in message_lower for k in calendar_keywords)


def is_task_create_query(message: str) -> bool:
    """Erkennt Wunsch nach Aufgaben-/Erinnerungs-Erstellung."""
    message_lower = message.lower()
    create_keywords = ['erstelle', 'anlegen', 'create', 'hinzufügen', 'add', 'new']
    task_keywords = ['aufgabe', 'aufgaben', 'todo', 'task', 'tasks', 'erinnerung', 'reminder']
    return any(k in message_lower for k in create_keywords) and any(k in message_lower for k in task_keywords)


def _normalize_task_due_date(due_value: Optional[str]) -> Optional[str]:
    """Normalisiert verschiedene Datumsangaben auf YYYY-MM-DD."""
    if not due_value:
        return None

    value = str(due_value).strip().lower()
    if not value:
        return None

    if value in ['heute', 'today']:
        return datetime.now().strftime('%Y-%m-%d')
    if value in ['morgen', 'tomorrow']:
        return (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    if value in ['uebermorgen', 'übermorgen']:
        return (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

    formats = ['%Y-%m-%d', '%d.%m.%Y', '%d.%m.%y']
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None


def get_available_task_lists() -> List[str]:
    """Lädt verfügbare Nextcloud-Tasklisten."""
    if not tasks_enabled or not task_manager.tasks_client:
        return []

    try:
        lists = task_manager.tasks_client.get_task_lists()
        return [name for name in lists if name]
    except Exception as e:
        logger.debug(f"Could not load task lists: {e}")
        return []


def _extract_task_priority(message: str) -> int:
    """Leitet Priorität aus Text ab (1=hoch, 5=mittel, 9=niedrig)."""
    text = message.lower()
    if any(k in text for k in ['dringend', 'wichtig', 'hoch', 'high', 'urgent']):
        return 1
    if any(k in text for k in ['mittel', 'medium', 'normal']):
        return 5
    if any(k in text for k in ['niedrig', 'low', 'später', 'spaeter']):
        return 9
    return 0


def extract_task_info_from_message(message: str) -> Dict[str, Any]:
    """Extrahiert Task-/Reminder-Informationen aus natürlicher Sprache."""
    result = {
        'title': None,
        'due_date': None,
        'priority': 0,
        'list_name': None,
        'location': None,
        'description': None,
        'missing_info': []
    }

    message_clean = ' '.join((message or '').strip().split())
    message_lower = message_clean.lower()
    now = datetime.now()

    # Datum extrahieren
    date_patterns = [
        r'\b(?:am|bis|fuer|für)\s+(\d{1,2}\.\d{1,2}\.\d{4})\b',
        r'\b(\d{4}-\d{2}-\d{2})\b'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, message_clean, re.IGNORECASE)
        if match:
            normalized = _normalize_task_due_date(match.group(1))
            if normalized:
                result['due_date'] = normalized
                break

    if not result['due_date']:
        if any(k in message_lower for k in ['morgen', 'tomorrow']):
            result['due_date'] = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        elif any(k in message_lower for k in ['heute', 'today']):
            result['due_date'] = now.strftime('%Y-%m-%d')

    # Priorität extrahieren
    result['priority'] = _extract_task_priority(message_clean)

    # Taskliste extrahieren (optional)
    list_match = re.search(r'\b(?:in\s+liste|liste)\s+([a-zA-Z0-9 _\-]+)\b', message_clean, re.IGNORECASE)
    if list_match:
        result['list_name'] = list_match.group(1).strip()

    # Ort extrahieren (optional)
    location_patterns = [
        r'\b(?:ort|location)[:\s]+([^,.!?]+?)(?=\s+(?:am|bis|fuer|für|heute|morgen|today|tomorrow|in\s+liste|liste)\b|[,.!?]|$)',
        r'\b(?:bei|in)\s+([^,.!?]+?)(?=\s+(?:am|bis|fuer|für|heute|morgen|today|tomorrow|in\s+liste|liste)\b|[,.!?]|$)'
    ]
    for pattern in location_patterns:
        match = re.search(pattern, message_clean, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate and not re.search(r'\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}', candidate):
                result['location'] = candidate.title()
                break

    # Titel extrahieren
    quoted_title = re.search(r'"([^"]+)"', message_clean)
    if quoted_title:
        result['title'] = quoted_title.group(1).strip()
    else:
        title_candidate = message_clean
        title_candidate = re.sub(
            r'^(?:kannst\s+du\s+)?(?:bitte\s+)?(?:erstelle|erstelle\s+mir|lege\s+an|lege|mach|add|create)\s+(?:mir\s+)?(?:eine?|neue?n?)?\s*(?:erinnerung|aufgabe|todo|task|reminder|tasks|aufgaben)?\s*',
            '',
            title_candidate,
            flags=re.IGNORECASE
        )
        title_candidate = re.sub(r'\b(?:am|bis|fuer|für|heute|morgen|today|tomorrow|in\s+liste|liste|mit\s+prioritaet|mit\s+priorität)\b.*$', '', title_candidate, flags=re.IGNORECASE)
        title_candidate = title_candidate.strip(' .,:;!-')
        if title_candidate:
            result['title'] = title_candidate

    if result['title'] and result['title'].islower():
        result['title'] = result['title'].title()

    # Generische Placeholder sollen den Dialog erzwingen.
    generic_titles = {
        'aufgabe', 'neue aufgabe', 'todo', 'neues todo', 'task', 'new task',
        'erinnerung', 'neue erinnerung', 'reminder', 'new reminder'
    }
    if (result.get('title') or '').strip().lower() in generic_titles:
        result['title'] = None

    result['description'] = message_clean

    if not result['title']:
        result['missing_info'].append('Titel')
    if not result['due_date']:
        result['missing_info'].append('Fälligkeitsdatum')

    return result


def create_task_reminder(title: str, description: str = '', due_date: Optional[str] = None,
                         priority: int = 0, list_name: Optional[str] = None,
                         location: Optional[str] = None) -> Dict[str, Any]:
    """Erstellt eine Aufgabe/Erinnerung über den Task-Manager."""
    if not tasks_enabled or not task_manager.tasks_client:
        return {'success': False, 'error': 'Tasks nicht verfügbar'}

    try:
        available_lists = get_available_task_lists()
        target_list_name = (list_name or '').strip()

        if target_list_name and available_lists:
            for candidate in available_lists:
                if target_list_name.lower() == candidate.lower():
                    target_list_name = candidate
                    break
            else:
                for candidate in available_lists:
                    if target_list_name.lower() in candidate.lower():
                        target_list_name = candidate
                        break

        if not target_list_name:
            target_list_name = available_lists[0] if available_lists else 'tasks'

        normalized_due = _normalize_task_due_date(due_date)
        parsed_priority = int(priority or 0)

        final_description = (description or '').strip()
        location_value = (location or '').strip()
        if location_value:
            location_line = f"Ort: {location_value}"
            if final_description:
                if location_line.lower() not in final_description.lower():
                    final_description = f"{final_description}\n{location_line}"
            else:
                final_description = location_line

        success = task_manager.create_task(
            title=title,
            description=final_description,
            due_date=normalized_due,
            priority=parsed_priority,
            list_name=target_list_name
        )

        if success:
            due_text = normalized_due if normalized_due else 'ohne Fälligkeitsdatum'
            return {
                'success': True,
                'message': f'Aufgabe "{title}" wurde erstellt (fällig: {due_text})',
                'title': title,
                'due_date': normalized_due,
                'priority': parsed_priority,
                'list_name': target_list_name,
                'location': location_value or None
            }

        return {'success': False, 'error': 'Fehler beim Erstellen des Tasks'}
    except Exception as e:
        logger.error(f"Error creating task reminder: {e}")
        return {'success': False, 'error': f'Fehler: {str(e)}'}

def get_activity_context(limit: int = 10) -> Dict:
    """Lädt aktuelle Nextcloud-Aktivitäten und formatiert sie für Chat-Kontext und Direktantworten."""
    config = get_nextcloud_runtime_config()
    if not config:
        return {
            'context': "",
            'summary_text': "Ich konnte keine Nextcloud-Konfiguration finden.",
            'count': 0,
            'error': 'missing_config'
        }

    try:
        activity_client = NextcloudActivityClient(config['url'], config['username'], config['password'])
        if not activity_client.test_connection():
            return {
                'context': "",
                'summary_text': "Die Activity-API ist aktuell nicht erreichbar oder nicht aktiviert.",
                'count': 0,
                'error': 'connection_failed'
            }

        activities = activity_client.get_recent_activities(limit=limit)
        if not activities:
            return {
                'context': "=== NEXTCLOUD AKTIVITÄTEN ===\nKeine neuen Aktivitäten gefunden.",
                'summary_text': "Es gibt aktuell keine neuen Aktivitäten auf deiner Nextcloud.",
                'count': 0,
                'error': None
            }

        lines = ["=== NEXTCLOUD AKTIVITÄTEN ===", f"Anzahl: {len(activities)}", ""]
        summary_lines = ["Ja, es gibt neue Aktivitäten:"]

        for idx, activity in enumerate(activities[:10], 1):
            subject = activity.get('subject') or 'Ohne Betreff'
            app_name = activity.get('app') or 'unknown'
            dt = activity.get('datetime') or ''
            line = f"{idx}. [{app_name}] {subject}"
            if dt:
                line += f" ({dt})"
            lines.append(line)
            if idx <= 5:
                summary_lines.append(f"- [{app_name}] {subject}")

        return {
            'context': "\n".join(lines),
            'summary_text': "\n".join(summary_lines),
            'count': len(activities),
            'error': None
        }
    except Exception as e:
        logger.error(f"Error getting activity context: {e}")
        return {
            'context': "",
            'summary_text': f"Beim Abruf der Aktivitäten ist ein Fehler aufgetreten: {str(e)[:120]}",
            'count': 0,
            'error': 'runtime_error'
        }

def get_notifications_context(limit: int = 10) -> Dict:
    """Lädt aktuelle Nextcloud-Benachrichtigungen und formatiert sie für Chat-Kontext."""
    config = get_nextcloud_runtime_config()
    if not config:
        return {
            'context': "",
            'summary_text': "",
            'count': 0,
            'error': 'missing_config'
        }

    try:
        notifications_client = NextcloudNotificationsClient(config['url'], config['username'], config['password'])
        if not notifications_client.test_connection():
            return {
                'context': "",
                'summary_text': "",
                'count': 0,
                'error': 'connection_failed'
            }

        notifications = notifications_client.get_notifications()[:limit]
        if not notifications:
            return {
                'context': "=== NEXTCLOUD BENACHRICHTIGUNGEN ===\nKeine offenen Benachrichtigungen.",
                'summary_text': "",
                'count': 0,
                'error': None
            }

        lines = ["=== NEXTCLOUD BENACHRICHTIGUNGEN ===", f"Anzahl: {len(notifications)}", ""]
        summary_lines = ["Zusätzlich gibt es Benachrichtigungen:"]

        for idx, notif in enumerate(notifications, 1):
            subject = notif.get('subject') or 'Ohne Betreff'
            app_name = notif.get('app') or 'unknown'
            dt = notif.get('datetime') or ''
            line = f"{idx}. [{app_name}] {subject}"
            if dt:
                line += f" ({dt})"
            lines.append(line)
            if idx <= 5:
                summary_lines.append(f"- [{app_name}] {subject}")

        return {
            'context': "\n".join(lines),
            'summary_text': "\n".join(summary_lines),
            'count': len(notifications),
            'error': None
        }
    except Exception as e:
        logger.error(f"Error getting notifications context: {e}")
        return {
            'context': "",
            'summary_text': "",
            'count': 0,
            'error': 'runtime_error'
        }

def get_updates_context(activity_limit: int = 10, notifications_limit: int = 10) -> Dict:
    """Kombiniert Nextcloud Activity und Notifications zu einer einheitlichen Update-Antwort."""
    activity_result = get_activity_context(limit=activity_limit)
    notifications_result = get_notifications_context(limit=notifications_limit)

    combined_context_parts = []
    if activity_result.get('context'):
        combined_context_parts.append(activity_result['context'])
    if notifications_result.get('context'):
        combined_context_parts.append(notifications_result['context'])

    total_count = int(activity_result.get('count', 0)) + int(notifications_result.get('count', 0))

    summary_lines = []
    if activity_result.get('count', 0) > 0:
        summary_lines.append(activity_result.get('summary_text', ''))
    if notifications_result.get('count', 0) > 0:
        summary_lines.append(notifications_result.get('summary_text', ''))

    if total_count == 0:
        summary_text = "Aktuell gibt es weder neue Aktivitäten noch offene Benachrichtigungen auf deiner Nextcloud."
    else:
        summary_text = "\n\n".join([line for line in summary_lines if line])
        if not summary_text:
            summary_text = f"Es gibt insgesamt {total_count} neue Einträge auf deiner Nextcloud."

    return {
        'context': "\n\n".join(combined_context_parts),
        'summary_text': summary_text,
        'count': total_count,
        'activity_count': activity_result.get('count', 0),
        'notification_count': notifications_result.get('count', 0)
    }

def create_calendar_event(title: str, start_time: str, end_time: str = None, 
                          calendar_name: str = None, location: str = None, 
                          description: str = None) -> dict:
    """Erstellt ein neues Kalendereignis über CalDAV"""
    if not simple_calendar_manager:
        refresh_simple_calendar_manager()

    if not simple_calendar_manager:
        return {'success': False, 'error': 'Kalender nicht verfügbar'}
    
    try:
        # Hole verfügbare Kalender
        calendars = simple_calendar_manager.get_calendars()
        if not calendars:
            return {'success': False, 'error': 'Keine Kalender gefunden'}
        
        # Wähle Kalender aus: explizit übergeben > gespeicherter Standard > erster Kalender
        target_calendar = None

        preferred_calendar_name = (calendar_name or '').strip()
        if not preferred_calendar_name:
            calendar_cfg = load_calendar_config()
            preferred_calendar_name = str(calendar_cfg.get('default_calendar_name', '')).strip()

        if preferred_calendar_name:
            # Suche nach Kalender mit passendem Namen
            for cal in calendars:
                if preferred_calendar_name.lower() in cal['name'].lower():
                    target_calendar = cal
                    break
        
        if not target_calendar:
            # Nutze den ersten Kalender oder frage nach Auswahl
            target_calendar = calendars[0]
        
        # Erstelle iCal-Daten für das Ereignis
        uid = f"{int(time.time())}@calendar-app"
        now = datetime.now().strftime('%Y%m%dT%H%M%SZ')
        
        # Parse Zeiten
        start_dt = parse_datetime_string(start_time)
        end_dt = parse_datetime_string(end_time) if end_time else start_dt + timedelta(hours=1)
        
        ical_data = f'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Calendar App//Calendar Event//EN
BEGIN:VEVENT
UID:{uid}
DTSTART:{start_dt.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%SZ')}
DTSTAMP:{now}
SUMMARY:{title}
{'LOCATION:' + location + '\n' if location else ''}{'DESCRIPTION:' + description + '\n' if description else ''}END:VEVENT
END:VCALENDAR'''
        
        # Sende PUT request um Ereignis zu erstellen
        event_url = f"{simple_calendar_manager.nextcloud_url}{target_calendar['url']}{uid}.ics"
        
        headers = {
            'Content-Type': 'text/calendar; charset=utf-8'
        }
        
        response = simple_calendar_manager.session.put(
            event_url, 
            data=ical_data.encode('utf-8'), 
            headers=headers
        )
        
        if response.status_code in [201, 204]:
            return {
                'success': True,
                'message': f'Ereignis "{title}" wurde im Kalender "{target_calendar["name"]}" erstellt',
                'event_id': uid,
                'calendar': target_calendar['name']
            }
        else:
            return {
                'success': False, 
                'error': f'Fehler beim Erstellen: {response.status_code} - {response.text[:200]}'
            }
            
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return {'success': False, 'error': f'Fehler: {str(e)}'}

def parse_datetime_string(dt_str: str) -> datetime:
    """Parst verschiedene Datums/Zeit-Formate"""
    if not dt_str:
        return datetime.now()
    
    # Verschiedene Formate versuchen
    formats = [
        '%d.%m.%Y %H:%M',  # 26.03.2026 14:30
        '%d.%m.%Y %H:%M:%S',  # 26.03.2026 14:30:00
        '%d.%m.%Y',  # 26.03.2026
        '%H:%M',  # 14:30 (heute)
        '%H:%M:%S',  # 14:30:00 (heute)
    ]
    
    for fmt in formats:
        try:
            if fmt in ['%H:%M', '%H:%M:%S']:
                # Nur Zeit - kombiniere mit heute
                today = date.today()
                time_part = datetime.strptime(dt_str, fmt).time()
                return datetime.combine(today, time_part)
            else:
                return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    # Fallback: aktuelle Zeit
    return datetime.now()

def cache_calendar_events(cache_key: str, events: list, description: str):
    """Cacht Kalendereignisse"""
    calendar_cache[cache_key] = {
        'events': events,
        'description': description,
        'timestamp': time.time()
    }

def extract_event_info_from_message(message: str) -> dict:
    """Extrahiert Ereignis-Informationen aus natürlicher Sprache"""
    import re
    
    result = {
        'title': None,
        'start_time': None,
        'end_time': None,
        'calendar_name': None,
        'location': None,
        'description': None,
        'missing_info': []
    }
    
    message_clean = ' '.join(message.strip().split())

    # Zeit extrahieren (inkl. relativer Angaben)
    now = datetime.now()

    match = re.search(r'\bmorgen\s+um\s+(\d{1,2}:\d{2})\b', message_clean, re.IGNORECASE)
    if match:
        tomorrow = now + timedelta(days=1)
        result['start_time'] = f"{tomorrow.strftime('%d.%m.%Y')} {match.group(1)}"
    else:
        match = re.search(r'\bheute\s+um\s+(\d{1,2}:\d{2})\b', message_clean, re.IGNORECASE)
        if match:
            result['start_time'] = f"{now.strftime('%d.%m.%Y')} {match.group(1)}"
        else:
            match = re.search(r'\b(\d{2}\.\d{2}\.\d{4})\s+um\s+(\d{1,2}:\d{2})\b', message_clean, re.IGNORECASE)
            if match:
                result['start_time'] = f"{match.group(1)} {match.group(2)}"
            else:
                match = re.search(r'\b(\d{2}\.\d{2}\.\d{4}\s+\d{1,2}:\d{2})\b', message_clean)
                if match:
                    result['start_time'] = match.group(1)
                else:
                    match = re.search(r'\bum\s+(\d{1,2}:\d{2})\b', message_clean, re.IGNORECASE)
                    if match:
                        result['start_time'] = match.group(1)

    # Kalender extrahieren
    calendar_patterns = [
        r'\bim\s+kalender\s+([^,.!?]+?)(?=\s+(?:in|bei|um|heute|morgen|am)\b|[,.!?]|$)',
        r'\bkalender[:\s]+([^,.!?]+?)(?=\s+(?:in|bei|um|heute|morgen|am)\b|[,.!?]|$)'
    ]
    for pattern in calendar_patterns:
        match = re.search(pattern, message_clean, re.IGNORECASE)
        if match:
            result['calendar_name'] = match.group(1).strip().title()
            break

    # Ort extrahieren
    location_patterns = [
        r'\bort[:\s]+([^,.!?]+?)(?=\s+(?:um|heute|morgen|am|im\s+kalender|kalender)\b|[,.!?]|$)',
        r'\bbei\s+([^,.!?]+?)(?=\s+(?:um|heute|morgen|am|im\s+kalender|kalender)\b|[,.!?]|$)',
        r'\bin\s+([^,.!?]+?)(?=\s+(?:um|heute|morgen|am|im\s+kalender|kalender)\b|[,.!?]|$)'
    ]
    for pattern in location_patterns:
        match = re.search(pattern, message_clean, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate and not re.search(r'\d{1,2}:\d{2}|\d{2}\.\d{2}\.\d{4}', candidate):
                result['location'] = candidate.title()
                break

    # Titel extrahieren
    quoted_title = re.search(r'"([^"]+)"', message_clean)
    if quoted_title:
        result['title'] = quoted_title.group(1).strip()
    else:
        title_candidate = message_clean
        title_candidate = re.sub(
            r'^(?:kannst\s+du\s+)?(?:bitte\s+)?(?:erstelle|erstelle\s+mir|lege\s+an|lege|mach|plane|create|add)\s+(?:mir\s+)?(?:einen|eine|ein)?\s*(?:neuen\s+)?(?:termin|ereignis)?\s*',
            '',
            title_candidate,
            flags=re.IGNORECASE
        )
        title_candidate = re.sub(r'\b(?:im\s+kalender|kalender|in|bei|um|heute|morgen|am)\b.*$', '', title_candidate, flags=re.IGNORECASE)
        title_candidate = title_candidate.strip(' .,:;!-')
        if title_candidate:
            result['title'] = title_candidate

    # Title-Case nur wenn komplett klein geschrieben
    if result['title'] and result['title'].islower():
        result['title'] = result['title'].title()
    
    # Prüfe welche Informationen fehlen
    if not result['title']:
        result['missing_info'].append('Titel')
    if not result['start_time']:
        result['missing_info'].append('Startzeit')
    
    return result

def get_calendar_context(message: str) -> str:
    """Holt Kalender-Kontext basierend auf intelligenten Analyse der Nachricht"""
    # Nutze den einfachen Kalender-Manager, der funktioniert
    if not simple_calendar_manager:
        refresh_simple_calendar_manager()

    if not simple_calendar_manager:
        return ""
    
    message_lower = message.lower()
    today_info = simple_calendar_manager.get_today_info() if hasattr(simple_calendar_manager, 'get_today_info') else {
        'date': date.today().strftime('%d.%m.%Y'),
        'weekday': ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][date.today().weekday()],
        'calendar_week': date.today().isocalendar()[1]
    }
    
    # Erweiterte Kalender-Kontext erstellen
    context_text = "=== KALENDER-KONTEXT ===\n\n"
    context_text += f"Heute ist {today_info['date']}, {today_info['weekday']} (Kalenderwoche {today_info['calendar_week']})\n\n"
    
    # Intelligente Zeitraum-Erkennung basierend auf Kontext
    events = []
    time_period = "unbekannt"
    
    # Zuerst relative Datumangaben prüfen
    relative_start, relative_end, relative_desc = parse_relative_date(message)
    if relative_start and relative_end:
        cache_key = f"relative_{relative_start.strftime('%Y%m%d')}"
        events, cached_desc = get_cached_calendar_events(cache_key)
        if events is None:
            # Hole alle Kalender und suche im Zeitraum
            try:
                calendars = simple_calendar_manager.get_calendars()
                all_events = []
                
                for cal in calendars:
                    if 'calendar' in cal.get('url', ''):
                        calendar_name = cal['url'].split('/')[-1]
                        cal_events = simple_calendar_manager.get_events(cal['url'], relative_start, relative_end)
                        for event in cal_events:
                            event['calendar'] = cal.get('name', 'Unknown')
                            all_events.append(event)
                
                all_events.sort(key=lambda x: x.get('start', ''))
                events = all_events
                cache_calendar_events(cache_key, events, relative_desc)
            except Exception as e:
                logger.error(f"Error getting relative date events: {e}")
                events = []
        
        time_period = relative_desc
    else:
        # Flexible Zeiträume basierend auf Kontextanalyse
        cache_key = None
        events = []
        time_period = "unbekannt"
        
        # Heutige Ereignisse
        if any(word in message_lower for word in ['heute', 'tag', 'aktuell']):
            cache_key = "today"
            events, cached_desc = get_cached_calendar_events(cache_key)
            if events is None:
                events = simple_calendar_manager.get_events_today() if hasattr(simple_calendar_manager, 'get_events_today') else []
                cache_calendar_events(cache_key, events, "heute")
            time_period = "heute"
        
        # Morgige Ereignisse
        elif 'morgen' in message_lower:
            cache_key = "tomorrow"
            events, cached_desc = get_cached_calendar_events(cache_key)
            if events is None:
                events = simple_calendar_manager.get_events_tomorrow() if hasattr(simple_calendar_manager, 'get_events_tomorrow') else []
                tomorrow = (date.today() + timedelta(days=1)).strftime('%d.%m.%Y')
                weekday = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][(date.today() + timedelta(days=1)).weekday()]
                context_text += f"Morgen ist {tomorrow}, {weekday}\n\n"
                cache_calendar_events(cache_key, events, "morgen")
            time_period = "morgen"
        
        # Wöchentliche Ereignisse
        elif any(word in message_lower for word in ['woche', 'wochenende', 'wochentage']):
            cache_key = "this_week"
            events, cached_desc = get_cached_calendar_events(cache_key)
            if events is None:
                events = simple_calendar_manager.get_events_this_week() if hasattr(simple_calendar_manager, 'get_events_this_week') else []
                cache_calendar_events(cache_key, events, "diese Woche")
            time_period = "diese Woche"
        
        # Nächste Woche
        elif 'nächste woche' in message_lower or 'kommende woche' in message_lower:
            cache_key = "next_week"
            events, cached_desc = get_cached_calendar_events(cache_key)
            if events is None:
                events = simple_calendar_manager.get_events_next_week() if hasattr(simple_calendar_manager, 'get_events_next_week') else []
                cache_calendar_events(cache_key, events, "nächste Woche")
            time_period = "nächste Woche"
        
        # Spezifische Wochentage
        else:
            weekdays = ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']
            for weekday in weekdays:
                if weekday in message_lower:
                    cache_key = f"day_{weekday}"
                    events, cached_desc = get_cached_calendar_events(cache_key)
                    if events is None:
                        events = simple_calendar_manager.get_events_for_day(weekday) if hasattr(simple_calendar_manager, 'get_events_for_day') else []
                        cache_calendar_events(cache_key, events, f"am {weekday.capitalize()}")
                    time_period = f"am {weekday.capitalize()}"
                    break
    
    # Ereignisse formatieren
    if events:
        context_text += f"Gefundene Ereignisse {time_period} ({len(events)}):\n"
        for i, event in enumerate(events, 1):
            event_line = f"{i}. {event.get('summary', 'Kein Titel')}"
            
            # Zeitinformationen hinzufügen
            if event.get('start'):
                event_line += f" um {event['start']}"
                if event.get('end') and event['end'] != event['start']:
                    event_line += f" - {event['end']}"
            
            # Ort hinzufügen
            if event.get('location'):
                event_line += f" in {event['location']}"
            
            # Kalendername hinzufügen
            if event.get('calendar') and event['calendar'] != 'Unknown':
                event_line += f" ({event['calendar']})"
            
            # Beschreibung hinzufügen falls vorhanden
            if event.get('description') and len(event['description']) < 100:
                event_line += f" - {event['description']}"
            
            context_text += event_line + "\n"
    else:
        # Wenn keine Ereignisse gefunden, aber es war eine zeitbezogene Anfrage
        if time_period != "unbekannt":
            context_text += f"Keine Ereignisse {time_period} gefunden.\n"
        else:
            # Kein spezifischer Zeitraum erkannt - gib allgemeinen Überblick
            try:
                all_week_events = simple_calendar_manager.get_events_this_week() if hasattr(simple_calendar_manager, 'get_events_this_week') else []
                if all_week_events:
                    context_text += f"Diese Woche gibt es {len(all_week_events)} Ereignisse.\n"
                    context_text += "Frag spezifisch nach einem Zeitraum für Details.\n"
                else:
                    context_text += "Diese Woche gibt es keine geplanten Ereignisse.\n"
            except:
                context_text += "Kalender-Informationen nicht verfügbar.\n"
    
    context_text += "\n=== ANWEISUNGEN FÜR ANTWORT ===\n"
    context_text += "1. Beantworte präzise basierend auf den gefundenen Kalendereignissen\n"
    context_text += "2. Wenn keine Ereignisse gefunden wurden: Sage das klar und deutlich\n"
    context_text += "3. Gib Datum, Uhrzeit und Ort an wenn verfügbar\n"
    context_text += "4. Sei hilfreich und organisiert in der Antwort\n"
    context_text += "5. Bei leeren Kalender: Biete an nach anderen Zeitperioden zu suchen\n"
    
    return context_text


def _parse_iso_anchor_date(value: Optional[str]) -> date:
    """Parse YYYY-MM-DD and fallback to today."""
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return date.today()


def _infer_calendar_card_config(prompt: str) -> Dict:
    """Infer default calendar card state from prompt."""
    message = (prompt or '').lower()
    view = 'day'
    if 'woche' in message or 'week' in message:
        view = 'week'
    elif 'monat' in message or 'month' in message:
        view = 'month'
    elif 'liste' in message or 'list' in message:
        view = 'list'

    anchor = date.today()
    if 'morgen' in message or 'tomorrow' in message:
        anchor = anchor + timedelta(days=1)
    elif 'gestern' in message or 'yesterday' in message:
        anchor = anchor - timedelta(days=1)
    else:
        rel_start, _, _ = parse_relative_date(prompt)
        if rel_start:
            anchor = rel_start.date()

    return {
        'view': view,
        'date': anchor.strftime('%Y-%m-%d')
    }


def _infer_task_card_config(prompt: str) -> Dict:
    """Infer default task card state from prompt."""
    message = (prompt or '').lower()
    scope = 'all'
    if 'überfällig' in message or 'overdue' in message:
        scope = 'overdue'
    elif 'heute' in message or 'today' in message:
        scope = 'today'

    anchor = date.today()
    if 'morgen' in message or 'tomorrow' in message:
        anchor = anchor + timedelta(days=1)
    elif 'gestern' in message or 'yesterday' in message:
        anchor = anchor - timedelta(days=1)

    return {
        'scope': scope,
        'date': anchor.strftime('%Y-%m-%d')
    }


def _build_email_card(prompt: str, language: str = 'de') -> Dict[str, Any]:
    """Build an interactive email compose card for the frontend."""
    is_german = str(language or '').lower().startswith('de')
    draft = extract_email_send_info_from_message(prompt)
    prompt_text = _normalize_lookup_text(prompt)
    reply_like = any(keyword in prompt_text for keyword in ['antwort', 'antworte', 'antworten', 'reply', 'antwort schreiben'])

    if reply_like:
        if not str(draft.get('subject', '')).strip():
            draft['subject'] = 'Re: Ihre Nachricht'
        if not str(draft.get('body', '')).strip() or str(draft.get('body', '')).strip() == str(prompt or '').strip():
            draft['body'] = (
                'Sehr geehrte Damen und Herren,\n\n'
                'vielen Dank für Ihre Information. Ich werde mir die Dokumente zeitnah ansehen.\n\n'
                'Mit freundlichen Grüßen\n'
                'Vinzenz Schächner'
            )
    elif not str(draft.get('body', '')).strip() or str(draft.get('body', '')).strip() == str(prompt or '').strip():
        draft['body'] = ''

    return {
        'type': 'email',
        'title': 'E-Mail verfassen' if is_german else 'Compose email',
        'subtitle': 'Vorlage erstellen, prüfen und direkt senden' if is_german else 'Draft, review, and send directly',
        'description': (
            'Fülle Empfänger, Betreff und Nachricht aus oder passe den Vorschlag an.'
            if is_german else
            'Fill in recipient, subject, and message or adjust the draft.'
        ),
        'to': draft.get('to', ''),
        'subject': draft.get('subject', ''),
        'body': draft.get('body', ''),
        'cc': draft.get('cc', ''),
        'bcc': draft.get('bcc', ''),
        'requires_confirmation': True,
        'confirmation_text': 'Bitte bestätige den Versand manuell, bevor die Nachricht gesendet wird.' if is_german else 'Please confirm the send manually before the message is sent.',
        'draft_kind': 'reply' if reply_like else 'compose',
        'quick_templates': [
            {'label': 'WEB.DE', 'preset': 'web.de'},
            {'label': 'GMX', 'preset': 'gmx.de'},
            {'label': 'Gmail', 'preset': 'gmail.com'},
            {'label': 'Outlook', 'preset': 'outlook.com'}
        ]
    }


def _build_contact_card(prompt: str, contacts: List[Dict[str, Any]], language: str = 'de') -> Dict[str, Any]:
    """Build an interactive contacts card for the frontend."""
    is_german = str(language or '').lower().startswith('de')
    contact_items = []

    for contact in contacts[:6]:
        title = str(contact.get('title', '')).strip() or str(contact.get('full_name', '')).strip() or 'Kontakt'
        subline = str(contact.get('subline', '')).strip()
        emails = []
        for email_value in contact.get('email', []) or []:
            email_value = str(email_value).strip()
            if email_value and email_value not in emails:
                emails.append(email_value)

        if not emails:
            for candidate in [contact.get('subline', ''), contact.get('title', '')]:
                extracted = _extract_email_from_text(candidate)
                if extracted and extracted not in emails:
                    emails.append(extracted)

        if isinstance(contact.get('attributes'), dict):
            for value in contact['attributes'].values():
                extracted = _extract_email_from_text(value)
                if extracted and extracted not in emails:
                    emails.append(extracted)

        contact_items.append({
            'title': title,
            'subline': subline,
            'emails': emails,
            'primary_email': emails[0] if emails else '',
            'resource_url': contact.get('resource_url', ''),
            'icon': contact.get('icon', ''),
            'organization': contact.get('organization', '')
        })

    return {
        'type': 'contacts',
        'title': 'Kontakte' if is_german else 'Contacts',
        'subtitle': f"{len(contact_items)} Treffer" if is_german else f"{len(contact_items)} matches",
        'description': (
            'Wähle einen Kontakt aus, um direkt eine E-Mail zu schreiben oder die Suche zu verfeinern.'
            if is_german else
            'Select a contact to draft an email or refine the search.'
        ),
        'query': prompt,
        'contacts': contact_items,
        'suggested_email_prompt': 'Schreibe eine E-Mail an {email}' if is_german else 'Compose an email to {email}'
    }


def _build_email_source_card(
    subject: str,
    sender: str,
    date_str: str,
    folder: str,
    body_preview: str,
    label: str = 'E-Mail'
) -> Dict[str, Any]:
    """Build a source-style card for a concrete email result."""
    return {
        'source_type': 'email',
        'source': sender or label,
        'document': subject or label,
        'path': folder or 'INBOX',
        'chunk_id': None,
        'matched_sentence': body_preview[:240] if body_preview else subject,
        'content_preview': body_preview[:600] if body_preview else subject,
        'similarity_score': 0.95,
        'subject': subject,
        'sender': sender,
        'date': date_str,
        'folder': folder or 'INBOX'
    }


def _build_contact_source_card(contact: Dict[str, Any], label: str = 'Kontakt') -> Dict[str, Any]:
    """Build a source-style card for a matched contact used in email compose/reply."""
    title = str(contact.get('title', '')).strip() or str(contact.get('full_name', '')).strip() or label
    emails: List[str] = []
    for value in contact.get('email', []) or []:
        email_value = str(value or '').strip()
        if email_value and email_value not in emails:
            emails.append(email_value)

    return {
        'source_type': 'email',
        'source': title,
        'document': emails[0] if emails else title,
        'path': str(contact.get('addressbook_name') or contact.get('organization') or label),
        'chunk_id': None,
        'matched_sentence': str(contact.get('subline', '')).strip() or ', '.join(emails),
        'content_preview': ', '.join(emails) if emails else str(contact.get('subline', '')).strip(),
        'similarity_score': 0.8,
        'contact': contact
    }


def _build_ui_cards(prompt: str, intent: str, calendar_ctx: Optional[Dict], todo_ctx: Optional[Dict], photo_ctx: Optional[Dict] = None, email_ctx: Optional[Dict] = None, nextcloud_search_ctx: Optional[Dict] = None, username: str = None, language: str = 'de') -> List[Dict]:
    """Return structured ui_cards metadata for frontend interactive cards."""
    cards: List[Dict] = []

    if calendar_ctx and (intent in ['calendar', 'mixed'] or should_use_calendar(prompt)):
        cfg = _infer_calendar_card_config(prompt)
        cards.append({
            'type': 'calendar',
            'title': 'Calendar',
            'default_view': cfg['view'],
            'anchor_date': cfg['date']
        })

    if todo_ctx and (intent in ['tasks', 'mixed'] or should_use_tasks(prompt) or is_todo_query(prompt)):
        cfg = _infer_task_card_config(prompt)
        cards.append({
            'type': 'tasks',
            'title': 'Tasks',
            'default_scope': cfg['scope'],
            'anchor_date': cfg['date']
        })

    if photo_ctx:
        photo_metadata = photo_ctx.get('metadata', {}) if isinstance(photo_ctx, dict) else {}
        photo_results = photo_metadata.get('photos', []) or []
        if photo_results:
            people_options: List[str] = []
            for photo in photo_results:
                for person in photo.get('people', []) or []:
                    name = person if isinstance(person, str) else person.get('name', '')
                    name = str(name).strip()
                    if name and name not in people_options:
                        people_options.append(name)

            detected_people = [str(name).strip() for name in photo_metadata.get('detected_people', []) if str(name).strip()]
            similar_people = [str(name).strip() for name in photo_metadata.get('similar_people', []) if str(name).strip()]
            card_people = []
            for name in detected_people + similar_people + people_options:
                if name and name not in card_people:
                    card_people.append(name)

            cards.append({
                'type': 'photos',
                'title': 'Fotos',
                'subtitle': f"{len(photo_results)} Treffer",
                'query': prompt,
                'date_phrase': photo_metadata.get('date_phrase', ''),
                'date_from': photo_metadata.get('date_from', ''),
                'date_to': photo_metadata.get('date_to', ''),
                'selected_people': detected_people[:2],
                'people_options': card_people[:6],
                'date_options': [
                    {'label': 'Heute', 'value': 'heute'},
                    {'label': 'Gestern', 'value': 'gestern'},
                    {'label': 'Letzte Woche', 'value': 'letzte Woche'},
                    {'label': 'Diesen Monat', 'value': 'diesen Monat'}
                ],
                'photos': photo_results[:4]
            })

    if is_email_send_query(prompt):
        recipient_resolution = resolve_email_contacts_for_prompt(prompt, username=username)
        if recipient_resolution.get('has_contact_match') and recipient_resolution.get('needs_selection'):
            contact_cards = recipient_resolution.get('contacts', [])
            if contact_cards:
                cards.append(_build_contact_card(prompt, contact_cards, language))
            return cards

        email_card = _build_email_card(prompt, language)
        if recipient_resolution.get('best_email') and not email_card.get('to'):
            email_card['to'] = recipient_resolution['best_email']
        elif recipient_resolution.get('has_contact_match') and not email_card.get('to'):
            contact_cards = recipient_resolution.get('contacts', [])
            if contact_cards:
                cards.append(_build_contact_card(prompt, contact_cards, language))
        cards.append(email_card)
    elif email_ctx and intent in ['email', 'mixed']:
        cards.append(_build_email_card(prompt, language))

    if nextcloud_search_ctx and (is_contact_query(prompt) or is_email_send_query(prompt)):
        search_metadata = nextcloud_search_ctx.get('metadata', {}) if isinstance(nextcloud_search_ctx, dict) else {}
        search_results = search_metadata.get('results', []) or []
        contact_results = [result for result in search_results if str(result.get('provider', '')).lower() == 'contacts']
        if contact_results and not any(card.get('type') == 'contacts' for card in cards):
            cards.append(_build_contact_card(prompt, contact_results, language))

    return cards

# Try to migrate existing data on startup
def try_migrate_existing_data():
    """Try to migrate existing JSON cache to database"""
    try:
        cache_file = "knowledge_cache.json"
        if os.path.exists(cache_file) and knowledge_base.db:
            # Check if database is empty
            stats = knowledge_base.db.get_document_stats()
            if stats.get('chunks', 0) == 0:
                logger.info("Migrating existing cache to database...")
                
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                chunks = cache_data.get('chunks', [])
                sources = cache_data.get('sources', [])
                
                if chunks and sources:
                    # Simple migration
                    for i, chunk in enumerate(chunks):
                        source = sources[i] if i < len(sources) else {'file': 'migrated', 'type': 'text'}
                        
                        doc_id = knowledge_base.db.add_document(
                            name=source.get('file', 'migrated'),
                            path=source.get('path', 'migrated'),
                            file_type=source.get('type', 'text'),
                            metadata=source
                        )
                        
                        knowledge_base.db.add_chunks(doc_id, [chunk])
                    
                    logger.info(f"Migrated {len(chunks)} chunks to database")
                    
                    # Schedule embedding update
                    if knowledge_base.search_engine:
                        try:
                            knowledge_base.search_engine.update_missing_embeddings()
                        except Exception as e:
                            logger.warning(f"Embedding update scheduled: {str(e)}")
    except Exception as e:
        logger.warning(f"Migration failed: {str(e)}")

@app.route('/api/indexing/start', methods=['POST'])
def start_indexing():
    """Startet die Hintergrund-Indexierung"""
    data = request.json
    nextcloud_config = data.get('nextcloud_config')
    
    # Wenn keine Konfiguration übergeben, versuche die gespeicherte zu laden
    if not nextcloud_config:
        saved_config = indexing_manager.get_config(mask_password=False)  # Intern volles Passwort
        if not saved_config.get('password'):
            return jsonify({'error': 'Keine Nextcloud Konfiguration vorhanden'}), 400
        nextcloud_config = saved_config
    
    try:
        success = indexing_manager.start_indexing(nextcloud_config)
        
        if success:
            return jsonify({
                'status': 'started',
                'message': 'Indexierung wurde gestartet'
            })
        else:
            return jsonify({
                'error': 'Indexierung läuft bereits oder Konfiguration fehlt'
            }), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/indexing/stop', methods=['POST'])
def stop_indexing():
    """Stoppt die aktuelle Indexierung"""
    try:
        indexing_manager.stop_indexing()
        return jsonify({
            'status': 'stopped',
            'message': 'Indexierung wurde gestoppt'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/indexing/progress', methods=['GET'])
def get_indexing_progress():
    """Gibt den aktuellen Indexierungs-Fortschritt zurück"""
    try:
        progress = indexing_manager.get_progress()
        return jsonify(progress)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/indexing/config', methods=['GET', 'POST'])
def indexing_config():
    """Lädt oder speichert die Indexierung-Konfiguration"""
    if request.method == 'GET':
        try:
            # Für Frontend-Anfragen Passwort maskieren
            config = indexing_manager.get_config(mask_password=True)
            return jsonify(config)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.json
            url = data.get('url')
            username = data.get('username')
            password = data.get('password')
            remote_path = data.get('path', '/')
            
            if not all([url, username, password]):
                return jsonify({'error': 'URL, Username und Password werden benötigt'}), 400
            
            indexing_manager.save_nextcloud_config(url, username, password, remote_path)
            refresh_simple_calendar_manager()
            
            return jsonify({
                'status': 'saved',
                'message': 'Konfiguration wurde gespeichert'
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/indexing/path', methods=['GET', 'POST'])
def indexing_path_config():
    """Lädt oder speichert nur den Indexierungs-Pfad"""
    if request.method == 'GET':
        try:
            config = indexing_manager.get_config(mask_password=False)
            saved_path = config.get('path', '/') if config else '/'

            # For UI convenience, represent root as empty input value.
            return jsonify({'path': '' if saved_path == '/' else saved_path})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.json or {}
            path_input = (data.get('path') or '').strip()
            normalized_path = path_input if path_input else '/'

            config = indexing_manager.get_config(mask_password=False)
            if not config or not all([config.get('url'), config.get('username'), config.get('password')]):
                return jsonify({'error': 'Nextcloud configuration required before saving path'}), 400

            indexing_manager.save_nextcloud_config(
                config['url'],
                config['username'],
                config['password'],
                normalized_path
            )
            refresh_simple_calendar_manager()

            return jsonify({
                'status': 'saved',
                'message': 'Path saved successfully',
                'path': '' if normalized_path == '/' else normalized_path
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/nextcloud/oauth/authorize', methods=['POST'])
def nextcloud_oauth_authorize():
    """
    Initiiert den OAuth2 Flow mit Nextcloud
    Erwartet Nextcloud URL, Client ID und Client Secret
    """
    try:
        data = request.json
        nextcloud_url = data.get('nextcloud_url', '').rstrip('/')
        client_id = data.get('client_id', '')
        client_secret = data.get('client_secret', '')

        if not all([nextcloud_url, client_id, client_secret]):
            return jsonify({'error': 'Missing required parameters'}), 400

        # Redirect URI - muss mit der Nextcloud OAuth2 App Konfiguration übereinstimmen
        redirect_uri = request.url_root.rstrip('/') + '/api/nextcloud/oauth/callback'

        # Erstelle OAuth2 Provider
        oauth_provider = OAuth2NextcloudProvider({
            'nextcloud_url': nextcloud_url,
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'files'
        })

        # Generiere Authorization URL
        authorization_url, state = oauth_provider.get_authorization_url(redirect_uri)

        # Speichere State und OAuth2 Config in Session für späteren Callback
        session['oauth2_state'] = state
        session['oauth2_nextcloud_url'] = nextcloud_url
        session['oauth2_client_id'] = client_id
        session['oauth2_client_secret'] = client_secret
        session['oauth2_redirect_uri'] = redirect_uri

        logger.info(f"OAuth2 Authorization initiated for {nextcloud_url}")

        return jsonify({
            'authorization_url': authorization_url,
            'state': state
        })

    except Exception as e:
        logger.error(f"Error initiating OAuth2: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/nextcloud/oauth/callback', methods=['GET'])
def nextcloud_oauth_callback():
    """
    Nextcloud OAuth2 Callback Handler
    Wird aufgerufen nach erfolgreicher Authentifizierung auf Nextcloud
    """
    try:
        # Hole Authorization Code
        authorization_code = request.args.get('code')
        state = request.args.get('state')

        if not authorization_code:
            return jsonify({'error': 'Missing authorization code'}), 400

        # Verifiziere State
        if state != session.get('oauth2_state'):
            logger.warning(f"State mismatch in OAuth2 callback")
            return jsonify({'error': 'Invalid state parameter'}), 400

        # Hole Konfiguration aus Session
        nextcloud_url = session.get('oauth2_nextcloud_url')
        client_id = session.get('oauth2_client_id')
        client_secret = session.get('oauth2_client_secret')
        redirect_uri = session.get('oauth2_redirect_uri')

        if not all([nextcloud_url, client_id, client_secret]):
            return jsonify({'error': 'OAuth2 configuration not found in session'}), 400

        # Erstelle OAuth2 Provider
        oauth_provider = OAuth2NextcloudProvider({
            'nextcloud_url': nextcloud_url,
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'files'
        })

        # Tausche Code gegen Token aus
        access_token, refresh_token = oauth_provider.exchange_code_for_token(
            authorization_code,
            redirect_uri
        )

        logger.info(f"OAuth2 token obtained successfully for {nextcloud_url}")

        # Hole User Info
        user_info = oauth_provider.get_user_info()
        username = user_info.get('id', 'unknown')

        logger.info(f"Authenticated as user: {username}")

        # Speichere OAuth2 Konfiguration
        oauth_config = {
            'nextcloud_url': nextcloud_url,
            'client_id': client_id,
            'client_secret': client_secret,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'username': username,
            'auth_type': 'oauth2',
            'scope': 'files'
        }

        # Speichere in Indexing Manager
        config_file = os.path.join(CONFIG_DIR, 'nextcloud_oauth2.json')
        with open(config_file, 'w') as f:
            json.dump(oauth_config, f, indent=2)

        # Speichere auch die Basis-Konfiguration für Indexing
        indexing_manager.save_nextcloud_config(
            nextcloud_url,
            username,
            '',  # Leeres Password, verwenden zu stattdessen OAuth2 Token
            '/'
        )
        refresh_simple_calendar_manager()
        initialize_tasks_from_config()

        # Cleanup Session
        session.pop('oauth2_state', None)
        session.pop('oauth2_nextcloud_url', None)
        session.pop('oauth2_client_id', None)
        session.pop('oauth2_client_secret', None)
        session.pop('oauth2_redirect_uri', None)

        # Erfolgreiche Antwort für Frontend
        return jsonify({
            'status': 'success',
            'message': 'OAuth2 authentication successful',
            'username': username,
            'nextcloud_url': nextcloud_url
        })

    except Exception as e:
        logger.error(f"Error in OAuth2 callback: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/nextcloud/oauth/config', methods=['GET'])
def nextcloud_oauth_config():
    """
    Gibt die aktuelle OAuth2 Konfiguration zurück (ohne sensitive Daten)
    """
    try:
        config_file = os.path.join(CONFIG_DIR, 'nextcloud_oauth2.json')
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Entferne sensitive Daten
            safe_config = {
                'nextcloud_url': config.get('nextcloud_url', ''),
                'username': config.get('username', ''),
                'auth_type': config.get('auth_type', ''),
                'configured': True
            }
            return jsonify(safe_config)
        else:
            return jsonify({'configured': False})

    except Exception as e:
        logger.error(f"Error getting OAuth2 config: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/nextcloud/loginflow/start', methods=['POST'])
def nextcloud_loginflow_start():
    """Startet Nextcloud Login Flow v2 ohne manuelle OAuth-Client-Registrierung."""
    try:
        data = request.json or {}
        nextcloud_url = data.get('nextcloud_url', '').rstrip('/')

        if not nextcloud_url:
            return jsonify({'error': 'nextcloud_url parameter required'}), 400

        # Basic URL validation against Nextcloud status endpoint.
        status_url = f"{nextcloud_url}/status.php"
        status_res = requests.get(status_url, timeout=8)
        status_res.raise_for_status()
        status_data = status_res.json()
        if not status_data.get('installed', False):
            return jsonify({'error': 'Invalid Nextcloud instance'}), 400

        flow_url = f"{nextcloud_url}/index.php/login/v2"
        flow_res = requests.post(
            flow_url,
            headers={'User-Agent': NEXTCLOUD_LOGINFLOW_USER_AGENT},
            timeout=10
        )
        flow_res.raise_for_status()
        flow_data = flow_res.json()

        login_url = flow_data.get('login')
        poll_data = flow_data.get('poll', {})
        poll_token = poll_data.get('token')
        poll_endpoint = poll_data.get('endpoint')

        if not all([login_url, poll_token, poll_endpoint]):
            return jsonify({'error': 'Nextcloud login flow response incomplete'}), 502

        session['loginflow_nextcloud_url'] = nextcloud_url
        session['loginflow_poll_token'] = poll_token
        session['loginflow_poll_endpoint'] = poll_endpoint
        session.permanent = True

        logger.info(f"Nextcloud Login Flow v2 started for {nextcloud_url}")
        return jsonify({'status': 'started', 'login_url': login_url})
    except Exception as e:
        logger.error(f"Error starting Nextcloud Login Flow v2: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/nextcloud/loginflow/poll', methods=['GET'])
def nextcloud_loginflow_poll():
    """Pollt den Nextcloud Login Flow v2 Status und speichert bei Erfolg App-Credentials."""
    try:
        nextcloud_url = session.get('loginflow_nextcloud_url')
        poll_token = session.get('loginflow_poll_token')
        poll_endpoint = session.get('loginflow_poll_endpoint')

        if not all([nextcloud_url, poll_token, poll_endpoint]):
            return jsonify({'error': 'No active login flow', 'status': 'idle'}), 400

        poll_res = requests.post(
            poll_endpoint,
            headers={'User-Agent': NEXTCLOUD_LOGINFLOW_USER_AGENT},
            data={'token': poll_token},
            timeout=10
        )

        if poll_res.status_code in [404, 202]:
            return jsonify({'status': 'pending'})

        poll_res.raise_for_status()
        poll_data = poll_res.json()

        username = poll_data.get('loginName')
        app_password = poll_data.get('appPassword')
        server = (poll_data.get('server') or nextcloud_url).rstrip('/')

        if not all([username, app_password]):
            return jsonify({'status': 'pending'})

        nextcloud_config = {
            'nextcloud_url': server,
            'username': username,
            'password': app_password,
            'auth_type': 'login_flow_v2',
            'display_name': username
        }

        config_file = os.path.join(CONFIG_DIR, 'nextcloud_config.json')
        with open(config_file, 'w') as f:
            json.dump(nextcloud_config, f, indent=2)

        indexing_manager.save_nextcloud_config(server, username, app_password, '/')
        refresh_simple_calendar_manager()
        initialize_tasks_from_config()

        session.pop('loginflow_nextcloud_url', None)
        session.pop('loginflow_poll_token', None)
        session.pop('loginflow_poll_endpoint', None)

        logger.info(f"Nextcloud Login Flow v2 successful for {username}@{server}")
        return jsonify({
            'status': 'connected',
            'username': username,
            'display_name': username,
            'nextcloud_url': server
        })
    except Exception as e:
        logger.error(f"Error polling Nextcloud Login Flow v2: {str(e)}")
        return jsonify({'error': str(e), 'status': 'error'}), 500


@app.route('/api/nextcloud/login', methods=['POST'])
def nextcloud_direct_login():
    """
    Vereinfachter Nextcloud Direct Login
    Der Nutzer gibt nur URL + Username + Password ein
    Keine OAuth2-App-Registration nötig!
    """
    try:
        data = request.json
        nextcloud_url = data.get('nextcloud_url', '').rstrip('/')
        username = data.get('username', '')
        password = data.get('password', '')

        if not all([nextcloud_url, username, password]):
            return jsonify({'error': 'Missing required parameters'}), 400

        # Erstelle Direct Provider
        direct_provider = DirectNextcloudProvider({
            'nextcloud_url': nextcloud_url,
            'username': username,
            'password': password
        })

        # Validiere Config
        if not direct_provider.validate_config():
            return jsonify({'error': 'Invalid configuration'}), 400

        # Teste Verbindung
        success, message = direct_provider.test_connection()
        if not success:
            return jsonify({'error': message}), 401

        logger.info(f"Direct login successful for {username}@{nextcloud_url}")

        # Hole User Info
        user_info = direct_provider.get_user_info()

        # Speichere Konfiguration
        nextcloud_config = {
            'nextcloud_url': nextcloud_url,
            'username': username,
            'password': password,
            'auth_type': 'direct',
            'display_name': user_info.get('displayName', username)
        }

        config_file = os.path.join(CONFIG_DIR, 'nextcloud_config.json')
        with open(config_file, 'w') as f:
            json.dump(nextcloud_config, f, indent=2)

        # Speichere auch die Basis-Konfiguration für Indexing
        indexing_manager.save_nextcloud_config(
            nextcloud_url,
            username,
            password,
            '/'
        )
        refresh_simple_calendar_manager()
        initialize_tasks_from_config()

        return jsonify({
            'status': 'success',
            'message': f'Logged in successfully as {user_info.get("displayName", username)}',
            'username': username,
            'nextcloud_url': nextcloud_url,
            'display_name': user_info.get('displayName', username)
        })

    except Exception as e:
        logger.error(f"Error in direct login: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/nextcloud/config', methods=['GET'])
def nextcloud_config_get():
    """
    Gibt die aktuelle Nextcloud Konfiguration zurück (ohne Passwort!)
    """
    try:
        config_file = os.path.join(CONFIG_DIR, 'nextcloud_config.json')
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Entferne Passwort
            safe_config = {
                'nextcloud_url': config.get('nextcloud_url', ''),
                'username': config.get('username', ''),
                'display_name': config.get('display_name', ''),
                'auth_type': config.get('auth_type', ''),
                'configured': True
            }
            return jsonify(safe_config)
        else:
            return jsonify({'configured': False})

    except Exception as e:
        logger.error(f"Error getting config: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/nextcloud/disconnect', methods=['POST'])
def nextcloud_disconnect():
    """Trennt die Nextcloud-Verbindung und entfernt gespeicherte Credentials."""
    global simple_calendar_manager, tasks_enabled
    try:
        removed_files = []

        config_file = os.path.join(CONFIG_DIR, 'nextcloud_config.json')
        if os.path.exists(config_file):
            os.remove(config_file)
            removed_files.append('nextcloud_config.json')

        legacy_oauth_file = os.path.join(CONFIG_DIR, 'nextcloud_oauth2.json')
        if os.path.exists(legacy_oauth_file):
            os.remove(legacy_oauth_file)
            removed_files.append('nextcloud_oauth2.json')

        # Reset indexing credentials so indexing cannot start with stale auth data.
        indexing_manager.save_nextcloud_config('', '', '', '/')
        simple_calendar_manager = None
        task_manager.tasks_client = None
        tasks_enabled = False

        # Cleanup potentially remaining auth session state.
        session.pop('pkce_code_verifier', None)
        session.pop('pkce_nextcloud_url', None)
        session.pop('loginflow_nextcloud_url', None)
        session.pop('loginflow_poll_token', None)
        session.pop('loginflow_poll_endpoint', None)
        session.pop('oauth2_state', None)
        session.pop('oauth2_nextcloud_url', None)
        session.pop('oauth2_client_id', None)
        session.pop('oauth2_client_secret', None)
        session.pop('oauth2_redirect_uri', None)

        logger.info(f"Nextcloud disconnected. Removed files: {removed_files}")

        return jsonify({
            'status': 'success',
            'message': 'Nextcloud connection removed',
            'removed_files': removed_files
        })
    except Exception as e:
        logger.error(f"Error disconnecting Nextcloud: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/sources', methods=['GET'])
def get_knowledge_sources():
    """Gibt die Quellen der Wissensbasis zurück"""
    return jsonify({
        'sources': knowledge_base.document_sources,
        'total_chunks': len(knowledge_base.knowledge_chunks)
    })

@app.route('/api/knowledge/status', methods=['GET'])
def knowledge_status():
    """Gibt den Status der Wissensdatenbank zurück"""
    try:
        if knowledge_base.search_engine:
            stats = knowledge_base.search_engine.get_stats()
            return jsonify({
                'chunks_loaded': stats.get('chunks', 0),
                'documents_count': stats.get('documents', 0),
                'embeddings_count': stats.get('embeddings', 0),
                'index_size': stats.get('index_size', 0),
                'total_words': stats.get('total_words', 0),
                'file_types': stats.get('file_types', {}),
                'model_name': stats.get('model_name', ''),
                'semantic_search_available': True,
                'database_path': knowledge_base.db.db_path if knowledge_base.db else None
            })
        else:
            # Fallback status
            chunks_count = len(knowledge_base.knowledge_chunks)
            return jsonify({
                'chunks_loaded': chunks_count,
                'semantic_search_available': False,
                'fallback_mode': True
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/graph-data', methods=['GET'])
def get_knowledge_graph_data():
    """Gibt Daten für Knowledge Graph Visualization zurück"""
    try:
        return jsonify({
            'chunks': knowledge_base.knowledge_chunks,
            'sources': knowledge_base.document_sources
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/migrate', methods=['POST'])
def migrate_knowledge():
    """Migrate existing JSON cache to new database"""
    try:
        cache_file = "knowledge_cache.json"
        if not os.path.exists(cache_file):
            return jsonify({'error': 'No cache file found'}), 404
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        chunks = cache_data.get('chunks', [])
        sources = cache_data.get('sources', [])
        
        if not chunks:
            return jsonify({'error': 'No data in cache'}), 400
        
        # Clear existing database
        if knowledge_base.db:
            knowledge_base.db.connection.execute("DELETE FROM chunks")
            knowledge_base.db.connection.execute("DELETE FROM documents")
            knowledge_base.db.connection.commit()
        
        # Group chunks by document
        doc_chunks = {}
        for i, chunk in enumerate(chunks):
            source = sources[i] if i < len(sources) else {'file': 'unknown', 'type': 'text'}
            doc_key = source.get('path', source.get('file', 'unknown'))
            
            if doc_key not in doc_chunks:
                doc_chunks[doc_key] = {
                    'chunks': [],
                    'source': source
                }
            doc_chunks[doc_key]['chunks'].append(chunk)
        
        # Add to database
        total_chunks = 0
        for doc_key, doc_data in doc_chunks.items():
            source = doc_data['source']
            doc_chunks_list = doc_data['chunks']
            
            doc_id = knowledge_base.db.add_document(
                name=source.get('file', os.path.basename(doc_key)),
                path=source.get('path', doc_key),
                file_type=source.get('type', 'text'),
                metadata=source
            )
            
            chunk_ids = knowledge_base.db.add_chunks(doc_id, doc_chunks_list)
            total_chunks += len(chunk_ids)
        
        # Update search engine
        if knowledge_base.search_engine:
            if hasattr(knowledge_base.search_engine, 'rebuild_index'):
                knowledge_base.search_engine.rebuild_index()
            else:
                logger.info("Search engine doesn't support index rebuilding")
        
        return jsonify({
            'status': 'success',
            'documents_migrated': len(doc_chunks),
            'chunks_migrated': total_chunks,
            'message': f'Migrated {total_chunks} chunks from {len(doc_chunks)} documents'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/create', methods=['POST'])
def create_event():
    """Erstellt ein neues Kalendereignis"""
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Keine Nachricht erhalten'}), 400
        
        # Extrahiere Informationen aus der Nachricht
        event_info = extract_event_info_from_message(message)
        
        # Hole verfügbare Kalender für UI
        calendars = []
        if simple_calendar_manager:
            calendars = simple_calendar_manager.get_calendars()
        
        # Wenn Informationen fehlen, gib interaktive UI zurück
        if event_info['missing_info']:
            return jsonify({
                'requires_input': True,
                'missing_info': event_info['missing_info'],
                'extracted_info': {
                    'title': event_info['title'],
                    'start_time': event_info['start_time'],
                    'end_time': event_info['end_time'],
                    'location': event_info['location'],
                    'calendar_name': event_info['calendar_name']
                },
                'available_calendars': calendars,
                'message': 'Bitte fehlende Informationen angeben'
            })
        
        # Versuche Ereignis zu erstellen
        result = create_calendar_event(
            title=event_info['title'],
            start_time=event_info['start_time'],
            end_time=event_info['end_time'],
            calendar_name=event_info['calendar_name'],
            location=event_info['location'],
            description=message
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in create_event: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/create-with-details', methods=['POST'])
def create_event_with_details():
    """Erstellt Ereignis mit detaillierten Informationen"""
    try:
        data = request.json
        
        title = data.get('title')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        calendar_name = data.get('calendar_name')
        location = data.get('location')
        description = data.get('description')
        
        if not title or not start_time:
            return jsonify({'error': 'Titel und Startzeit sind erforderlich'}), 400
        
        result = create_calendar_event(
            title=title,
            start_time=start_time,
            end_time=end_time,
            calendar_name=calendar_name,
            location=location,
            description=description
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in create_event_with_details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/calendars', methods=['GET'])
def get_calendars():
    """Gibt verfügbare Kalender zurück"""
    try:
        # Always refresh to ensure latest Login Flow credentials are used.
        refresh_simple_calendar_manager()

        if not simple_calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar. Bitte zuerst Nextcloud verbinden.'}), 400
        
        calendars = simple_calendar_manager.get_calendars()
        return jsonify({
            'calendars': calendars,
            'count': len(calendars)
        })
        
    except Exception as e:
        logger.error(f"Error getting calendars: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/calendar/config', methods=['GET', 'POST'])
def calendar_config():
    """Liest oder speichert Kalender-Konfiguration (z.B. Standard-Kalender)."""
    try:
        if request.method == 'GET':
            config = load_calendar_config()
            return jsonify(config)

        data = request.json or {}
        default_calendar_name = str(data.get('default_calendar_name', '')).strip()

        save_calendar_config(default_calendar_name)

        return jsonify({
            'status': 'saved',
            'default_calendar_name': default_calendar_name
        })
    except Exception as e:
        logger.error(f"Error in calendar_config: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/debug/calendars', methods=['GET'])
def debug_calendars():
    """Debug endpoint: zeigt rohe CalDAV-Kalender-Responses inkl. Resource-Typen."""
    try:
        if not simple_calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 500

        url = f"{simple_calendar_manager.nextcloud_url}/remote.php/dav/calendars/{simple_calendar_manager.username}/"
        response = simple_calendar_manager.session.request('PROPFIND', url, headers={'Depth': '1'})

        debug_entries = []
        if response.status_code == 207:
            root = ET.fromstring(response.text)
            namespaces = {
                'd': 'DAV:',
                'c': 'urn:ietf:params:xml:ns:caldav',
                'cs': 'http://calendarserver.org/ns/'
            }

            for response_elem in root.findall('.//d:response', namespaces):
                href_elem = response_elem.find('.//d:href', namespaces)
                displayname_elem = response_elem.find('.//d:displayname', namespaces)

                resourcetype_elem = response_elem.find('.//d:resourcetype', namespaces)
                resource_types = []
                if resourcetype_elem is not None:
                    for child in list(resourcetype_elem):
                        tag = child.tag
                        if '}' in tag:
                            tag = tag.split('}', 1)[1]
                        resource_types.append(tag)

                debug_entries.append({
                    'display_name': displayname_elem.text if displayname_elem is not None else '',
                    'href': href_elem.text if href_elem is not None else '',
                    'is_calendar': response_elem.find('.//d:resourcetype/c:calendar', namespaces) is not None,
                    'is_subscribed': response_elem.find('.//d:resourcetype/cs:subscribed', namespaces) is not None,
                    'resource_types': resource_types
                })

        return jsonify({
            'status_code': response.status_code,
            'calendar_count': len(debug_entries),
            'entries': debug_entries
        })

    except Exception as e:
        logger.error(f"Error in debug_calendars: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/update-embeddings', methods=['POST'])
def update_embeddings():
    """Update embeddings for chunks that don't have them"""
    try:
        if not knowledge_base.search_engine:
            return jsonify({'error': 'Semantic search not available'}), 400
        
        knowledge_base.search_engine.update_missing_embeddings()
        
        return jsonify({
            'status': 'success',
            'message': 'Embeddings updated successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/stats', methods=['GET'])
def training_stats():
    """Gibt Trainings-Statistiken zurück"""
    try:
        stats = training_manager.get_training_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/reload', methods=['POST'])
def reload_knowledge():
    """Lädt die Wissensbasis neu (aus Cache oder Datei)"""
    try:
        # Cache direkt laden und Daten manuell setzen
        import json
        import os
        
        cache_file = "knowledge_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            knowledge_base.knowledge_chunks = cache_data.get('chunks', [])
            knowledge_base.document_sources = cache_data.get('sources', [])
            
            return jsonify({
                'status': 'reloaded',
                'source': 'cache',
                'chunks_loaded': len(knowledge_base.knowledge_chunks)
            })
        else:
            knowledge_base.load_knowledge()
            return jsonify({
                'status': 'reloaded',
                'source': 'file',
                'chunks_loaded': len(knowledge_base.knowledge_chunks)
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ollama/status', methods=['GET'])
def ollama_status():
    """Prüft den Ollama-Verbindungsstatus"""
    return jsonify({
        'connected': ollama_client.check_connection(),
        'base_url': ollama_client.base_url,
        'model': ollama_client.model
    })


@app.route('/api/ollama/models', methods=['GET'])
def ollama_models():
    """Gibt verfügbare Ollama-Modelle für die UI-Auswahl zurück."""
    try:
        models = ollama_client.list_models()
        if ollama_client.model and ollama_client.model not in models:
            models.insert(0, ollama_client.model)

        return jsonify({
            'connected': True,
            'base_url': ollama_client.base_url,
            'current_model': ollama_client.model,
            'models': models
        })
    except Exception as e:
        fallback_models = [ollama_client.model] if ollama_client.model else []
        return jsonify({
            'connected': False,
            'base_url': ollama_client.base_url,
            'current_model': ollama_client.model,
            'models': fallback_models,
            'error': str(e)
        })


@app.route('/api/ai/config', methods=['GET', 'POST'])
def ai_config():
    """Liest oder speichert die AI-Konfiguration (aktuell Ollama)."""
    try:
        if request.method == 'GET':
            return jsonify({
                'provider': 'ollama',
                'base_url': ollama_client.base_url,
                'model': ollama_client.model,
                'connected': ollama_client.check_connection()
            })

        data = request.json or {}
        base_url = str(data.get('base_url', '')).strip().rstrip('/')
        model = str(data.get('model', '')).strip()

        if not base_url or not model:
            return jsonify({'error': 'base_url und model sind erforderlich'}), 400

        if not (base_url.startswith('http://') or base_url.startswith('https://')):
            return jsonify({'error': 'base_url muss mit http:// oder https:// beginnen'}), 400

        ollama_client.update_config(base_url, model)
        save_ai_config(base_url, model)

        return jsonify({
            'status': 'saved',
            'provider': 'ollama',
            'base_url': ollama_client.base_url,
            'model': ollama_client.model,
            'connected': ollama_client.check_connection()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/test', methods=['POST'])
def ai_test():
    """Testet die aktuelle AI-Konfiguration mit einem kurzen Prompt."""
    try:
        data = request.json or {}
        prompt = str(data.get('prompt', 'Antworte nur mit: OK')).strip()

        if not prompt:
            return jsonify({'error': 'prompt darf nicht leer sein'}), 400

        start_time = time.time()
        response = ollama_client.chat([
            {'role': 'user', 'content': prompt}
        ])
        duration_ms = int((time.time() - start_time) * 1000)

        if 'error' in response:
            return jsonify({
                'status': 'error',
                'connected': False,
                'base_url': ollama_client.base_url,
                'model': ollama_client.model,
                'duration_ms': duration_ms,
                'error': response['error']
            }), 502

        message = response.get('message', {}) or {}
        content = str(message.get('content', '')).strip()

        return jsonify({
            'status': 'ok',
            'connected': True,
            'base_url': ollama_client.base_url,
            'model': ollama_client.model,
            'duration_ms': duration_ms,
            'response': content,
            'response_preview': content[:280]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Kalender API Endpunkte
@app.route('/api/calendar/status', methods=['GET'])
def calendar_status():
    """Gibt Kalender-Status zurück"""
    try:
        if not calendar_enabled:
            return jsonify({
                'enabled': False,
                'message': 'Kalender-Funktionalität ist deaktiviert'
            })
        
        if not calendar_manager:
            return jsonify({
                'enabled': False,
                'message': 'Kalender konnte nicht initialisiert werden'
            })
        
        calendars = calendar_manager.get_calendar_list()
        today_info = calendar_manager.get_today_info()
        
        return jsonify({
            'enabled': True,
            'connected': True,
            'calendars': calendars,
            'today': today_info,
            'calendar_count': len(calendars)
        })
    except Exception as e:
        logger.error(f"Calendar status error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/today', methods=['GET'])
def calendar_today():
    """Gibt alle Ereignisse für heute zurück"""
    try:
        if not calendar_enabled or not calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 400
        
        events = calendar_manager.get_events_today()
        today_info = calendar_manager.get_today_info()
        
        return jsonify({
            'date': today_info['date'],
            'weekday': today_info['weekday'],
            'events': events,
            'event_count': len(events)
        })
    except Exception as e:
        logger.error(f"Calendar today error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/tomorrow', methods=['GET'])
def calendar_tomorrow():
    """Gibt alle Ereignisse für morgen zurück"""
    try:
        if not calendar_enabled or not calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 400
        
        events = calendar_manager.get_events_tomorrow()
        
        return jsonify({
            'events': events,
            'event_count': len(events)
        })
    except Exception as e:
        logger.error(f"Calendar tomorrow error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/week', methods=['GET'])
def calendar_week():
    """Gibt alle Ereignisse für diese Woche zurück"""
    try:
        if not calendar_enabled or not calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 400
        
        events = calendar_manager.get_events_this_week()
        
        return jsonify({
            'events': events,
            'event_count': len(events)
        })
    except Exception as e:
        logger.error(f"Calendar week error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/next-week', methods=['GET'])
def calendar_next_week():
    """Gibt alle Ereignisse für nächste Woche zurück"""
    try:
        if not calendar_enabled or not calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 400
        
        events = calendar_manager.get_events_next_week()
        
        return jsonify({
            'events': events,
            'event_count': len(events)
        })
    except Exception as e:
        logger.error(f"Calendar next week error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/day/<day_name>', methods=['GET'])
def calendar_day(day_name):
    """Gibt Ereignisse für einen bestimmten Wochentag zurück"""
    try:
        if not calendar_enabled or not calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 400
        
        events = calendar_manager.get_events_for_day(day_name)
        
        return jsonify({
            'day': day_name,
            'events': events,
            'event_count': len(events)
        })
    except Exception as e:
        logger.error(f"Calendar day error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/calendar/ui', methods=['GET'])
def calendar_ui():
    """Structured calendar data for interactive frontend cards."""
    try:
        if not calendar_enabled:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 400

        if not simple_calendar_manager:
            refresh_simple_calendar_manager()

        if not simple_calendar_manager:
            return jsonify({'error': 'Kalender nicht initialisiert'}), 400

        view = (request.args.get('view') or 'day').strip().lower()
        anchor_date = _parse_iso_anchor_date(request.args.get('date'))

        if view == 'week':
            start_date = anchor_date - timedelta(days=anchor_date.weekday())
            end_date = start_date + timedelta(days=6)
            period_label = f"Week of {start_date.strftime('%d.%m.%Y')}"
        elif view == 'month':
            start_date = date(anchor_date.year, anchor_date.month, 1)
            if anchor_date.month == 12:
                next_month = date(anchor_date.year + 1, 1, 1)
            else:
                next_month = date(anchor_date.year, anchor_date.month + 1, 1)
            end_date = next_month - timedelta(days=1)
            period_label = start_date.strftime('%B %Y')
        elif view == 'list':
            start_date = anchor_date
            end_date = anchor_date + timedelta(days=13)
            period_label = f"Next 14 days from {anchor_date.strftime('%d.%m.%Y')}"
        else:
            view = 'day'
            start_date = anchor_date
            end_date = anchor_date
            period_label = anchor_date.strftime('%A, %d.%m.%Y')

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        events: List[Dict] = []
        calendars = simple_calendar_manager.get_calendars()
        for cal in calendars:
            cal_events = simple_calendar_manager.get_events(cal.get('url', ''), start_dt, end_dt)
            for event in cal_events:
                event['calendar'] = cal.get('name', 'Unknown')
                events.append(event)

        events.sort(key=lambda item: item.get('start', ''))

        return jsonify({
            'success': True,
            'view': view,
            'anchor_date': anchor_date.strftime('%Y-%m-%d'),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'period_label': period_label,
            'events': events,
            'count': len(events)
        })
    except Exception as e:
        logger.error(f"Calendar UI error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/calendar/update', methods=['POST'])
def update_calendar_event():
    """Update an existing calendar event by Nextcloud path."""
    try:
        if not calendar_enabled:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 400

        if not simple_calendar_manager:
            refresh_simple_calendar_manager()

        if not simple_calendar_manager:
            return jsonify({'error': 'Kalender nicht initialisiert'}), 400

        data = request.json or {}
        nextcloud_path = (data.get('nextcloud_path') or '').strip()
        title = (data.get('title') or '').strip()
        start_time = (data.get('start_time') or '').strip()
        end_time = (data.get('end_time') or '').strip()
        location = data.get('location')
        description = data.get('description')

        if not nextcloud_path or not title or not start_time:
            return jsonify({'error': 'nextcloud_path, title and start_time are required'}), 400

        success = simple_calendar_manager.update_event(
            nextcloud_path=nextcloud_path,
            title=title,
            start_time=start_time,
            end_time=end_time or None,
            location=location,
            description=description
        )

        if not success:
            return jsonify({'error': 'Event could not be updated'}), 500

        return jsonify({'success': True, 'message': 'Event updated successfully'})
    except Exception as e:
        logger.error(f"Calendar update error: {e}")
        return jsonify({'error': str(e)}), 500


def _filter_tasks_for_scope(tasks: List[Dict], scope: str, anchor: date) -> List[Dict]:
    """Filter tasks by due-date scope for card rendering."""
    scope_lower = (scope or 'all').lower()
    filtered = []

    for task in tasks:
        due = _parse_task_due_date(task.get('due_date'))
        if scope_lower == 'today':
            if due == anchor:
                filtered.append(task)
        elif scope_lower == 'overdue':
            if due and due < anchor:
                filtered.append(task)
        else:
            filtered.append(task)

    def task_sort_key(task: Dict):
        due = _parse_task_due_date(task.get('due_date'))
        if due is None:
            return (1, date.max, task.get('title', ''))
        return (0, due, task.get('title', ''))

    return sorted(filtered, key=task_sort_key)


@app.route('/api/tasks/ui', methods=['GET'])
def tasks_ui():
    """Structured task data for interactive frontend cards."""
    try:
        if not tasks_enabled or not task_manager.tasks_client:
            return jsonify({'error': 'Tasks nicht verfügbar'}), 400

        scope = (request.args.get('scope') or 'all').strip().lower()
        anchor_date = _parse_iso_anchor_date(request.args.get('date'))

        tasks = task_manager.get_tasks(use_cache=True, list_name=None)
        open_tasks = [task for task in tasks if not task.get('completed', False)]
        filtered_tasks = _filter_tasks_for_scope(open_tasks, scope, anchor_date)

        return jsonify({
            'success': True,
            'scope': scope,
            'anchor_date': anchor_date.strftime('%Y-%m-%d'),
            'tasks': filtered_tasks,
            'count': len(filtered_tasks)
        })
    except Exception as e:
        logger.error(f"Tasks UI error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/update/<task_uid>', methods=['POST'])
def update_task(task_uid):
    """Update an existing task by UID."""
    try:
        if not tasks_enabled or not task_manager.tasks_client:
            return jsonify({'error': 'Tasks nicht verfügbar'}), 400

        data = request.json or {}
        list_name = data.get('list_name') or 'tasks'

        success = task_manager.update_task(
            task_uid=task_uid,
            list_name=list_name,
            title=data.get('title'),
            description=data.get('description'),
            due_date=data.get('due_date'),
            priority=data.get('priority')
        )

        if not success:
            return jsonify({'error': 'Task could not be updated'}), 500

        return jsonify({'success': True, 'message': 'Task updated successfully'})
    except Exception as e:
        logger.error(f"Task update error: {e}")
        return jsonify({'error': str(e)}), 500

# Task/Todo API Endpunkte
@app.route('/api/tasks/init', methods=['POST'])
def init_tasks():
    """Initialisiert den Task-Manager mit Nextcloud-Konfiguration"""
    try:
        initialize_tasks_from_config()
        return jsonify({
            'enabled': tasks_enabled,
            'message': 'Tasks initialized' if tasks_enabled else 'Tasks could not be initialized'
        })
    except Exception as e:
        logger.error(f"Task initialization error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/list', methods=['GET'])
def list_tasks():
    """Gibt alle aktiven Todos/Tasks zurück"""
    try:
        if not tasks_enabled or not task_manager.tasks_client:
            return jsonify({'error': 'Tasks nicht verfügbar'}), 400
        
        # get_tasks mit None wird automatisch verschiedene Listen-Namen versuchen
        tasks = task_manager.get_tasks(use_cache=True, list_name=None)
        return jsonify({
            'tasks': tasks,
            'count': len(tasks),
            'enabled': True
        })
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/create', methods=['POST'])
def create_task():
    """Erstellt ein neues Task/Todo"""
    try:
        if not tasks_enabled or not task_manager.tasks_client:
            return jsonify({'error': 'Tasks nicht verfügbar'}), 400
        
        data = request.json
        title = data.get('title')
        description = data.get('description', '')
        due_date = data.get('due_date')  # YYYY-MM-DD
        priority = data.get('priority', 0)
        list_name = data.get('list_name', 'tasks')
        location = data.get('location')
        
        if not title:
            return jsonify({'error': 'Titel ist erforderlich'}), 400

        result = create_task_reminder(
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            list_name=list_name,
            location=location
        )

        if result.get('success'):
            return jsonify({
                'status': 'created',
                'title': title,
                'message': result.get('message', f'Task "{title}" wurde erstellt')
            })
        return jsonify({'error': result.get('error', 'Fehler beim Erstellen des Tasks')}), 500
    
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/create-with-details', methods=['POST'])
def create_task_with_details():
    """Erstellt eine Aufgabe/Erinnerung mit strukturierten Formular-Daten."""
    try:
        if not tasks_enabled or not task_manager.tasks_client:
            return jsonify({'error': 'Tasks nicht verfügbar'}), 400

        data = request.json or {}

        title = (data.get('title') or '').strip()
        description = data.get('description', '')
        due_date = data.get('due_date')
        priority = data.get('priority', 0)
        list_name = data.get('list_name')
        location = data.get('location')

        if not title:
            return jsonify({'error': 'Titel ist erforderlich'}), 400

        result = create_task_reminder(
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            list_name=list_name,
            location=location
        )

        if result.get('success'):
            return jsonify(result)

        return jsonify({'error': result.get('error', 'Fehler beim Erstellen des Tasks')}), 500
    except Exception as e:
        logger.error(f"Error in create_task_with_details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/complete/<task_uid>', methods=['POST'])
def complete_task(task_uid):
    """Markiert ein Task als abgeschlossen"""
    try:
        if not tasks_enabled or not task_manager.tasks_client:
            return jsonify({'error': 'Tasks nicht verfügbar'}), 400
        
        data = request.json or {}
        list_name = data.get('list_name', 'tasks')
        
        success = task_manager.complete_task(task_uid, list_name)
        
        if success:
            return jsonify({
                'status': 'completed',
                'task_uid': task_uid,
                'message': 'Task wurde als erledigt markiert'
            })
        else:
            return jsonify({'error': 'Fehler beim Abschließen des Tasks'}), 500
    
    except Exception as e:
        logger.error(f"Error completing task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/status', methods=['GET'])
def tasks_status():
    """Gibt Status der Task-Integration zurück"""
    try:
        auto_sync_status = task_manager.get_auto_sync_status()
        return jsonify({
            'enabled': tasks_enabled,
            'connected': tasks_enabled and task_manager.tasks_client is not None,
            'message': 'Tasks sind aktiviert und verbunden' if tasks_enabled else 'Tasks nicht verfügbar',
            'auto_sync': auto_sync_status
        })
    except Exception as e:
        logger.error(f"Task status error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/sync', methods=['POST'])
def tasks_sync():
    """
    Startet den Background-Load aller Tasks von Nextcloud in die Datenbank
    **WICHTIG**: Dies sollte nur EINMAL gemacht werden!
    Nach dem Sync werden Chat-Queries von der DB (ultra-schnell) gelesen
    """
    if not tasks_enabled or not task_manager.tasks_client:
        return jsonify({'error': 'Tasks nicht initialisiert'}), 400
    
    if not task_manager.database:
        return jsonify({'error': 'Database nicht verfügbar'}), 400
    
    try:
        # Starte Background-Load
        payload = request.get_json(silent=True) or {}
        success = task_manager.sync_tasks_to_database(
            list_name=payload.get('list_name', 'auto'),
            batch_size=payload.get('batch_size', 100)
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '🔄 Background task sync gestartet! Tasks werden in Batches geladen...',
                'status': task_manager.get_sync_status()
            })
        else:
            return jsonify({'error': 'Sync konnte nicht gestartet werden'}), 500
            
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/sync-status', methods=['GET'])
def tasks_sync_status():
    """Gibt Status des laufenden Task-Syncs zurück"""
    if not task_manager.database:
        return jsonify({'error': 'Database nicht verfügbar'}), 400
    
    try:
        status = task_manager.get_sync_status()
        return jsonify({
            'status': status,
            'is_loading': task_manager.batch_loader.is_loading if task_manager.batch_loader else False
        })
    except Exception as e:
        logger.error(f"Sync status error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/db-stats', methods=['GET'])
def tasks_db_stats():
    """Gibt Statistiken über Tasks in der Datenbank zurück"""
    if not task_manager.database:
        return jsonify({'error': 'Database nicht verfügbar'}), 400

    try:
        stats = task_manager.database.get_task_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"DB stats error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== Immich Photo API Endpoints ====================

from backend.features.integration.immich_client import ImmichClient

def get_immich_client(username: str = None) -> Optional[ImmichClient]:
    """Holt Immich-Client mit Credentials aus Konfiguration"""
    try:
        # Versuche user-spezifische Konfiguration
        if username:
            user_config = load_user_config(username)
            immich_url = user_config.get('immich_url')
            immich_api_key = user_config.get('immich_api_key')
            # Custom timeout configuration
            timeout_short = user_config.get('immich_timeout_short', 15)
            timeout_long = user_config.get('immich_timeout_long', 45)
        else:
            immich_url = None
            immich_api_key = None
            timeout_short = 15
            timeout_long = 45

        # Fallback auf globale Konfiguration
        if not immich_url or not immich_api_key:
            global_config = load_ai_config()
            immich_url = immich_url or global_config.get('immich_url_default')
            immich_api_key = immich_api_key or global_config.get('immich_api_key_default')
            # Get global timeout settings if not from user config
            if username is None or not user_config.get('immich_url'):
                timeout_short = global_config.get('immich_timeout_short', 15)
                timeout_long = global_config.get('immich_timeout_long', 45)

        if immich_url and immich_api_key:
            return ImmichClient(immich_url, immich_api_key, timeout_short, timeout_long)
        else:
            logger.warning("Immich not configured")
            return None

    except Exception as e:
        logger.error(f"Error creating Immich client: {e}")
        return None

def build_immich_thumbnail_proxy_url(asset_id: str, username: str = None, size: str = 'preview') -> str:
    """Erzeugt eine Browser-taugliche Thumbnail-URL über den Backend-Proxy."""
    if not asset_id:
        return ''
    params = {'size': size}
    if username:
        params['username'] = username
    return f"{request.host_url.rstrip('/')}/api/immich/thumbnail/{asset_id}?{urlencode(params)}"


def get_nextcloud_search_client(username: str = None) -> Optional[NextcloudSearchClient]:
    """Get Nextcloud Search API client with credentials"""
    try:
        if username:
            user_config = load_user_config(username)
            nextcloud_url = user_config.get('nextcloud_url')
            nextcloud_username = user_config.get('nextcloud_username')
            nextcloud_password = user_config.get('nextcloud_password')

            if nextcloud_url and nextcloud_username and nextcloud_password:
                return NextcloudSearchClient(
                    url=nextcloud_url,
                    username=nextcloud_username,
                    password=nextcloud_password
                )

        # Fallback to environment variables
        nextcloud_url = os.getenv('NEXTCLOUD_URL')
        nextcloud_username = os.getenv('NEXTCLOUD_USERNAME')
        nextcloud_password = os.getenv('NEXTCLOUD_PASSWORD')

        if nextcloud_url and nextcloud_username and nextcloud_password:
            return NextcloudSearchClient(nextcloud_url, nextcloud_username, nextcloud_password)

        logger.warning("Nextcloud search client not configured")
        return None

    except Exception as e:
        logger.error(f"Error creating Nextcloud search client: {e}")
        return None


def get_nextcloud_client(username: str = None) -> Optional[NextcloudClient]:
    """Get Nextcloud WebDAV client with credentials"""
    try:
        if username:
            user_config = load_user_config(username)
            nextcloud_url = user_config.get('nextcloud_url')
            nextcloud_username = user_config.get('nextcloud_username')
            nextcloud_password = user_config.get('nextcloud_password')

            if nextcloud_url and nextcloud_username and nextcloud_password:
                return NextcloudClient(
                    url=nextcloud_url,
                    username=nextcloud_username,
                    password=nextcloud_password
                )

        # Fallback to environment variables
        nextcloud_url = os.getenv('NEXTCLOUD_URL')
        nextcloud_username = os.getenv('NEXTCLOUD_USERNAME')
        nextcloud_password = os.getenv('NEXTCLOUD_PASSWORD')

        if nextcloud_url and nextcloud_username and nextcloud_password:
            return NextcloudClient(nextcloud_url, nextcloud_username, nextcloud_password)

        logger.warning("Nextcloud client not configured")
        return None

    except Exception as e:
        logger.error(f"Error creating Nextcloud client: {e}")
        return None


def extract_search_terms(prompt: str) -> str:
    """Extract meaningful search terms from user prompt"""
    # Remove common question words and filler words
    stop_words = {
        'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines',
        'und', 'oder', 'aber', 'nicht', 'auch', 'mit', 'für', 'von', 'auf', 'an',
        'ist', 'sind', 'war', 'waren', 'hat', 'haben', 'wird', 'werden', 'mir', 'mein', 'meine',
        'the', 'a', 'an', 'and', 'or', 'but', 'not', 'also', 'with', 'for', 'from',
        'is', 'are', 'was', 'were', 'has', 'have', 'will', 'would', 'my', 'me',
        'was', 'wie', 'wo', 'wann', 'warum', 'what', 'how', 'where', 'when', 'why',
        'gibt', 'es', 'über', 'alle', 'zum', 'zur', 'about', 'all', 'to', 'zeig', 'zeige',
        'finde', 'suche', 'such', 'find', 'search', 'show', 'tell'
    }

    words = prompt.lower().split()
    meaningful_words = []

    for word in words:
        # Clean punctuation
        word = word.strip('.,!?;:()[]{}"\'-')
        # Keep if not stop word and length > 2
        if word and word not in stop_words and len(word) > 2:
            meaningful_words.append(word)

    # Return first 3-5 most meaningful words as search query; empty string if none found
    return ' '.join(meaningful_words[:5]) if meaningful_words else ''


@app.route('/api/immich/test', methods=['POST'])
def immich_test_connection():
    """Testet die Verbindung zu Immich"""
    try:
        data = request.get_json()
        username = data.get('username')

        client = get_immich_client(username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Immich nicht konfiguriert. Bitte URL und API-Key setzen.'
            }), 400

        success = client.test_connection()

        response_payload = {
            'success': success,
            'message': 'Verbindung erfolgreich' if success else 'Verbindung fehlgeschlagen',
        }
        if not success:
            response_payload['error'] = client.last_error or 'Immich-Verbindung fehlgeschlagen'

        return jsonify(response_payload)

    except Exception as e:
        logger.error(f"Immich test error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/immich/search', methods=['POST'])
def immich_search_photos():
    """Sucht Fotos in Immich"""
    try:
        data = request.get_json()
        username = data.get('username')
        query = data.get('query', '')
        limit = data.get('limit', 20)

        client = get_immich_client(username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Immich nicht konfiguriert'
            }), 400

        result = client.search_photos_intelligent(query, limit=limit)

        # Ersetze direkte Immich-Thumbnail-Links durch Backend-Proxy-Links
        for photo in result.get('results', []):
            asset_id = photo.get('id')
            if asset_id:
                photo['thumbnail_url'] = build_immich_thumbnail_proxy_url(asset_id, username, 'preview')

        return jsonify(result)

    except Exception as e:
        logger.error(f"Immich search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/immich/people', methods=['GET'])
def immich_get_people():
    """Holt alle erkannten Personen von Immich"""
    try:
        username = request.args.get('username')

        client = get_immich_client(username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Immich nicht konfiguriert'
            }), 400

        people = client.get_people()

        return jsonify({
            'success': True,
            'people': people
        })

    except Exception as e:
        logger.error(f"Immich people error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/immich/assets', methods=['GET'])
def immich_get_assets():
    """Holt Assets von Immich"""
    try:
        username = request.args.get('username')
        limit = int(request.args.get('limit', 100))
        skip = int(request.args.get('skip', 0))

        client = get_immich_client(username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Immich nicht konfiguriert'
            }), 400

        assets = client.get_all_assets(limit=limit, skip=skip)

        return jsonify({
            'success': True,
            'count': len(assets),
            'assets': assets
        })

    except Exception as e:
        logger.error(f"Immich assets error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/immich/thumbnail/<asset_id>', methods=['GET'])
def immich_thumbnail_proxy(asset_id):
    """Proxy für Immich-Thumbnails, damit Browser keinen API-Key benötigen."""
    try:
        username = request.args.get('username')
        size = request.args.get('size', 'preview')

        client = get_immich_client(username)
        if not client:
            return jsonify({'success': False, 'error': 'Immich nicht konfiguriert'}), 400

        upstream_url = f"{client.url}/api/assets/{asset_id}/thumbnail?size={size}"
        upstream = requests.get(upstream_url, headers=client._get_headers(), timeout=client.timeout_short)

        if upstream.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'Thumbnail konnte nicht geladen werden (HTTP {upstream.status_code})'
            }), upstream.status_code

        return Response(upstream.content, content_type=upstream.headers.get('Content-Type', 'image/jpeg'))

    except Exception as e:
        logger.error(f"Immich thumbnail proxy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/immich/download/<asset_id>', methods=['GET'])
def immich_download_proxy(asset_id):
    """Proxy für originale Immich-Dateien als Download."""
    try:
        username = request.args.get('username')

        client = get_immich_client(username)
        if not client:
            return jsonify({'success': False, 'error': 'Immich nicht konfiguriert'}), 400

        filename = f"{asset_id}.jpg"
        metadata_url = f"{client.url}/api/assets/{asset_id}"
        metadata_response = requests.get(metadata_url, headers=client._get_headers(), timeout=client.timeout_short)
        if metadata_response.status_code == 200:
            metadata = metadata_response.json() if metadata_response.content else {}
            original_name = metadata.get('originalFileName')
            if original_name:
                safe_name = str(original_name).replace('"', '').replace('\n', '').replace('\r', '').strip()
                if safe_name:
                    filename = safe_name

        original_url = f"{client.url}/api/assets/{asset_id}/original"
        upstream = requests.get(original_url, headers=client._get_headers(), timeout=client.timeout_long)

        if upstream.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'Original konnte nicht geladen werden (HTTP {upstream.status_code})'
            }), upstream.status_code

        response = Response(upstream.content, content_type=upstream.headers.get('Content-Type', 'application/octet-stream'))
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Immich download proxy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/immich/search-by-context', methods=['POST'])
def immich_search_by_context():
    """Sucht Fotos basierend auf KI-erkannte Kontextinformationen (Objekte, Tags)"""
    try:
        data = request.get_json()
        username = data.get('username')
        query = data.get('query', '')
        limit = data.get('limit', 20)

        client = get_immich_client(username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Immich nicht konfiguriert'
            }), 400

        # Search by context (objects, tags, description)
        results = client.search_by_context(query, limit=limit)
        
        # Format results for display
        formatted_results = [client.format_asset_for_display(asset) for asset in results]
        for photo in formatted_results:
            asset_id = photo.get('id')
            if asset_id:
                photo['thumbnail_url'] = build_immich_thumbnail_proxy_url(asset_id, username, 'preview')

        return jsonify({
            'success': True,
            'query': query,
            'count': len(formatted_results),
            'results': formatted_results
        })

    except Exception as e:
        logger.error(f"Immich context search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== API Registry Endpoints ====================

@app.route('/api/registry/apis', methods=['GET'])
def get_all_apis():
    """Get all available APIs with their configuration status"""
    try:
        username = request.args.get('username')
        registry = get_api_registry()
        apis = registry.get_all_configured_apis(username)

        return jsonify({
            'success': True,
            'apis': apis
        })
    except Exception as e:
        logger.error(f"Error getting APIs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/registry/health', methods=['GET'])
def check_all_apis_health():
    """Check health of all configured APIs"""
    try:
        username = request.args.get('username')
        registry = get_api_registry()
        health = registry.check_all_apis_health(username)

        return jsonify({
            'success': True,
            'health': health
        })
    except Exception as e:
        logger.error(f"Error checking API health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/registry/<api_name>/health', methods=['GET'])
def check_api_health(api_name):
    """Check health of a specific API"""
    try:
        username = request.args.get('username')
        use_cache = request.args.get('use_cache', 'true').lower() == 'true'

        registry = get_api_registry()
        health = registry.check_api_health(api_name, username, use_cache=use_cache)

        return jsonify({
            'success': True,
            'api_name': api_name,
            'health': health
        })
    except Exception as e:
        logger.error(f"Error checking {api_name} health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/registry/<api_name>/config', methods=['GET', 'POST', 'DELETE'])
def manage_api_config(api_name):
    """Get, update, or delete API configuration"""
    try:
        username = request.args.get('username')
        registry = get_api_registry()

        if request.method == 'GET':
            config = registry.load_config(api_name, username)
            api_class = registry.get_api_class(api_name)
            configured = bool(config)

            if api_class and not config and not api_class.requires_config():
                config = api_class.get_default_config()
                configured = True

            # Get schema even when the API has not been configured yet.
            schema = registry.get_api_schema(api_name, config, username)

            # Remove sensitive values from response
            safe_config = {}
            for key, value in config.items():
                if schema.get(key, {}).get('secret'):
                    safe_config[key] = '***' if value else ''
                else:
                    safe_config[key] = value

            return jsonify({
                'success': True,
                'api_name': api_name,
                'config': safe_config,
                'schema': schema,
                'configured': configured
            })

        elif request.method == 'POST':
            data = request.get_json()
            config = data.get('config', {})

            # Preserve existing secret values when UI sends masked placeholders (***).
            existing_config = registry.load_config(api_name, username) or {}
            api_class = registry.get_api_class(api_name)
            schema = registry.get_api_schema(
                api_name,
                existing_config if existing_config else (api_class.get_default_config() if api_class and not api_class.requires_config() else config),
                username
            )

            merged_config = dict(config)
            for key, field_meta in schema.items():
                if field_meta.get('secret') and merged_config.get(key) == '***' and existing_config.get(key):
                    merged_config[key] = existing_config.get(key)

            # Validate by trying to create instance
            try:
                instance = registry.create_api_instance(api_name, merged_config, username, use_cache=False)
                if not instance:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to create API instance with provided config'
                    }), 400

                # Test connection
                if not instance.test_connection():
                    return jsonify({
                        'success': False,
                        'error': 'Connection test failed with provided configuration'
                    }), 400

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid configuration: {str(e)}'
                }), 400

            # Save config
            if registry.save_config(api_name, merged_config, username):
                return jsonify({
                    'success': True,
                    'message': f'{api_name} configuration saved successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to save configuration'
                }), 500

        elif request.method == 'DELETE':
            if registry.delete_config(api_name, username):
                return jsonify({
                    'success': True,
                    'message': f'{api_name} configuration deleted successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to delete configuration'
                }), 500

    except Exception as e:
        logger.error(f"Error managing {api_name} config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/registry/<api_name>/test', methods=['POST'])
def test_api_connection(api_name):
    """Test API connection with provided config"""
    try:
        data = request.get_json()
        config = data.get('config', {})
        username = data.get('username')

        registry = get_api_registry()

        # Preserve existing secret values when UI sends masked placeholders (***).
        existing_config = registry.load_config(api_name, username) or {}
        api_class = registry.get_api_class(api_name)
        schema = registry.get_api_schema(
            api_name,
            existing_config if existing_config else (api_class.get_default_config() if api_class and not api_class.requires_config() else config),
            username
        )

        merged_config = dict(config)
        for key, field_meta in schema.items():
            if field_meta.get('secret') and merged_config.get(key) == '***' and existing_config.get(key):
                merged_config[key] = existing_config.get(key)

        # Create instance with provided config
        instance = registry.create_api_instance(api_name, merged_config, username, use_cache=False)
        if not instance:
            return jsonify({
                'success': False,
                'error': 'Failed to create API instance'
            }), 400

        # Test connection and get health info
        health = instance.get_health_info()

        return jsonify({
            'success': True,
            'api_name': api_name,
            'health': health
        })

    except Exception as e:
        logger.error(f"Error testing {api_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== Email Endpoints ====================

@app.route('/api/email/test', methods=['POST'])
def email_test_connection():
    """Test the IMAP email connection."""
    try:
        data = request.get_json()
        username = data.get('username')
        account_id = data.get('account_id')
        client = get_email_client(username=username, account_id=account_id)
        if not client:
            return jsonify({'success': False, 'error': 'E-Mail nicht konfiguriert. Bitte IMAP-Einstellungen setzen.'}), 400
        success = client.test_connection()
        return jsonify({
            'success': success,
            'message': 'Verbindung erfolgreich' if success else 'Verbindung fehlgeschlagen',
        })
    except Exception as e:
        logger.error("Email test error: %s", e)
        return jsonify({'success': False, 'error': 'Interner Fehler beim E-Mail-Verbindungstest.'}), 500


@app.route('/api/email/search', methods=['POST'])
def email_search():
    """Search emails by keyword query."""
    try:
        data = request.get_json()
        username = data.get('username')
        account_id = data.get('account_id')
        query = data.get('query', '')
        limit = int(data.get('limit', 10))

        client = get_email_client(username=username, account_id=account_id)
        if not client:
            return jsonify({'success': False, 'error': 'E-Mail nicht konfiguriert.'}), 400

        results = client.search_emails(query, limit=limit)
        sanitized = []
        for mail in results:
            body = mail.get('body', '')
            sanitized.append({
                'subject': mail.get('subject', ''),
                'sender': mail.get('sender', ''),
                'date': mail.get('date', ''),
                'folder': mail.get('folder', ''),
                'body_preview': (body[:300] + '...') if len(body) > 300 else body
            })
        return jsonify({'success': True, 'count': len(sanitized), 'results': sanitized})
    except Exception as e:
        logger.error("Email search error: %s", e)
        return jsonify({'success': False, 'error': 'Interner Fehler bei der E-Mail-Suche.'}), 500


@app.route('/api/email/summary', methods=['GET'])
def email_summary():
    """Return a summary of recent emails."""
    try:
        username = request.args.get('username')
        account_id = request.args.get('account_id')
        limit = int(request.args.get('limit', 20))

        client = get_email_client(username=username, account_id=account_id)
        if not client:
            return jsonify({'success': False, 'error': 'E-Mail nicht konfiguriert.'}), 400

        summary = client.get_email_summary(max_emails=limit)
        return jsonify({'success': True, **summary})
    except Exception as e:
        logger.error("Email summary error: %s", e)
        return jsonify({'success': False, 'error': 'Interner Fehler beim Laden der E-Mail-Übersicht.'}), 500


@app.route('/api/email/folders', methods=['POST'])
def email_folders():
    """Return the available IMAP folders for the current configuration."""
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username')
        account_id = data.get('account_id')
        config = data.get('config')

        client = get_email_client(
            username=username,
            account_id=account_id,
            config=config if config else None,
            use_cache=False
        )
        if not client:
            return jsonify({'success': False, 'error': 'E-Mail nicht konfiguriert.'}), 400

        folders = client.list_folders()
        return jsonify({'success': True, 'folders': folders, 'count': len(folders)})
    except Exception as e:
        logger.error("Email folders error: %s", e)
        return jsonify({'success': False, 'error': 'Interner Fehler beim Laden der Ordnerliste.'}), 500


@app.route('/api/email/send', methods=['POST'])
def email_send():
    """Send an email via the configured SMTP server."""
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username')
        account_id = data.get('account_id')
        config = data.get('config')
        payload = data.get('message', data)

        client = get_email_client(
            username=username,
            account_id=account_id,
            config=config if config else None,
            use_cache=False
        )
        if not client:
            return jsonify({'success': False, 'error': 'E-Mail nicht konfiguriert.'}), 400

        result = client.send_email(
            to=payload.get('to', ''),
            subject=payload.get('subject', ''),
            body=payload.get('body', ''),
            cc=payload.get('cc', ''),
            bcc=payload.get('bcc', ''),
            reply_to=payload.get('reply_to', ''),
            from_name=payload.get('from_name', ''),
            from_address=payload.get('from_address', '')
        )

        return jsonify({
            'success': True,
            'message': 'E-Mail gesendet',
            'result': result
        })
    except Exception as e:
        logger.error("Email send error: %s", e)
        return jsonify({'success': False, 'error': 'Interner Fehler beim E-Mail-Versand.'}), 500


@app.route('/api/email/accounts', methods=['GET'])
def email_accounts():
    """Return configured email accounts and active account info."""
    try:
        username = request.args.get('username')
        account_id = request.args.get('account_id')

        client = get_email_client(username=username, account_id=account_id)
        if not client:
            return jsonify({'success': False, 'error': 'E-Mail nicht konfiguriert.'}), 400

        return jsonify({
            'success': True,
            'accounts': client.get_accounts_overview(),
            'active_account_id': client.active_account_id,
        })
    except Exception as e:
        logger.error("Email accounts error: %s", e)
        return jsonify({'success': False, 'error': 'Interner Fehler beim Laden der E-Mail-Konten.'}), 500


# ==================== HomeAssistant Endpoints ====================

@app.route('/api/homeassistant/states', methods=['GET'])
def homeassistant_get_states():
    """Get all Home Assistant entity states"""
    try:
        username = request.args.get('username')
        registry = get_api_registry()

        client = registry.create_api_instance('homeassistant', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Home Assistant not configured'
            }), 400

        states = client.get_states()

        return jsonify({
            'success': True,
            'states': states
        })

    except Exception as e:
        logger.error(f"HomeAssistant get states error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homeassistant/state/<path:entity_id>', methods=['GET'])
def homeassistant_get_state(entity_id):
    """Get state of a specific Home Assistant entity"""
    try:
        username = request.args.get('username')
        registry = get_api_registry()

        client = registry.create_api_instance('homeassistant', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Home Assistant not configured'
            }), 400

        state = client.get_state(entity_id)

        if state:
            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'state': state
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Entity not found'
            }), 404

    except Exception as e:
        logger.error(f"HomeAssistant get state error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homeassistant/service', methods=['POST'])
def homeassistant_call_service():
    """Call a Home Assistant service"""
    try:
        data = request.get_json()
        username = data.get('username')
        domain = data.get('domain')
        service = data.get('service')
        entity_id = data.get('entity_id')
        service_data = data.get('data', {})

        if not domain or not service:
            return jsonify({
                'success': False,
                'error': 'domain and service are required'
            }), 400

        registry = get_api_registry()
        client = registry.create_api_instance('homeassistant', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Home Assistant not configured'
            }), 400

        success = client.call_service(domain, service, entity_id, service_data)

        return jsonify({
            'success': success,
            'message': f'Service {domain}.{service} called' if success else 'Service call failed'
        })

    except Exception as e:
        logger.error(f"HomeAssistant service call error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homeassistant/search', methods=['POST'])
def homeassistant_search():
    """Search Home Assistant entities"""
    try:
        data = request.get_json()
        username = data.get('username')
        query = data.get('query', '')
        domains = data.get('domains')

        registry = get_api_registry()
        client = registry.create_api_instance('homeassistant', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Home Assistant not configured'
            }), 400

        results = client.search_entities(query, domains)

        return jsonify({
            'success': True,
            'query': query,
            'count': len(results),
            'results': results
        })

    except Exception as e:
        logger.error(f"HomeAssistant search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Uptime Kuma Endpoints ====================

@app.route('/api/uptimekuma/monitors', methods=['GET'])
def uptimekuma_get_monitors():
    """Get all Uptime Kuma monitors"""
    try:
        username = request.args.get('username')
        registry = get_api_registry()

        client = registry.create_api_instance('uptimekuma', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Uptime Kuma not configured'
            }), 400

        monitors = client.get_monitors()

        return jsonify({
            'success': True,
            'monitors': monitors
        })

    except Exception as e:
        logger.error(f"Uptime Kuma get monitors error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/uptimekuma/monitor/<int:monitor_id>', methods=['GET'])
def uptimekuma_get_monitor(monitor_id):
    """Get a specific Uptime Kuma monitor"""
    try:
        username = request.args.get('username')
        registry = get_api_registry()

        client = registry.create_api_instance('uptimekuma', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Uptime Kuma not configured'
            }), 400

        monitor = client.get_monitor(monitor_id)

        if monitor:
            return jsonify({
                'success': True,
                'monitor': monitor
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Monitor not found'
            }), 404

    except Exception as e:
        logger.error(f"Uptime Kuma get monitor error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/uptimekuma/stats', methods=['GET'])
def uptimekuma_get_stats():
    """Get Uptime Kuma statistics"""
    try:
        username = request.args.get('username')
        monitor_id = request.args.get('monitor_id', type=int)

        registry = get_api_registry()
        client = registry.create_api_instance('uptimekuma', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Uptime Kuma not configured'
            }), 400

        stats = client.get_uptime_stats(monitor_id)

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Uptime Kuma get stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/uptimekuma/search', methods=['POST'])
def uptimekuma_search():
    """Search Uptime Kuma monitors"""
    try:
        data = request.get_json()
        username = data.get('username')
        query = data.get('query', '')

        registry = get_api_registry()
        client = registry.create_api_instance('uptimekuma', username=username)
        if not client:
            return jsonify({
                'success': False,
                'error': 'Uptime Kuma not configured'
            }), 400

        results = client.search_monitors(query)

        return jsonify({
            'success': True,
            'query': query,
            'count': len(results),
            'results': results
        })

    except Exception as e:
        logger.error(f"Uptime Kuma search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Public API Endpoints ====================

def _reverse_geocode(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                'format': 'jsonv2',
                'lat': latitude,
                'lon': longitude,
                'addressdetails': 1
            },
            headers={'User-Agent': 'MYND Assistant'},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning("Reverse geocoding failed: %s", exc)
        return None


def _collect_place_candidates(address: Dict[str, Any]) -> List[str]:
    candidates = [
        address.get('city'),
        address.get('town'),
        address.get('village'),
        address.get('municipality'),
        address.get('county'),
        address.get('state')
    ]
    return [entry for entry in candidates if entry]


def _safe_text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _extract_nina_warning_items(payload: Any, limit: int = 5) -> List[Dict[str, Any]]:
    """Normalize NINA dashboard payload into a stable warning list."""
    items = []
    data = payload

    if isinstance(payload, dict):
        data = payload.get('warnings', payload)

    if isinstance(data, list):
        for raw in data:
            if not isinstance(raw, dict):
                continue

            payload_data = raw.get('payload') if isinstance(raw.get('payload'), dict) else {}
            detail_data = payload_data.get('data') if isinstance(payload_data.get('data'), dict) else {}
            i18n_title = raw.get('i18nTitle') if isinstance(raw.get('i18nTitle'), dict) else {}
            translated_headline = _safe_text(i18n_title.get('de') or i18n_title.get('en'))

            identifier = _safe_text(raw.get('id') or raw.get('identifier') or raw.get('warningId'))
            headline = _safe_text(
                raw.get('headline')
                or detail_data.get('headline')
                or translated_headline
                or raw.get('title')
                or raw.get('i18nTitle')
                or raw.get('event')
                or raw.get('msgType')
            )
            severity = _safe_text(
                raw.get('severity')
                or detail_data.get('severity')
                or raw.get('warnLevel')
                or raw.get('level')
            )
            sent = _safe_text(raw.get('sent') or raw.get('effective') or raw.get('published'))
            expires = _safe_text(raw.get('expires') or raw.get('until') or raw.get('ends'))
            provider = _safe_text(
                raw.get('provider')
                or detail_data.get('provider')
                or raw.get('sender')
                or raw.get('source')
            )
            description = _safe_text(
                raw.get('description')
                or detail_data.get('description')
                or detail_data.get('event')
                or raw.get('text')
                or raw.get('body')
            )

            if not headline and identifier:
                headline = f"Warnung {identifier}"

            if not headline:
                continue

            items.append({
                'id': identifier,
                'headline': headline,
                'severity': severity,
                'sent': sent,
                'expires': expires,
                'provider': provider,
                'description': description
            })

    return items[:limit]


def _classify_weather_icon(weather_id: Optional[int], weather_main: str) -> str:
    main = _safe_text(weather_main).lower()
    if weather_id is not None and 200 <= int(weather_id) < 700:
        return 'rain'
    if any(token in main for token in ['rain', 'drizzle', 'thunder', 'snow']):
        return 'rain'
    if any(token in main for token in ['cloud', 'mist', 'fog', 'haze', 'smoke']):
        return 'cloud'
    return 'sun'


def _format_temperature(value: Any, units: str) -> str:
    try:
        temp = float(value)
    except (TypeError, ValueError):
        return ''

    if units == 'imperial':
        return f"{round(temp)}°F"
    if units == 'standard':
        return f"{round(temp)}K"
    return f"{round(temp)}°C"


def get_local_weather_status() -> Dict[str, Any]:
    """Collect local weather and forecast from OpenWeather for configured coordinates."""
    result = {
        'success': False,
        'configured': False,
        'status': 'not_configured',
        'location_name': '',
        'lat': None,
        'lon': None,
        'temperature': None,
        'temperature_display': '',
        'description': '',
        'icon': 'sun',
        'alerts': [],
        'alerts_count': 0,
        'hourly_preview': '',
        'daily_preview': '',
        'summary': ''
    }

    try:
        registry = get_api_registry()
        config = registry.load_config('openweather')
        result['location_name'] = _safe_text(config.get('location_name'))

        client = registry.create_api_instance('openweather')
        if not client:
            result['summary'] = 'OpenWeather ist nicht konfiguriert.'
            return result

        result['configured'] = True
        payload = client.get_current_and_forecast(exclude='minutely')
        current = payload.get('current') if isinstance(payload, dict) else {}
        weather_entries = current.get('weather') if isinstance(current, dict) else []
        weather = weather_entries[0] if isinstance(weather_entries, list) and weather_entries else {}

        result['status'] = 'ok'
        result['success'] = True
        result['lat'] = payload.get('lat')
        result['lon'] = payload.get('lon')
        result['temperature'] = current.get('temp')
        result['temperature_display'] = _format_temperature(current.get('temp'), client.units)
        result['description'] = _safe_text(weather.get('description') or weather.get('main'))
        result['icon'] = _classify_weather_icon(weather.get('id'), weather.get('main'))

        hourly = payload.get('hourly') if isinstance(payload, dict) else []
        if isinstance(hourly, list) and len(hourly) > 1 and isinstance(hourly[1], dict):
            next_hour_temp = _format_temperature(hourly[1].get('temp'), client.units)
            next_hour_pop = hourly[1].get('pop')
            pop_text = ''
            try:
                if next_hour_pop is not None:
                    pop_text = f", Regenwahrscheinlichkeit {round(float(next_hour_pop) * 100)}%"
            except (TypeError, ValueError):
                pop_text = ''
            if next_hour_temp:
                result['hourly_preview'] = f"In der nächsten Stunde etwa {next_hour_temp}{pop_text}."

        daily = payload.get('daily') if isinstance(payload, dict) else []
        if isinstance(daily, list) and len(daily) > 1 and isinstance(daily[1], dict):
            tomorrow = daily[1]
            temp_block = tomorrow.get('temp') if isinstance(tomorrow.get('temp'), dict) else {}
            t_min = _format_temperature(temp_block.get('min'), client.units)
            t_max = _format_temperature(temp_block.get('max'), client.units)
            if t_min and t_max:
                result['daily_preview'] = f"Morgen voraussichtlich zwischen {t_min} und {t_max}."

        alerts = payload.get('alerts') if isinstance(payload, dict) else []
        if isinstance(alerts, list):
            normalized = []
            for entry in alerts[:5]:
                if not isinstance(entry, dict):
                    continue
                normalized.append({
                    'event': _safe_text(entry.get('event')),
                    'sender_name': _safe_text(entry.get('sender_name')),
                    'description': _safe_text(entry.get('description')),
                    'start': entry.get('start'),
                    'end': entry.get('end')
                })
            result['alerts'] = normalized
            result['alerts_count'] = len(normalized)

        location_label = result['location_name'] or 'deinem Standort'
        temp_label = result['temperature_display'] or 'n/a'
        desc_label = result['description'] or 'unbekannt'
        if result['alerts_count'] > 0:
            result['summary'] = (
                f"Aktuell {temp_label} und {desc_label} in {location_label}. "
                f"Es liegen {result['alerts_count']} Wetterwarnung(en) vor."
            )
        else:
            result['summary'] = f"Aktuell {temp_label} und {desc_label} in {location_label}."

        if result['hourly_preview']:
            result['summary'] = f"{result['summary']} {result['hourly_preview']}"
        if result['daily_preview']:
            result['summary'] = f"{result['summary']} {result['daily_preview']}"

        return result

    except Exception as exc:
        logger.warning('OpenWeather status failed: %s', exc)
        result['status'] = 'error'
        result['summary'] = f"Wetter konnte nicht geladen werden: {str(exc)}"
        return result


def get_local_security_status() -> Dict[str, Any]:
    """Collect local security status from configured NINA plus weather from OpenWeather."""
    result = {
        'success': True,
        'ars': '',
        'nina_warning_count': 0,
        'nina_warnings': [],
        'headline': '',
        'summary': '',
        'weather': {},
        'sources': {
            'nina': False,
            'openweather': False
        },
        'errors': []
    }

    registry = get_api_registry()

    # NINA warnings for configured ARS
    try:
        nina_config = registry.load_config('nina')
        ars = _safe_text(nina_config.get('ars'))
        result['ars'] = ars

        nina_client = registry.create_api_instance('nina')
        if nina_client:
            result['sources']['nina'] = True
            if ars:
                dashboard_result = nina_client.get_dashboard_with_fallback(ars)
                result['ars'] = _safe_text(dashboard_result.get('ars_used') or ars)
                warnings = _extract_nina_warning_items(dashboard_result.get('data'), limit=6)
                result['nina_warnings'] = warnings
                result['nina_warning_count'] = len(warnings)
            else:
                result['errors'].append('NINA ARS ist nicht konfiguriert')
        else:
            result['errors'].append('NINA Client nicht verfügbar')
    except Exception as exc:
        logger.error("NINA security status failed: %s", exc)
        result['errors'].append(f"NINA Fehler: {str(exc)}")

    try:
        weather = get_local_weather_status()
        result['weather'] = weather
        result['sources']['openweather'] = weather.get('configured', False)
    except Exception as exc:
        logger.warning('OpenWeather attach failed: %s', exc)
        result['errors'].append(f"OpenWeather Fehler: {str(exc)}")

    if result['nina_warning_count'] > 0:
        result['headline'] = f"{result['nina_warning_count']} aktive Warnung(en) für deinen Standort"
        lines = [result['headline'] + '.']
        for idx, warning in enumerate(result['nina_warnings'][:3], 1):
            label = warning.get('headline') or f"Warnung {idx}"
            severity = warning.get('severity')
            if severity:
                lines.append(f"{idx}. {label} (Stufe: {severity})")
            else:
                lines.append(f"{idx}. {label}")
        result['summary'] = "\n".join(lines)
    else:
        result['headline'] = 'Keine akuten NINA-Warnungen für deinen Standort'
        result['summary'] = (
            'Aktuell liegen laut NINA keine akuten Warnungen für deinen Standort vor.'
        )

    return result


def is_security_query(message: str) -> bool:
    text = (message or '').lower()
    keywords = [
        'sicherheitslage',
        'warnung',
        'warnungen',
        'nina',
        'gefahrenlage',
        'alarm',
        'katastrophenschutz',
        'lage bei mir'
    ]
    return any(keyword in text for keyword in keywords)


def is_weather_query(message: str) -> bool:
    text = (message or '').lower()
    keywords = [
        'wetter',
        'temperatur',
        'vorhersage',
        'forecast',
        'regen',
        'sonne',
        'wind',
        'wie warm',
        'weather'
    ]
    return any(keyword in text for keyword in keywords)


@app.route('/api/location/resolve', methods=['POST'])
def resolve_location():
    """Resolve browser location to NINA ARS and OpenWeather coordinates."""
    try:
        payload = request.get_json() or {}
        latitude = payload.get('lat')
        longitude = payload.get('lon')
        save_config = payload.get('save', True)

        if latitude is None or longitude is None:
            return jsonify({'success': False, 'error': 'lat and lon required'}), 400

        latitude = float(latitude)
        longitude = float(longitude)

        reverse = _reverse_geocode(latitude, longitude)
        address = reverse.get('address', {}) if reverse else {}
        display_name = reverse.get('display_name', '') if reverse else ''
        candidates = _collect_place_candidates(address)

        registry = get_api_registry()
        nina_result = None
        nina_client = registry.create_api_instance('nina')
        if nina_client:
            resolved = nina_client.resolve_ars_for_places(candidates)
            if resolved:
                nina_result = {
                    'ars': resolved.get('ars'),
                    'name': resolved.get('name'),
                    'hint': resolved.get('hint'),
                    'score': resolved.get('score')
                }
                if save_config:
                    nina_config = registry.load_config('nina')
                    nina_config['ars'] = resolved.get('ars')
                    registry.save_config('nina', nina_config)

        openweather_result = {
            'lat': latitude,
            'lon': longitude,
            'location_name': _safe_text(display_name)
        }
        openweather_error = None
        if save_config:
            try:
                openweather_config = registry.load_config('openweather')
                openweather_config['lat'] = latitude
                openweather_config['lon'] = longitude
                if display_name:
                    openweather_config['location_name'] = display_name
                registry.save_config('openweather', openweather_config)
            except Exception as exc:
                openweather_error = str(exc)
                logger.warning('Could not persist OpenWeather coordinates: %s', exc)

        return jsonify({
            'success': True,
            'location': {
                'latitude': latitude,
                'longitude': longitude,
                'display_name': display_name,
                'address': address
            },
            'nina': nina_result,
            'openweather': openweather_result,
            'openweather_error': openweather_error
        })

    except Exception as e:
        logger.error(f"Location resolve error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dwd/warnings/nowcast', methods=['GET'])
def dwd_get_warnings_nowcast():
    """Get DWD nowcast warnings"""
    try:
        language = request.args.get('lang', 'de')
        registry = get_api_registry()
        client = registry.create_api_instance('dwd')
        if not client:
            return jsonify({'success': False, 'error': 'DWD client unavailable'}), 400

        data = client.get_warnings_nowcast(language)
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"DWD warnings error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dwd/station-overview', methods=['GET'])
def dwd_station_overview():
    """Get DWD station overview by station IDs"""
    try:
        registry = get_api_registry()
        station_ids = request.args.get('station_ids', '').strip()
        if not station_ids:
            config = registry.load_config('dwd')
            station_ids = str(config.get('station_ids', '')).strip()
        if not station_ids:
            return jsonify({'success': False, 'error': 'station_ids required'}), 400

        client = registry.create_api_instance('dwd')
        if not client:
            return jsonify({'success': False, 'error': 'DWD client unavailable'}), 400

        data = client.get_station_overview_extended(
            [entry.strip() for entry in station_ids.split(',') if entry.strip()]
        )
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"DWD station overview error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/nina/event-codes', methods=['GET'])
def nina_event_codes():
    """Get NINA event codes"""
    try:
        registry = get_api_registry()
        client = registry.create_api_instance('nina')
        if not client:
            return jsonify({'success': False, 'error': 'NINA client unavailable'}), 400

        data = client.get_event_codes()
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"NINA event codes error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/nina/dashboard', methods=['GET'])
def nina_dashboard():
    """Get NINA dashboard data for an ARS"""
    try:
        ars = request.args.get('ars')
        if not ars:
            registry = get_api_registry()
            config = registry.load_config('nina')
            ars = str(config.get('ars', '')).strip()
        if not ars:
            return jsonify({'success': False, 'error': 'ars required'}), 400

        registry = get_api_registry()
        client = registry.create_api_instance('nina')
        if not client:
            return jsonify({'success': False, 'error': 'NINA client unavailable'}), 400

        dashboard_result = client.get_dashboard_with_fallback(ars)
        return jsonify({
            'success': True,
            'ars': dashboard_result.get('ars_requested', ars),
            'ars_used': dashboard_result.get('ars_used', ars),
            'fallback_used': bool(dashboard_result.get('fallback_used')),
            'data': dashboard_result.get('data')
        })

    except Exception as e:
        logger.error(f"NINA dashboard error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/nina/map-data', methods=['GET'])
def nina_map_data():
    """Get NINA map data for a specific source"""
    try:
        source = request.args.get('source')
        if not source:
            return jsonify({'success': False, 'error': 'source required'}), 400

        registry = get_api_registry()
        client = registry.create_api_instance('nina')
        if not client:
            return jsonify({'success': False, 'error': 'NINA client unavailable'}), 400

        data = client.get_map_data(source)
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"NINA map data error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/nina/regions', methods=['GET'])
def nina_regions():
    """Get NINA regional keys (ARS) list"""
    try:
        query = request.args.get('query', '').strip()
        limit = int(request.args.get('limit', 200))

        registry = get_api_registry()
        client = registry.create_api_instance('nina')
        if not client:
            return jsonify({'success': False, 'error': 'NINA client unavailable'}), 400

        data = client.get_regional_keys(query=query, limit=limit)
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"NINA regions error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/security/status', methods=['GET'])
def security_status():
    """Get local security status based on configured NINA ARS and OpenWeather."""
    try:
        data = get_local_security_status()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Security status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/weather/current', methods=['GET'])
def weather_current():
    """Get local current weather and forecast summary from OpenWeather."""
    try:
        data = get_local_weather_status()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Weather current error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/autobahn/roads', methods=['GET'])
def autobahn_list_roads():
    """List available Autobahn roads"""
    try:
        registry = get_api_registry()
        client = registry.create_api_instance('autobahn')
        if not client:
            return jsonify({'success': False, 'error': 'Autobahn client unavailable'}), 400

        data = client.list_roads()
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"Autobahn list roads error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/autobahn/road-services', methods=['GET'])
def autobahn_road_services():
    """Get Autobahn services for a road"""
    try:
        road_id = request.args.get('road_id')
        service = request.args.get('service')
        if not road_id or not service:
            return jsonify({'success': False, 'error': 'road_id and service required'}), 400

        registry = get_api_registry()
        client = registry.create_api_instance('autobahn')
        if not client:
            return jsonify({'success': False, 'error': 'Autobahn client unavailable'}), 400

        data = client.get_road_services(road_id, service)
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"Autobahn road services error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard-deutschland/dashboard', methods=['GET'])
def dashboard_deutschland_dashboard():
    """Get Dashboard Deutschland entries"""
    try:
        registry = get_api_registry()
        client = registry.create_api_instance('dashboard_deutschland')
        if not client:
            return jsonify({'success': False, 'error': 'Dashboard client unavailable'}), 400

        data = client.get_dashboard_entries()
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"Dashboard Deutschland dashboard error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard-deutschland/indicators', methods=['GET'])
def dashboard_deutschland_indicators():
    """Get Dashboard Deutschland indicators by ids"""
    try:
        ids = request.args.get('ids', '')
        if not ids:
            return jsonify({'success': False, 'error': 'ids required'}), 400

        registry = get_api_registry()
        client = registry.create_api_instance('dashboard_deutschland')
        if not client:
            return jsonify({'success': False, 'error': 'Dashboard client unavailable'}), 400

        data = client.get_indicators([entry.strip() for entry in ids.split(',') if entry.strip()])
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"Dashboard Deutschland indicators error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard-deutschland/geojson', methods=['GET'])
def dashboard_deutschland_geojson():
    """Get Dashboard Deutschland GeoJSON"""
    try:
        registry = get_api_registry()
        client = registry.create_api_instance('dashboard_deutschland')
        if not client:
            return jsonify({'success': False, 'error': 'Dashboard client unavailable'}), 400

        data = client.get_geojson()
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"Dashboard Deutschland geojson error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deutschland-atlas/service-info', methods=['GET'])
def deutschland_atlas_service_info():
    """Get Deutschland Atlas service info"""
    try:
        service = request.args.get('service')
        if not service:
            return jsonify({'success': False, 'error': 'service required'}), 400

        registry = get_api_registry()
        client = registry.create_api_instance('deutschland_atlas')
        if not client:
            return jsonify({'success': False, 'error': 'Deutschland Atlas client unavailable'}), 400

        data = client.get_service_info(service)
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"Deutschland Atlas service info error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== UI Configuration Endpoints ====================

@app.route('/api/ui/system-config', methods=['GET', 'POST'])
def ui_system_config():
    """System-wide configuration (admin level)"""
    try:
        if request.method == 'GET':
            config = load_ai_config()
            return jsonify({
                'success': True,
                'config': {
                    'provider': config.get('provider', 'ollama'),
                    'base_url': config.get('base_url', ''),
                    'model': config.get('model', ''),
                    'immich_url_default': config.get('immich_url_default', ''),
                    'immich_api_key_default': config.get('immich_api_key_default', ''),
                    'vector_db_enabled': config.get('vector_db_enabled', True),
                    'vector_db_provider': config.get('vector_db_provider', 'qdrant'),
                    'vector_db_path': config.get('vector_db_path', './qdrant_data'),
                    'briefing_daily_enabled': config.get('briefing_daily_enabled', BRIEFING_DAILY_ENABLED_DEFAULT),
                    'briefing_weekly_enabled': config.get('briefing_weekly_enabled', BRIEFING_WEEKLY_ENABLED_DEFAULT),
                    'briefing_morning_hour': config.get('briefing_morning_hour', int(BRIEFING_MORNING_HOUR)),
                }
            })

        # POST - update system config
        data = request.get_json()
        config = load_ai_config()

        # Update config values
        if 'immich_url_default' in data:
            config['immich_url_default'] = data['immich_url_default']
        if 'immich_api_key_default' in data:
            config['immich_api_key_default'] = data['immich_api_key_default']
        if 'base_url' in data:
            config['base_url'] = data['base_url']
        if 'model' in data:
            config['model'] = data['model']
        if 'vector_db_enabled' in data:
            config['vector_db_enabled'] = data['vector_db_enabled']
        if 'briefing_daily_enabled' in data:
            config['briefing_daily_enabled'] = bool(data['briefing_daily_enabled'])
        if 'briefing_weekly_enabled' in data:
            config['briefing_weekly_enabled'] = bool(data['briefing_weekly_enabled'])
        if 'briefing_morning_hour' in data:
            config['briefing_morning_hour'] = max(0, min(23, int(data['briefing_morning_hour'])))

        # Save to file
        with open(AI_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # Reload config
        load_ai_config()

        return jsonify({'success': True, 'message': 'System configuration updated'})

    except Exception as e:
        logger.error(f"System config error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/runtime-config', methods=['GET', 'POST'])
def ui_runtime_config():
    """Runtime configuration (current session)"""
    try:
        if request.method == 'GET':
            config = load_ai_config()
            return jsonify({
                'success': True,
                'config': {
                    'ollama_base_url': config.get('base_url', ''),
                    'ollama_model': config.get('model', ''),
                    'ollama_connected': ollama_client.check_connection(),
                    'vector_db_enabled': config.get('vector_db_enabled', True),
                    'calendar_enabled': calendar_enabled,
                    'tasks_enabled': tasks_enabled
                }
            })

        # POST - update runtime config
        data = request.get_json()

        if 'base_url' in data and 'model' in data:
            ollama_client.update_config(data['base_url'], data['model'])
            save_ai_config(data['base_url'], data['model'])

        return jsonify({'success': True, 'message': 'Runtime configuration updated'})

    except Exception as e:
        logger.error(f"Runtime config error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/profile-config', methods=['GET', 'POST'])
def ui_profile_config():
    """User-specific profile configuration"""
    try:
        username = request.args.get('username') if request.method == 'GET' else request.get_json().get('username')

        if not username:
            return jsonify({'success': False, 'error': 'Username required'}), 400

        if request.method == 'GET':
            user_config = load_user_config(username)
            return jsonify({
                'success': True,
                'username': username,
                'config': {
                    'immich_url': user_config.get('immich_url', ''),
                    'immich_api_key': user_config.get('immich_api_key', ''),
                    'nextcloud_url': user_config.get('nextcloud_url', ''),
                    'nextcloud_username': user_config.get('nextcloud_username', ''),
                    'nextcloud_password': user_config.get('nextcloud_password', ''),
                    'caldav_url': user_config.get('caldav_url', ''),
                    'caldav_username': user_config.get('caldav_username', ''),
                    'caldav_password': user_config.get('caldav_password', '')
                }
            })

        # POST - update user config
        data = request.get_json()
        user_config = load_user_config(username)

        # Update user-specific settings
        if 'immich_url' in data:
            user_config['immich_url'] = data['immich_url']
        if 'immich_api_key' in data:
            user_config['immich_api_key'] = data['immich_api_key']
        if 'nextcloud_url' in data:
            user_config['nextcloud_url'] = data['nextcloud_url']
        if 'nextcloud_username' in data:
            user_config['nextcloud_username'] = data['nextcloud_username']
        if 'nextcloud_password' in data:
            user_config['nextcloud_password'] = data['nextcloud_password']
        if 'caldav_url' in data:
            user_config['caldav_url'] = data['caldav_url']
        if 'caldav_username' in data:
            user_config['caldav_username'] = data['caldav_username']
        if 'caldav_password' in data:
            user_config['caldav_password'] = data['caldav_password']

        save_user_config(username, user_config)

        return jsonify({'success': True, 'message': 'User profile updated'})

    except Exception as e:
        logger.error(f"Profile config error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/connectivity-status', methods=['GET'])
def ui_connectivity_status():
    """Check connectivity status of all services"""
    try:
        username = request.args.get('username')

        status = {
            'ollama': {
                'connected': ollama_client.check_connection(),
                'url': ollama_client.base_url,
                'model': ollama_client.model
            },
            'calendar': {
                'enabled': calendar_enabled,
                'connected': False
            },
            'tasks': {
                'enabled': tasks_enabled,
                'connected': False
            },
            'immich': {
                'configured': False,
                'connected': False
            }
        }

        # Check Immich connection
        if username:
            client = get_immich_client(username)
            if client:
                status['immich']['configured'] = True
                status['immich']['connected'] = client.test_connection()

        return jsonify({'success': True, 'status': status})

    except Exception as e:
        logger.error(f"Connectivity status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/index-status', methods=['GET'])
def ui_index_status():
    """Get indexing status"""
    try:
        # Get knowledge base stats
        stats = {
            'total_documents': 0,
            'total_chunks': 0,
            'last_indexed': None,
            'indexing_in_progress': False
        }

        if knowledge_base and knowledge_base.db:
            cursor = knowledge_base.db.cursor()

            # Count documents
            cursor.execute("SELECT COUNT(*) FROM files")
            stats['total_documents'] = cursor.fetchone()[0]

            # Count chunks
            cursor.execute("SELECT COUNT(*) FROM chunks")
            stats['total_chunks'] = cursor.fetchone()[0]

            # Get last indexed timestamp
            cursor.execute("SELECT MAX(indexed_at) FROM files")
            last_indexed = cursor.fetchone()[0]
            if last_indexed:
                stats['last_indexed'] = last_indexed

        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Index status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/suggestions', methods=['GET'])
def ui_suggestions():
    """Get query suggestions based on available data"""
    try:
        username = request.args.get('username')

        suggestions = []

        # Add calendar suggestions if available
        if calendar_enabled:
            suggestions.append({
                'type': 'calendar',
                'text': 'Was steht heute in meinem Kalender?',
                'icon': 'calendar'
            })

        # Add tasks suggestions if available
        if tasks_enabled:
            suggestions.append({
                'type': 'tasks',
                'text': 'Zeige meine offenen Aufgaben',
                'icon': 'checklist'
            })

        # Add Immich suggestions if configured
        if username:
            client = get_immich_client(username)
            if client:
                suggestions.append({
                    'type': 'photos',
                    'text': 'Zeige mir Fotos vom letzten Urlaub',
                    'icon': 'photo'
                })

        # Add file search suggestions
        suggestions.append({
            'type': 'files',
            'text': 'Suche nach Dokumenten zu Projekt X',
            'icon': 'document'
        })

        return jsonify({'success': True, 'suggestions': suggestions})

    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/immich', methods=['GET'])
def ui_immich_status():
    """Get Immich integration status"""
    try:
        username = request.args.get('username')

        if not username:
            return jsonify({'success': False, 'error': 'Username required'}), 400

        client = get_immich_client(username)

        status = {
            'configured': client is not None,
            'connected': False,
            'person_count': 0,
            'asset_count': 0
        }

        if client:
            status['connected'] = client.test_connection()

            if status['connected']:
                try:
                    # Get people count
                    people = client.get_people()
                    status['person_count'] = len(people)
                except:
                    pass

        return jsonify({'success': True, 'status': status})

    except Exception as e:
        logger.error(f"Immich status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Tools Execution Endpoint ====================

@app.route('/api/tools/test/<tool_name>', methods=['POST'])
def tools_test_execution(tool_name: str):
    """Execute a tool by name with provided parameters"""
    try:
        data = request.get_json() or {}
        username = data.get('username')

        # Map tool names to their implementations
        if tool_name == 'search_photos_immich':
            query = data.get('query', '')
            limit = data.get('limit', 20)

            client = get_immich_client(username)
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Immich nicht konfiguriert'
                }), 400

            result = client.search_photos_intelligent(query, limit=limit)
            return jsonify(result)

        elif tool_name == 'get_people_immich':
            client = get_immich_client(username)
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Immich nicht konfiguriert'
                }), 400

            people = client.get_people()
            return jsonify({
                'success': True,
                'people': people
            })

        elif tool_name == 'test_immich_connection':
            client = get_immich_client(username)
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Immich nicht konfiguriert'
                }), 400

            connected = client.test_connection()
            return jsonify({
                'success': True,
                'connected': connected
            })

        else:
            return jsonify({
                'success': False,
                'error': f'Unknown tool: {tool_name}'
            }), 404

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Agent Query Endpoint (Unified Chat Interface) ====================

_EMAIL_KEYWORDS = [
    'email', 'e-mail', 'e mail', 'mail', 'mails', 'emails', 'nachricht',
    'posteingang', 'inbox', 'absender', 'betreff', 'gesendet', 'sent',
    'newsletter', 'message', 'messages', 'inboxnachrichten'
]

_EMAIL_SEND_KEYWORDS = [
    'sende', 'schicke', 'schick', 'verschicke', 'email schreiben', 'mail schreiben',
    'schreibe eine mail', 'schreibe eine e-mail', 'write email', 'send email',
    'compose email', 'verfasse', 'antworten', 'reply', 'weiterleiten', 'forward'
]

_CONTACT_KEYWORDS = [
    'kontakt', 'kontakte', 'adressbuch', 'carddav', 'contact', 'contacts',
    'telefonbuch', 'person', 'personen', 'anschrift', 'email adresse', 'e-mail adresse', 'mailadresse'
]


def is_email_query(prompt: str) -> bool:
    """Return True if the prompt is likely asking about emails."""
    prompt_lower = prompt.lower()
    return any(kw in prompt_lower for kw in _EMAIL_KEYWORDS)


def is_email_send_query(prompt: str) -> bool:
    """Return True if the prompt is likely asking to draft or send an email."""
    prompt_lower = prompt.lower()
    if any(kw in prompt_lower for kw in _EMAIL_SEND_KEYWORDS):
        r'\b(?:schick\w*|sende|send|reply|antworte|antwort\w*)\b.*\b(?:antwort\w*|reply|e-?mail|mail|nachricht)\b',
        return True

    flexible_patterns = [
        r'\bschreib\w*\b.*\b(?:e-?mail|mail|nachricht)\b',
        r'\b(?:verfass\w*|formulier\w*|entwerf\w*|compose|write)\b.*\b(?:e-?mail|mail|nachricht)\b',
        r'\b(?:sende|send|schick\w*|verschick\w*|reply|antwort\w*|weiterleit\w*|forward)\b.*\b(?:e-?mail|mail|nachricht)\b',
    ]
    if any(re.search(pattern, prompt_lower, flags=re.IGNORECASE) for pattern in flexible_patterns):
        return True

    return is_email_query(prompt) and any(
        kw in prompt_lower for kw in ['sende', 'schicke', 'verschicke', 'schreib', 'verfasse', 'write', 'send', 'reply', 'antwort']
    )


def is_contact_query(prompt: str) -> bool:
    """Return True if the prompt is likely asking about contacts or an address book."""
    prompt_lower = prompt.lower()
    return any(kw in prompt_lower for kw in _CONTACT_KEYWORDS)


def is_email_read_query(prompt: str) -> bool:
    """Return True for inbox/list/search style email questions (not compose/send)."""
    prompt_lower = (prompt or '').lower()
    if not is_email_query(prompt) or is_email_send_query(prompt):
        return False

    return any(token in prompt_lower for token in [
        'welche', 'zeige', 'liste', 'list', 'posteingang', 'inbox', 'ungelesen',
        'heute', 'gestern', 'woche', 'month', 'monat', 'erhalten', 'eingegangen', 'angekommen'
    ])


def is_email_content_query(prompt: str) -> bool:
    """Return True for prompts asking for email content/summary."""
    prompt_lower = (prompt or '').lower()
    if not is_email_query(prompt) or is_email_send_query(prompt):
        return False

    return any(token in prompt_lower for token in [
        'was steht', 'inhalt', 'worum geht', 'zusammenfassen', 'zusammenfassung',
        'was schreibt', 'was steht drin', 'was steht in', 'content'
    ])


def _extract_email_query_tokens(prompt: str) -> List[str]:
    """Extract meaningful tokens for ranking a target email from a result list."""
    text = _normalize_lookup_text(prompt)
    stop_words = {
        'was', 'steht', 'in', 'dem', 'der', 'die', 'das', 'den', 'heute', 'gestern', 'mail',
        'email', 'e', 'von', 'ich', 'habe', 'bekommen', 'bitte', 'mir', 'zu', 'und', 'oder',
        'worum', 'geht', 'inhalt', 'zusammenfassung', 'zusammenfassen', 'welche', 'zeige',
        'posteingang', 'inbox', 'nachricht', 'nachrichten', 'ein', 'eine', 'einer'
    }
    tokens = [token for token in re.findall(r'[a-z0-9]+', text) if len(token) >= 3 and token not in stop_words]
    # Preserve order while removing duplicates.
    seen = set()
    result: List[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result


def _score_email_for_prompt(mail: Dict[str, Any], prompt: str) -> int:
    """Score an email entry by how well it matches the user prompt."""
    tokens = _extract_email_query_tokens(prompt)
    sender = _normalize_lookup_text(mail.get('sender', ''))
    subject = _normalize_lookup_text(mail.get('subject', ''))
    body = _normalize_lookup_text((mail.get('body', '') or '')[:600])

    score = 0
    for token in tokens:
        if token in sender:
            score += 30
        if token in subject:
            score += 18
        if token in body:
            score += 5

    prompt_lower = (prompt or '').lower()
    date_str = str(mail.get('date') or '').lower()
    if 'heute' in prompt_lower and datetime.now().strftime('%d %b').lower() in date_str:
        score += 5
    if 'gestern' in prompt_lower:
        score += 2

    return score


def _email_body_to_text(body: str) -> str:
    """Convert raw email body (plain text or HTML) into readable text."""
    if not body:
        return ''

    text = str(body)
    looks_like_html = '<html' in text.lower() or '<body' in text.lower() or '</' in text.lower()
    if looks_like_html:
        text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', ' ', text)
        text = re.sub(r'(?i)</?(br|p|div|li|tr|h1|h2|h3|h4|h5|h6)[^>]*>', '\n', text)
        text = re.sub(r'(?is)<[^>]+>', ' ', text)

    text = html.unescape(text)
    text = text.replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _build_email_content_summary(mail: Dict[str, Any], prompt: str) -> str:
    """Build a concise content summary for a single email."""
    subject = str(mail.get('subject') or '(kein Betreff)').strip()
    sender = str(mail.get('sender') or '').strip()
    date_str = str(mail.get('date') or '').strip()
    body_text = _email_body_to_text(str(mail.get('body') or ''))

    if not body_text:
        return f"Ich habe die Mail gefunden ({subject}), aber keinen lesbaren Inhalt extrahieren können."

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', body_text) if len(s.strip()) >= 30]
    preferred = [
        s for s in sentences
        if any(kw in s.lower() for kw in ['bewertung', 'bestellung', 'lass uns wissen', 'würden gerne wissen', 'feedback'])
    ]

    summary_sentences = preferred[:3] if preferred else sentences[:3]
    summary_text = ' '.join(summary_sentences).strip()
    if not summary_text:
        summary_text = body_text[:600] + ('...' if len(body_text) > 600 else '')

    header = f"In der Mail \"{subject}\""
    if sender:
        header += f" von {sender}"
    if date_str:
        header += f" ({date_str})"
    header += " geht es um Folgendes:"

    return f"{header}\n\n{summary_text}"


def extract_email_send_info_from_message(message: str) -> Dict[str, Any]:
    """Extract a rough email draft from a natural language request."""
    text = (message or '').strip()
    normalized = ' '.join(text.split())
    address_matches = re.findall(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', normalized, flags=re.IGNORECASE)

    subject = ''
    subject_match = re.search(r'(?:betreff|subject)[:\-]\s*(.+?)(?:\s{2,}|$)', normalized, flags=re.IGNORECASE)
    if subject_match:
        subject = subject_match.group(1).strip(' "')

    body = normalized
    body_match = re.search(r'(?:nachricht|text|inhalt|body)[:\-]\s*(.+)$', normalized, flags=re.IGNORECASE)
    if body_match:
        body = body_match.group(1).strip()

    if not subject:
        if is_email_send_query(normalized):
            subject = 'Neue Nachricht'
        elif address_matches:
            subject = 'Nachricht an ' + address_matches[0]

    missing_info = []
    if not address_matches:
        missing_info.append('Empfänger')
    if not body:
        missing_info.append('Nachrichtentext')

    return {
        'to': ', '.join(address_matches),
        'subject': subject,
        'body': body,
        'cc': '',
        'bcc': '',
        'missing_info': missing_info,
        'has_recipient': bool(address_matches)
    }


def _extract_email_from_text(text: str) -> str:
    """Extract the first email address from arbitrary text."""
    if not text:
        return ''
    match = re.search(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', str(text), flags=re.IGNORECASE)
    return match.group(0).strip() if match else ''


def _extract_contact_query_from_email_prompt(prompt: str) -> str:
    """Extract the intended recipient name from a compose-email prompt."""
    text = ' '.join((prompt or '').split())
    if not text:
        return ''

    patterns = [
        r'(?:an|für|to)\s+(?:den|die|das|dem|der|the)?\s*([^,.;:]+?)(?:\s+(?:und|mit|wegen|bezüglich)\b.*)?$',
        r'(?:schreibe|sende|schick(?:e)?|verschicke|compose|write)\s+(?:eine\s+)?(?:e-?mail|mail|nachricht)\s+(?:an|für|to)\s+([^,.;:]+?)(?:\s+(?:und|mit|wegen|bezüglich)\b.*)?$',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(' "')
            if candidate and not _extract_email_from_text(candidate):
                return candidate

    return ''


def _normalize_lookup_text(text: str) -> str:
    """Normalize text for robust contact matching without umlaut sensitivity."""
    value = str(text or '').lower().strip()
    replacements = {
        'ä': 'ae',
        'ö': 'oe',
        'ü': 'ue',
        'ß': 'ss',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r'[^a-z0-9\s@._-]+', ' ', value)
    return ' '.join(value.split())


def _score_contact_match(contact: Dict[str, Any], recipient_query: str) -> int:
    """Score how well a contact fits the requested recipient name."""
    query_norm = _normalize_lookup_text(recipient_query)
    if not query_norm:
        return 0

    full_name = _normalize_lookup_text(contact.get('full_name', ''))
    given_name = _normalize_lookup_text(contact.get('given_name', ''))
    family_name = _normalize_lookup_text(contact.get('family_name', ''))
    organization = _normalize_lookup_text(contact.get('organization', ''))
    haystack = ' '.join([full_name, given_name, family_name, organization]).strip()

    score = 0
    if full_name == query_norm:
        score += 100
    if given_name and family_name and query_norm in [
        f'{given_name} {family_name}'.strip(),
        f'{family_name} {given_name}'.strip()
    ]:
        score += 95
    if query_norm and query_norm in haystack:
        score += 35

    query_tokens = [token for token in query_norm.split() if len(token) >= 2]
    for token in query_tokens:
        if token in full_name:
            score += 10
        elif token in haystack:
            score += 4

    score += min(5, len(contact.get('email', []) or []))
    return score


def get_carddav_client(username: str = None) -> Optional['NextcloudCardDAVClient']:
    """Return a configured CardDAV client for *username*, or None if unavailable."""
    try:
        config = get_nextcloud_runtime_config()
        if not config:
            return None

        nextcloud_url = str(config.get('url') or config.get('nextcloud_url') or '').strip()
        nextcloud_username = str(username or config.get('username') or '').strip()
        password = str(config.get('password') or '').strip()
        if not all([nextcloud_url, nextcloud_username, password]):
            return None

        return NextcloudCardDAVClient(nextcloud_url, nextcloud_username, password)
    except Exception as e:
        logger.debug('CardDAV client not available: %s', e)
        return None


def search_carddav_contacts(query: str, username: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Search contacts in CardDAV address books by query."""
    client = get_carddav_client(username)
    if not client or not query.strip():
        return []

    matches: List[Dict[str, Any]] = []
    query_lower = query.lower().strip()

    try:
        addressbooks = client.get_addressbooks()
        addressbook_names = [book.get('name') for book in addressbooks if book.get('name')] or ['contacts']

        for addressbook_name in addressbook_names:
            try:
                contacts = client.search_contacts(query, addressbook_name)
                for contact in contacts:
                    display_name = contact.get('full_name') or ' '.join([
                        contact.get('given_name', ''),
                        contact.get('family_name', '')
                    ]).strip()
                    searchable = ' '.join([
                        display_name,
                        contact.get('given_name', ''),
                        contact.get('family_name', ''),
                        contact.get('organization', ''),
                        ' '.join(contact.get('email', [])),
                    ]).lower()

                    if query_lower in searchable:
                        enriched = dict(contact)
                        enriched['addressbook_name'] = addressbook_name
                        matches.append(enriched)
            except Exception as e:
                logger.debug('CardDAV search failed for addressbook %s: %s', addressbook_name, e)

        # Deduplicate by contact URL/id and prefer contacts with the most email addresses.
        deduped: Dict[str, Dict[str, Any]] = {}
        for contact in matches:
            key = str(contact.get('url') or contact.get('id') or contact.get('full_name') or contact.get('organization') or id(contact))
            existing = deduped.get(key)
            if not existing or len(contact.get('email', [])) > len(existing.get('email', [])):
                deduped[key] = contact

        sorted_matches = sorted(
            deduped.values(),
            key=lambda item: (
                0 if query_lower in str(item.get('full_name', '')).lower() else 1,
                -(len(item.get('email', [])) or 0),
                str(item.get('full_name', '')).lower()
            )
        )
        return sorted_matches[:limit]
    except Exception as e:
        logger.debug('CardDAV contact search error: %s', e)
        return []


def resolve_email_contacts_for_prompt(
    prompt: str,
    username: str = None,
    limit: int = 5,
    timeout_seconds: float = 8.0
) -> Dict[str, Any]:
    """Resolve likely recipient contacts for an email compose prompt."""
    recipient_query = _extract_contact_query_from_email_prompt(prompt)
    search_query = recipient_query or prompt
    contacts: List[Dict[str, Any]] = []

    # CardDAV lookups can be slow on some servers. Use a hard timeout so
    # compose requests never block the full chat endpoint.
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(search_carddav_contacts, search_query, username, limit)
    try:
        contacts = future.result(timeout=max(0.5, float(timeout_seconds or 3.0)))
    except FuturesTimeoutError:
        logger.warning('CardDAV recipient lookup timed out for query: %s', search_query)
        future.cancel()
        contacts = []
    except Exception as e:
        logger.debug('CardDAV recipient lookup failed: %s', e)
        contacts = []
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    scored_contacts: List[Dict[str, Any]] = sorted(
        contacts,
        key=lambda item: _score_contact_match(item, recipient_query),
        reverse=True
    )

    email_candidates: List[str] = []
    for contact in scored_contacts:
        for email_address in contact.get('email', []) or []:
            email_address = str(email_address).strip()
            if email_address and email_address not in email_candidates:
                email_candidates.append(email_address)

    top_contact = scored_contacts[0] if scored_contacts else None
    top_score = _score_contact_match(top_contact, recipient_query) if top_contact else 0

    best_email = ''
    if len(email_candidates) == 1:
        best_email = email_candidates[0]
    elif top_contact and (top_contact.get('email') or []):
        # For clearly identified recipients, auto-pick the primary address.
        best_email = str((top_contact.get('email') or [''])[0]).strip()

    needs_selection = len(email_candidates) > 1 and not (best_email and top_score >= 45)

    return {
        'recipient_query': recipient_query,
        'contacts': scored_contacts,
        'email_candidates': email_candidates,
        'best_email': best_email,
        'needs_selection': needs_selection,
        'has_contact_match': bool(contacts)
    }


def get_email_client(
    username: str = None,
    account_id: str = None,
    config: Dict[str, Any] = None,
    use_cache: bool = True
) -> Optional['EmailClient']:
    """Return a configured EmailClient for *username* and optional *account_id*."""
    try:
        registry = get_api_registry()

        effective_config = None
        if config is not None:
            effective_config = dict(config)
        elif account_id:
            effective_config = registry.load_config('email', username)

        if account_id:
            if effective_config is None:
                effective_config = {}
            effective_config['selected_account_id'] = account_id

        if effective_config is None:
            return registry.create_api_instance('email', username=username, use_cache=use_cache)

        return registry.create_api_instance('email', config=effective_config, username=username, use_cache=False)
    except Exception as e:
        logger.debug("Email client not available: %s", e)
        return None


def detect_query_intent(prompt: str, preferred_source: str = 'auto') -> str:
    """
    Erkennt die Intention der Anfrage

    Returns: 'photos', 'files', 'calendar', 'tasks', 'email', 'mixed', 'general'
    """
    prompt_lower = prompt.lower()

    # Wenn explizite Quelle gewählt wurde, respektiere das
    if preferred_source == 'photos':
        return 'photos'
    elif preferred_source == 'files':
        return 'files'
    elif preferred_source == 'email':
        return 'email'

    # Erkenne Foto-Anfragen
    photo_keywords = ['foto', 'fotos', 'bild', 'bilder', 'image', 'images', 'photo', 'photos',
                     'immich', 'person', 'personen', 'gesicht', 'album', 'aufnahme', 
                     'zeig mir', 'gib mir', 'show me', 'finde', 'find',
                     'katze', 'hund', 'baum', 'auto', 'haus', 'mensch',
                     'katzen', 'hunde', 'bäume', 'autos', 'häuser', 'menschen']
    has_photo = any(keyword in prompt_lower for keyword in photo_keywords)
    
    # Erkenne Datei-Anfragen
    file_keywords = ['datei', 'dateien', 'dokument', 'dokumente', 'pdf', 'unterlage',
                    'unterlagen', 'file', 'files', 'document', 'documents', 'nextcloud']
    has_file = any(keyword in prompt_lower for keyword in file_keywords)

    # Erkenne Kalender-Anfragen
    time_keywords = ['termin', 'termine', 'kalender', 'heute', 'morgen', 'wann', 'woche',
                    'datum', 'event', 'ereignis', 'meeting', 'appointment',
                    'steht an', 'habe ich', 'mache ich', 'ist geplant', 'vorhaben']
    has_time = any(keyword in prompt_lower for keyword in time_keywords)

    # Erkenne Task-Anfragen
    task_keywords = ['task', 'tasks', 'todo', 'todos', 'aufgabe', 'aufgaben',
                    'erledigen', 'machen', 'erinnerung', 'erinnerungen', 'reminder', 'reminders']
    has_task = any(keyword in prompt_lower for keyword in task_keywords)

    # Erkenne E-Mail-Anfragen
    has_email = is_email_query(prompt)

    # Bestimme primäre Intention
    active_intents = sum([has_photo, has_file, has_time, has_task, has_email])

    # E-Mail-Anfragen haben Vorrang wenn eindeutig
    if has_email and not has_photo and not has_file and not has_task:
        return 'email'
    # Fotoanfragen mit Zeitbezug (z. B. "Foto von heute") sollen als
    # Foto-Intent laufen und nicht in den gemischten Pfad fallen.
    if has_photo and not has_file and not has_task:
        return 'photos'
    elif has_file and not has_photo and not has_time and not has_task:
        return 'files'
    elif has_task and not has_photo and not has_file:
        return 'tasks'
    elif has_time and not has_photo and not has_file and not has_task:
        return 'calendar'
    elif active_intents >= 2:
        return 'mixed'
    else:
        return 'general'


def _build_integration_connect_response(provider: str, prompt: str, language: str = 'de', feature: str = '') -> Dict[str, Any]:
    """Builds a unified interactive setup response for missing integrations."""
    is_german = str(language or '').lower().startswith('de')
    requested_feature = feature or provider

    if provider == 'nextcloud':
        response_text = (
            "Ich kann diese Anfrage erst ausführen, wenn Nextcloud verbunden ist. "
            "Du kannst dich jetzt direkt hier verbinden."
            if is_german else
            "I can run this request once Nextcloud is connected. You can connect it directly here now."
        )
        title = 'Nextcloud verbinden' if is_german else 'Connect Nextcloud'
        description = (
            'Verbinde zuerst Nextcloud per Login-Flow oder hinterlege URL + Benutzername + App-Passwort.'
            if is_german else
            'Connect Nextcloud via login flow or provide URL, username, and app password.'
        )
        fields = [
            {
                'name': 'nextcloud_url',
                'label': 'Nextcloud URL',
                'type': 'url',
                'required': True,
                'placeholder': 'https://cloud.example.com'
            },
            {
                'name': 'username',
                'label': 'Username',
                'type': 'text',
                'required': True,
                'placeholder': 'your.username'
            },
            {
                'name': 'password',
                'label': 'App Password',
                'type': 'password',
                'required': True,
                'placeholder': '••••••••'
            }
        ]
        quick_actions = [
            {
                'type': 'nextcloud_login_flow',
                'label': 'Login with Nextcloud' if not is_german else 'Mit Nextcloud einloggen'
            }
        ]
        submit_endpoint = '/api/nextcloud/login'
    elif provider == 'immich':
        response_text = (
            'Ich brauche eine konfigurierte Immich-Verbindung, um danach suchen zu können.'
            if is_german else
            'I need an active Immich connection before I can search photos.'
        )
        title = 'Immich konfigurieren' if is_german else 'Configure Immich'
        description = (
            'Trage Immich URL und API Key ein. Die Werte werden als Standard-Konfiguration gespeichert.'
            if is_german else
            'Enter Immich URL and API key. Values will be saved as default configuration.'
        )
        fields = [
            {
                'name': 'immich_url_default',
                'label': 'Immich URL',
                'type': 'url',
                'required': True,
                'placeholder': 'https://immich.example.com'
            },
            {
                'name': 'immich_api_key_default',
                'label': 'API Key',
                'type': 'password',
                'required': True,
                'placeholder': '••••••••'
            }
        ]
        quick_actions = []
        submit_endpoint = '/api/ui/system-config'
    else:
        response_text = (
            'Für diese Funktion fehlt noch eine API-Verbindung.'
            if is_german else
            'This feature needs an API connection before it can be used.'
        )
        title = 'API konfigurieren' if is_german else 'Configure API'
        description = (
            'Bitte hinterlege die notwendigen Zugangsdaten.'
            if is_german else
            'Please enter the required credentials.'
        )
        fields = []
        quick_actions = []
        submit_endpoint = ''

    return {
        'success': True,
        'response': response_text,
        'action': 'integration_connect_required',
        'requires_input': True,
        'integration_setup': {
            'provider': provider,
            'feature': requested_feature,
            'title': title,
            'description': description,
            'fields': fields,
            'quick_actions': quick_actions,
            'submit_endpoint': submit_endpoint,
            'prefill': {},
            'original_prompt': prompt
        },
        'sources': [],
        'ui_cards': []
    }

@app.route('/api/agent/query', methods=['POST'])
def agent_query():
    """
    Unified query endpoint that intelligently routes queries to appropriate sources
    (photos, files, calendar, tasks) and generates AI responses
    """
    try:
        data = request.get_json()
        prompt = data.get('prompt', '').strip()
        username = data.get('username')
        account_id = data.get('account_id')
        language = data.get('language', 'de')
        context = data.get('context', '')  # Previous conversation context
        preferred_source = data.get('preferred_source', 'auto')
        email_config = data.get('email_config') or data.get('emailConfig')

        if not prompt:
            return jsonify({
                'success': False,
                'error': 'Keine Anfrage erhalten'
            }), 400

        # Fast path for compose/send email requests before running other
        # potentially slow context gatherers (weather/security/activity).
        if is_email_send_query(prompt):
            recipient_resolution = resolve_email_contacts_for_prompt(prompt, username=username)
            draft_card = _build_email_card(prompt, language)
            draft_source = _build_email_source_card(
                subject=str(draft_card.get('subject') or 'Neue Nachricht').strip(),
                sender=str(draft_card.get('to') or recipient_resolution.get('recipient_query') or 'Entwurf').strip() or 'Entwurf',
                date_str='',
                folder='Entwurf',
                body_preview=str(draft_card.get('body') or '').strip() or str(prompt or '').strip(),
                label='E-Mail-Entwurf'
            )
            contact_sources = [
                _build_contact_source_card(contact, 'Empfänger')
                for contact in (recipient_resolution.get('contacts', []) or [])[:3]
            ]

            if recipient_resolution.get('has_contact_match') and recipient_resolution.get('needs_selection'):
                contact_cards = recipient_resolution.get('contacts', [])
                contact_title = recipient_resolution.get('recipient_query') or 'den Kontakt'
                contact_card = _build_contact_card(prompt, contact_cards, language)

                return jsonify({
                    'success': True,
                    'response': f'Ich habe mehrere E-Mail-Adressen für {contact_title} gefunden. Welche soll ich verwenden?',
                    'action': 'email_recipient_selection',
                    'requires_input': True,
                    'recipient_query': recipient_resolution.get('recipient_query', ''),
                    'contacts': contact_cards,
                    'email_candidates': recipient_resolution.get('email_candidates', []),
                    'sources': [draft_source, *contact_sources],
                    'ui_cards': [contact_card],
                    'context_used': False,
                    'context_count': 0,
                    'training_saved': False
                })

            email_card = draft_card
            cards = []

            if recipient_resolution.get('best_email') and not email_card.get('to'):
                email_card['to'] = recipient_resolution.get('best_email', '')

            if recipient_resolution.get('has_contact_match') and not email_card.get('to'):
                contact_cards = recipient_resolution.get('contacts', [])
                if contact_cards:
                    cards.append(_build_contact_card(prompt, contact_cards, language))

            cards.append(email_card)

            if email_card.get('to'):
                response_text = 'Ich habe eine E-Mail-Vorlage vorbereitet. Du kannst sie jetzt direkt prüfen und senden.'
            else:
                response_text = 'Ich habe eine E-Mail-Vorlage vorbereitet. Bitte wähle einen Empfänger oder ergänze die Adresse.'

            return jsonify({
                'success': True,
                'response': response_text,
                'action': 'email_compose',
                'requires_input': True,
                'recipient_query': recipient_resolution.get('recipient_query', ''),
                'contacts': recipient_resolution.get('contacts', []),
                'email_candidates': recipient_resolution.get('email_candidates', []),
                'sources': [draft_source, *contact_sources],
                'ui_cards': cards,
                'context_used': False,
                'context_count': 0,
                'training_saved': False
            })

        # Fast path for email read/list queries to avoid slow mixed pipelines and
        # ensure deterministic inbox answers.
        if is_email_read_query(prompt):
            email_client_instance = get_email_client(
                username=username,
                account_id=account_id,
                config=email_config if isinstance(email_config, dict) else None
            )
            if not email_client_instance:
                return jsonify({
                    'success': False,
                    'error': 'E-Mail ist nicht konfiguriert. Bitte hinterlege die IMAP-Zugangsdaten in den Einstellungen.'
                }), 400

            profile = _build_email_query_profile(prompt)
            is_content_request = is_email_content_query(prompt)

            if profile.get('mode') == 'general':
                emails = email_client_instance.search_emails(prompt, limit=10)
                prompt_norm = ' '.join((prompt or '').split()).strip().lower()
                if not emails and ('heute' in prompt_norm or 'today' in prompt_norm) and any(
                    token in prompt_norm for token in ['mail', 'e-mail', 'email', 'posteingang', 'inbox']
                ):
                    today = date.today()
                    emails = email_client_instance.fetch_emails(
                        limit=20,
                        folder_focus='inbox',
                        since=today,
                        until=today,
                        unread=None,
                    )
            else:
                emails = email_client_instance.fetch_emails(
                    limit=profile.get('limit', 10),
                    folder_focus=profile.get('folder_focus', 'all'),
                    since=profile.get('since'),
                    until=profile.get('until'),
                    unread=profile.get('unread'),
                )

                # If today's inbox is empty, retry across all folders to avoid
                # false negatives caused by provider-specific inbox mapping.
                if not emails and profile.get('mode') in ['today_received', 'today_content']:
                    emails = email_client_instance.fetch_emails(
                        limit=profile.get('limit', 10),
                        folder_focus='all',
                        since=profile.get('since'),
                        until=profile.get('until'),
                        unread=profile.get('unread'),
                    )

            if not emails:
                return jsonify({
                    'success': True,
                    'response': 'Ich habe keine passenden E-Mails gefunden. Möchtest du, dass ich ohne Zeitfilter im gesamten Posteingang suche?',
                    'action': 'email_list',
                    'requires_input': False,
                    'sources': [],
                    'ui_cards': [],
                    'context_used': False,
                    'context_count': 0,
                    'training_saved': False
                })

            if is_content_request:
                target_mail = max(emails, key=lambda m: _score_email_for_prompt(m, prompt))
                content_response = _build_email_content_summary(target_mail, prompt)
                body_text = _email_body_to_text(str(target_mail.get('body') or ''))
                preview = body_text[:300] + ('...' if len(body_text) > 300 else '')
                email_source = _build_email_source_card(
                    subject=str(target_mail.get('subject') or '(kein Betreff)').strip(),
                    sender=str(target_mail.get('sender') or '').strip(),
                    date_str=str(target_mail.get('date') or '').strip(),
                    folder=str(target_mail.get('folder') or 'INBOX').strip(),
                    body_preview=preview,
                    label='E-Mail-Inhalt'
                )

                return jsonify({
                    'success': True,
                    'response': content_response,
                    'action': 'email_content',
                    'requires_input': False,
                    'email_results': [{
                        'subject': str(target_mail.get('subject') or '(kein Betreff)').strip(),
                        'sender': str(target_mail.get('sender') or '').strip(),
                        'date': str(target_mail.get('date') or '').strip(),
                        'folder': str(target_mail.get('folder') or 'INBOX').strip(),
                        'body_preview': preview,
                        'uid': target_mail.get('uid')
                    }],
                    'sources': [email_source],
                    'ui_cards': [],
                    'context_used': False,
                    'context_count': 0,
                    'training_saved': False
                })

            preview_items = []
            response_lines = [f"Ich habe {len(emails)} passende E-Mails gefunden:"]
            for idx, mail in enumerate(emails[:10], 1):
                subject = str(mail.get('subject') or '(kein Betreff)').strip()
                sender = str(mail.get('sender') or '').strip()
                date_str = str(mail.get('date') or '').strip()
                folder = str(mail.get('folder') or 'INBOX').strip()
                response_lines.append(f"{idx}. {subject}" + (f" - von {sender}" if sender else "") + (f" ({date_str})" if date_str else ""))

                body = str(mail.get('body') or '').strip()
                preview_items.append({
                    'subject': subject,
                    'sender': sender,
                    'date': date_str,
                    'folder': folder,
                    'body_preview': (body[:300] + '...') if len(body) > 300 else body,
                    'uid': mail.get('uid')
                })

            return jsonify({
                'success': True,
                'response': '\n'.join(response_lines),
                'action': 'email_list',
                'requires_input': False,
                'email_results': preview_items,
                'sources': [],
                'ui_cards': [],
                'context_used': False,
                'context_count': 0,
                'training_saved': False
            })

        message_lower = prompt.lower()

        # Gather weather context if query is weather-related (but let AI respond)
        weather_context = gather_weather_context(
            get_local_weather_status, is_weather_query, prompt, _safe_text
        )

        # Gather security context if query is security-related (but let AI respond)
        security_context = gather_security_context(
            get_local_security_status, is_security_query, prompt
        )

        # Gather activity context if query is activity-related (but let AI respond)
        activity_context = gather_activity_context(
            get_updates_context, is_activity_query, prompt
        )
        is_activity_question = is_activity_query(prompt)

        # Calendar heuristic (same as legacy /api/chat)
        time_related_indicators = [
            'wann', 'zeit', 'datum', 'termin', 'ereignis', 'appointment',
            'event', 'kalender', 'heute', 'morgen', 'woche', 'tag', 'monat',
            'steht an', 'habe ich', 'mache ich', 'ist geplant', 'vorhaben'
        ]
        question_words = ['was', 'welche', 'wie', 'wann', 'ob', 'kannst du']
        has_time_indicators = any(indicator in message_lower for indicator in time_related_indicators)
        has_question = any(word in message_lower.split()[:3] for word in question_words)
        is_potentially_calendar_query = has_time_indicators and has_question
        intent = detect_query_intent(prompt, preferred_source)

        # If the user wants to draft an email and we found multiple contact emails,
        # ask which one should be used before composing the draft.
        if is_email_send_query(prompt):
            recipient_resolution = resolve_email_contacts_for_prompt(prompt, username=username)
            if recipient_resolution.get('has_contact_match') and recipient_resolution.get('needs_selection'):
                contact_cards = recipient_resolution.get('contacts', [])
                contact_title = recipient_resolution.get('recipient_query') or 'den Kontakt'
                contact_card = _build_contact_card(prompt, contact_cards, language)

                return jsonify({
                    'success': True,
                    'response': f'Ich habe mehrere E-Mail-Adressen für {contact_title} gefunden. Welche soll ich verwenden?',
                    'action': 'email_recipient_selection',
                    'requires_input': True,
                    'recipient_query': recipient_resolution.get('recipient_query', ''),
                    'contacts': contact_cards,
                    'email_candidates': recipient_resolution.get('email_candidates', []),
                    'sources': [],
                    'ui_cards': [contact_card],
                    'context_used': False,
                    'context_count': 0,
                    'training_saved': False
                })

            # Fast path for compose/send requests: return interactive UI cards immediately
            # instead of running the full autonomous + context pipeline.
            email_card = _build_email_card(prompt, language)
            cards = []

            if recipient_resolution.get('best_email') and not email_card.get('to'):
                email_card['to'] = recipient_resolution.get('best_email', '')

            if recipient_resolution.get('has_contact_match') and not email_card.get('to'):
                contact_cards = recipient_resolution.get('contacts', [])
                if contact_cards:
                    cards.append(_build_contact_card(prompt, contact_cards, language))

            cards.append(email_card)

            if email_card.get('to'):
                response_text = 'Ich habe eine E-Mail-Vorlage vorbereitet. Du kannst sie jetzt direkt prüfen und senden.'
            else:
                response_text = 'Ich habe eine E-Mail-Vorlage vorbereitet. Bitte wähle einen Empfänger oder ergänze die Adresse.'

            return jsonify({
                'success': True,
                'response': response_text,
                'action': 'email_compose',
                'requires_input': True,
                'recipient_query': recipient_resolution.get('recipient_query', ''),
                'contacts': recipient_resolution.get('contacts', []),
                'email_candidates': recipient_resolution.get('email_candidates', []),
                'sources': [],
                'ui_cards': cards,
                'context_used': False,
                'context_count': 0,
                'training_saved': False
            })

        # Interactive event creation: Let AI handle missing information naturally
        if is_calendar_create_query(prompt):
            if not get_nextcloud_runtime_config():
                return jsonify(_build_integration_connect_response('nextcloud', prompt, language, feature='calendar_create'))

            event_info = extract_event_info_from_message(prompt)

            if event_info.get('missing_info'):
                calendars = []
                if simple_calendar_manager:
                    try:
                        calendars = simple_calendar_manager.get_calendars()
                    except Exception as e:
                        logger.warning(f"Could not load calendars for interactive form: {e}")

                # Build context for AI to handle missing information
                missing_context = {
                    'content': f"""=== TERMIN-ERSTELLUNG ===
Der Nutzer möchte einen Termin erstellen.

Bereits extrahierte Informationen:
- Titel: {event_info.get('title') or 'nicht angegeben'}
- Startzeit: {event_info.get('start_time') or 'nicht angegeben'}
- Endzeit: {event_info.get('end_time') or 'nicht angegeben'}
- Ort: {event_info.get('location') or 'nicht angegeben'}
- Kalender: {event_info.get('calendar_name') or 'nicht angegeben'}

Fehlende Informationen: {', '.join(event_info['missing_info'])}

Verfügbare Kalender: {', '.join([cal['name'] for cal in calendars]) if calendars else 'nicht verfügbar'}

AUFGABE: Frage den Nutzer natürlich nach den fehlenden Informationen.
Erkläre, welche Angaben noch benötigt werden, um den Termin zu erstellen.""",
                    'source': 'Termin-Erstellung',
                    'path': 'calendar_creation',
                    'similarity_score': 1.0,
                    'metadata': {
                        'action': 'calendar_missing_input',
                        'extracted_info': event_info,
                        'available_calendars': calendars
                    }
                }

                # Let AI generate the response about missing information
                system_message = f"""Du bist ein intelligenter persönlicher Assistent.

{missing_context['content']}

WICHTIG:
- Antworte auf {language}
- Frage natürlich und freundlich nach den fehlenden Informationen
- Variiere deine Formulierung - vermeide stereotype Phrasen
- Sei präzise und hilfreich"""

                messages = [
                    {'role': 'system', 'content': system_message},
                    {'role': 'user', 'content': prompt}
                ]

                try:
                    response = ollama_client.chat(messages, [])
                    ai_response = response.get('message', {}).get('content',
                        f"Um den Termin zu erstellen, benötige ich noch: {', '.join(event_info['missing_info'])}")
                except Exception as e:
                    logger.error(f"AI generation error for calendar missing input: {e}")
                    ai_response = f"Um den Termin zu erstellen, benötige ich noch: {', '.join(event_info['missing_info'])}"

                return jsonify({
                    'response': ai_response,
                    'action': 'calendar_missing_input',
                    'requires_input': True,
                    'missing_info': event_info['missing_info'],
                    'extracted_info': {
                        'title': event_info.get('title'),
                        'start_time': event_info.get('start_time'),
                        'end_time': event_info.get('end_time'),
                        'location': event_info.get('location'),
                        'calendar_name': event_info.get('calendar_name')
                    },
                    'available_calendars': calendars,
                    'context_used': False,
                    'context_count': 0,
                    'calendar_used': True,
                    'training_saved': False,
                    'sources': []
                })

            # Create event and let AI generate success/failure message
            create_result = create_calendar_event(
                title=event_info.get('title'),
                start_time=event_info.get('start_time'),
                end_time=event_info.get('end_time'),
                calendar_name=event_info.get('calendar_name'),
                location=event_info.get('location'),
                description=prompt
            )

            # Let AI generate natural response about success/failure
            result_context = f"""=== TERMIN-ERSTELLUNG ===
Ergebnis: {'Erfolg' if create_result.get('success') else 'Fehler'}
{create_result.get('message', '') if create_result.get('success') else create_result.get('error', 'Unbekannter Fehler')}

Erstellter Termin:
- Titel: {event_info.get('title')}
- Startzeit: {event_info.get('start_time')}
- Endzeit: {event_info.get('end_time')}
- Ort: {event_info.get('location') or 'kein Ort'}
- Kalender: {event_info.get('calendar_name') or 'Standard-Kalender'}

AUFGABE: Informiere den Nutzer {'über die erfolgreiche Erstellung' if create_result.get('success') else 'über den Fehler'} des Termins.
Formuliere die Nachricht natürlich und variiert."""

            system_message = f"""Du bist ein intelligenter persönlicher Assistent.

{result_context}

WICHTIG:
- Antworte auf {language}
- Formuliere die Nachricht natürlich und freundlich
- Variiere deine Formulierung - vermeide stereotype Phrasen"""

            messages = [
                {'role': 'system', 'content': system_message},
                {'role': 'user', 'content': prompt}
            ]

            try:
                response = ollama_client.chat(messages, [])
                ai_response = response.get('message', {}).get('content',
                    create_result.get('message', 'Termin wurde erstellt.') if create_result.get('success')
                    else f"Fehler: {create_result.get('error', 'Unbekannter Fehler')}")
            except Exception as e:
                logger.error(f"AI generation error for calendar result: {e}")
                ai_response = (create_result.get('message', 'Termin wurde erstellt.') if create_result.get('success')
                              else f"Fehler: {create_result.get('error', 'Unbekannter Fehler')}")

            return jsonify({
                'response': ai_response,
                'action': 'calendar_created' if create_result.get('success') else 'calendar_create_failed',
                'calendar_used': True,
                'context_used': False,
                'context_count': 0,
                'training_saved': False,
                'sources': [],
                'created_event': create_result if create_result.get('success') else None
            })

        # Interactive task/reminder creation: Let AI handle missing information naturally
        if is_task_create_query(prompt):
            if not get_nextcloud_runtime_config():
                return jsonify(_build_integration_connect_response('nextcloud', prompt, language, feature='task_create'))

            task_info = extract_task_info_from_message(prompt)

            if task_info.get('missing_info'):
                available_task_lists = get_available_task_lists()

                # Build context for AI to handle missing information
                missing_context = f"""=== AUFGABEN-ERSTELLUNG ===
Der Nutzer möchte eine Aufgabe/Erinnerung erstellen.

Bereits extrahierte Informationen:
- Titel: {task_info.get('title') or 'nicht angegeben'}
- Fälligkeitsdatum: {task_info.get('due_date') or 'nicht angegeben'}
- Priorität: {task_info.get('priority', 0) or 'nicht angegeben'}
- Liste: {task_info.get('list_name') or 'nicht angegeben'}
- Ort: {task_info.get('location') or 'nicht angegeben'}

Fehlende Informationen: {', '.join(task_info['missing_info'])}

Verfügbare Aufgabenlisten: {', '.join(available_task_lists) if available_task_lists else 'nicht verfügbar'}

AUFGABE: Frage den Nutzer natürlich nach den fehlenden Informationen.
Erkläre, welche Angaben noch benötigt werden, um die Aufgabe zu erstellen."""

                system_message = f"""Du bist ein intelligenter persönlicher Assistent.

{missing_context}

WICHTIG:
- Antworte auf {language}
- Frage natürlich und freundlich nach den fehlenden Informationen
- Variiere deine Formulierung - vermeide stereotype Phrasen
- Sei präzise und hilfreich"""

                messages = [
                    {'role': 'system', 'content': system_message},
                    {'role': 'user', 'content': prompt}
                ]

                try:
                    response = ollama_client.chat(messages, [])
                    ai_response = response.get('message', {}).get('content',
                        f"Um die Aufgabe zu erstellen, benötige ich noch: {', '.join(task_info['missing_info'])}")
                except Exception as e:
                    logger.error(f"AI generation error for task missing input: {e}")
                    ai_response = f"Um die Aufgabe zu erstellen, benötige ich noch: {', '.join(task_info['missing_info'])}"

                return jsonify({
                    'response': ai_response,
                    'action': 'task_missing_input',
                    'requires_input': True,
                    'missing_info': task_info['missing_info'],
                    'extracted_info': {
                        'title': task_info.get('title'),
                        'due_date': task_info.get('due_date'),
                        'priority': task_info.get('priority', 0),
                        'list_name': task_info.get('list_name'),
                        'location': task_info.get('location'),
                        'description': task_info.get('description')
                    },
                    'available_task_lists': available_task_lists,
                    'context_used': False,
                    'context_count': 0,
                    'calendar_used': False,
                    'training_saved': False,
                    'sources': []
                })

            # Create task and let AI generate success/failure message
            create_result = create_task_reminder(
                title=task_info.get('title'),
                description=task_info.get('description') or prompt,
                due_date=task_info.get('due_date'),
                priority=task_info.get('priority', 0),
                list_name=task_info.get('list_name'),
                location=task_info.get('location')
            )

            # Let AI generate natural response about success/failure
            result_context = f"""=== AUFGABEN-ERSTELLUNG ===
Ergebnis: {'Erfolg' if create_result.get('success') else 'Fehler'}
{create_result.get('message', '') if create_result.get('success') else create_result.get('error', 'Unbekannter Fehler')}

Erstellte Aufgabe:
- Titel: {task_info.get('title')}
- Fälligkeitsdatum: {task_info.get('due_date') or 'kein Datum'}
- Priorität: {task_info.get('priority', 0)}
- Liste: {task_info.get('list_name') or 'Standard-Liste'}
- Ort: {task_info.get('location') or 'kein Ort'}

AUFGABE: Informiere den Nutzer {'über die erfolgreiche Erstellung' if create_result.get('success') else 'über den Fehler'} der Aufgabe.
Formuliere die Nachricht natürlich und variiert."""

            system_message = f"""Du bist ein intelligenter persönlicher Assistent.

{result_context}

WICHTIG:
- Antworte auf {language}
- Formuliere die Nachricht natürlich und freundlich
- Variiere deine Formulierung - vermeide stereotype Phrasen"""

            messages = [
                {'role': 'system', 'content': system_message},
                {'role': 'user', 'content': prompt}
            ]

            try:
                response = ollama_client.chat(messages, [])
                ai_response = response.get('message', {}).get('content',
                    create_result.get('message', 'Aufgabe wurde erstellt.') if create_result.get('success')
                    else f"Fehler: {create_result.get('error', 'Unbekannter Fehler')}")
            except Exception as e:
                logger.error(f"AI generation error for task result: {e}")
                ai_response = (create_result.get('message', 'Aufgabe wurde erstellt.') if create_result.get('success')
                              else f"Fehler: {create_result.get('error', 'Unbekannter Fehler')}")

            return jsonify({
                'response': ai_response,
                'action': 'task_created' if create_result.get('success') else 'task_create_failed',
                'calendar_used': False,
                'context_used': False,
                'context_count': 0,
                'training_saved': False,
                'sources': [],
                'created_task': create_result if create_result.get('success') else None
            })

        # Detect missing integrations early and return interactive setup payloads.
        requires_nextcloud = any([
            intent in ['calendar', 'tasks'],
            should_use_calendar(prompt),
            should_use_tasks(prompt),
            is_activity_question,
            is_potentially_calendar_query,
            'nextcloud' in message_lower
        ])
        if requires_nextcloud and not get_nextcloud_runtime_config():
            return jsonify(_build_integration_connect_response('nextcloud', prompt, language, feature='nextcloud_context'))

        if intent == 'photos' and not get_immich_client(username):
            return jsonify(_build_integration_connect_response('immich', prompt, language, feature='photo_search'))

        logger.info(f"Query intent: {intent}, preferred_source: {preferred_source}")

        # Collect context from different sources based on intent
        photo_context = None
        photo_results = []
        file_context = None
        calendar_context = None
        todo_context = None

        # Gather photo context if relevant
        if intent in ['photos', 'mixed']:
            client = get_immich_client(username)
            photo_context = gather_photo_context(client, prompt, username, build_immich_thumbnail_proxy_url)
            if photo_context:
                photo_results = photo_context.get('metadata', {}).get('photos', [])
                logger.info(f"Found {len(photo_results)} photos for context with full metadata")

        # Gather file context for file/mixed/general queries so indexed chunks are
        # consistently available for broad knowledge questions.
        if intent in ['files', 'mixed', 'general']:
            file_context = gather_file_context(knowledge_base, training_manager, prompt)
            if file_context:
                logger.info(f"Found {file_context[0].get('metadata', {}).get('count', 0)} file results with enhanced context (intent-based)")

        # Intelligente Erkennung was kontexte werden sollten
        use_calendar_intelligent = should_use_calendar(prompt)
        use_tasks_intelligent = should_use_tasks(prompt)

        # Gather calendar context if relevant (Intent ODER intelligente Erkennung)
        calendar_context = gather_calendar_context(
            get_calendar_context, should_use_calendar, prompt, intent, calendar_enabled
        )

        # Gather todo context if relevant (Intent ODER intelligente Erkennung)
        todo_context = gather_todo_context(
            get_todo_data, is_todo_query, should_use_tasks, prompt, intent
        )

        # Gather email context if query is email-related
        email_context = None
        try:
            if intent in ['email', 'mixed'] or is_email_query(prompt):
                email_client_instance = get_email_client(username)
                if email_client_instance:
                    email_context = gather_email_context(email_client_instance, prompt, limit=10)
                    if email_context:
                        logger.info("Email context added (%d emails)", email_context.get('metadata', {}).get('count', 0))
        except Exception as e:
            logger.warning("Email context error: %s", e)

        # NEW: Proactively gather Nextcloud search context
        # This searches across all Nextcloud providers (files, contacts, calendar, tasks)
        nextcloud_search_context = None
        try:
            search_client = get_nextcloud_search_client(username)
            if search_client:
                nextcloud_search_context = gather_nextcloud_search_context(
                    search_client, prompt, extract_search_terms
                )
                if nextcloud_search_context:
                    logger.info(f"Nextcloud search found {nextcloud_search_context.get('metadata', {}).get('count', 0)} results")
        except Exception as e:
            logger.warning(f"Nextcloud search error: {e}")

        # NEW: Autonomous agent for comprehensive research
        # The agent proactively searches multiple sources and gathers detailed information
        autonomous_context = None
        _ai_cfg = load_ai_config()
        autonomous_enabled = _ai_cfg.get('autonomous_agent_enabled', True)
        try:
            if autonomous_enabled:
                # Get clients for autonomous agent
                nextcloud_client = get_nextcloud_client(username)
                search_client = get_nextcloud_search_client(username)
                immich_client = get_immich_client(username)
                autonomous_email_client = get_email_client(username)

                # Create autonomous agent
                agent = AutonomousAgent(
                    nextcloud_client=nextcloud_client,
                    search_client=search_client,
                    knowledge_base=knowledge_base,
                    immich_client=immich_client,
                    training_manager=training_manager,
                    email_client=autonomous_email_client
                )

                # Plan and execute autonomous actions
                logger.info("Starting autonomous research...")
                planned_actions = agent.analyze_query_and_plan_actions(prompt, {
                    'intent': intent,
                    'language': language
                })

                if planned_actions:
                    # Skip SEARCH_KNOWLEDGE_BASE action when file_context already provides KB results
                    if file_context:
                        original_count = len(planned_actions)
                        planned_actions = [
                            a for a in planned_actions
                            if a.action_type.value != 'search_knowledge_base'
                        ]
                        skipped = original_count - len(planned_actions)
                        if skipped > 0:
                            logger.info(
                                "Skipping %d autonomous SEARCH_KNOWLEDGE_BASE action(s) "
                                "because file_context is already available",
                                skipped,
                            )

                    if not planned_actions:
                        logger.info("No autonomous actions to execute after filtering")
                    else:
                        logger.info(f"Autonomous agent planned {len(planned_actions)} actions")
                        results = agent.execute_actions(planned_actions, username)

                        if results.get('success') and results.get('gathered_information'):
                            autonomous_context = agent.format_autonomous_results_for_context(results)
                            if autonomous_context:
                                logger.info("Autonomous research completed successfully")
        except Exception as e:
            logger.warning(f"Autonomous agent error: {e}", exc_info=True)

        # Combine all contexts in priority order using gatherers helper
        combined_context = combine_contexts(
            weather_context, security_context, activity_context,
            photo_context, file_context, calendar_context, todo_context, nextcloud_search_context,
            email_ctx=email_context
        )

        # Add autonomous research results if available
        if autonomous_context:
            combined_context.append(autonomous_context)

        # Build system message with context using gatherers helper
        system_message = build_agent_system_message(combined_context, language)

        # Generate AI response
        messages = [
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': prompt}
        ]

        if context:
            messages.insert(1, {'role': 'assistant', 'content': context})

        try:
            response = ollama_client.chat(messages, [])

            if 'error' in response:
                return jsonify({
                    'success': False,
                    'error': response['error']
                }), 500

            ai_response = response.get('message', {}).get('content', 'Entschuldigung, ich konnte keine Antwort generieren.')

            source_cards = []
            if file_context:
                for context_item in file_context:
                    cards = context_item.get('metadata', {}).get('source_cards', [])
                    if cards:
                        source_cards.extend(cards)

            # Add email source cards
            if email_context:
                email_cards = email_context.get('metadata', {}).get('source_cards', [])
                if email_cards:
                    source_cards.extend(email_cards)

            ui_cards = _build_ui_cards(prompt, intent, calendar_context, todo_context, photo_context, email_context, nextcloud_search_context, username, language)

            # No hard source limit: rely on relevance filtering in context gatherers.

            return jsonify({
                'success': True,
                'response': ai_response,
                'sources': source_cards,
                'ui_cards': ui_cards,
                'context_used': len(combined_context) > 0,
                'context_count': len(combined_context),
                'intent': intent,
                'sources_used': {
                    'photos': photo_context is not None,
                    'files': file_context is not None and len(file_context) > 0,
                    'calendar': calendar_context is not None,
                    'todos': todo_context is not None,
                    'emails': email_context is not None
                }
            })

        except Exception as e:
            logger.error(f"AI generation error: {e}")
            return jsonify({
                'success': False,
                'error': f'Fehler bei der AI-Generierung: {str(e)}'
            }), 500

    except Exception as e:
        logger.error(f"Agent query error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/suggestions/query', methods=['POST'])
def get_query_suggestions():
    """
    Generate personalized query suggestions based on time of day,
    user behavior, and conversation history.
    """
    try:
        data = request.get_json()
        username = data.get('username')
        language = data.get('language', 'de')

        # Get current time context
        now = datetime.now()
        hour = now.hour
        day_of_week = now.strftime('%A')

        # Determine time period
        if 5 <= hour < 12:
            time_period = 'morning'
        elif 12 <= hour < 17:
            time_period = 'afternoon'
        elif 17 <= hour < 22:
            time_period = 'evening'
        else:
            time_period = 'night'

        # Load user's chat history from request (sent from frontend)
        chat_history = data.get('chatHistory', [])

        # Analyze user behavior patterns
        user_patterns = analyze_user_patterns(chat_history, hour, day_of_week)

        # Generate suggestions using AI
        suggestions = generate_ai_suggestions(
            username=username,
            language=language,
            time_period=time_period,
            day_of_week=day_of_week,
            user_patterns=user_patterns
        )

        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'time_period': time_period,
            'personalized': len(user_patterns) > 0
        })

    except Exception as e:
        logger.error(f"Error generating query suggestions: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'suggestions': []  # Return empty suggestions on error
        }), 500

def analyze_user_patterns(chat_history, current_hour, current_day):
    """
    Analyze user's chat history to identify patterns:
    - Frequent topics
    - Time-based query patterns
    - Common question types
    """
    patterns = {}

    if not chat_history or len(chat_history) == 0:
        return patterns

    # Analyze message topics and timing
    topic_frequency = {}
    hourly_topics = {}
    daily_topics = {}

    for chat in chat_history:
        messages = chat.get('messages', [])
        created_at = chat.get('createdAt', 0)

        # Parse timestamp
        if created_at:
            try:
                chat_time = datetime.fromtimestamp(created_at / 1000)
                chat_hour = chat_time.hour
                chat_day = chat_time.strftime('%A')

                # Track hourly patterns
                if chat_hour not in hourly_topics:
                    hourly_topics[chat_hour] = []

                # Track daily patterns
                if chat_day not in daily_topics:
                    daily_topics[chat_day] = []

                # Extract topics from user messages
                for msg in messages:
                    if msg.get('role') == 'user':
                        content = msg.get('content', '').lower()
                        # Track topics
                        hourly_topics[chat_hour].append(content)
                        daily_topics[chat_day].append(content)

                        # Count topic frequency (simple keyword extraction)
                        words = content.split()
                        for word in words:
                            if len(word) > 4:  # Only consider words longer than 4 chars
                                topic_frequency[word] = topic_frequency.get(word, 0) + 1
            except:
                pass

    # Identify patterns for current context
    patterns['frequent_topics'] = sorted(topic_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
    patterns['same_hour_queries'] = hourly_topics.get(current_hour, [])[:3]
    patterns['same_day_queries'] = daily_topics.get(current_day, [])[:3]

    return patterns

def generate_ai_suggestions(username, language, time_period, day_of_week, user_patterns):
    """
    Generate contextual query suggestions using the AI model.
    Falls back to template-based suggestions if AI is unavailable.
    """

    # Template-based suggestions by time period and language
    template_suggestions = {
        'de': {
            'morning': [
                'Was steht heute auf meinem Kalender?',
                'Zeige mir meine Aufgaben für heute',
                'Was ist neu in meinen Dateien?',
                'Gib mir eine Zusammenfassung meiner E-Mails'
            ],
            'afternoon': [
                'Wie viel habe ich heute geschafft?',
                'Zeige mir wichtige Dokumente',
                'Was sind meine nächsten Termine?',
                'Suche nach Notizen vom letzten Meeting'
            ],
            'evening': [
                'Was muss ich morgen erledigen?',
                'Zeige mir Fotos von heute',
                'Zusammenfassung meines Tages',
                'Welche Aufgaben sind noch offen?'
            ],
            'night': [
                'Plane meinen morgigen Tag',
                'Was steht morgen an?',
                'Zeige mir entspannende Fotos',
                'Erstelle eine To-Do-Liste für morgen'
            ]
        },
        'en': {
            'morning': [
                'What\'s on my calendar today?',
                'Show me my tasks for today',
                'What\'s new in my files?',
                'Give me a summary of my emails'
            ],
            'afternoon': [
                'How much have I accomplished today?',
                'Show me important documents',
                'What are my next appointments?',
                'Search for notes from last meeting'
            ],
            'evening': [
                'What do I need to do tomorrow?',
                'Show me photos from today',
                'Summary of my day',
                'Which tasks are still open?'
            ],
            'night': [
                'Plan my tomorrow',
                'What\'s scheduled for tomorrow?',
                'Show me relaxing photos',
                'Create a to-do list for tomorrow'
            ]
        },
        'fr': {
            'morning': [
                'Qu\'est-ce qui est prévu sur mon calendrier aujourd\'hui?',
                'Montre-moi mes tâches pour aujourd\'hui',
                'Quoi de neuf dans mes fichiers?',
                'Donne-moi un résumé de mes e-mails'
            ],
            'afternoon': [
                'Combien ai-je accompli aujourd\'hui?',
                'Montre-moi les documents importants',
                'Quels sont mes prochains rendez-vous?',
                'Recherche des notes de la dernière réunion'
            ],
            'evening': [
                'Que dois-je faire demain?',
                'Montre-moi les photos d\'aujourd\'hui',
                'Résumé de ma journée',
                'Quelles tâches sont encore ouvertes?'
            ],
            'night': [
                'Planifie ma journée de demain',
                'Qu\'est-ce qui est prévu demain?',
                'Montre-moi des photos relaxantes',
                'Crée une liste de tâches pour demain'
            ]
        },
        'es': {
            'morning': [
                '¿Qué hay en mi calendario hoy?',
                'Muéstrame mis tareas para hoy',
                '¿Qué hay de nuevo en mis archivos?',
                'Dame un resumen de mis correos'
            ],
            'afternoon': [
                '¿Cuánto he logrado hoy?',
                'Muéstrame documentos importantes',
                '¿Cuáles son mis próximas citas?',
                'Busca notas de la última reunión'
            ],
            'evening': [
                '¿Qué necesito hacer mañana?',
                'Muéstrame fotos de hoy',
                'Resumen de mi día',
                '¿Qué tareas están aún pendientes?'
            ],
            'night': [
                'Planifica mi día de mañana',
                '¿Qué está programado para mañana?',
                'Muéstrame fotos relajantes',
                'Crea una lista de tareas para mañana'
            ]
        },
        'it': {
            'morning': [
                'Cosa c\'è nel mio calendario oggi?',
                'Mostrami le mie attività per oggi',
                'Cosa c\'è di nuovo nei miei file?',
                'Dammi un riepilogo delle mie email'
            ],
            'afternoon': [
                'Quanto ho realizzato oggi?',
                'Mostrami documenti importanti',
                'Quali sono i miei prossimi appuntamenti?',
                'Cerca note dell\'ultima riunione'
            ],
            'evening': [
                'Cosa devo fare domani?',
                'Mostrami le foto di oggi',
                'Riepilogo della mia giornata',
                'Quali attività sono ancora aperte?'
            ],
            'night': [
                'Pianifica il mio domani',
                'Cosa è programmato per domani?',
                'Mostrami foto rilassanti',
                'Crea una lista di cose da fare per domani'
            ]
        },
        'pt': {
            'morning': [
                'O que está no meu calendário hoje?',
                'Mostre-me minhas tarefas para hoje',
                'O que há de novo nos meus arquivos?',
                'Me dê um resumo dos meus e-mails'
            ],
            'afternoon': [
                'Quanto realizei hoje?',
                'Mostre-me documentos importantes',
                'Quais são meus próximos compromissos?',
                'Procure notas da última reunião'
            ],
            'evening': [
                'O que preciso fazer amanhã?',
                'Mostre-me fotos de hoje',
                'Resumo do meu dia',
                'Quais tarefas ainda estão pendentes?'
            ],
            'night': [
                'Planeje meu dia de amanhã',
                'O que está agendado para amanhã?',
                'Mostre-me fotos relaxantes',
                'Crie uma lista de tarefas para amanhã'
            ]
        },
        'nl': {
            'morning': [
                'Wat staat er vandaag op mijn agenda?',
                'Laat me mijn taken voor vandaag zien',
                'Wat is er nieuw in mijn bestanden?',
                'Geef me een samenvatting van mijn e-mails'
            ],
            'afternoon': [
                'Hoeveel heb ik vandaag bereikt?',
                'Laat me belangrijke documenten zien',
                'Wat zijn mijn volgende afspraken?',
                'Zoek naar notities van de laatste vergadering'
            ],
            'evening': [
                'Wat moet ik morgen doen?',
                'Laat me foto\'s van vandaag zien',
                'Samenvatting van mijn dag',
                'Welke taken staan nog open?'
            ],
            'night': [
                'Plan mijn dag van morgen',
                'Wat staat er morgen gepland?',
                'Laat me ontspannende foto\'s zien',
                'Maak een takenlijst voor morgen'
            ]
        },
        'pl': {
            'morning': [
                'Co jest w moim kalendarzu dzisiaj?',
                'Pokaż mi moje zadania na dziś',
                'Co nowego w moich plikach?',
                'Daj mi podsumowanie moich e-maili'
            ],
            'afternoon': [
                'Ile osiągnąłem dzisiaj?',
                'Pokaż mi ważne dokumenty',
                'Jakie są moje następne spotkania?',
                'Szukaj notatek z ostatniego spotkania'
            ],
            'evening': [
                'Co muszę zrobić jutro?',
                'Pokaż mi zdjęcia z dzisiaj',
                'Podsumowanie mojego dnia',
                'Które zadania są jeszcze otwarte?'
            ],
            'night': [
                'Zaplanuj mój jutrzejszy dzień',
                'Co jest zaplanowane na jutro?',
                'Pokaż mi relaksujące zdjęcia',
                'Stwórz listę zadań na jutro'
            ]
        },
        'tr': {
            'morning': [
                'Bugün takvimimde ne var?',
                'Bugün için görevlerimi göster',
                'Dosyalarımda ne yeni var?',
                'E-postalarımın özetini ver'
            ],
            'afternoon': [
                'Bugün ne kadar başardım?',
                'Önemli belgeleri göster',
                'Bir sonraki randevularım neler?',
                'Son toplantıdan notları ara'
            ],
            'evening': [
                'Yarın ne yapmam gerekiyor?',
                'Bugünkü fotoğrafları göster',
                'Günümün özeti',
                'Hangi görevler hala açık?'
            ],
            'night': [
                'Yarınımı planla',
                'Yarın için ne planlandı?',
                'Rahatlatıcı fotoğraflar göster',
                'Yarın için yapılacaklar listesi oluştur'
            ]
        },
        'ru': {
            'morning': [
                'Что у меня в календаре на сегодня?',
                'Покажи мои задачи на сегодня',
                'Что нового в моих файлах?',
                'Дай мне резюме моих электронных писем'
            ],
            'afternoon': [
                'Сколько я сделал сегодня?',
                'Покажи важные документы',
                'Какие мои следующие встречи?',
                'Найди заметки с последней встречи'
            ],
            'evening': [
                'Что мне нужно сделать завтра?',
                'Покажи фотографии сегодняшнего дня',
                'Резюме моего дня',
                'Какие задачи еще открыты?'
            ],
            'night': [
                'Спланируй мой завтрашний день',
                'Что запланировано на завтра?',
                'Покажи расслабляющие фотографии',
                'Создай список дел на завтра'
            ]
        },
        'ja': {
            'morning': [
                '今日のカレンダーには何がありますか？',
                '今日のタスクを表示',
                'ファイルに何か新しいものは？',
                'メールの要約を教えて'
            ],
            'afternoon': [
                '今日どれだけ達成しましたか？',
                '重要な文書を表示',
                '次の予定は何ですか？',
                '最後の会議のメモを検索'
            ],
            'evening': [
                '明日は何をする必要がありますか？',
                '今日の写真を表示',
                '今日の要約',
                'どのタスクがまだ開いていますか？'
            ],
            'night': [
                '明日を計画する',
                '明日は何が予定されていますか？',
                'リラックスできる写真を表示',
                '明日のToDoリストを作成'
            ]
        },
        'zh': {
            'morning': [
                '我今天的日历上有什么？',
                '显示我今天的任务',
                '我的文件中有什么新内容？',
                '给我一个电子邮件摘要'
            ],
            'afternoon': [
                '我今天完成了多少？',
                '显示重要文档',
                '我的下一个约会是什么？',
                '搜索上次会议的笔记'
            ],
            'evening': [
                '我明天需要做什么？',
                '显示今天的照片',
                '我的一天总结',
                '哪些任务还未完成？'
            ],
            'night': [
                '计划我的明天',
                '明天有什么安排？',
                '显示放松的照片',
                '为明天创建待办事项列表'
            ]
        }
    }

    # Get base suggestions for language and time period
    lang = language if language in template_suggestions else 'en'
    base_suggestions = template_suggestions[lang].get(time_period, template_suggestions[lang]['morning'])

    # Personalize based on user patterns
    personalized_suggestions = []

    # Add personalized suggestions based on frequent topics
    if user_patterns.get('frequent_topics'):
        # Language-specific personalization templates
        personalization_templates = {
            'de': 'Mehr zu {topic}',
            'en': 'More about {topic}',
            'fr': 'En savoir plus sur {topic}',
            'es': 'Más sobre {topic}',
            'it': 'Maggiori informazioni su {topic}',
            'pt': 'Mais sobre {topic}',
            'nl': 'Meer over {topic}',
            'pl': 'Więcej o {topic}',
            'tr': '{topic} hakkında daha fazla',
            'ru': 'Больше о {topic}',
            'ja': '{topic}についてもっと',
            'zh': '更多关于{topic}'
        }

        template = personalization_templates.get(lang, personalization_templates['en'])
        for topic, count in user_patterns['frequent_topics'][:2]:
            personalized_suggestions.append(template.format(topic=topic))

    # Combine: 3 template-based + up to 2 personalized
    final_suggestions = base_suggestions[:3] + personalized_suggestions[:2]

    # Try to enhance with AI if available
    try:
        if ollama_client and ollama_client.check_connection():
            # Generate AI-enhanced suggestions
            prompt = f"""Generate 3 helpful query suggestions for a personal knowledge assistant.
Context:
- Time: {time_period} ({day_of_week})
- Language: {language}
- User frequently asks about: {', '.join([t[0] for t in user_patterns.get('frequent_topics', [])][:3]) if user_patterns.get('frequent_topics') else 'various topics'}

Requirements:
- Return ONLY 3 short, actionable questions
- Each on a new line
- No numbering, no markdown
- In {language} language
- Relevant to time of day and user interests"""

            response = ollama_client.generate(prompt, stream=False)
            if response and response.get('text'):
                ai_suggestions = [s.strip() for s in response['text'].strip().split('\n') if s.strip()]
                if len(ai_suggestions) >= 3:
                    return ai_suggestions[:5]  # Return up to 5 AI-generated suggestions
    except Exception as e:
        logger.warning(f"Could not generate AI suggestions, using templates: {e}")

    return final_suggestions[:5]  # Return max 5 suggestions

# Tasks/Todos Manager initialisieren wenn Konfiguration vorhanden
# IMPORTANT: Initialize BEFORE if __name__ == '__main__' so it runs on module import too
try:
    initialize_tasks_from_config()
except Exception as e:
    logger.error(f"Error in initialize_tasks_from_config: {e}")

try:
    start_briefing_scheduler()
except Exception as e:
    logger.error(f"Error starting briefing scheduler: {e}")

if __name__ == '__main__':
    # Initialize knowledge base
    try:
        knowledge_base.load_knowledge()
        
        # Try to migrate existing data
        try_migrate_existing_data()
        
    except Exception as e:
        logger.error(f"Knowledge base initialization error: {str(e)}")
    
    # Indexing Manager konfiguration laden
    indexing_manager.load_nextcloud_config()
    
    print("AI-Chat-Anwendung wird gestartet...")
    
    # Show status
    if knowledge_base.search_engine:
        stats = knowledge_base.search_engine.get_stats()
        print(f"Second Brain Status: {stats.get('chunks', 0)} Chunks, {stats.get('documents', 0)} Dokumente")
        print(f"Semantic Search: {'Aktiv' if stats.get('index_size', 0) > 0 else 'Wird initialisiert...'}")
        print(f"Model: {stats.get('model_name', 'Unknown')}")
    else:
        print("Semantic Search: Nicht verfügbar (Fallback Mode)")
    
    print(f"Ollama-Verbindung: {'OK' if ollama_client.check_connection() else 'Nicht verfügbar'}")
    print(f"Todos/Tasks: {'Aktiviert' if tasks_enabled else 'Nicht verfügbar'}")
    print("Öffne http://localhost:5001 im Browser")
    
    app.run(debug=False, host='0.0.0.0', port=5001, use_reloader=False)
