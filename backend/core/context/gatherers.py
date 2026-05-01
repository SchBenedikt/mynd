"""
Context gathering for AI agent queries
Handles gathering context from photos, files, calendar, tasks, weather, security, activities, and Nextcloud Search
"""
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Characters of email body included in AI context per email
_EMAIL_CONTEXT_BODY_LENGTH = 600
# Characters of body in email source card preview
_SOURCE_CARD_PREVIEW_LENGTH = 260


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


def _normalize_email_prompt(prompt: str) -> str:
    """Normalize a free-form email question for intent matching."""
    return ' '.join((prompt or '').split()).strip().lower()


def _build_email_query_profile(prompt: str) -> Dict[str, Any]:
    """Map a natural-language email question to a structured retrieval profile."""
    text = _normalize_email_prompt(prompt)
    today = date.today()
    yesterday = today - timedelta(days=1)
    current_week_start = today - timedelta(days=today.weekday())
    last_week_start = current_week_start - timedelta(days=7)
    last_week_end = current_week_start - timedelta(days=1)

    def has_any(phrases: List[str]) -> bool:
        return any(phrase in text for phrase in phrases)

    email_terms_present = has_any([
        'e-mail', 'email', 'mails', 'mail', 'posteingang', 'inbox', 'nachrichten'
    ])

    last_sent = (
        has_any([
            'letzte e-mail', 'letzte mail', 'letzte nachricht', 'zuletzt gesendete',
            'letzte gesendete', 'letzte von mir gesendete', 'letzte geschriebene',
            'letzte verfasste'
        ]) and has_any([
            'geschrieben', 'gesendet', 'geschickt', 'verschickt', 'verfasst',
            'mail geschrieben', 'e-mail geschrieben'
        ])
    )

    today_received = (
        has_any([
            'e-mails von heute', 'emails von heute', 'mails von heute', 'heutige e-mails',
            'heutige mails', 'was ist heute angekommen', 'was kam heute rein',
            'was ist heute reingekommen', 'heute angekommen', 'heute erhalten'
        ]) or (
            'heute' in text and has_any([
                'angekommen', 'angekommenen', 'erhalten', 'eingegangen', 'eingetroffen',
                'bekommen', 'neu angekommen', 'eingelaufen'
            ])
        ) or (
            # Catch natural formulations like: "welche e-mails habe ich von heute?"
            email_terms_present and 'heute' in text and has_any([
                'welche', 'welcher', 'welches', 'habe ich', 'gibt es', 'zeige', 'list', 'liste'
            ])
        ) or (
            email_terms_present and 'von heute' in text
        )
    )

    today_content = (
        has_any([
            'inhalt der e-mails von heute', 'inhalt der emails von heute',
            'was war der inhalt der e-mails von heute', 'was war der inhalt der emails von heute',
            'fasse die e-mails von heute zusammen', 'fasse die emails von heute zusammen',
            'zusammenfassung der e-mails von heute', 'zusammenfassung der emails von heute'
        ]) or (
            'heute' in text and has_any(['inhalt', 'zusammenfasse', 'zusammenfassung', 'fasse zusammen'])
        )
    )

    yesterday_or_recent = (
        email_terms_present and (
            'gestern' in text or 'yesterday' in text
        )
    )

    yesterday_and_today = (
        yesterday_or_recent and (
            'heute' in text or 'today' in text or 'und heute' in text or 'and today' in text
        )
    )

    unread_last_week = (
        has_any(['ungelesene e-mails von letzter woche', 'ungelesene emails von letzter woche', 'ungelesene mails von letzter woche'])
        or ('ungelesen' in text and ('letzte woche' in text or 'letzter woche' in text or 'letzten woche' in text))
        or ('unread' in text and 'last week' in text)
    )

    if last_sent:
        return {
            'mode': 'last_sent',
            'folder_focus': 'sent',
            'since': None,
            'until': None,
            'unread': None,
            'limit': 1,
            'summary_mode': 'single',
            'label': 'letzte gesendete E-Mail'
        }

    if today_content:
        return {
            'mode': 'today_content',
            'folder_focus': 'inbox',
            'since': today,
            'until': today,
            'unread': None,
            'limit': 20,
            'summary_mode': 'summary',
            'label': 'E-Mails von heute mit Inhalt'
        }

    if today_received:
        return {
            'mode': 'today_received',
            'folder_focus': 'inbox',
            'since': today,
            'until': today,
            'unread': None,
            'limit': 20,
            'summary_mode': 'list',
            'label': 'heute erhaltene E-Mails'
        }

    if yesterday_and_today:
        return {
            'mode': 'yesterday_and_today',
            'folder_focus': 'inbox',
            'since': yesterday,
            'until': today,
            'unread': None,
            'limit': 30,
            'summary_mode': 'list',
            'label': 'E-Mails von gestern und heute'
        }

    if yesterday_or_recent:
        return {
            'mode': 'yesterday_received',
            'folder_focus': 'inbox',
            'since': yesterday,
            'until': yesterday,
            'unread': None,
            'limit': 20,
            'summary_mode': 'list',
            'label': 'E-Mails von gestern'
        }

    if unread_last_week:
        return {
            'mode': 'unread_last_week',
            'folder_focus': 'inbox',
            'since': last_week_start,
            'until': last_week_end,
            'unread': True,
            'limit': 20,
            'summary_mode': 'summary',
            'label': 'ungelesene E-Mails von letzter Woche'
        }

    return {
        'mode': 'general',
        'folder_focus': 'all',
        'since': None,
        'until': None,
        'unread': None,
        'limit': 10,
        'summary_mode': 'list',
        'label': 'allgemeine E-Mail-Suche'
    }


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


def gather_email_context(email_client, prompt: str, limit: int = 10) -> Optional[Dict]:
    """Gather email context from an IMAP email account.

    Returns a context dict whose *content* field contains a formatted summary of
    recent or query-relevant emails ready for injection into the AI system message.
    Source cards are stored in metadata['source_cards'] so they can be displayed
    to the user as clickable sources.
    """
    try:
        if not email_client:
            return None

        profile = _build_email_query_profile(prompt)

        if profile.get('mode') == 'general':
            # Use search when the prompt contains meaningful keywords; fall back to
            # a general recent-email summary otherwise.
            emails = email_client.search_emails(prompt, limit=limit)

            # Fallback: if a "today + email" query slipped into general mode,
            # force an inbox date filter so today's messages are still returned.
            prompt_norm = _normalize_email_prompt(prompt)
            if not emails and ('heute' in prompt_norm or 'today' in prompt_norm) and any(
                token in prompt_norm for token in ['mail', 'e-mail', 'email', 'posteingang', 'inbox']
            ):
                today = date.today()
                emails = email_client.fetch_emails(
                    limit=max(limit, 20),
                    folder_focus='inbox',
                    since=today,
                    until=today,
                    unread=None,
                )
        else:
            emails = email_client.fetch_emails(
                limit=profile.get('limit', limit),
                folder_focus=profile.get('folder_focus', 'all'),
                since=profile.get('since'),
                until=profile.get('until'),
                unread=profile.get('unread'),
            )

        if not emails:
            return None

        lines: List[str] = []
        lines.append("=== E-MAILS ===")
        lines.append("")
        lines.append(f"Abfrage: {profile.get('label', 'E-Mails')}")
        if profile.get('since') and profile.get('until') and profile.get('since') == profile.get('until'):
            lines.append(f"Zeitraum: {profile['since'].strftime('%Y-%m-%d')}")
        elif profile.get('since') and profile.get('until'):
            lines.append(f"Zeitraum: {profile['since'].strftime('%Y-%m-%d')} bis {profile['until'].strftime('%Y-%m-%d')}")
        if profile.get('folder_focus') and profile.get('folder_focus') != 'all':
            lines.append(f"Ordnerfokus: {profile['folder_focus']}")
        if profile.get('unread') is True:
            lines.append("Filter: nur ungelesene E-Mails")
        if profile.get('mode') == 'last_sent':
            lines.append("Aufgabe: Nenne die letzte gesendete E-Mail möglichst konkret und knapp.")
        elif profile.get('mode') == 'today_received':
            lines.append("Aufgabe: Liste die heute eingegangenen E-Mails kurz auf.")
        elif profile.get('mode') == 'today_content':
            lines.append("Aufgabe: Fasse die Inhalte der heutigen E-Mails zusammen.")
        elif profile.get('mode') == 'yesterday_received':
            lines.append("Aufgabe: Liste die gestern eingegangenen E-Mails kurz auf.")
        elif profile.get('mode') == 'yesterday_and_today':
            lines.append("Aufgabe: Liste die E-Mails von gestern und heute kurz auf.")
        elif profile.get('mode') == 'unread_last_week':
            lines.append("Aufgabe: Fasse die ungelesenen E-Mails von letzter Woche zusammen.")
        lines.append("")
        lines.append(f"Gefundene E-Mails ({len(emails)}):")
        lines.append("")

        source_cards = []
        for i, mail in enumerate(emails, 1):
            subject = mail.get('subject', '(kein Betreff)')
            sender = mail.get('sender', '')
            date_str = mail.get('date', '')
            folder = mail.get('folder', 'INBOX')
            body = mail.get('body', '')

            # Truncate body for context to keep prompt manageable
            body_for_context = body[:_EMAIL_CONTEXT_BODY_LENGTH].strip()
            if len(body) > _EMAIL_CONTEXT_BODY_LENGTH:
                body_for_context += '...'

            lines.append(f"**E-Mail {i}:** {subject}")
            if sender:
                lines.append(f"- Von: {sender}")
            if date_str:
                lines.append(f"- Datum: {date_str}")
            lines.append(f"- Ordner: {folder}")
            if body_for_context:
                lines.append(f"- Inhalt: {body_for_context}")
            lines.append("")

            # Build a source card for the UI
            matched_sentence = _extract_matching_sentence(prompt, body or subject)
            preview_length = _SOURCE_CARD_PREVIEW_LENGTH if profile.get('mode') == 'general' else _EMAIL_CONTEXT_BODY_LENGTH
            body_preview = (body[:preview_length] + '...') if len(body) > preview_length else body
            source_cards.append({
                'source': sender or 'E-Mail',
                'source_type': 'email',
                'document': subject,
                'path': f'email://{folder}',
                'chunk_id': mail.get('uid'),
                'matched_sentence': matched_sentence,
                'content_preview': body_preview or subject,
                'similarity_score': None,
            })

        return {
            'content': '\n'.join(lines),
            'source': 'E-Mails',
            'path': 'email',
            'similarity_score': 1.0,
            'metadata': {
                'count': len(emails),
                'source_cards': source_cards,
            }
        }
    except Exception as e:
        logger.error("Email context error: %s", e)
        return None


def combine_contexts(weather_ctx, security_ctx, activity_ctx, photo_ctx,
                    file_ctx, calendar_ctx, todo_ctx, nextcloud_search_ctx=None,
                    email_ctx=None) -> List[Dict]:
    """Combine all contexts in the correct order.

    All ctx parameters are single context dicts (or None), except file_ctx
    which is a list of context dicts (or None) as returned by gather_file_context().
    """
    combined = []

    # Priority order: weather, security, activity, Nextcloud search, photos, files, calendar, todos, emails
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
    if email_ctx:
        combined.append(email_ctx)

    return combined


def build_system_message(combined_context: List[Dict], language: str = 'de') -> str:
    """Build a deep-reasoning, synthesis-focused system message for the AI."""
    from datetime import date as _date
    today_str = _date.today().strftime('%d.%m.%Y')
    lang_label = 'auf Deutsch' if str(language).lower().startswith('de') else 'in the language of the question'

    # Core identity and reasoning instructions — always present
    base = f"""You are mynd — a highly capable, deeply analytical personal AI assistant. Today is {today_str}.

Your mission: give the user the most insightful, complete answer possible by reasoning across ALL available sources.

Reasoning process for every query:
1. UNDERSTAND INTENT — what does the user truly want? Look beyond the literal wording.
2. SURVEY ALL CONTEXT — scan every section below, including indirect mentions.
3. CONNECT THE DOTS — a name in one source may link to an event or message in another; piece the full picture together.
4. SYNTHESIZE — draw conclusions and explain relationships; don't just list raw facts.
5. BE HONEST — if something is not in the data, say so clearly; never invent personal details.

Answer {lang_label}. Use markdown (headers, lists, bold) for complex answers; keep simple answers short."""

    if not combined_context:
        return base + "\n\nNo personal context is available for this query. Answer from your general knowledge and label it transparently (e.g. \"Nach meinem allgemeinen Wissen …\")."

    context_parts = []
    for ctx in combined_context:
        source_name = ctx.get('source', 'Unknown')
        content = ctx.get('content', '')
        if content:
            context_parts.append(f"--- {source_name} ---\n{content}")

    context_text = '\n\n'.join(context_parts)

    return f"""{base}

=== PERSONAL CONTEXT (primary source of truth) ===

{context_text}

=== END OF CONTEXT ===

How to use the context above:
- **Knowledge base / files**: extract facts, names, dates and relationships; cite the source when you reference specific data (e.g. "laut deiner Wissensdatenbank", "in your notes").
- **Calendar / tasks**: reference specific events and deadlines by name and date; for scheduling questions show free/busy slots.
- **Autonomous research results**: the system already searched multiple data sources automatically — use those findings as additional evidence and combine them with the rest.
- **Photos**: embed inline with `![description](url)` using the thumbnail URL; describe people, place and date from the metadata.
- **Emails**: reference subject and sender; never expose full email addresses unnecessarily.
- **Nextcloud search**: use found file/contact/event titles and URLs to strengthen your answer.

General rules:
- The personal context above takes priority over your general training knowledge.
- For questions the context does not answer, use your general knowledge and prefix with "Nach meinem allgemeinen Wissen …" / "Based on my general knowledge …".
- If the context contains scattered or partial information, assemble it into a coherent answer rather than dumping raw excerpts.
- Never repeat the same information twice.
- Be precise and direct — avoid filler phrases and unnecessary repetition."""
