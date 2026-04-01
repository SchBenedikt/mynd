"""
Context gathering for AI agent queries
Handles gathering context from photos, files, calendar, tasks, weather, security, and activities
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date

logger = logging.getLogger(__name__)


def gather_photo_context(client, prompt: str, username: str, build_thumbnail_url_func) -> Optional[Dict]:
    """Gather photo context from Immich"""
    try:
        if not client:
            return None

        result = client.search_photos_intelligent(prompt, limit=6)
        if not result.get('success') or not result.get('results'):
            return None

        photos = result['results']
        photo_lines = []

        photo_lines.append("### 📸 Gefundene Fotos")
        photo_lines.append("")
        photo_lines.append("WICHTIG: Bette die Fotos direkt in deine Antwort ein mit Markdown-Bildern: ![Beschreibung](URL)")
        photo_lines.append("")

        for i, photo in enumerate(photos[:5], 1):
            name = photo['original_file_name']
            date_val = photo.get('created_at', 'Unknown')
            people = photo.get('people', [])
            location = photo.get('location', '')
            objects = photo.get('objects', [])
            tags = photo.get('tags', [])
            photo_id = photo.get('id', 'N/A')
            asset_url = photo['asset_url']
            thumbnail_url = build_thumbnail_url_func(photo_id, username, 'preview') if photo_id != 'N/A' else photo.get('thumbnail_url', '')

            photo_lines.append(f"**Foto {i}: {name}**")
            photo_lines.append(f"- Bild-URL für Einbettung: {thumbnail_url}")
            photo_lines.append(f"- Vollbild-Link: {asset_url}")
            photo_lines.append(f"- ID: {photo_id}")

            if date_val and date_val != 'Unknown':
                date_str = date_val[:10] if len(str(date_val)) > 10 else date_val
                photo_lines.append(f"- Aufgenommen am: {date_str}")

            if people:
                people_names = [p if isinstance(p, str) else p.get('name', str(p)) for p in people]
                photo_lines.append(f"- Personen auf dem Foto: {', '.join(people_names)}")

            if location:
                photo_lines.append(f"- Ort: {location}")

            if objects:
                obj_names = [o if isinstance(o, str) else o.get('name', str(o)) for o in objects[:5]]
                photo_lines.append(f"- Erkannte Objekte: {', '.join(obj_names)}")

            if tags:
                tag_names = [t if isinstance(t, str) else t.get('name', str(t)) for t in tags[:5]]
                photo_lines.append(f"- Tags: {', '.join(tag_names)}")

            photo_lines.append("")

        return {
            'content': '=== FOTOS VON IMMICH ===\n\n' + '\n'.join(photo_lines),
            'source': 'Immich Photos',
            'path': 'immich',
            'similarity_score': 1.0,
            'metadata': {
                'count': len(photos),
                'photo_ids': [p.get('id') for p in photos],
                'photos': photos
            }
        }
    except Exception as e:
        logger.error(f"Photo search error: {e}")
        return None


def gather_file_context(knowledge_base, training_manager, prompt: str) -> Optional[List[Dict]]:
    """Gather file context from knowledge base with enhanced training manager context"""
    try:
        file_results = knowledge_base.search_knowledge(prompt, k=10)
        if not file_results:
            return None

        # Use training manager to create enhanced context with metadata
        enhanced_context_text = training_manager.create_enhanced_context_for_ai(prompt, file_results)

        return [{
            'content': enhanced_context_text,
            'source': 'Nextcloud Dateien & Wissensbasis',
            'path': 'knowledge_base',
            'similarity_score': 1.0,
            'metadata': {
                'count': len(file_results),
                'enhanced': True
            }
        }]
    except Exception as e:
        logger.error(f"File search error: {e}")
        return None


def gather_weather_context(get_weather_func, is_weather_query_func, prompt: str, safe_text_func) -> Optional[Dict]:
    """Gather weather context"""
    if not is_weather_query_func(prompt):
        return None

    try:
        weather = get_weather_func()
        weather_lines = []
        weather_lines.append("=== WETTER-INFORMATION ===")
        weather_lines.append(f"Zusammenfassung: {weather.get('summary', 'Nicht verfügbar')}")

        if weather.get('alerts_count', 0) > 0:
            weather_lines.append(f"\nWetterwarnungen ({weather.get('alerts_count')} aktiv):")
            for idx, alert in enumerate((weather.get('alerts') or [])[:5], 1):
                event = alert.get('event') or f'Warnung {idx}'
                sender = safe_text_func(alert.get('sender_name'))
                desc = alert.get('description', '')[:200] + '...' if len(alert.get('description', '')) > 200 else alert.get('description', '')
                weather_lines.append(f"{idx}. {event}" + (f" ({sender})" if sender else ""))
                if desc:
                    weather_lines.append(f"   {desc}")

        return {
            'content': '\n'.join(weather_lines),
            'source': 'Wetter',
            'path': 'weather',
            'similarity_score': 1.0,
            'metadata': weather
        }
    except Exception as e:
        logger.error(f"Weather context error: {e}")
        return None


def gather_security_context(get_security_func, is_security_query_func, prompt: str) -> Optional[Dict]:
    """Gather security context"""
    if not is_security_query_func(prompt):
        return None

    try:
        security = get_security_func()
        security_lines = []
        security_lines.append("=== SICHERHEITSLAGE ===")
        security_lines.append(f"NINA Warnungen: {security.get('nina_warning_count', 0)}")

        if security.get('nina_warning_count', 0) > 0:
            for idx, warning in enumerate(security.get('nina_warnings', [])[:5], 1):
                security_lines.append(f"{idx}. {warning.get('headline', 'Warnung')}")
                security_lines.append(f"   Schweregrad: {warning.get('severity', 'Unbekannt')}")
                desc = warning.get('description', '')[:200] + '...' if len(warning.get('description', '')) > 200 else warning.get('description', '')
                if desc:
                    security_lines.append(f"   {desc}")

        return {
            'content': '\n'.join(security_lines),
            'source': 'Sicherheitslage',
            'path': 'security',
            'similarity_score': 1.0,
            'metadata': security
        }
    except Exception as e:
        logger.error(f"Security context error: {e}")
        return None


def gather_activity_context(get_updates_func, is_activity_query_func, prompt: str) -> Optional[Dict]:
    """Gather activity context from Nextcloud"""
    if not is_activity_query_func(prompt):
        return None

    try:
        updates_result = get_updates_func(activity_limit=10, notifications_limit=10)
        activity_context_str = updates_result.get('context', '')
        if not activity_context_str:
            return None

        return {
            'content': activity_context_str,
            'source': 'Nextcloud Aktivitäten',
            'path': 'activity',
            'similarity_score': 1.0,
            'metadata': {}
        }
    except Exception as e:
        logger.error(f"Activity context error: {e}")
        return None


def gather_calendar_context(get_calendar_context_func, should_use_calendar_func,
                           prompt: str, intent: str, calendar_enabled: bool) -> Optional[Dict]:
    """Gather calendar context"""
    use_calendar_intelligent = should_use_calendar_func(prompt)

    if not ((intent in ['calendar', 'mixed'] or use_calendar_intelligent) and calendar_enabled):
        return None

    try:
        calendar_context_str = get_calendar_context_func(prompt)
        if not calendar_context_str:
            return None

        logger.info(f"Calendar context added (intent={intent}, intelligent={use_calendar_intelligent})")
        return {
            'content': calendar_context_str,
            'source': 'Kalender',
            'path': 'calendar',
            'similarity_score': 1.0,
            'metadata': {}
        }
    except Exception as e:
        logger.error(f"Calendar error: {e}")
        return None


def gather_todo_context(get_todo_data_func, is_todo_query_func, should_use_tasks_func,
                       prompt: str, intent: str) -> Optional[Dict]:
    """Gather todo/task context"""
    use_tasks_intelligent = should_use_tasks_func(prompt)

    if not (intent in ['tasks', 'mixed'] or use_tasks_intelligent):
        return None

    try:
        if not (is_todo_query_func(prompt) or use_tasks_intelligent):
            return None

        todo_data = get_todo_data_func(prompt)
        todo_context_str = todo_data.get('context', '')
        if not todo_context_str:
            return None

        logger.info(f"Todo context added (intent={intent}, intelligent={use_tasks_intelligent})")
        return {
            'content': todo_context_str,
            'source': 'Todos',
            'path': 'todos',
            'similarity_score': 1.0,
            'metadata': {}
        }
    except Exception as e:
        logger.error(f"Todo error: {e}")
        return None


def combine_contexts(weather_ctx, security_ctx, activity_ctx, photo_ctx,
                    file_ctx, calendar_ctx, todo_ctx) -> List[Dict]:
    """Combine all contexts in the correct order"""
    combined = []

    # Priority order: weather, security, activity, photos, files, calendar, todos
    if weather_ctx:
        combined.insert(0, weather_ctx)
    if security_ctx:
        combined.insert(0, security_ctx)
    if activity_ctx:
        combined.insert(0, activity_ctx)
    if photo_ctx:
        combined.insert(0, photo_ctx)
    if file_ctx:
        combined.extend(file_ctx)
    if calendar_ctx:
        combined.insert(0, calendar_ctx)
    if todo_ctx:
        combined.insert(0, todo_ctx)

    return combined


def build_system_message(combined_context: List[Dict], language: str = 'de') -> str:
    """Build system message for AI based on available context"""
    if not combined_context:
        return f"""Du bist ein intelligenter persönlicher Assistent.

WICHTIG:
- Antworte auf {language}
- Sei natürlich und variiere deine Formulierungen
- Vermeide Floskeln und vorgefertigte Phrasen
- Sprich direkt und persönlich mit dem Nutzer
- Sei präzise und hilfreich

Antworte natürlich auf die Anfrage."""

    context_parts = []
    for ctx in combined_context:
        source_name = ctx.get('source', 'Unknown')
        content = ctx.get('content', '')
        if content:
            context_parts.append(f"--- {source_name} ---\n{content}")

    context_text = '\n\n'.join(context_parts)
    return f"""Du bist ein intelligenter persönlicher Assistent mit Zugriff auf folgende Informationen:

{context_text}

WICHTIGE ANWEISUNGEN ZUR NUTZUNG DER INFORMATIONEN:

**Nextcloud-Dateien & Wissensbasis:**
- Die bereitgestellten Dokumente aus der Nextcloud enthalten wichtige persönliche und fachliche Informationen
- Nutze diese Informationen aktiv und direkt in deiner Antwort
- Verweise auf konkrete Inhalte, Daten und Fakten aus den Dokumenten
- Bei Datumsangaben, Personen oder Organisationen: Nenne diese explizit aus den Metadaten
- Die Intent-Analyse zeigt dir, wie du die Informationen am besten strukturierst

**Fotos von Immich:**
- Wenn Fotos verfügbar sind, BETTE SIE DIREKT EIN mit: ![Beschreibung](Bild-URL)
- Nutze die "Bild-URL für Einbettung" aus dem Kontext
- Beschreibe die Fotos mit den verfügbaren Metadaten (Personen, Ort, Objekte, Datum)
- Zeige maximal 5 Fotos pro Antwort
- Beispiel: ![Foto von Max und Lisa am Strand](https://immich.example.com/thumbnail/...)

**Allgemeine Richtlinien:**
- Antworte auf {language}
- Sei natürlich und variiere deine Formulierungen - vermeide stereotype Antworten
- Nutze die Intent-Analyse und Antwort-Anweisungen aus dem Kontext
- Bei Aufgaben oder Terminen: stelle sie übersichtlich und natürlich dar
- Bei Wetterdaten: fasse die wichtigsten Informationen verständlich zusammen
- Bei Sicherheitswarnungen: kommuniziere klar und sachlich
- Sprich direkt mit dem Nutzer und vermeide unnötige Floskeln
- Sei präzise, hilfsbereit und persönlich

Falls Informationen fehlen oder unvollständig sind, sage dies ehrlich.
Erfinde keine Informationen, die nicht in den bereitgestellten Daten enthalten sind."""
