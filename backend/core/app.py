import os
import json
import sys
import requests
import numpy as np
from flask import Flask, request, jsonify, redirect, url_for, session, Response
from dotenv import load_dotenv
import re
import logging
from datetime import datetime, timedelta, date
import time
import secrets
from urllib.parse import urljoin
from urllib.parse import urlencode
from urllib.parse import urlparse
from typing import Optional, List, Dict

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.features.documents.parser import DocumentParser
from backend.features.integration.nextcloud_client import NextcloudClient
from backend.features.integration.activity_client import NextcloudActivityClient
from backend.features.integration.notifications_client import NextcloudNotificationsClient
from backend.features.integration.auth_manager import get_auth_manager, AuthManager
from backend.features.integration.oauth2_nextcloud import OAuth2NextcloudProvider
from backend.features.integration.auth_nextcloud_direct import DirectNextcloudProvider
from backend.features.knowledge.indexing import indexing_manager, IndexingProgress
# from backend.features.knowledge.engine import SemanticSearchEngine
# Temporär deaktiviert wegen faiss Problemen
class SemanticSearchEngine:
    def __init__(self):
        pass
from backend.features.knowledge.search import SimpleSearchEngine
from backend.features.training.manager import TrainingManager
from backend.features.knowledge.metadata import MetadataExtractor
from backend.core.security_utils import (
    sanitize_username,
    mask_secret,
    validate_service_url,
    clamp_int,
)
# from backend.features.calendar.manager import create_calendar_manager
# Temporär deaktiviert wegen caldav Problemen
def create_calendar_manager():
    return None
from backend.features.calendar.simple import create_simple_calendar_manager
from backend.features.tasks.manager import task_manager, set_database
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

# Setup directories
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Create Flask app with correct template folder
app = Flask(__name__, template_folder=TEMPLATES_DIR)

# Konfiguriere Session für OAuth2 State Management
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# HEALTH CHECK ENDPOINT
# ==============================
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring and diagnostics"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'MYND Backend',
        'version': '1.0.0'
    }), 200

AI_CONFIG_FILE = os.path.join(CONFIG_DIR, "ai_config.json")
CALENDAR_CONFIG_FILE = os.path.join(CONFIG_DIR, "calendar_config.json")
ALLOW_PRIVATE_NETWORK_TARGETS = os.getenv('ALLOW_PRIVATE_NETWORK_TARGETS', 'false').lower() == 'true'


def _safe_json_dump(path: str, data: Dict) -> None:
    """Write JSON atomically with restrictive file permissions for secrets."""
    tmp_path = f"{path}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, path)


def _safe_config_path_for_user(username: str) -> Optional[str]:
    safe_username = sanitize_username(username)
    if not safe_username:
        return None
    return os.path.join(CONFIG_DIR, f"user_{safe_username}.json")


def load_calendar_config() -> Dict:
    """Lädt Kalender-Konfiguration mit Priority: Environment Variables > Config File > Defaults."""
    config = {
        'default_calendar_name': os.getenv('DEFAULT_CALENDAR_NAME', '')
    }

    if os.path.exists(CALENDAR_CONFIG_FILE):
        try:
            with open(CALENDAR_CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)

            # Only use file config if env var not explicitly set
            if not os.getenv('DEFAULT_CALENDAR_NAME'):
                config['default_calendar_name'] = str(file_config.get('default_calendar_name', '')).strip()
        except Exception as e:
            logger.warning(f"Konnte Kalender-Konfiguration nicht laden: {str(e)}")

    logger.debug(f"Calendar config: {config['default_calendar_name'] or '(not set)'}")
    return config


def save_calendar_config(default_calendar_name: str) -> None:
    """Speichert Kalender-Konfiguration persistent in einer lokalen JSON-Datei."""
    config = {
        'default_calendar_name': str(default_calendar_name or '').strip()
    }

    _safe_json_dump(CALENDAR_CONFIG_FILE, config)

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
            
            # Erweiterter System-Prompt mit intelligenter Reasoning-Fähigkeit
            system_prompt = f"""Du bist ein hochintelligenter KI-Assistent mit Zugang zu einer Wissensdatenbank, einem Kalender-System und einer TODO-Liste. Du arbeitest präzise, analytisch und kontextbewusst.

=== DEINE KERNKOMPETENZEN ===
1. INTELLIGENTE ANALYSE: Verstehe die Absicht hinter der Anfrage, nicht nur die Wörter
2. KONTEXTUELLES DENKEN: Verknüpfe Informationen aus verschiedenen Quellen intelligent
3. RELEVANZFILTERUNG: Fokussiere auf die wichtigsten und relevantesten Informationen
4. PRÄZISE KOMMUNIKATION: Antworte konkret, strukturiert und mit klaren Quellenangaben

=== INFORMATIONSQUELLEN-STRATEGIE ===
Du hast Zugang zu drei Hauptquellen:
• WISSENSDATENBANK: Dokumente, Notizen, technische Informationen, persönliche Daten
• KALENDER: Termine, Events, zeitliche Planungen
• TODO-LISTE: Aufgaben mit Fälligkeitsdaten und Prioritäten

ENTSCHEIDUNGSLOGIK:
1. Bei Fragen nach AUFGABEN/TODOS/TASKS/VERPFLICHTUNGEN:
   → Priorisiere TODO-Liste (mit Fälligkeitsdatum!)
   → Zeige IMMER konkrete TODO-Einträge wenn vorhanden
   → Sortiere nach Dringlichkeit (heute > morgen > diese Woche)

2. Bei Fragen nach TERMINEN/EVENTS/ZEITPLÄNEN:
   → Nutze primär Kalender-Kontext
   → Berücksichtige zeitliche Nähe und Wichtigkeit

3. Bei Fragen nach WISSEN/FAKTEN/DOKUMENTEN:
   → Durchsuche Wissensdatenbank
   → Wäge Relevanz-Scores und Aktualität ab
   → Kombiniere Informationen aus mehreren Quellen intelligent

4. Bei PERSÖNLICHEN FRAGEN ohne gefundene Quellen:
   → Antworte ehrlich: "Ich habe dazu keine Informationen in meiner Wissensbasis."

=== REASONING-PROZESS ===
Für jede Anfrage:
1. VERSTEHEN: Was ist die eigentliche Absicht der Frage?
2. IDENTIFIZIEREN: Welche Informationsquelle(n) sind relevant?
3. PRIORISIEREN: Welche Informationen sind am wichtigsten?
4. SYNTHESTISIEREN: Wie kombiniere ich die Informationen optimal?
5. ANTWORTEN: Präsentiere die Antwort strukturiert und präzise

=== ANTWORTQUALITÄT ===
• Nutze klare Strukturierung (Listen, Absätze, Hervorhebungen)
• Gib IMMER konkrete Quellenangaben an
• Vermeide Wiederholungen und Füllwörter
• Bei mehreren relevanten Informationen: Sortiere nach Relevanz
• Bei zeitbezogenen Fragen: Beachte Aktualität und Fälligkeitsdaten

=== VERFÜGBARER KONTEXT ===
{enhanced_context}

=== KRITISCHE REGELN ===
⚠ Bei TODO-Anfragen: Zeige IMMER die konkreten TODO-Einträge mit Fälligkeitsdatum
⚠ Bei fehlenden Informationen: Gib dies klar zu, erfinde nichts
⚠ Bei widersprüchlichen Quellen: Erwähne dies und priorisiere nach Relevanz-Score
⚠ Sei präzise aber nicht unnötig ausschweifend

Beantworte nun die Anfrage basierend auf dem verfügbaren Kontext mit maximaler Intelligenz und Präzision."""
            
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
    """Lädt AI-Konfiguration mit Priority: Environment Variables > Config File > Defaults."""
    config = {
        'provider': 'ollama',
        'base_url': os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/'),
        'model': os.getenv('OLLAMA_MODEL', 'gemma3:latest'),
        'immich_url_default': os.getenv('IMMICH_URL', ''),
        'immich_api_key_default': os.getenv('IMMICH_API_KEY', ''),
        'vector_db_enabled': os.getenv('VECTOR_DB_ENABLED', 'true').lower() == 'true',
        'vector_db_provider': os.getenv('VECTOR_DB_PROVIDER', 'qdrant'),
        'vector_db_path': os.getenv('VECTOR_DB_PATH', './qdrant_data'),
        'calendar_auto_reindex_hours': clamp_int(os.getenv('CALENDAR_AUTO_REINDEX_HOURS', '6'), default=6, minimum=1, maximum=168),
        'calendar_auto_reindex_past_days': clamp_int(os.getenv('CALENDAR_AUTO_REINDEX_PAST_DAYS', '730'), default=730, minimum=1, maximum=3650),
        'calendar_auto_reindex_future_days': clamp_int(os.getenv('CALENDAR_AUTO_REINDEX_FUTURE_DAYS', '365'), default=365, minimum=1, maximum=3650)
    }

    # Load from config file (ONLY if env vars not explicitly set)
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)

            # Only use file config if env var not set
            if not os.getenv('OLLAMA_BASE_URL'):
                config['base_url'] = str(file_config.get('base_url', config['base_url'])).rstrip('/')
            if not os.getenv('OLLAMA_MODEL'):
                config['model'] = str(file_config.get('model', config['model']))
            if not os.getenv('IMMICH_URL'):
                config['immich_url_default'] = file_config.get('immich_url_default', '')
            if not os.getenv('IMMICH_API_KEY'):
                config['immich_api_key_default'] = file_config.get('immich_api_key_default', '')
            
            config['vector_db_enabled'] = file_config.get('vector_db_enabled', config['vector_db_enabled'])
            config['vector_db_provider'] = file_config.get('vector_db_provider', config['vector_db_provider'])
            config['vector_db_path'] = file_config.get('vector_db_path', config['vector_db_path'])
            config['calendar_auto_reindex_hours'] = file_config.get('calendar_auto_reindex_hours', config['calendar_auto_reindex_hours'])
            config['calendar_auto_reindex_past_days'] = file_config.get('calendar_auto_reindex_past_days', config['calendar_auto_reindex_past_days'])
            config['calendar_auto_reindex_future_days'] = file_config.get('calendar_auto_reindex_future_days', config['calendar_auto_reindex_future_days'])
        except Exception as e:
            logger.warning(f"Konnte AI-Konfiguration nicht laden: {str(e)}")

    # Log masked config for debugging
    masked_config = config.copy()
    masked_config['immich_api_key_default'] = mask_secret(config['immich_api_key_default'])
    logger.info(f"AI Config loaded with provider={config['provider']}, model={config['model']}")

    ollama_client.update_config(config['base_url'], config['model'])
    return config


def save_ai_config(base_url: str, model: str) -> None:
    """Speichert AI-Konfiguration persistent in einer lokalen JSON-Datei."""
    config = {
        'provider': 'ollama',
        'base_url': base_url.rstrip('/'),
        'model': model
    }

    _safe_json_dump(AI_CONFIG_FILE, config)

def load_user_config(username: str) -> dict:
    """Lädt benutzerspezifische Konfiguration"""
    user_config_file = _safe_config_path_for_user(username)
    if not user_config_file:
        logger.warning("Invalid username supplied for user config load")
        return {}
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
    user_config_file = _safe_config_path_for_user(username)
    if not user_config_file:
        raise ValueError("Invalid username")

    try:
        _safe_json_dump(user_config_file, config)
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

# Tasks/Todos Manager initialisieren
tasks_enabled = False
TASKS_AUTO_SYNC_ENABLED = os.getenv('TASKS_AUTO_SYNC_ENABLED', 'true').lower() == 'true'
TASKS_AUTO_SYNC_INTERVAL_SECONDS = int(os.getenv('TASKS_AUTO_SYNC_INTERVAL_SECONDS', '300'))
TASKS_AUTO_SYNC_LIST_NAME = os.getenv('TASKS_AUTO_SYNC_LIST_NAME', 'todo')

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
                    auto_sync_started = task_manager.start_auto_sync(
                        list_name=TASKS_AUTO_SYNC_LIST_NAME,
                        interval_seconds=TASKS_AUTO_SYNC_INTERVAL_SECONDS
                    )
                    logger.info(f"🔁 Task auto-sync {'enabled' if auto_sync_started else 'not started'}")
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
            return "Du hast aktuell keine überfälligen Erinnerungen."
        if 'heute' in message_lower:
            return "Für heute hast du keine fälligen Erinnerungen."
        return "Du hast aktuell keine offenen Erinnerungen."

    lines = []
    lines.append(f"Du hast {len(tasks)} offene Erinnerungen.")
    lines.append(f"Davon: {overdue_count} überfällig, {due_today_count} für heute, {no_due_count} ohne Datum.")
    lines.append("")
    lines.append("Relevante Erinnerungen:")

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

    # 3) Fallback auf bekannte Konfig-Dateien im Projekt
    config_candidates = [
        os.path.join(CONFIG_DIR, 'indexing_config.json'),
        os.path.join(BASE_DIR, 'indexing_config.json')
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

def is_calendar_create_query(message: str) -> bool:
    """Erkennt Wunsch nach Termin-Erstellung."""
    message_lower = message.lower()
    create_keywords = ['erstelle', 'anlegen', 'create', 'eintragen', 'hinzufügen']
    calendar_keywords = ['termin', 'ereignis', 'kalender', 'event', 'appointment']
    return any(k in message_lower for k in create_keywords) and any(k in message_lower for k in calendar_keywords)

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
                'context': "=== NEXTCLOUD AKTIVITAETEN ===\nKeine neuen Aktivitäten gefunden.",
                'summary_text': "Es gibt aktuell keine neuen Aktivitäten auf deiner Nextcloud.",
                'count': 0,
                'error': None
            }

        lines = ["=== NEXTCLOUD AKTIVITAETEN ===", f"Anzahl: {len(activities)}", ""]
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

@app.route('/api/indexing/start', methods=['POST'])
def start_indexing():
    """Startet die Hintergrund-Indexierung"""
    data = request.get_json(silent=True) or {}
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
            data = request.get_json(silent=True) or {}
            url = data.get('url')
            username = data.get('username')
            password = data.get('password')
            remote_path = data.get('path', '/')

            normalized_url = validate_service_url(url, allow_private_network=ALLOW_PRIVATE_NETWORK_TARGETS)
            if not normalized_url:
                return jsonify({'error': 'Ungültige oder nicht erlaubte URL'}), 400
            
            if not all([url, username, password]):
                return jsonify({'error': 'URL, Username und Password werden benötigt'}), 400
            
            indexing_manager.save_nextcloud_config(normalized_url, username, password, remote_path)
            
            return jsonify({
                'status': 'saved',
                'message': 'Konfiguration wurde gespeichert'
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
        data = request.get_json(silent=True) or {}
        nextcloud_url = validate_service_url(
            data.get('nextcloud_url', ''),
            allow_private_network=ALLOW_PRIVATE_NETWORK_TARGETS,
        )
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
        _safe_json_dump(config_file, oauth_config)

        # Speichere auch die Basis-Konfiguration für Indexing
        indexing_manager.save_nextcloud_config(
            nextcloud_url,
            username,
            '',  # Leeres Password, verwenden zu stattdessen OAuth2 Token
            '/'
        )

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
        data = request.get_json(silent=True) or {}
        nextcloud_url = validate_service_url(
            data.get('nextcloud_url', ''),
            allow_private_network=ALLOW_PRIVATE_NETWORK_TARGETS,
        )

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

        nextcloud_host = (urlparse(nextcloud_url).hostname or '').lower()
        poll_host = (urlparse(poll_endpoint).hostname or '').lower()
        if not nextcloud_host or not poll_host or nextcloud_host != poll_host:
            return jsonify({'error': 'Invalid poll endpoint host', 'status': 'error'}), 400

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
        _safe_json_dump(config_file, nextcloud_config)

        indexing_manager.save_nextcloud_config(server, username, app_password, '/')

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
        data = request.get_json(silent=True) or {}
        nextcloud_url = validate_service_url(
            data.get('nextcloud_url', ''),
            allow_private_network=ALLOW_PRIVATE_NETWORK_TARGETS,
        )
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
        _safe_json_dump(config_file, nextcloud_config)

        # Speichere auch die Basis-Konfiguration für Indexing
        indexing_manager.save_nextcloud_config(
            nextcloud_url,
            username,
            password,
            '/'
        )

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

        normalized_immich_url = validate_service_url(
            immich_url,
            allow_private_network=ALLOW_PRIVATE_NETWORK_TARGETS,
        ) if immich_url else None

        if normalized_immich_url and immich_api_key:
            return ImmichClient(normalized_immich_url, immich_api_key, timeout_short, timeout_long)
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
        limit = clamp_int(data.get('limit', 20), default=20, minimum=1, maximum=200)

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
        limit = clamp_int(request.args.get('limit', 100), default=100, minimum=1, maximum=500)
        skip = clamp_int(request.args.get('skip', 0), default=0, minimum=0, maximum=50000)

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

        if size not in {'preview', 'thumbnail'}:
            return jsonify({'success': False, 'error': 'Invalid thumbnail size'}), 400

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
    """Proxy fuer originale Immich-Dateien als Download."""
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
        limit = clamp_int(data.get('limit', 20), default=20, minimum=1, maximum=200)

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
                    'immich_api_key_default': mask_secret(config.get('immich_api_key_default', '')),
                    'immich_api_key_default_configured': bool(config.get('immich_api_key_default')),
                    'vector_db_enabled': config.get('vector_db_enabled', True),
                    'vector_db_provider': config.get('vector_db_provider', 'qdrant'),
                    'vector_db_path': config.get('vector_db_path', './qdrant_data')
                }
            })

        # POST - update system config
        data = request.get_json()
        config = load_ai_config()

        # Update config values
        if 'immich_url_default' in data:
            normalized_default_immich = validate_service_url(
                data['immich_url_default'],
                allow_private_network=ALLOW_PRIVATE_NETWORK_TARGETS,
            )
            if data['immich_url_default'] and not normalized_default_immich:
                return jsonify({'success': False, 'error': 'Invalid immich_url_default'}), 400
            config['immich_url_default'] = normalized_default_immich or ''
        if 'immich_api_key_default' in data and data['immich_api_key_default'] not in {'', '***'}:
            config['immich_api_key_default'] = data['immich_api_key_default']
        if 'base_url' in data:
            config['base_url'] = data['base_url']
        if 'model' in data:
            config['model'] = data['model']
        if 'vector_db_enabled' in data:
            config['vector_db_enabled'] = data['vector_db_enabled']

        # Save to file
        _safe_json_dump(AI_CONFIG_FILE, config)

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
        payload = request.get_json(silent=True) or {}
        username = request.args.get('username') if request.method == 'GET' else payload.get('username')
        username = sanitize_username(username)

        if not username:
            return jsonify({'success': False, 'error': 'Username required'}), 400

        if request.method == 'GET':
            user_config = load_user_config(username)
            return jsonify({
                'success': True,
                'username': username,
                'config': {
                    'immich_url': user_config.get('immich_url', ''),
                    'immich_api_key': mask_secret(user_config.get('immich_api_key', '')),
                    'immich_api_key_configured': bool(user_config.get('immich_api_key')),
                    'nextcloud_url': user_config.get('nextcloud_url', ''),
                    'nextcloud_username': user_config.get('nextcloud_username', ''),
                    'nextcloud_password': mask_secret(user_config.get('nextcloud_password', '')),
                    'nextcloud_password_configured': bool(user_config.get('nextcloud_password')),
                    'caldav_url': user_config.get('caldav_url', ''),
                    'caldav_username': user_config.get('caldav_username', ''),
                    'caldav_password': mask_secret(user_config.get('caldav_password', '')),
                    'caldav_password_configured': bool(user_config.get('caldav_password')),
                }
            })

        # POST - update user config
        data = payload
        user_config = load_user_config(username)

        # Update user-specific settings
        if 'immich_url' in data:
            user_config['immich_url'] = data['immich_url']
        if 'immich_api_key' in data and data['immich_api_key'] not in {'', '***'}:
            user_config['immich_api_key'] = data['immich_api_key']
        if 'nextcloud_url' in data:
            user_config['nextcloud_url'] = data['nextcloud_url']
        if 'nextcloud_username' in data:
            user_config['nextcloud_username'] = data['nextcloud_username']
        if 'nextcloud_password' in data and data['nextcloud_password'] not in {'', '***'}:
            user_config['nextcloud_password'] = data['nextcloud_password']
        if 'caldav_url' in data:
            user_config['caldav_url'] = data['caldav_url']
        if 'caldav_username' in data:
            user_config['caldav_username'] = data['caldav_username']
        if 'caldav_password' in data and data['caldav_password'] not in {'', '***'}:
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
        username = sanitize_username(request.args.get('username'))

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
            db_stats = knowledge_base.db.get_document_stats()
            stats['total_documents'] = db_stats.get('documents', 0)
            stats['total_chunks'] = db_stats.get('chunks', 0)
            stats['last_indexed'] = db_stats.get('last_updated')

        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Index status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/suggestions', methods=['GET'])
def ui_suggestions():
    """Get query suggestions based on available data"""
    try:
        username = sanitize_username(request.args.get('username'))

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
        username = sanitize_username(request.args.get('username'))

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

def detect_query_intent(prompt: str, preferred_source: str = 'auto') -> str:
    """
    Erkennt die Intention der Anfrage

    Returns: 'photos', 'files', 'calendar', 'tasks', 'mixed', 'general'
    """
    prompt_lower = prompt.lower()

    # Wenn explizite Quelle gewählt wurde, respektiere das
    if preferred_source == 'photos':
        return 'photos'
    elif preferred_source == 'files':
        return 'files'

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

    # Bestimme primäre Intention
    active_intents = sum([has_photo, has_file, has_time, has_task])

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
        language = data.get('language', 'de')
        context = data.get('context', '')  # Previous conversation context
        preferred_source = data.get('preferred_source', 'auto')

        if not prompt:
            return jsonify({
                'success': False,
                'error': 'Keine Anfrage erhalten'
            }), 400

        message_lower = prompt.lower()

        # Action parser: explicit reminder/task creation
        action_response = None
        try:
            import re

            pattern = r'(?:erstelle|create)\s+(?:eine?\s+)?(?:erinnerung|aufgabe|task|todo|aufgaben|tasks|reminder)\s+(?:fuer|für|um)\s+([^:]+):\s*(.+?)(?:\.|$)'
            match = re.search(pattern, message_lower)

            if match:
                time_ref = match.group(1).strip()
                title = match.group(2).strip()

                due_date = None
                if 'morgen' in time_ref or 'tomorrow' in time_ref:
                    due_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                elif 'heute' in time_ref or 'today' in time_ref:
                    due_date = datetime.now().strftime('%Y-%m-%d')

                if title and tasks_enabled and task_manager.tasks_client:
                    success = task_manager.create_task(
                        title=title,
                        due_date=due_date,
                        list_name='todo'
                    )
                    if success:
                        action_response = f"✓ Erinnerung '{title}' wurde erstellt (faellig: {due_date or 'unbegrenzt'})"
        except Exception as e:
            logger.debug(f"Action parser error (this is OK): {e}")

        if action_response:
            return jsonify({
                'success': True,
                'response': action_response,
                'action': 'task_created',
                'context_used': False,
                'context_count': 0,
                'intent': 'tasks',
                'sources_used': {
                    'photos': False,
                    'files': False,
                    'calendar': False,
                    'todos': False
                }
            })

        # Activity shortcut: direct response without LLM
        activity_context = None
        is_activity_question = is_activity_query(prompt)
        if is_activity_question:
            updates_result = get_updates_context(activity_limit=10, notifications_limit=10)
            activity_context = updates_result.get('context', '')

            if not is_todo_query(prompt) and not any(k in message_lower for k in ['termin', 'kalender', 'aufgabe', 'todo', 'task']):
                return jsonify({
                    'success': True,
                    'response': updates_result.get('summary_text', 'Keine Aktivitaetsdaten verfuegbar.'),
                    'action': 'activity_lookup',
                    'context_used': bool(activity_context),
                    'context_count': 1 if activity_context else 0,
                    'intent': 'activity',
                    'sources_used': {
                        'photos': False,
                        'files': False,
                        'calendar': False,
                        'todos': False
                    }
                })

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

        # Interaktive Termin-Erstellung: Liefere Missing-Input-Form direkt an das Frontend
        if is_calendar_create_query(prompt):
            event_info = extract_event_info_from_message(prompt)

            if event_info.get('missing_info'):
                calendars = []
                if simple_calendar_manager:
                    try:
                        calendars = simple_calendar_manager.get_calendars()
                    except Exception as e:
                        logger.warning(f"Could not load calendars for interactive form: {e}")

                return jsonify({
                    'response': "Ich kann den Termin erstellen, mir fehlen aber noch: " + ", ".join(event_info['missing_info']) + ".",
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

            create_result = create_calendar_event(
                title=event_info.get('title'),
                start_time=event_info.get('start_time'),
                end_time=event_info.get('end_time'),
                calendar_name=event_info.get('calendar_name'),
                location=event_info.get('location'),
                description=prompt
            )

            if create_result.get('success'):
                return jsonify({
                    'response': create_result.get('message', 'Termin wurde erstellt.'),
                    'action': 'calendar_created',
                    'calendar_used': True,
                    'context_used': False,
                    'context_count': 0,
                    'training_saved': False,
                    'sources': [],
                    'created_event': create_result
                })

            return jsonify({
                'response': "Der Termin konnte nicht erstellt werden: " + create_result.get('error', 'Unbekannter Fehler'),
                'action': 'calendar_create_failed',
                'calendar_used': True,
                'context_used': False,
                'context_count': 0,
                'training_saved': False,
                'sources': []
            })

        # Detect query intent
        intent = detect_query_intent(prompt, preferred_source)
        logger.info(f"Query intent: {intent}, preferred_source: {preferred_source}")

        # Collect context from different sources based on intent
        photo_context = None
        photo_results = []
        file_context = None
        calendar_context = None
        todo_context = None

        # Gather photo context if relevant
        if intent in ['photos', 'mixed']:
            try:
                client = get_immich_client(username)
                if client:
                    # Reduced limit for quicker response in agent context
                    result = client.search_photos_intelligent(prompt, limit=6)
                    if result.get('success') and result.get('results') and len(result['results']) > 0:
                        # Format photo results for context with full details
                        photos = result['results']
                        photo_results = photos
                        photo_lines = []
                        
                        photo_lines.append("### 📸 Gefundene Fotos")
                        photo_lines.append("")
                        
                        for i, photo in enumerate(photos[:5], 1):  # Limit to 5 for context
                            name = photo['original_file_name']
                            date = photo.get('created_at', 'Unknown')
                            people = photo.get('people', [])
                            location = photo.get('location', '')
                            objects = photo.get('objects', [])
                            tags = photo.get('tags', [])
                            photo_id = photo.get('id', 'N/A')
                            asset_url = photo['asset_url']
                            thumbnail_url = build_immich_thumbnail_proxy_url(photo_id, username, 'preview') if photo_id != 'N/A' else photo.get('thumbnail_url', '')

                            # Add numbered photo entry with thumbnail as clickable link
                            photo_lines.append(f"#### Foto {i}: {name}")
                            photo_lines.append(f"**ID:** `{photo_id}`")
                            photo_lines.append(f"**Link:** [{asset_url}]({asset_url})")
                            
                            if date and date != 'Unknown':
                                date_str = date[:10] if len(str(date)) > 10 else date
                                photo_lines.append(f"**Datum:** {date_str}")
                            
                            if people:
                                photo_lines.append(f"**Personen:** {', '.join(people)}")
                            
                            if location:
                                photo_lines.append(f"**Ort:** {location}")
                            
                            if objects:
                                photo_lines.append(f"**Objekte erkannt:** {', '.join(objects[:5])}")  # Show first 5
                            
                            if tags:
                                photo_lines.append(f"**Tags:** {', '.join(tags[:5])}")  # Show first 5
                            
                            # Add thumbnail as image with link
                            photo_lines.append(f"[![Vorschau]({thumbnail_url})]({asset_url})")
                            photo_lines.append("")

                        photo_context = {
                            'content': '=== FOTOS VON IMMICH ===\n\n' + '\n'.join(photo_lines),
                            'source': 'Immich Photos',
                            'path': 'immich',
                            'similarity_score': 1.0,
                            'metadata': {
                                'count': len(photos),
                                'photo_ids': [p.get('id') for p in photos]
                            }
                        }
                        logger.info(f"Found {len(photos)} photos for context with full metadata")
            except Exception as e:
                logger.error(f"Photo search error: {e}")

        # Gather file context if relevant
        if intent in ['files', 'mixed']:
            try:
                file_results = knowledge_base.search_knowledge(prompt, k=8)
                if file_results:
                    file_context = file_results
                    logger.info(f"Found {len(file_results)} file results for context")
            except Exception as e:
                logger.error(f"File search error: {e}")

        # Gather calendar context if relevant
        if (intent in ['calendar', 'mixed'] or is_potentially_calendar_query) and calendar_enabled:
            try:
                calendar_context_str = get_calendar_context(prompt)
                if calendar_context_str:
                    calendar_context = {
                        'content': calendar_context_str,
                        'source': 'Kalender',
                        'path': 'calendar',
                        'similarity_score': 1.0,
                        'metadata': {}
                    }
                    logger.info("Calendar context added")
            except Exception as e:
                logger.error(f"Calendar error: {e}")

        # Gather todo context if relevant
        todo_data = None
        if intent in ['tasks', 'mixed']:
            try:
                if is_todo_query(prompt):
                    todo_data = get_todo_data(prompt)
                    todo_context_str = todo_data.get('context', '')
                    if todo_context_str:
                        todo_context = {
                            'content': todo_context_str,
                            'source': 'Todos',
                            'path': 'todos',
                            'similarity_score': 1.0,
                            'metadata': {}
                        }
                        logger.info("Todo context added")
            except Exception as e:
                logger.error(f"Todo error: {e}")

        # Für reine Todo/Erinnerungs-Anfragen direkt antworten,
        # um generische LLM-Antworten ohne Datenbezug zu vermeiden.
        if intent == 'tasks' and is_todo_query(prompt):
            todo_data = todo_data or get_todo_data(prompt)
            open_tasks = todo_data.get('tasks', [])
            filtered_tasks = todo_data.get('filtered_tasks', open_tasks)

            if not todo_data.get('enabled', False):
                return jsonify({
                    'success': True,
                    'response': 'Deine Erinnerungen sind aktuell nicht verbunden. Bitte prüfe die Nextcloud-Task-Konfiguration.',
                    'context_used': False,
                    'context_count': 0,
                    'intent': intent,
                    'sources_used': {
                        'photos': False,
                        'files': False,
                        'calendar': False,
                        'todos': False
                    }
                })

            direct_response = _build_direct_todo_response(open_tasks, filtered_tasks, prompt)
            return jsonify({
                'success': True,
                'response': direct_response,
                'context_used': len(open_tasks) > 0,
                'context_count': len(open_tasks),
                'intent': intent,
                'sources_used': {
                    'photos': False,
                    'files': False,
                    'calendar': False,
                    'todos': True
                }
            })

        # Combine all contexts
        combined_context = []

        if photo_context:
            combined_context.insert(0, photo_context)

        if file_context:
            combined_context.extend(file_context)

        if calendar_context:
            combined_context.insert(0, calendar_context)

        if todo_context:
            combined_context.insert(0, todo_context)

        # Für reine Foto-Anfragen direkt antworten, um LLM-Ausreden zu vermeiden
        if intent == 'photos':
            if photo_results:
                response_lines = ["Hier sind passende Fotos aus Immich:", ""]
                for i, photo in enumerate(photo_results[:5], 1):
                    url = photo.get('asset_url')
                    name = photo.get('original_file_name', f'Foto {i}')
                    photo_id = photo.get('id', 'N/A')
                    thumbnail_url = build_immich_thumbnail_proxy_url(photo_id, username, 'preview') if photo_id != 'N/A' else photo.get('thumbnail_url')
                    people = photo.get('people', [])
                    date_value = photo.get('created_at', '')
                    date_label = date_value[:10] if date_value else ''

                    response_lines.append(f"{i}. [{name}]({url})")
                    response_lines.append(f"   ID: {photo_id}")
                    if people:
                        response_lines.append(f"   Personen: {', '.join(people)}")
                    if date_label:
                        response_lines.append(f"   Datum: {date_label}")
                    if thumbnail_url and url:
                        response_lines.append(f"   [![Vorschau {i}]({thumbnail_url})]({url})")
                    response_lines.append("")

                return jsonify({
                    'success': True,
                    'response': '\n'.join(response_lines).strip(),
                    'context_used': True,
                    'context_count': len(combined_context),
                    'intent': intent,
                    'sources_used': {
                        'photos': True,
                        'files': False,
                        'calendar': False,
                        'todos': False
                    }
                })

            return jsonify({
                'success': True,
                'response': 'Ich habe in Immich keine passenden Fotos gefunden. Versuche einen anderen Namen oder ein anderes Suchwort.',
                'context_used': False,
                'context_count': 0,
                'intent': intent,
                'sources_used': {
                    'photos': False,
                    'files': False,
                    'calendar': False,
                    'todos': False
                }
            })

        # Build system message with context
        if not combined_context:
            system_message = "Du bist ein hilfreicher Assistent. Antworte natürlich und präzise."
        else:
            context_parts = []
            for ctx in combined_context:
                source_name = ctx.get('source', 'Unknown')
                content = ctx.get('content', '')
                if content:
                    context_parts.append(f"--- {source_name} ---\n{content}")

            context_text = '\n\n'.join(context_parts)
            system_message = f"""Du bist ein hilfreicher Assistent mit Zugriff auf folgende Informationen:

{context_text}

Nutze diese Informationen um die Frage präzise zu beantworten.
Falls Fotos verfügbar sind, stelle sie als Markdown-Links dar.
Antworte auf {language}."""

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

            return jsonify({
                'success': True,
                'response': ai_response,
                'context_used': len(combined_context) > 0,
                'context_count': len(combined_context),
                'intent': intent,
                'sources_used': {
                    'photos': photo_context is not None,
                    'files': file_context is not None and len(file_context) > 0,
                    'calendar': calendar_context is not None,
                    'todos': todo_context is not None
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
