import json
import time
import sys
import logging
from typing import List, Dict, Optional, Tuple
import os
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from backend.core.database import KnowledgeDatabase

logger = logging.getLogger(__name__)

class QueryIntent:
    """Klassifizierung von Query-Intents für besseres Kontext-Management"""

    PERSONAL = "personal"           # Persönliche Informationen (Name, Alter, System)
    FACTUAL = "factual"             # Fakten und Wissen (Was ist X?, Wie funktioniert Y?)
    TEMPORAL = "temporal"           # Zeitbezogene Fragen (Wann war X?, Datum von Y?)
    COMPARATIVE = "comparative"     # Vergleichsfragen (Unterschied zwischen X und Y?)
    PROCEDURAL = "procedural"       # Anleitungen (Wie mache ich X?, Schritt für Schritt)
    EXPLORATORY = "exploratory"     # Offene Erkundungsfragen (Erzähl mir über X)
    SPECIFIC = "specific"           # Sehr spezifische Fragen mit klarer Antwort
    AGGREGATIVE = "aggregative"     # Fragen die mehrere Quellen zusammenfassen (Alle X, Liste von Y)

    @staticmethod
    def classify_query(query: str) -> Tuple[str, float]:
        """Klassifiziert eine Query und gibt Intent + Confidence zurück"""
        query_lower = query.lower().strip()

        # Personal intent patterns
        personal_patterns = [
            r'\b(mein|dein|welch(?:es|er|e))\s+(?:betriebssystem|computer|laptop|pc|system)',
            r'\b(?:wie|was)\s+(?:heiß|bist)\s+du',
            r'\bwie\s+alt\s+bist\s+du',
            r'\b(?:wer|was)\s+bist\s+du',
            r'\b(?:dein|mein)\s+name',
            r'\bnutzt\s+du',
            r'\bverwendest\s+du'
        ]

        # Temporal intent patterns
        temporal_patterns = [
            r'\b(?:wann|datum|zeitpunkt|tag|monat|jahr)',
            r'\b(?:heute|gestern|morgen|letzte|nächste)\s+(?:woche|monat)',
            r'\bvor\s+(?:\d+|einem|einer)\s+(?:tag|woche|monat|jahr)',
            r'\bseit\s+wann',
            r'\bab\s+wann'
        ]

        # Comparative intent patterns
        comparative_patterns = [
            r'\b(?:unterschied|differenz|vergleich|versus|vs\.?)',
            r'\bbesser\s+als',
            r'\bschlechter\s+als',
            r'\b(?:ähnlich|gleich|identisch)\s+(?:wie|zu)',
            r'\bim\s+vergleich\s+zu'
        ]

        # Procedural intent patterns
        procedural_patterns = [
            r'\b(?:wie|anleitung|schritte|vorgehen)',
            r'\b(?:mache|erstelle|konfiguriere|installiere|richte\s+ein)',
            r'\bschritt\s+für\s+schritt',
            r'\b(?:tutorial|guide)',
            r'\bwie\s+(?:kann|könnte)\s+ich'
        ]

        # Exploratory intent patterns
        exploratory_patterns = [
            r'\b(?:erzähl|erklär|beschreib|berichte)',
            r'\b(?:was\s+weißt\s+du|informationen)\s+(?:über|zu)',
            r'\b(?:alles|mehr)\s+(?:über|zu)',
            r'\b(?:überblick|zusammenfassung|übersicht)',
            r'\bwas\s+gibt\s+es'
        ]

        # Aggregative intent patterns
        aggregative_patterns = [
            r'\b(?:alle|sämtliche|liste|aufzählung)',
            r'\b(?:welche|was\s+für)\s+.+\s+(?:gibt\s+es|existieren|vorhanden)',
            r'\bzeige\s+(?:alle|mir)',
            r'\b(?:übersicht|sammlung)\s+(?:von|der|aller)'
        ]

        # Specific intent patterns (very focused questions)
        specific_patterns = [
            r'^(?:was|wer|wo|welch)\s+(?:ist|sind|war|waren)\s+[^\?]{1,30}\??$',
            r'\b(?:definition|bedeutung)\s+von',
            r'\bwas\s+bedeutet'
        ]

        # Check patterns in order of specificity
        if any(re.search(p, query_lower) for p in personal_patterns):
            return QueryIntent.PERSONAL, 0.9

        if any(re.search(p, query_lower) for p in comparative_patterns):
            return QueryIntent.COMPARATIVE, 0.85

        if any(re.search(p, query_lower) for p in procedural_patterns):
            return QueryIntent.PROCEDURAL, 0.85

        if any(re.search(p, query_lower) for p in temporal_patterns):
            return QueryIntent.TEMPORAL, 0.8

        if any(re.search(p, query_lower) for p in aggregative_patterns):
            return QueryIntent.AGGREGATIVE, 0.8

        if any(re.search(p, query_lower) for p in exploratory_patterns):
            return QueryIntent.EXPLORATORY, 0.75

        if any(re.search(p, query_lower) for p in specific_patterns):
            return QueryIntent.SPECIFIC, 0.7

        # Default: Factual
        return QueryIntent.FACTUAL, 0.5

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
        """Erstelle verbesserten Kontext für die KI mit Intent-basierter Optimierung"""

        # Klassifiziere Query-Intent
        intent, confidence = QueryIntent.classify_query(query)

        # Metadaten extrahieren
        try:
            from backend.core.app import metadata_extractor
            enhanced_context = metadata_extractor.enhance_context_with_metadata(context_results)
        except ImportError:
            # Fallback wenn metadata_extractor nicht verfügbar ist
            enhanced_context = context_results

        # Intent-basierte Kontextkonfiguration
        context_config = self._get_context_config_for_intent(intent, confidence)

        # Bei persönlichen Fragen mit keinen Informationen
        if intent == QueryIntent.PERSONAL and (not enhanced_context or len(enhanced_context) == 0):
            return """=== PERSÖNLICHE FRAGE ===

Die Frage bezieht sich auf persönliche Informationen, die nicht in der Wissensbasis gefunden wurden.
Antworte kurz und direkt, dass diese Information nicht verfügbar ist."""

        # Sortiere Ergebnisse nach Relevanz
        sorted_results = sorted(
            enhanced_context,
            key=lambda x: x.get('similarity_score', 0.0),
            reverse=True
        )

        # Begrenze Anzahl basierend auf Intent
        max_sources = context_config['max_sources']
        sorted_results = sorted_results[:max_sources]

        # Erstelle Kontext-Header mit Intent-Information
        context_text = f"""=== QUERY-ANALYSE ===
Intent: {intent.upper()} (Konfidenz: {confidence:.0%})
Strategie: {context_config['strategy']}
Gefundene Quellen: {len(sorted_results)}

=== GEFUNDENE INFORMATIONEN ===

"""

        # Formatiere Quellen basierend auf Intent
        for i, result in enumerate(sorted_results):
            source_file = result.get('source', 'Unknown')
            file_path = result.get('path', '')
            file_type = result.get('path', '').split('.')[-1] if '.' in result.get('path', '') else 'unknown'
            relevance = result.get('similarity_score', 0.5)
            content = result.get('content', '')
            metadata = result.get('metadata', {})

            context_text += f"[QUELLE {i+1}] (Relevanz: {relevance:.1%})\n"
            context_text += f"📄 Datei: {source_file}\n"

            # Zeige Metadaten basierend auf Intent
            if intent == QueryIntent.TEMPORAL and metadata.get('dates'):
                dates = [d['normalized'] or d['raw'] for d in metadata['dates']]
                context_text += f"📅 Datum: {', '.join(dates[:3])}\n"

            if intent in [QueryIntent.PROCEDURAL, QueryIntent.EXPLORATORY] and metadata.get('people'):
                people = metadata['people'][:3]
                context_text += f"👤 Personen: {', '.join([p['raw'] for p in people])}\n"

            if metadata.get('organizations'):
                orgs = metadata['organizations'][:2]
                context_text += f"🏢 Organisationen: {', '.join([o['raw'] for o in orgs])}\n"

            if metadata.get('locations'):
                locs = metadata['locations'][:2]
                context_text += f"📍 Orte: {', '.join([l['raw'] for l in locs])}\n"

            # Content mit Intent-basiertem Limit
            if content:
                content_limit = context_config['content_limit']
                content_preview = content[:content_limit] + "..." if len(content) > content_limit else content
                context_text += f"💬 Inhalt: {content_preview}\n"

            context_text += "\n"

        # Intent-spezifische Anweisungen
        context_text += "=== ANTWORT-ANWEISUNGEN ===\n"
        context_text += context_config['instructions']

        return context_text

    def _get_context_config_for_intent(self, intent: str, confidence: float) -> Dict:
        """Gibt Intent-spezifische Kontextkonfiguration zurück"""

        configs = {
            QueryIntent.PERSONAL: {
                'max_sources': 3,
                'content_limit': 400,
                'strategy': 'Direkte und präzise Antwort aus begrenzten Quellen',
                'instructions': """1. Antworte kurz und direkt auf die persönliche Frage
2. Nutze nur die relevantesten Informationen
3. Bei fehlenden Informationen: "Ich habe dazu keine Informationen."
4. Vermeide unnötige Details oder Ausschweifungen"""
            },
            QueryIntent.TEMPORAL: {
                'max_sources': 5,
                'content_limit': 600,
                'strategy': 'Fokus auf zeitliche Informationen und Chronologie',
                'instructions': """1. Priorisiere Datums- und Zeitangaben in der Antwort
2. Sortiere Informationen chronologisch wenn möglich
3. Gib konkrete Zeitpunkte und Zeiträume an
4. Nutze gefundene Metadaten für präzise zeitliche Einordnung"""
            },
            QueryIntent.COMPARATIVE: {
                'max_sources': 8,
                'content_limit': 800,
                'strategy': 'Sammle Informationen für strukturierten Vergleich',
                'instructions': """1. Strukturiere die Antwort als klaren Vergleich
2. Hebe Gemeinsamkeiten und Unterschiede hervor
3. Nutze mehrere Quellen für ausgewogene Perspektive
4. Präsentiere Vergleich tabellarisch oder in Gegenüberstellung"""
            },
            QueryIntent.PROCEDURAL: {
                'max_sources': 6,
                'content_limit': 1000,
                'strategy': 'Schritt-für-Schritt Anleitung aus Quellen extrahieren',
                'instructions': """1. Strukturiere Antwort als klare Schritt-für-Schritt Anleitung
2. Nummeriere Schritte logisch und sequenziell
3. Füge wichtige Details und Warnungen hinzu
4. Nutze mehrere Quellen für vollständige Anleitung"""
            },
            QueryIntent.EXPLORATORY: {
                'max_sources': 10,
                'content_limit': 900,
                'strategy': 'Umfassende Übersicht aus vielen Quellen',
                'instructions': """1. Gib einen umfassenden Überblick über das Thema
2. Integriere Informationen aus verschiedenen Quellen
3. Strukturiere die Antwort thematisch
4. Füge verwandte Themen und Kontext hinzu
5. Sei informativ und ausführlich"""
            },
            QueryIntent.AGGREGATIVE: {
                'max_sources': 12,
                'content_limit': 500,
                'strategy': 'Sammle und liste alle relevanten Informationen',
                'instructions': """1. Erstelle eine strukturierte Liste aller gefundenen Elemente
2. Gruppiere ähnliche Einträge wenn sinnvoll
3. Sortiere nach Relevanz oder logischer Ordnung
4. Nutze Bullet Points oder Nummerierung
5. Sei vollständig aber prägnant"""
            },
            QueryIntent.SPECIFIC: {
                'max_sources': 4,
                'content_limit': 500,
                'strategy': 'Präzise Antwort auf spezifische Frage',
                'instructions': """1. Beantworte die Frage direkt und präzise
2. Nutze die relevanteste Quelle primär
3. Vermeide unnötige Zusatzinformationen
4. Gib klare Quellenangabe"""
            },
            QueryIntent.FACTUAL: {
                'max_sources': 7,
                'content_limit': 700,
                'strategy': 'Faktische Antwort mit ausreichendem Kontext',
                'instructions': """1. Beantworte die Frage faktisch und informativ
2. Nutze multiple Quellen für ausgewogene Antwort
3. Gib relevanten Kontext und Details
4. Strukturiere Antwort klar und logisch"""
            }
        }

        return configs.get(intent, configs[QueryIntent.FACTUAL])
    
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
