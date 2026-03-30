import os
import json
import sys
import requests
import numpy as np
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import re
import logging
from datetime import datetime, timedelta, date
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.features.documents.parser import DocumentParser
from backend.features.integration.nextcloud_client import NextcloudClient
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
import xml.etree.ElementTree as ET

load_dotenv()

# Define base directories BEFORE Flask app creation
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONFIG_DIR = os.path.join(BASE_DIR, 'backend', 'config')
DATA_DIR = os.path.join(BASE_DIR, 'data')
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
TEMPLATES_DIR = os.path.join(BACKEND_DIR, 'templates')
DB_PATH = os.path.join(BASE_DIR, 'knowledge_base.db')

# Setup directories
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Create Flask app with correct template folder
app = Flask(__name__, template_folder=TEMPLATES_DIR)

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AI_CONFIG_FILE = os.path.join(CONFIG_DIR, "ai_config.json")

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
                        'source': result.get('doc_name', 'Unknown'),
                        'path': result.get('doc_path', ''),
                        'similarity_score': result.get('similarity_score', 0.5),
                        'search_type': result.get('search_type', 'search')
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
            
            # Detaillierter System-Prompt für intelligente Entscheidungen
            system_prompt = f"""Du bist ein präziser KI-Assistent mit Zugang zu einer Wissensdatenbank, einem Kalender-System und einer TODO-Liste.

WICHTIGE ANWEISUNGEN:
1. Analysiere die Nutzeranfrage intelligent und selbstständig
2. Bei Fragen nach AUFGABEN/TODOS/TASKS: Überprüfe ZUERST die TODO-Liste mit Fälligkeitsdatum
3. Bei Fragen nach TERMINEN/EVENTS: Nutze den Kalender-Kontext
4. Bei anderen Fragen: Nutze die Wissensdatenbank
5. Bei persönlichen Fragen ohne Quellen: Antworte "Ich habe dazu keine Informationen."
6. Sei informativ aber vermeide unnötig lange Erklärungen
7. WICHTIG: Wenn TODOs mit Fälligkeitsdatum vorhanden sind, zeige sie IMMER in deiner Antwort!

FÄLLIGKEITSDATUM-ANFRAGEN:
- "Welche Aufgaben habe ich heute/morgen/diese Woche?" → Suche nach Fälligkeitsdatum
- "Was ist heute fällig?" → Zeige Aufgaben mit heute's Datum
- "Welche todos/tasks?" → Zeige Aufgaben aus der TODO-Liste

{enhanced_context}

KRITISCH: Antworte mit konkreten TODO-Einträgen wenn die Anfrage nach Aufgaben/Todos fragt!

Basierend auf den Informationen beantworte die Frage informativ und direkt."""
            
            # System-Nachricht erstellen oder ersetzen
            if messages and messages[0].get('role') == 'system':
                messages[0]['content'] = system_prompt
            else:
                messages.insert(0, {'role': 'system', 'content': system_prompt})
        
        # Erweiterte Parameter für bessere Antworten
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Weniger Kreativität, mehr Fakten
                "top_p": 0.9,         # Fokussiertere Antworten
                "max_tokens": 2048,   # Längere Antworten erlauben
                "repeat_penalty": 1.1, # Wiederholungen vermeiden
                "num_predict": 2048   # Maximale Antwortlänge
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
        'model': os.getenv('OLLAMA_MODEL', 'gemma3:latest')
    }

    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)

            config['base_url'] = str(file_config.get('base_url', config['base_url'])).rstrip('/')
            config['model'] = str(file_config.get('model', config['model']))
        except Exception as e:
            logger.warning(f"Konnte AI-Konfiguration nicht laden: {str(e)}")

    ollama_client.update_config(config['base_url'], config['model'])
    return config


def save_ai_config(base_url: str, model: str) -> None:
    """Speichert AI-Konfiguration persistent in einer lokalen JSON-Datei."""
    config = {
        'provider': 'ollama',
        'base_url': base_url.rstrip('/'),
        'model': model
    }

    with open(AI_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

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

# Tasks/Todos Manager initialisieren
tasks_enabled = False

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
        'muss ich', 'sollte ich', 'vergesse ich nicht',
        'was habe ich', 'was muss ich'
    ]
    return any(keyword in message_lower for keyword in todo_keywords)

def get_todo_context(message: str) -> str:
    """Holt Todo-Kontext basierend auf der Nachricht"""
    if not tasks_enabled or not task_manager.tasks_client:
        return ""
    
    try:
        # get_tasks mit None wird automatisch verschiedene Listen-Namen versuchen
        tasks = task_manager.get_tasks(use_cache=True, list_name=None)
        if not tasks:
            return ""
        
        context = task_manager.format_tasks_for_context(tasks)
        return context
    except Exception as e:
        logger.error(f"Error getting todo context: {str(e)}")
        return ""

def create_calendar_event(title: str, start_time: str, end_time: str = None, 
                          calendar_name: str = None, location: str = None, 
                          description: str = None) -> dict:
    """Erstellt ein neues Kalendereignis über CalDAV"""
    if not simple_calendar_manager:
        return {'success': False, 'error': 'Kalender nicht verfügbar'}
    
    try:
        # Hole verfügbare Kalender
        calendars = simple_calendar_manager.get_calendars()
        if not calendars:
            return {'success': False, 'error': 'Keine Kalender gefunden'}
        
        # Wähle Kalender aus
        target_calendar = None
        if calendar_name:
            # Suche nach Kalender mit passendem Namen
            for cal in calendars:
                if calendar_name.lower() in cal['name'].lower():
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
    
    message_lower = message.lower()
    
    # Titel extrahieren (oft nach "erstelle", "termin", "ereignis")
    title_patterns = [
        r'"([^"]+)"',  # In Anführungszeichen
        r'termin[:\s]+([^.!?]+)',  # "termin: Titel"
        r'ereignis[:\s]+([^.!?]+)',  # "ereignis: Titel"
        r'erstelle[:\s]+([^.!?]+)',  # "erstelle Titel"
    ]
    
    for pattern in title_patterns:
        match = re.search(pattern, message_lower)
        if match:
            result['title'] = match.group(1).strip().title()
            break
    
    # Zeit extrahieren
    time_patterns = [
        r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})',  # 26.03.2026 14:30
        r'(\d{2}:\d{2})',  # 14:30
        r'heute\s+um\s+(\d{2}:\d{2})',  # heute um 14:30
        r'morgen\s+um\s+(\d{2}:\d{2})',  # morgen um 14:30
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, message_lower)
        if match:
            result['start_time'] = match.group(1)
            break
    
    # Ort extrahieren
    location_patterns = [
        r'in\s+([^.!?]+)',
        r'bei\s+([^.!?]+)',
        r'ort[:\s]+([^.!?]+)'
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, message_lower)
        if match:
            location = match.group(1).strip()
            # Vermeide Zeitangaben als Ort
            if not any(char.isdigit() for char in location):
                result['location'] = location.title()
                break
    
    # Kalender extrahieren
    calendar_patterns = [
        r'im\s+kalender[:\s]+([^.!?]+)',
        r'kalender[:\s]+([^.!?]+)'
    ]
    
    for pattern in calendar_patterns:
        match = re.search(pattern, message_lower)
        if match:
            result['calendar_name'] = match.group(1).strip().title()
            break
    
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

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    feedback = data.get('feedback', None)  # Optionales Feedback für Training
    
    if not message:
        return jsonify({'error': 'Keine Nachricht erhalten'}), 400
    
    # Intelligente Kalender-Erkennung ohne feste Muster
    calendar_context = None
    todo_context = None
    
    # Lasse die KI entscheiden, ob es eine Kalender-Frage ist
    # durch semantische Analyse statt feste Keywords
    message_lower = message.lower()
    
    # TODOS erkennen - NOW RE-ENABLED: Auto-loading is fast because tasks are loaded from DB (not WebDAV)
    if is_todo_query(message):
        try:
            todo_context = get_todo_context(message)
            if todo_context:
                logger.info(f"Todo context found: {len(todo_context)} characters")
        except Exception as e:
            logger.error(f"Todo error: {e}")
    
    # Nur grundlegende Prüfung, ob es zeitbezogen sein könnte
    time_related_indicators = [
        'wann', 'wann', 'wann', 'zeit', 'datum', 'termin', 'ereignis', 'appointment', 
        'event', 'kalender', 'heute', 'morgen', 'woche', 'tag', 'monat',
        'steht an', 'habe ich', 'mache ich', 'ist geplant', 'vorhaben'
    ]
    
    # Prüfe ob zeitbezogene Indikatoren vorhanden sind
    has_time_indicators = any(indicator in message_lower for indicator in time_related_indicators)
    
    # Zusätzliche Prüfung auf Fragewörter die auf Zeit hindeuten
    question_words = ['was', 'welche', 'wie', 'wann', 'ob', 'kannst du']
    has_question = any(word in message_lower.split()[:3] for word in question_words)
    
    # Die KI soll selbst entscheiden, aber nur wenn es wirklich zeitbezogen sein könnte
    is_potentially_calendar_query = has_time_indicators and has_question
    
    # Wenn potenzielle Kalender-Frage, hole Kalender-Daten mit besserer Fehlerbehandlung
    if is_potentially_calendar_query and calendar_enabled:
        try:
            calendar_context = get_calendar_context(message)
            if calendar_context:
                logger.info(f"Calendar context found: {len(calendar_context)} characters")
            else:
                logger.info("Potential calendar query but no context generated")
        except Exception as e:
            logger.error(f"Calendar error: {e}")
            # Fallback-Kontext bei Kalenderfehlern
            calendar_context = f"=== KALENDER-FEHLER ===\n\nLeider konnte ich nicht auf deinen Kalender zugreifen.\nFehler: {str(e)[:100]}\n\nBitte überprüfe deine Kalender-Konfiguration."
    
    # Suche nach relevantem Wissen mit mehr Ergebnissen
    try:
        relevant_context = knowledge_base.search_knowledge(message, k=10)  # Mehr Kontext!
        logger.info(f"Found {len(relevant_context)} context items for query: {message[:50]}...")
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        relevant_context = []
    
    # Chat-Nachrichten vorbereiten
    messages = [
        {'role': 'user', 'content': message}
    ]
    
    # Kombiniere Kontexte (Wissensbasis + Kalender + Todos)
    combined_context = relevant_context.copy()
    
    # Füge Todo-Kontext hinzu wenn vorhanden
    if todo_context:
        combined_context.insert(0, {
            'content': todo_context,
            'source': 'Todos',
            'path': 'todos',
            'similarity_score': 1.0,
            'metadata': {}
        })
    
    if calendar_context:
        # Füge Kalender-Kontext als speziellen Kontext hinzu
        combined_context.insert(0, {
            'content': calendar_context,
            'source': 'Kalender',
            'path': 'calendar',
            'similarity_score': 1.0,
            'metadata': {}
        })
    
    # Anfrage an Ollama senden mit verbessertem Kontext
    try:
        response = ollama_client.chat(messages, combined_context)
        
        if 'error' in response:
            logger.error(f"Ollama error: {response['error']}")
            return jsonify({'error': response['error']}), 500
        
        ai_response = response.get('message', {}).get('content', 'Entschuldigung, ich konnte keine Antwort generieren.')
        
        # Speichere Trainings-Interaktion
        try:
            training_manager.save_training_interaction(message, combined_context, ai_response, feedback)
        except Exception as e:
            logger.warning(f"Failed to save training interaction: {str(e)}")
        
        # Debug-Informationen loggen
        context_used = len(combined_context) > 0
        logger.info(f"Response generated, context used: {context_used}")
        if calendar_context:
            logger.info(f"Calendar context included in response")
        if todo_context:
            logger.info(f"Todo context included in response")
        
        # ACTION PARSER: Versuche natürlichsprachige Aktionen auszuführen
        action_response = None
        try:
            # Erkenne "erstelle erinnerung/task/todo für [datum]: [titel]"
            import re
            
            # Pattern: "erstelle (erinnerung|aufgabe|task|todo) für (morgen|heute|[datum]) *: *(.+)"
            pattern = r'(?:erstelle|create)\s+(?:eine?\s+)?(?:erinnerung|aufgabe|task|todo|aufgaben|tasks|reminder)\s+(?:für|um)\s+([^:]+):\s*(.+?)(?:\.|$)'
            match = re.search(pattern, message.lower())
            
            if match:
                time_ref = match.group(1).strip()
                title = match.group(2).strip()
                
                # Parse the time reference
                due_date = None
                if 'morgen' in time_ref or 'tomorrow' in time_ref:
                    due_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                elif 'heute' in time_ref or 'today' in time_ref:
                    due_date = datetime.now().strftime('%Y-%m-%d')
                
                # Create the task if we parsed everything
                if title and tasks_enabled and task_manager.tasks_client:
                    try:
                        success = task_manager.create_task(
                            title=title,
                            due_date=due_date,
                            list_name='todo'
                        )
                        if success:
                            action_response = f"✓ Erinnerung '{title}' wurde erstellt (fällig: {due_date or 'unbegrenzt'})"
                            logger.info(f"Action executed: Created task '{title}'")
                    except Exception as e:
                        logger.warning(f"Failed to create task from action: {e}")
        except Exception as e:
            logger.debug(f"Action parser error (this is OK): {e}")
        
        # Prepare detailed source attribution
        sources = []
        for ctx in combined_context:
            source_info = {
                'source': ctx.get('source', 'Unknown'),
                'path': ctx.get('path', ''),
                'content_preview': ctx.get('content', '')[:200] + '...' if len(ctx.get('content', '')) > 200 else ctx.get('content', ''),
                'similarity_score': ctx.get('similarity_score', 0.0),
                'chunk_id': ctx.get('chunk_id', ''),
                'document_id': ctx.get('document_id', ''),
                'search_type': ctx.get('search_type', 'unknown')
            }
            sources.append(source_info)
        
        return jsonify({
            'response': ai_response,
            'action': action_response,  # Include action result if any
            'context_used': context_used,
            'context_count': len(combined_context),
            'calendar_used': calendar_context is not None,
            'training_saved': True,
            'sources': sources,  # Detailed source attribution
            'debug_info': {
                'query': message,
                'found_context': len(relevant_context),
                'context_sources': [c.get('source', 'Unknown') for c in relevant_context[:3]],
                'response_length': len(ai_response)
            }
        })
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        # Fallback-Antwort bei Ollama-Problemen
        return jsonify({
            'response': f'Entschuldigung, bei der Verarbeitung deiner Anfrage ist ein Fehler aufgetreten. ({str(e)[:100]}...). Versuche es bitte noch einmal.',
            'context_used': False,
            'error': str(e)
        })

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
            
            return jsonify({
                'status': 'saved',
                'message': 'Konfiguration wurde gespeichert'
            })
            
        except Exception as e:
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
        if not simple_calendar_manager:
            return jsonify({'error': 'Kalender nicht verfügbar'}), 500
        
        calendars = simple_calendar_manager.get_calendars()
        return jsonify({
            'calendars': calendars,
            'count': len(calendars)
        })
        
    except Exception as e:
        logger.error(f"Error getting calendars: {e}")
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
        
        if not title:
            return jsonify({'error': 'Titel ist erforderlich'}), 400
        
        success = task_manager.create_task(title, description, due_date, priority, list_name)
        
        if success:
            return jsonify({
                'status': 'created',
                'title': title,
                'message': f'Task "{title}" wurde erstellt'
            })
        else:
            return jsonify({'error': 'Fehler beim Erstellen des Tasks'}), 500
    
    except Exception as e:
        logger.error(f"Error creating task: {e}")
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
        return jsonify({
            'enabled': tasks_enabled,
            'connected': tasks_enabled and task_manager.tasks_client is not None,
            'message': 'Tasks sind aktiviert und verbunden' if tasks_enabled else 'Tasks nicht verfügbar'
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
        success = task_manager.sync_tasks_to_database(
            list_name=request.json.get('list_name', 'todo'),
            batch_size=request.json.get('batch_size', 100)
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

# Tasks/Todos Manager initialisieren wenn Konfiguration vorhanden
# IMPORTANT: Initialize BEFORE if __name__ == '__main__' so it runs on module import too
try:
    initialize_tasks_from_config()
except Exception as e:
    logger.error(f"Error in initialize_tasks_from_config: {e}")

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
