import secrets
import threading
import time


class AgentSessionStore:
    def __init__(self, ttl_seconds=300):
        self.ttl_seconds = ttl_seconds
        self._sessions = {}
        self._lock = threading.Lock()

    def _purge_expired(self, now):
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session['created_at'] > self.ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    def create(self, owner, payload):
        if not owner:
            raise ValueError('An authenticated owner is required for agent sessions')
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            self._sessions[session_id] = {
                'owner': owner,
                'created_at': now,
                'payload': dict(payload),
            }
        return session_id

    def consume(self, owner, session_id):
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            session = self._sessions.get(session_id)
            if session is None:
                return None, 'not_found'
            if session['owner'] != owner:
                return None, 'forbidden'
            self._sessions.pop(session_id, None)
            return session['payload'], None

    def clear(self):
        with self._lock:
            self._sessions.clear()


agent_sessions = AgentSessionStore()
