"""
Context gathering for AI agent queries
Handles gathering context from photos, files, calendar, tasks, weather, security, activities, and Nextcloud Search
"""
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


_QUERY_STOP_WORDS = {
    'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines',
    'und', 'oder', 'aber', 'nicht', 'auch', 'mit', 'für', 'von', 'auf', 'an',
    'ist', 'sind', 'war', 'waren', 'hat', 'haben', 'wird', 'werden',
    'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'man', 'mich', 'dir', 'mir',
    'wer', 'wie', 'was', 'wann', 'wo', 'warum', 'wieso',
    'the', 'a', 'an', 'and', 'or', 'but', 'not', 'also', 'with', 'for', 'from',
    'is', 'are', 'was', 'were', 'has', 'have', 'will', 'would', 'who', 'what', 'when', 'where', 'why'
}


def _extract_matching_sentence(prompt: str, content: str) -> str:
    """Return the most likely matching sentence from a chunk for source attribution cards."""
    normalized = " ".join((content or "").split())
    if not normalized:
        return ""

    keywords = [w.lower() for w in re.findall(r"\w+", (prompt or "").lower()) if len(w) > 3]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]

    if keywords and sentences:
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in keywords):
                return sentence

    if sentences:
        return sentences[0]

    return normalized[:220] + ("..." if len(normalized) > 220 else "")


def _extract_query_keywords(prompt: str) -> List[str]:
    """Extract meaningful query keywords for source relevance checks."""
    words = [w.lower() for w in re.findall(r"\w+", (prompt or ""), flags=re.UNICODE)]
    keywords = [w for w in words if len(w) > 2 and w not in _QUERY_STOP_WORDS]
    # Keep order, remove duplicates
    seen = set()
    deduped = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            deduped.append(kw)
    return deduped


def _is_person_definition_query(prompt: str) -> bool:
    """Detect simple "who is X" style questions to apply stricter source filtering."""
    text = (prompt or "").strip().lower()
    return bool(re.search(r"\b(wer\s+ist|who\s+is|wer\s+war|who\s+was)\b", text))


def _is_meaningful_source(query_keywords: List[str], content: str, matched_sentence: str, score) -> bool:
    """Return True if a source is likely relevant to the user's query."""
    if not query_keywords:
        if isinstance(score, (int, float)) and abs(float(score) - 0.5) > 1e-9:
            return float(score) >= 0.25
        return bool((matched_sentence or content).strip())

    sentence_haystack = (matched_sentence or "").lower()
    content_haystack = (content or "").lower()
    sentence_overlap = sum(1 for kw in query_keywords if kw in sentence_haystack)
    content_overlap = sum(1 for kw in query_keywords if kw in content_haystack)

    has_real_score = isinstance(score, (int, float)) and abs(float(score) - 0.5) > 1e-9
    score_ok = float(score) >= 0.18 if has_real_score else True

    if len(query_keywords) == 1:
        # Single-keyword matches are often noisy in large personal knowledge bases.
        return score_ok and sentence_overlap >= 1

    if len(query_keywords) == 2:
        # Require both terms in the same matched sentence to avoid unrelated source cards.
        return score_ok and sentence_overlap >= 2

    # For longer queries, require stronger lexical overlap before showing a source card.
    if len(query_keywords) >= 3:
        return score_ok and sentence_overlap >= 2 and content_overlap >= 2

    return score_ok and sentence_overlap >= 1


def _guess_document_name(source_name: str, path: str) -> str:
    """Return a stable, readable document name for source cards."""
    name = (source_name or "").strip()
    if name and name.lower() != 'unknown':
        return name

    if path:
        normalized_path = path.rstrip('/')
        if normalized_path:
            return normalized_path.split('/')[-1] or normalized_path

    return 'Knowledge Base'


def gather_photo_context(client, prompt: str, username: str, build_thumbnail_url_func) -> Optional[Dict]:
    """Gather photo context from Immich"""
    try:
        if not client:
            return None

        result = client.search_photos_intelligent(prompt, limit=6)
        if not result.get('success') or not result.get('results'):
            return None

        photos = result['results']
        ui_photos = []
        photo_lines = []

        photo_lines.append("### 📸 Gefundene Fotos")
        photo_lines.append("")
        photo_lines.append("WICHTIG: Bette die Fotos direkt in deine Antwort ein mit Markdown-Bildern: ![Beschreibung](URL)")
        photo_lines.append("")

        for i, photo in enumerate(photos[:3], 1):
            name = photo['original_file_name']
            date_val = photo.get('created_at', 'Unknown')
            people = photo.get('people', [])
            location = photo.get('location', '')
            objects = photo.get('objects', [])
            tags = photo.get('tags', [])
            photo_id = photo.get('id', 'N/A')
            asset_url = photo['asset_url']
            thumbnail_url = build_thumbnail_url_func(photo_id, username, 'preview') if photo_id != 'N/A' else photo.get('thumbnail_url', '')

            photo_for_ui = dict(photo)
            if thumbnail_url:
                photo_for_ui['thumbnail_url'] = thumbnail_url
            ui_photos.append(photo_for_ui)

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
                'photos': ui_photos
            }
        }
    except Exception as e:
        logger.error(f"Photo search error: {e}")
        return None


def gather_file_context(knowledge_base, training_manager, prompt: str) -> Optional[List[Dict]]:
    """Gather file context from knowledge base with enhanced training manager context"""
    try:
        file_results = knowledge_base.search_knowledge(prompt, k=80)
        if not file_results:
            return None

        query_keywords = _extract_query_keywords(prompt)
        meaningful_results = []

        source_cards = []
        is_person_query = _is_person_definition_query(prompt)
        max_source_cards = 3 if is_person_query else 8
        for result in file_results:
            content = result.get('content', '')
            doc_name = _guess_document_name(result.get('source', ''), result.get('path', ''))
            matched_sentence = _extract_matching_sentence(prompt, content)
            score = result.get('similarity_score')
            # 0.5 is currently a neutral placeholder in this backend; hide it in UI cards.
            if isinstance(score, (int, float)) and abs(float(score) - 0.5) < 1e-9:
                score = None

            if not _is_meaningful_source(query_keywords, content, matched_sentence, score):
                continue

            if is_person_query and len(query_keywords) >= 2:
                sentence_lower = (matched_sentence or "").lower()
                full_name = " ".join(query_keywords[:2])
                if full_name not in sentence_lower:
                    continue

            meaningful_results.append(result)

            source_cards.append({
                'source': doc_name,
                'source_type': 'chunk',
                'document': doc_name,
                'path': result.get('path', ''),
                'chunk_id': result.get('chunk_id'),
                'matched_sentence': matched_sentence,
                'content_preview': (content[:260] + '...') if len(content) > 260 else content,
                'similarity_score': score,
                'search_type': result.get('search_type', 'fulltext')
            })

            if len(source_cards) >= max_source_cards:
                break

        if not meaningful_results:
            return None

        # Use training manager to create enhanced context with metadata
        enhanced_context_text = training_manager.create_enhanced_context_for_ai(prompt, meaningful_results)

        return [{
            'content': enhanced_context_text,
            'source': 'Nextcloud Dateien & Wissensbasis',
            'path': 'knowledge_base',
            'similarity_score': 1.0,
            'metadata': {
                'count': len(meaningful_results),
                'enhanced': True,
                'source_cards': source_cards
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


def gather_nextcloud_search_context(search_client, prompt: str, extract_search_terms_func) -> Optional[Dict]:
    """Gather context from Nextcloud unified search API

    This function proactively searches across all Nextcloud providers (files, contacts, calendar, tasks)
    to find relevant information for the user's query.
    """
    if not search_client:
        return None

    try:
        # Extract meaningful search terms from the prompt
        search_terms = extract_search_terms_func(prompt)
        if not search_terms:
            logger.info("No search terms extracted for Nextcloud search")
            return None

        logger.info(f"Searching Nextcloud with terms: {search_terms}")

        # Perform unified search across all providers
        search_results = search_client.search(search_terms, limit=15)

        if not search_results or not search_results.get('results'):
            logger.info("No results from Nextcloud search")
            return None

        results = search_results['results']
        logger.info(f"Found {len(results)} results from Nextcloud unified search")

        # Group results by provider
        grouped = {}
        for result in results:
            provider = result.get('provider', 'unknown')
            if provider not in grouped:
                grouped[provider] = []
            grouped[provider].append(result)

        # Format results for AI consumption
        search_lines = []
        search_lines.append("### 🔍 Nextcloud Unified Search Results")
        search_lines.append("")
        search_lines.append(f"Search query: **{search_terms}**")
        search_lines.append("")

        for provider, items in grouped.items():
            provider_name = {
                'files': '📁 Dateien',
                'contacts': '👤 Kontakte',
                'calendar': '📅 Kalender',
                'tasks': '✅ Aufgaben',
                'talk': '💬 Talk',
                'deck': '📋 Deck'
            }.get(provider, f'📌 {provider.capitalize()}')

            search_lines.append(f"**{provider_name}** ({len(items)} results):")
            search_lines.append("")

            for i, item in enumerate(items[:5], 1):  # Limit to 5 per provider
                title = item.get('title', 'Untitled')
                subline = item.get('subline', '')
                url = item.get('resource_url', '')

                search_lines.append(f"{i}. **{title}**")
                if subline:
                    search_lines.append(f"   {subline}")
                if url:
                    search_lines.append(f"   URL: {url}")
                search_lines.append("")

        return {
            'content': '\n'.join(search_lines),
            'source': 'Nextcloud Unified Search',
            'path': 'nextcloud_search',
            'similarity_score': 0.9,
            'metadata': {
                'count': len(results),
                'providers': list(grouped.keys()),
                'search_terms': search_terms,
                'results': results
            }
        }
    except Exception as e:
        logger.error(f"Nextcloud search error: {e}")
        return None


def combine_contexts(weather_ctx, security_ctx, activity_ctx, photo_ctx,
                    file_ctx, calendar_ctx, todo_ctx, nextcloud_search_ctx=None) -> List[Dict]:
    """Combine all contexts in the correct order.

    All ctx parameters are single context dicts (or None), except file_ctx
    which is a list of context dicts (or None) as returned by gather_file_context().
    """
    combined = []

    # Priority order: weather, security, activity, Nextcloud search, photos, files, calendar, todos
    if weather_ctx:
        combined.append(weather_ctx)
    if security_ctx:
        combined.append(security_ctx)
    if activity_ctx:
        combined.append(activity_ctx)
    if nextcloud_search_ctx:
        combined.append(nextcloud_search_ctx)
    if photo_ctx:
        combined.append(photo_ctx)
    if file_ctx:
        combined.extend(file_ctx)
    if calendar_ctx:
        combined.append(calendar_ctx)
    if todo_ctx:
        combined.append(todo_ctx)

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

**Nextcloud Unified Search:**
- Wenn Nextcloud-Suchergebnisse verfügbar sind, nutze sie für umfassende Antworten
- Die Suche deckt Dateien, Kontakte, Kalender, Aufgaben und mehr ab
- Verweise auf gefundene Ressourcen mit ihren Titeln und URLs

**Autonomous Research Results:**
- Das System hat automatisch mehrere Datenquellen durchsucht
- Nutze die Ergebnisse der autonomen Recherche für eine umfassende Antwort
- Die automatisch gesammelten Informationen aus verschiedenen Quellen ergänzen deine Wissensbasis
- Kombiniere alle verfügbaren Informationen zu einer kohärenten Antwort

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

**WICHTIG FÜR FEHLENDE TREFFER:**
- Wenn die bereitgestellten Daten die Frage NICHT beantworten, darfst du mit deinem allgemeinen Modellwissen antworten.
- Kennzeichne das dann kurz transparent, z.B. "Nach meinem allgemeinen Wissen ...".
- Erfinde keine persönlichen Fakten über den Nutzer oder nicht belegte konkrete Details.

Falls Informationen fehlen oder unvollständig sind, sage dies ehrlich.
Erfinde keine persönlichen oder kontextspezifischen Informationen, die nicht belegt sind."""
