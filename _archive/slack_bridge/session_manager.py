#!/usr/bin/env python3
"""
Session Manager for Slack Bridge
Minimal, fail-closed user session tracking for conversation continuity
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List


class UserSession:
    """
    Per-user conversation context.
    Stores only factual history, no interpretations or preferences.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.last_activity = datetime.now()
        self.command_history = []  # Last 3 commands only (minimal)
        self.active_jobs = []      # Currently running job IDs only
        self.pending_clarification = None  # Awaiting clarification response
        # NO preferences stored - ask every time to avoid assumptions

    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def add_command(self, command_dict: Dict, job_id: str = None):
        """Record a command execution."""
        entry = {
            'timestamp': datetime.now(),
            'command': command_dict,
            'job_id': job_id,
            'status': 'started' if job_id else 'immediate'
        }

        self.command_history.append(entry)

        # Keep only last 3 commands (minimal memory)
        if len(self.command_history) > 3:
            self.command_history.pop(0)

        if job_id:
            self.active_jobs.append(job_id)

    def mark_job_completed(self, job_id: str):
        """Update job status when complete."""
        if job_id in self.active_jobs:
            self.active_jobs.remove(job_id)

        # Update command history status
        for entry in self.command_history:
            if entry.get('job_id') == job_id:
                entry['status'] = 'completed'
                entry['completed_at'] = datetime.now()
                break

    def set_pending_clarification(self, clarification_context: Dict):
        """Set pending clarification state."""
        self.pending_clarification = {
            'context': clarification_context,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=2)  # 2-minute timeout
        }

    def get_pending_clarification(self) -> Optional[Dict]:
        """Get pending clarification if not expired."""
        if not self.pending_clarification:
            return None

        # Check if expired
        if datetime.now() > self.pending_clarification['expires_at']:
            self.pending_clarification = None
            return None

        return self.pending_clarification['context']

    def clear_pending_clarification(self):
        """Clear pending clarification state."""
        self.pending_clarification = None

    def can_resolve_context_reference(self, message: str) -> Optional[Dict]:
        """
        Conservative check for unambiguous context references.
        Only resolves very clear cases to avoid assumptions.
        """
        clean_msg = message.lower().strip()

        # ONLY resolve if there's exactly one active job and message clearly refers to status
        status_phrases = ['how', 'status', 'going', 'progress', 'done', 'finished', 'complete']
        if any(phrase in clean_msg for phrase in status_phrases):
            if len(self.active_jobs) == 1:  # Must be exactly one, not multiple
                most_recent = self.command_history[-1] if self.command_history else None
                if most_recent and most_recent.get('job_id') == self.active_jobs[0]:
                    return {
                        'type': 'job_status_request',
                        'job_id': most_recent['job_id'],
                        'original_command': most_recent['command']['description'],
                        'started_at': most_recent['timestamp']
                    }

        # Refinements disabled for now - too ambiguous
        # If user wants refinement, they should issue new explicit command

        return None

    def is_expired(self, timeout_minutes: int = 15) -> bool:
        """Check if session has expired."""
        return (datetime.now() - self.last_activity).total_seconds() > (timeout_minutes * 60)

    def to_dict(self) -> Dict:
        """Serialize session for inspection/debugging."""
        return {
            'user_id': self.user_id,
            'last_activity': self.last_activity.isoformat(),
            'command_count': len(self.command_history),
            'active_jobs': self.active_jobs,
            'has_pending_clarification': self.pending_clarification is not None,
            'expires_in_minutes': round((datetime.now() + timedelta(minutes=15) - self.last_activity).total_seconds() / 60)
        }


class SessionManager:
    """
    Minimal, fail-closed user session tracking.
    Only stores factual interaction history - no interpretation or inference.
    JSON-serializable, inspectable, time-boxed with enforced expiry.
    """

    def __init__(self):
        self.sessions: Dict[str, UserSession] = {}
        self.session_timeout_minutes = 15  # 15 minutes (conservative)

    def get_or_create_session(self, user_id: str) -> UserSession:
        """Get existing session or create new one."""
        # Cleanup expired sessions first
        self._cleanup_expired_sessions()

        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id)

        session = self.sessions[user_id]
        session.touch()  # Update last_activity

        return session

    def get_session(self, user_id: str) -> Optional[UserSession]:
        """Get existing session without creating new one."""
        self._cleanup_expired_sessions()
        return self.sessions.get(user_id)

    def _cleanup_expired_sessions(self):
        """Remove expired sessions to prevent memory leaks."""
        expired_users = []
        for user_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout_minutes):
                expired_users.append(user_id)

        for user_id in expired_users:
            del self.sessions[user_id]

    def get_all_sessions_status(self) -> List[Dict]:
        """Get status of all active sessions for debugging."""
        self._cleanup_expired_sessions()
        return [session.to_dict() for session in self.sessions.values()]

    def clear_all_sessions(self):
        """Clear all sessions (for testing or reset)."""
        self.sessions.clear()

    def get_session_count(self) -> int:
        """Get count of active sessions."""
        self._cleanup_expired_sessions()
        return len(self.sessions)