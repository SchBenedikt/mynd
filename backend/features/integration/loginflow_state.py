"""In-Memory Login Flow State Management für Nextcloud Login Flow v2

Dieses Modul verwaltet den Zustand von Nextcloud Login Flows UNABHÄNGIG 
von Flask Sessions, um CORS + Credentials-Probleme zu vermeiden.
"""

import secrets
import time
from typing import Optional, Dict, Any
from threading import Lock
from datetime import datetime, timedelta

class LoginFlowState:
    """Manages login flow state with automatic expiration"""
    
    def __init__(self, expiration_minutes: int = 10):
        self._flows: Dict[str, Dict[str, Any]] = {}
        self._expiration = timedelta(minutes=expiration_minutes)
        self._lock = Lock()
    
    def create_flow(self, nextcloud_url: str, poll_token: str, poll_endpoint: str) -> str:
        """Creates a new login flow entry and returns a session ID
        
        Args:
            nextcloud_url: The Nextcloud base URL
            poll_token: The polling token from Nextcloud
            poll_endpoint: The polling endpoint from Nextcloud
            
        Returns:
            session_id: A unique session ID for this flow
        """
        session_id = secrets.token_urlsafe(32)
        with self._lock:
            self._flows[session_id] = {
                'nextcloud_url': nextcloud_url,
                'poll_token': poll_token,
                'poll_endpoint': poll_endpoint,
                'created_at': datetime.now(),
                'status': 'pending'
            }
        return session_id
    
    def get_flow(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a login flow entry, returns None if expired or not found
        
        Args:
            session_id: The session ID to retrieve
            
        Returns:
            Flow data or None if not found/expired
        """
        with self._lock:
            if session_id not in self._flows:
                return None
            
            flow = self._flows[session_id]
            if datetime.now() - flow['created_at'] > self._expiration:
                del self._flows[session_id]
                return None
            
            return flow.copy()
    
    def update_flow(self, session_id: str, **kwargs) -> bool:
        """Updates a login flow entry
        
        Args:
            session_id: The session ID to update
            **kwargs: Fields to update
            
        Returns:
            True if updated, False if not found/expired
        """
        with self._lock:
            if session_id not in self._flows:
                return False
            
            flow = self._flows[session_id]
            if datetime.now() - flow['created_at'] > self._expiration:
                del self._flows[session_id]
                return False
            
            flow.update(kwargs)
            return True
    
    def delete_flow(self, session_id: str) -> bool:
        """Deletes a login flow entry
        
        Args:
            session_id: The session ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if session_id in self._flows:
                del self._flows[session_id]
                return True
            return False
    
    def cleanup_expired(self) -> int:
        """Removes all expired flows, returns count of removed flows"""
        removed = 0
        with self._lock:
            expired_ids = [
                sid for sid, flow in self._flows.items()
                if datetime.now() - flow['created_at'] > self._expiration
            ]
            for sid in expired_ids:
                del self._flows[sid]
                removed += 1
        return removed


# Global instance
loginflow_state = LoginFlowState(expiration_minutes=15)
