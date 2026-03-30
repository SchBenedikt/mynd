import json
import time
import logging
from typing import List, Dict, Optional
from database import KnowledgeDatabase
import os

logger = logging.getLogger(__name__)

class TrainingManager:
    """Manager für KI-Training mit JSON-basierten Kontext-Daten"""
    
    def __init__(self, db_path: str = "knowledge_base.db"):
        self.db = KnowledgeDatabase(db_path)
        self.training_data_path = "training_data.json"
        self.model_info_path = "model_info.json"
        
    def create_training_dataset(self, query: str, context_results: List[Dict]) -> Dict:
        """Erstelle strukturierte Trainingsdaten für eine Query"""
        
        # Formatieren des Kontexts mit Quellen-Informationen
        formatted_context = []
        for i, result in enumerate(context_results):
            context_item = {
                "id": result.get('chunk_id', i),
                "content": result.get('content', ''),
                "source_file": result.get('source', 'Unknown'),
                "file_path": result.get('path', ''),
                "file_type": self._get_file_type(result.get('path', '')),
                "relevance_score": result.get('similarity_score', 0.5),
                "chunk_preview": result.get('content', '')[:100] + "..." if len(result.get('content', '')) > 100 else result.get('content', '')
            }
            formatted_context.append(context_item)
        
        # Erstelle Trainings-Beispiel
        training_example = {
            "query": query,
            "timestamp": time.time(),
            "context_sources": len(context_results),
            "context_data": formatted_context,
            "source_summary": self._create_source_summary(context_results)
        }
        
        return training_example
    
    def _get_file_type(self, file_path: str) -> str:
        """Extrahiere Dateityp aus Pfad"""
        if not file_path:
            return "unknown"
        return os.path.splitext(file_path)[1].lower() or "unknown"
    
    def _create_source_summary(self, context_results: List[Dict]) -> Dict:
        """Erstelle Zusammenfassung der Quellen"""
        sources = {}
        file_types = {}
        
        for result in context_results:
            source = result.get('source', 'Unknown')
            file_path = result.get('path', '')
            file_type = self._get_file_type(file_path)
            
            # Zähle Quellen
            sources[source] = sources.get(source, 0) + 1
            
            # Zähle Dateitypen
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        return {
            "unique_sources": len(sources),
            "source_distribution": sources,
            "file_types": file_types,
            "total_chunks": len(context_results)
        }
    
    def save_training_interaction(self, query: str, context_results: List[Dict], ai_response: str, feedback: Optional[str] = None):
        """Speichere eine komplette Trainings-Interaktion"""
        
        training_data = self.create_training_dataset(query, context_results)
        
        # Füge KI-Antwort und Feedback hinzu
        interaction = {
            **training_data,
            "ai_response": ai_response,
            "response_length": len(ai_response),
            "feedback": feedback,
            "interaction_id": f"int_{int(time.time())}"
        }
        
        # Lade existierende Daten
        existing_data = []
        if os.path.exists(self.training_data_path):
            try:
                with open(self.training_data_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading training data: {e}")
        
        # Füge neue Interaktion hinzu
        existing_data.append(interaction)
        
        # Behalte nur die letzten 1000 Interaktionen
        if len(existing_data) > 1000:
            existing_data = existing_data[-1000:]
        
        # Speichere Daten
        try:
            with open(self.training_data_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Training interaction saved: {query[:50]}...")
        except Exception as e:
            logger.error(f"Error saving training data: {e}")
    
    def get_training_stats(self) -> Dict:
        """Hole Trainings-Statistiken"""
        if not os.path.exists(self.training_data_path):
            return {"total_interactions": 0}
        
        try:
            with open(self.training_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            total_interactions = len(data)
            avg_context_sources = sum(item.get('context_sources', 0) for item in data) / max(total_interactions, 1)
            avg_response_length = sum(item.get('response_length', 0) for item in data) / max(total_interactions, 1)
            
            # Häufigste Queries
            queries = [item.get('query', '') for item in data]
            query_frequency = {}
            for query in queries:
                query_frequency[query] = query_frequency.get(query, 0) + 1
            
            return {
                "total_interactions": total_interactions,
                "avg_context_sources": round(avg_context_sources, 2),
                "avg_response_length": round(avg_response_length, 2),
                "most_common_queries": sorted(query_frequency.items(), key=lambda x: x[1], reverse=True)[:5],
                "training_file_size": os.path.getsize(self.training_data_path) if os.path.exists(self.training_data_path) else 0
            }
        except Exception as e:
            logger.error(f"Error getting training stats: {e}")
            return {"error": str(e)}
    
    def create_enhanced_context_for_ai(self, query: str, context_results: List[Dict]) -> str:
        """Erstelle verbesserten Kontext für die KI mit Metadaten und detaillierten Quellenangaben"""
        
        # Metadaten extrahieren
        try:
            from backend.core.app import metadata_extractor
            enhanced_context = metadata_extractor.enhance_context_with_metadata(context_results)
        except ImportError:
            # Fallback wenn metadata_extractor nicht verfügbar ist
            enhanced_context = context_results
        
        # Prüfen, ob die Frage nach persönlichen Informationen geht
        personal_query_patterns = [
            'welches betriebssystem', 'welcher computer', 'welcher laptop',
            'welche software', 'welche version', 'welches programm',
            'was nutzt du', 'was verwendest du', 'was hast du',
            'dein name', 'wer bist du', 'wie alt bist du'
        ]
        
        # Prüfen, ob es eine themenbezogene Frage ist (mehr Inhalt erwünscht)
        topic_query_patterns = [
            'wann war', 'was ist', 'wie funktioniert', 'welche', 'warum', 'wo',
            'nextcloud', 'conference', 'server', 'dell', 'poweredge', 'dokument',
            'projekt', 'system', 'anwendung', 'technologie', 'daten'
        ]
        
        query_lower = query.lower()
        is_personal_query = any(pattern in query_lower for pattern in personal_query_patterns)
        is_topic_query = any(pattern in query_lower for pattern in topic_query_patterns)
        
        if is_personal_query:
            # Bei persönlichen Fragen mit keinen Informationen antworten
            if not enhanced_context or len(enhanced_context) == 0:
                return "=== PERSÖNLICHE FRAGE ===\n\nDie Frage bezieht sich auf persönliche Informationen, die nicht in der Wissensbasis gefunden wurden. Antworte kurz und direkt, dass diese Information nicht verfügbar ist."
        
        # Für themenbezogene Fragen mehr Inhalt erlauben
        if is_topic_query:
            content_limit = 800  # Mehr Inhalt für themenbezogene Fragen
        else:
            content_limit = 500  # Standard-Limit
        
        context_text = "=== GEFUNDENE INFORMATIONEN ===\n\n"
        
        for i, result in enumerate(enhanced_context):
            source_file = result.get('source', 'Unknown')
            file_path = result.get('path', '')
            file_type = result.get('path', '').split('.')[-1] if '.' in result.get('path', '') else 'unknown'
            relevance = result.get('similarity_score', 0.5)
            content = result.get('content', '')
            metadata = result.get('metadata', {})
            
            context_text += f"[QUELLE {i+1}]\n"
            context_text += f"Datei: {source_file}\n"
            
            # Nur relevante Metadaten anzeigen
            if metadata.get('dates'):
                dates = [d['normalized'] or d['raw'] for d in metadata['dates']]
                context_text += f"Datum: {', '.join(dates[:2])}\n"  # Max 2 Daten
            
            if metadata.get('people'):
                people = metadata['people'][:3]  # Max 3 Personen
                context_text += f"Personen: {', '.join([p['raw'] for p in people])}\n"
            
            if metadata.get('organizations'):
                orgs = metadata['organizations'][:2]  # Max 2 Organisationen
                context_text += f"Organisationen: {', '.join([o['raw'] for o in orgs])}\n"
            
            # Content mit dynamischem Limit
            if content:
                content_preview = content[:content_limit] + "..." if len(content) > content_limit else content
                context_text += f"Inhalt: {content_preview}\n"
            
            context_text += "\n"
        
        context_text += "=== ANWEISUNGEN FÜR ANTWORT ===\n"
        
        if is_topic_query:
            context_text += "1. Beantworte die Frage ausführlich und themenbezogen\n"
            context_text += "2. Beziehe auch verwandte Themen und Kontexte mit ein\n"
            context_text += "3. Gib zusätzliche nützliche Informationen zum Thema\n"
            context_text += "4. Strukturiere die Antwort informativ mit Beispielen\n"
            context_text += "5. Bleibe themenbezogen, darf aber etwas abschweifen\n"
        else:
            context_text += "1. Beantworte die Frage basierend auf den Quellen\n"
            context_text += "2. Wenn keine Informationen gefunden wurden: Antworte 'Diese Information ist nicht verfügbar.'\n"
            context_text += "3. Bei persönlichen Fragen ohne Quellen: Antworte 'Ich habe dazu keine Informationen.'\n"
            context_text += "4. Sei informativ aber vermeide unnötig lange Erklärungen\n"
            context_text += "5. Nutze Metadaten wenn sie für die Antwort relevant sind\n"
        
        return context_text
    
    def load_model_info(self) -> Dict:
        """Lade Modell-Informationen"""
        default_info = {
            "model_name": "gemma3:latest",
            "training_version": "1.0",
            "last_updated": time.time(),
            "context_window": 4096,
            "max_response_tokens": 2048
        }
        
        if os.path.exists(self.model_info_path):
            try:
                with open(self.model_info_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading model info: {e}")
        
        return default_info
    
    def save_model_info(self, info: Dict):
        """Speichere Modell-Informationen"""
        try:
            info["last_updated"] = time.time()
            with open(self.model_info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving model info: {e}")
