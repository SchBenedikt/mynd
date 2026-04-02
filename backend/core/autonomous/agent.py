"""
Autonomous Agent Framework
Enables the AI to plan and execute multi-step actions independently
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the autonomous agent can perform"""
    SEARCH_FILES = "search_files"
    READ_FILE = "read_file"
    SEARCH_CONTACTS = "search_contacts"
    SEARCH_CALENDAR = "search_calendar"
    SEARCH_TASKS = "search_tasks"
    SEARCH_PHOTOS = "search_photos"
    SEARCH_KNOWLEDGE_BASE = "search_knowledge_base"
    SEARCH_EMAILS = "search_emails"


@dataclass
class Action:
    """Represents a single action to be executed"""
    action_type: ActionType
    description: str
    parameters: Dict[str, Any]
    priority: int = 5  # 1-10, higher = more important
    dependencies: List[str] = None  # Action IDs that must complete first

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class ActionResult:
    """Result of an executed action"""
    action_type: ActionType
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time: float = 0.0


class AutonomousAgent:
    """
    Autonomous agent that can plan and execute multi-step research and actions
    """

    def __init__(self, nextcloud_client, search_client, knowledge_base,
                 immich_client, training_manager, email_client=None):
        """
        Initialize autonomous agent with access to various services

        Args:
            nextcloud_client: NextcloudClient instance
            search_client: NextcloudSearchClient instance
            knowledge_base: KnowledgeBase instance for indexed content
            immich_client: ImmichClient instance for photos
            training_manager: TrainingManager instance
            email_client: EmailClient instance (optional)
        """
        self.nextcloud = nextcloud_client
        self.search = search_client
        self.knowledge = knowledge_base
        self.immich = immich_client
        self.training = training_manager
        self.email = email_client
        self.action_results = []

    def analyze_query_and_plan_actions(self, query: str, context: Dict) -> List[Action]:
        """
        Analyze user query and plan autonomous actions to gather comprehensive information

        Args:
            query: User's query
            context: Current context information

        Returns:
            List of planned actions to execute
        """
        actions = []
        query_lower = query.lower()

        logger.info(f"Planning autonomous actions for query: {query}")

        # Extract key entities and topics from query
        keywords = self._extract_keywords(query)
        logger.info(f"Extracted keywords: {keywords}")

        # Plan actions based on query analysis
        # 1. Always search knowledge base for indexed content
        actions.append(Action(
            action_type=ActionType.SEARCH_KNOWLEDGE_BASE,
            description=f"Search indexed documents for: {', '.join(keywords[:3])}",
            parameters={'query': query, 'keywords': keywords, 'limit': 15},
            priority=9
        ))

        # 2. Proactively search Nextcloud for files
        if keywords:
            search_term = ' '.join(keywords[:3])  # Use top 3 keywords
            actions.append(Action(
                action_type=ActionType.SEARCH_FILES,
                description=f"Search Nextcloud files for: {search_term}",
                parameters={'query': search_term, 'limit': 10},
                priority=8
            ))

        # 3. Search for related contacts if query mentions people or names
        person_indicators = ['wer', 'kontakt', 'person', 'email', 'telefon', 'adresse',
                            'who', 'contact', 'phone', 'address']
        if any(ind in query_lower for ind in person_indicators):
            actions.append(Action(
                action_type=ActionType.SEARCH_CONTACTS,
                description="Search contacts for relevant people",
                parameters={'query': ' '.join(keywords[:2]), 'limit': 5},
                priority=7
            ))

        # 4. Search calendar if query has temporal aspects
        time_indicators = ['wann', 'termin', 'meeting', 'datum', 'when', 'schedule',
                          'appointment', 'event', 'kalendar', 'calendar']
        if any(ind in query_lower for ind in time_indicators):
            actions.append(Action(
                action_type=ActionType.SEARCH_CALENDAR,
                description="Search calendar events",
                parameters={'query': ' '.join(keywords[:2]), 'limit': 8},
                priority=7
            ))

        # 5. Search tasks/todos if query mentions tasks
        task_indicators = ['aufgabe', 'todo', 'task', 'erledigen', 'machen',
                          'do', 'complete', 'finish']
        if any(ind in query_lower for ind in task_indicators):
            actions.append(Action(
                action_type=ActionType.SEARCH_TASKS,
                description="Search tasks and todos",
                parameters={'query': ' '.join(keywords[:2]), 'limit': 8},
                priority=7
            ))

        # 6. Search photos if visual content mentioned
        # BUT: Skip if person+date query (already handled efficiently by main search)
        photo_indicators = ['foto', 'bild', 'photo', 'picture', 'image', 'zeig']
        has_photo_keyword = any(ind in query_lower for ind in photo_indicators)
        
        # Detect if this is a simple person+date photo query (handled by main flow)
        person_keywords = ['vinzenz', 'schächner', 'benedikt', 'person', 'wer']
        date_keywords = ['letzter', 'woche', 'gestern', 'heute', 'morgen', 'wann', 'datum',
                        'last', 'week', 'yesterday', 'today', 'tomorrow', 'when']
        has_person = any(p in query_lower for p in person_keywords)
        has_date = any(d in query_lower for d in date_keywords)
        
        # Only search photos if it's NOT a simple person+date query (main flow handles that)
        if has_photo_keyword and not (has_person and has_date):
            actions.append(Action(
                action_type=ActionType.SEARCH_PHOTOS,
                description="Search photos",
                parameters={'query': query, 'limit': 6},
                priority=8
            ))

        # 7. Search emails if query mentions email
        email_indicators = ['email', 'e-mail', 'mail', 'mails', 'emails', 'nachricht',
                            'posteingang', 'inbox', 'absender', 'betreff', 'message', 'messages']
        if any(ind in query_lower for ind in email_indicators) and self.email:
            actions.append(Action(
                action_type=ActionType.SEARCH_EMAILS,
                description="Search emails",
                parameters={'query': query, 'limit': 8},
                priority=7
            ))

        # Sort by priority (higher first)
        actions.sort(key=lambda a: a.priority, reverse=True)

        logger.info(f"Planned {len(actions)} autonomous actions")
        return actions

    def execute_actions(self, actions: List[Action], username: str) -> Dict[str, Any]:
        """
        Execute planned actions in parallel and gather results.

        Args:
            actions: List of actions to execute
            username: Username for context

        Returns:
            Dictionary with combined results from all actions
        """
        results = {
            'success': True,
            'actions_executed': [],
            'gathered_information': [],
            'errors': []
        }

        # Execute actions in parallel using a thread pool (all calls are I/O-bound)
        per_action_timeout = 15  # seconds per action
        # Total wall-clock limit: actions run in parallel, so use a modest multiplier
        total_timeout = per_action_timeout * 2

        def _run(action: Action):
            return action, self._execute_single_action(action, username)

        with ThreadPoolExecutor(max_workers=min(len(actions), 8)) as executor:
            future_to_action = {executor.submit(_run, action): action for action in actions}
            for future in as_completed(future_to_action, timeout=total_timeout):
                try:
                    action, result = future.result(timeout=per_action_timeout)
                    if result.success:
                        results['actions_executed'].append({
                            'type': action.action_type.value,
                            'description': action.description,
                            'success': True,
                            'execution_time': result.execution_time
                        })
                        if result.data:
                            results['gathered_information'].append({
                                'source': action.action_type.value,
                                'data': result.data
                            })
                    else:
                        logger.warning(f"Action failed: {action.description} - {result.error}")
                        results['errors'].append({
                            'action': action.description,
                            'error': result.error
                        })
                except FuturesTimeoutError:
                    action = future_to_action[future]
                    logger.warning(f"Action timed out: {action.description}")
                    results['errors'].append({
                        'action': action.description,
                        'error': 'Action timed out'
                    })
                except Exception as e:
                    action = future_to_action[future]
                    logger.error(f"Error executing action {action.description}: {e}", exc_info=True)
                    results['errors'].append({
                        'action': action.description,
                        'error': str(e)
                    })

        results['success'] = len(results['actions_executed']) > 0
        logger.info(f"Executed {len(results['actions_executed'])} actions successfully, "
                   f"{len(results['errors'])} errors")

        return results

    def _execute_single_action(self, action: Action, username: str) -> ActionResult:
        """Execute a single action and return result"""
        start_time = time.time()

        try:
            if action.action_type == ActionType.SEARCH_KNOWLEDGE_BASE:
                result = self._search_knowledge_base(action.parameters)

            elif action.action_type == ActionType.SEARCH_FILES:
                result = self._search_files(action.parameters)

            elif action.action_type == ActionType.SEARCH_CONTACTS:
                result = self._search_contacts(action.parameters)

            elif action.action_type == ActionType.SEARCH_CALENDAR:
                result = self._search_calendar(action.parameters)

            elif action.action_type == ActionType.SEARCH_TASKS:
                result = self._search_tasks(action.parameters)

            elif action.action_type == ActionType.SEARCH_PHOTOS:
                result = self._search_photos(action.parameters, username)

            elif action.action_type == ActionType.SEARCH_EMAILS:
                result = self._search_emails(action.parameters)

            elif action.action_type == ActionType.READ_FILE:
                result = self._read_file(action.parameters)

            else:
                return ActionResult(
                    action_type=action.action_type,
                    success=False,
                    data=None,
                    error=f"Unknown action type: {action.action_type}",
                    execution_time=time.time() - start_time
                )

            result.execution_time = time.time() - start_time
            return result

        except Exception as e:
            logger.error(f"Action execution error: {e}", exc_info=True)
            return ActionResult(
                action_type=action.action_type,
                success=False,
                data=None,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def _search_knowledge_base(self, params: Dict) -> ActionResult:
        """Search the indexed knowledge base"""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 15)

            if not self.knowledge:
                return ActionResult(
                    action_type=ActionType.SEARCH_KNOWLEDGE_BASE,
                    success=False,
                    data=None,
                    error="Knowledge base not available"
                )

            results = self.knowledge.search_knowledge(query, k=limit)

            if results:
                # Format results for AI consumption
                formatted = {
                    'count': len(results),
                    'chunks': []
                }

                for result in results:
                    formatted['chunks'].append({
                        'content': result.get('content', ''),
                        'source': result.get('source', ''),
                        'path': result.get('path', ''),
                        'score': result.get('similarity_score', 0.0)
                    })

                return ActionResult(
                    action_type=ActionType.SEARCH_KNOWLEDGE_BASE,
                    success=True,
                    data=formatted
                )
            else:
                return ActionResult(
                    action_type=ActionType.SEARCH_KNOWLEDGE_BASE,
                    success=True,
                    data={'count': 0, 'chunks': []}
                )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.SEARCH_KNOWLEDGE_BASE,
                success=False,
                data=None,
                error=str(e)
            )

    def _search_files(self, params: Dict) -> ActionResult:
        """Search Nextcloud files"""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 10)

            if not self.search:
                return ActionResult(
                    action_type=ActionType.SEARCH_FILES,
                    success=False,
                    data=None,
                    error="Search client not available"
                )

            results = self.search.search_files(query, limit=limit)

            return ActionResult(
                action_type=ActionType.SEARCH_FILES,
                success=True,
                data={'count': len(results), 'files': results}
            )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.SEARCH_FILES,
                success=False,
                data=None,
                error=str(e)
            )

    def _search_contacts(self, params: Dict) -> ActionResult:
        """Search contacts"""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 5)

            if not self.search:
                return ActionResult(
                    action_type=ActionType.SEARCH_CONTACTS,
                    success=False,
                    data=None,
                    error="Search client not available"
                )

            results = self.search.search_contacts(query, limit=limit)

            return ActionResult(
                action_type=ActionType.SEARCH_CONTACTS,
                success=True,
                data={'count': len(results), 'contacts': results}
            )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.SEARCH_CONTACTS,
                success=False,
                data=None,
                error=str(e)
            )

    def _search_calendar(self, params: Dict) -> ActionResult:
        """Search calendar events"""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 8)

            if not self.search:
                return ActionResult(
                    action_type=ActionType.SEARCH_CALENDAR,
                    success=False,
                    data=None,
                    error="Search client not available"
                )

            results = self.search.search_calendar(query, limit=limit)

            return ActionResult(
                action_type=ActionType.SEARCH_CALENDAR,
                success=True,
                data={'count': len(results), 'events': results}
            )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.SEARCH_CALENDAR,
                success=False,
                data=None,
                error=str(e)
            )

    def _search_tasks(self, params: Dict) -> ActionResult:
        """Search tasks"""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 8)

            if not self.search:
                return ActionResult(
                    action_type=ActionType.SEARCH_TASKS,
                    success=False,
                    data=None,
                    error="Search client not available"
                )

            results = self.search.search_tasks(query, limit=limit)

            return ActionResult(
                action_type=ActionType.SEARCH_TASKS,
                success=True,
                data={'count': len(results), 'tasks': results}
            )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.SEARCH_TASKS,
                success=False,
                data=None,
                error=str(e)
            )

    def _search_photos(self, params: Dict, username: str) -> ActionResult:
        """Search photos"""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 6)

            if not self.immich:
                return ActionResult(
                    action_type=ActionType.SEARCH_PHOTOS,
                    success=False,
                    data=None,
                    error="Immich client not available"
                )

            result = self.immich.search_photos_intelligent(query, limit=limit)

            if result.get('success') and result.get('results'):
                return ActionResult(
                    action_type=ActionType.SEARCH_PHOTOS,
                    success=True,
                    data={'count': len(result['results']), 'photos': result['results']}
                )
            else:
                return ActionResult(
                    action_type=ActionType.SEARCH_PHOTOS,
                    success=True,
                    data={'count': 0, 'photos': []}
                )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.SEARCH_PHOTOS,
                success=False,
                data=None,
                error=str(e)
            )

    def _search_emails(self, params: Dict) -> ActionResult:
        """Search emails using the configured email client."""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 8)

            if not self.email:
                return ActionResult(
                    action_type=ActionType.SEARCH_EMAILS,
                    success=False,
                    data=None,
                    error="Email client not available"
                )

            results = self.email.search_emails(query, limit=limit)
            summaries = []
            for mail in results:
                body = mail.get('body', '')
                summaries.append({
                    'subject': mail.get('subject', ''),
                    'sender': mail.get('sender', ''),
                    'date': mail.get('date', ''),
                    'folder': mail.get('folder', ''),
                    'body_preview': (body[:200] + '...') if len(body) > 200 else body
                })

            return ActionResult(
                action_type=ActionType.SEARCH_EMAILS,
                success=True,
                data={'count': len(summaries), 'emails': summaries}
            )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.SEARCH_EMAILS,
                success=False,
                data=None,
                error=str(e)
            )

    def _read_file(self, params: Dict) -> ActionResult:
        """Read a specific file from Nextcloud"""
        try:
            file_path = params.get('path', '')

            if not self.nextcloud:
                return ActionResult(
                    action_type=ActionType.READ_FILE,
                    success=False,
                    data=None,
                    error="Nextcloud client not available"
                )

            content = self.nextcloud.parse_remote_file(file_path)

            if content:
                return ActionResult(
                    action_type=ActionType.READ_FILE,
                    success=True,
                    data={'path': file_path, 'content': content[:5000]}  # Limit size
                )
            else:
                return ActionResult(
                    action_type=ActionType.READ_FILE,
                    success=False,
                    data=None,
                    error="File not found or empty"
                )

        except Exception as e:
            return ActionResult(
                action_type=ActionType.READ_FILE,
                success=False,
                data=None,
                error=str(e)
            )

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query"""
        # Remove common German/English stop words
        stop_words = {
            'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines',
            'und', 'oder', 'aber', 'nicht', 'auch', 'mit', 'für', 'von', 'auf', 'an',
            'ist', 'sind', 'war', 'waren', 'hat', 'haben', 'wird', 'werden',
            'the', 'a', 'an', 'and', 'or', 'but', 'not', 'also', 'with', 'for', 'from',
            'is', 'are', 'was', 'were', 'has', 'have', 'will', 'would',
            'mein', 'meine', 'meinem', 'meiner', 'meines', 'my', 'mine',
            'was', 'wie', 'wo', 'wann', 'warum', 'what', 'how', 'where', 'when', 'why',
            'gibt', 'es', 'mir', 'über', 'alle', 'zum', 'zur', 'about', 'all', 'to'
        }

        # Split and clean
        words = query.lower().split()
        keywords = []

        for word in words:
            # Remove punctuation
            word = word.strip('.,!?;:()[]{}"\'-')
            # Keep if not stop word and length > 2
            if word and word not in stop_words and len(word) > 2:
                keywords.append(word)

        return keywords

    def format_autonomous_results_for_context(self, results: Dict) -> Optional[Dict]:
        """Format autonomous action results for AI context"""
        if not results.get('gathered_information'):
            return None

        lines = []
        lines.append("=== AUTONOMOUS RESEARCH RESULTS ===")
        lines.append("")
        lines.append(f"Executed {len(results['actions_executed'])} autonomous actions:")
        lines.append("")

        # Group information by source
        info_by_source = {}
        for info in results['gathered_information']:
            source = info['source']
            if source not in info_by_source:
                info_by_source[source] = []
            info_by_source[source].append(info['data'])

        # Format each source
        for source, data_list in info_by_source.items():
            source_names = {
                'search_knowledge_base': '📚 Indexed Documents',
                'search_files': '📁 File Search Results',
                'search_contacts': '👤 Contact Search',
                'search_calendar': '📅 Calendar Search',
                'search_tasks': '✅ Task Search',
                'search_photos': '📸 Photo Search',
                'search_emails': '📧 Email Search'
            }

            lines.append(f"**{source_names.get(source, source)}**:")
            lines.append("")

            for data in data_list:
                if source == 'search_knowledge_base':
                    count = data.get('count', 0)
                    lines.append(f"Found {count} relevant document chunks:")
                    for chunk in data.get('chunks', [])[:5]:
                        lines.append(f"- {chunk.get('source', 'Unknown')} (Score: {chunk.get('score', 0):.2f})")
                        content_preview = chunk.get('content', '')[:150]
                        lines.append(f"  {content_preview}...")

                elif source == 'search_files':
                    count = data.get('count', 0)
                    lines.append(f"Found {count} files:")
                    for file in data.get('files', [])[:5]:
                        title = file.get('title', 'Unknown')
                        subline = file.get('subline', '')
                        lines.append(f"- {title}")
                        if subline:
                            lines.append(f"  {subline}")

                elif source in ['search_contacts', 'search_calendar', 'search_tasks']:
                    key = 'contacts' if source == 'search_contacts' else ('events' if source == 'search_calendar' else 'tasks')
                    count = data.get('count', 0)
                    items = data.get(key, [])
                    lines.append(f"Found {count} items")
                    for item in items[:3]:
                        lines.append(f"- {item.get('title', 'Unknown')}")

                elif source == 'search_photos':
                    count = data.get('count', 0)
                    lines.append(f"Found {count} photos")

                elif source == 'search_emails':
                    count = data.get('count', 0)
                    lines.append(f"Found {count} emails:")
                    for mail in data.get('emails', [])[:5]:
                        subject = mail.get('subject', '(no subject)')
                        sender = mail.get('sender', '')
                        date = mail.get('date', '')
                        lines.append(f"- {subject}" + (f" (von {sender})" if sender else '') + (f" [{date}]" if date else ''))
                        preview = mail.get('body_preview', '')
                        if preview:
                            lines.append(f"  {preview[:150]}")

            lines.append("")

        return {
            'content': '\n'.join(lines),
            'source': 'Autonomous Agent Research',
            'path': 'autonomous',
            'similarity_score': 1.0,
            'metadata': results
        }
