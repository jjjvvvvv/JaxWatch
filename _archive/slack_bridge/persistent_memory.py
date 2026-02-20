#!/usr/bin/env python3
"""
Persistent Conversation Memory for JaxWatch
Markdown-based conversation storage with civic analysis context
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any


class ConversationContext:
    """
    Rich conversation context for LLM to understand ongoing civic work.

    Stores conversation history, civic preferences, and active project context
    to enable intelligent multi-turn workflows.
    """

    def __init__(self, user_id: str):
        """
        Initialize conversation context for a user.

        Args:
            user_id: Unique identifier for the user
        """
        self.user_id = user_id
        self.recent_exchanges: List[Dict] = []
        self.active_civic_projects: List[str] = []
        self.civic_preferences: Dict[str, str] = {}
        self.session_start: datetime = datetime.now()
        self.last_activity: datetime = datetime.now()

    def get_recent_exchanges(self, limit: int = 3) -> str:
        """
        Format recent conversation for LLM context.

        Args:
            limit: Maximum number of recent exchanges to include

        Returns:
            Formatted conversation history
        """
        if not self.recent_exchanges:
            return "No recent conversation history."

        formatted = []
        for exchange in self.recent_exchanges[-limit:]:
            timestamp = exchange.get('timestamp', 'Unknown time')
            formatted.append(f"[{timestamp}]")
            formatted.append(f"User: {exchange['user_message']}")
            formatted.append(f"Molty: {exchange['molty_response']}")

            if exchange.get('civic_action'):
                action = exchange['civic_action']
                formatted.append(f"Action: {action['description']}")
                if 'job_id' in action:
                    formatted.append(f"Job ID: {action['job_id']}")
            formatted.append("")

        return "\n".join(formatted)

    def add_exchange(self, user_message: str, molty_response: str,
                    civic_action: Optional[Dict] = None):
        """
        Add a conversation exchange to the context.

        Args:
            user_message: What the user said
            molty_response: Molty's response
            civic_action: Optional civic action that was taken
        """
        exchange = {
            'timestamp': datetime.now().strftime('%H:%M'),
            'user_message': user_message,
            'molty_response': molty_response,
            'civic_action': civic_action
        }

        self.recent_exchanges.append(exchange)

        # Keep only recent exchanges in memory (last 10)
        if len(self.recent_exchanges) > 10:
            self.recent_exchanges = self.recent_exchanges[-10:]

        self.last_activity = datetime.now()

    def add_civic_preference(self, preference_type: str, value: str):
        """
        Learn user preferences over time for better assistance.

        Args:
            preference_type: Type of preference (e.g., 'project_focus', 'notification_style')
            value: Preference value
        """
        self.civic_preferences[preference_type] = value

    def add_active_project(self, project_id: str):
        """Add a project to the active projects list."""
        if project_id not in self.active_civic_projects:
            self.active_civic_projects.append(project_id)

        # Keep only recent projects (last 5)
        if len(self.active_civic_projects) > 5:
            self.active_civic_projects = self.active_civic_projects[-5:]

    def is_session_expired(self, timeout_minutes: int = 60) -> bool:
        """
        Check if the conversation session has expired.

        Args:
            timeout_minutes: Session timeout in minutes

        Returns:
            True if session is expired
        """
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.now() - self.last_activity > timeout

    def get_session_duration(self) -> str:
        """Get human-readable session duration."""
        duration = datetime.now() - self.session_start
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


class PersistentConversationMemory:
    """
    Persistent conversation memory using markdown file storage.

    Stores conversation history, civic context, and learned preferences
    in human-readable markdown format for transparency and auditability.
    """

    def __init__(self, conversations_dir: Path):
        """
        Initialize persistent conversation memory.

        Args:
            conversations_dir: Directory to store conversation files
        """
        self.conversations_dir = conversations_dir
        self.conversations_dir.mkdir(exist_ok=True)

        # In-memory cache for active conversations
        self._context_cache: Dict[str, ConversationContext] = {}

    def get_context(self, user_id: str) -> ConversationContext:
        """
        Load conversation context for a user.

        Args:
            user_id: User identifier

        Returns:
            ConversationContext with full history and preferences
        """
        # Check cache first
        if user_id in self._context_cache:
            context = self._context_cache[user_id]
            # Refresh context from disk if session might be stale
            if context.is_session_expired(timeout_minutes=15):
                context = self._load_context_from_disk(user_id)
            return context

        # Load from disk
        context = self._load_context_from_disk(user_id)
        self._context_cache[user_id] = context
        return context

    def _load_context_from_disk(self, user_id: str) -> ConversationContext:
        """Load conversation context from markdown file."""
        conversation_file = self.conversations_dir / f"{user_id}.md"

        if not conversation_file.exists():
            return ConversationContext(user_id)

        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                content = f.read()

            return self._parse_conversation_markdown(user_id, content)

        except Exception as e:
            print(f"Error loading conversation for {user_id}: {e}")
            return ConversationContext(user_id)

    def _parse_conversation_markdown(self, user_id: str, content: str) -> ConversationContext:
        """
        Parse conversation context from markdown content.

        Args:
            user_id: User identifier
            content: Markdown file content

        Returns:
            Parsed ConversationContext
        """
        context = ConversationContext(user_id)

        # Parse preferences section
        preferences_match = re.search(r'## Preferences\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if preferences_match:
            prefs_text = preferences_match.group(1)
            for line in prefs_text.split('\n'):
                if ':' in line:
                    key, value = line.strip('- ').split(':', 1)
                    context.add_civic_preference(key.strip(), value.strip())

        # Parse active projects section
        projects_match = re.search(r'## Active Projects\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if projects_match:
            projects_text = projects_match.group(1)
            for line in projects_text.split('\n'):
                if line.strip().startswith('-'):
                    project = line.strip('- ').strip()
                    if project:
                        context.add_active_project(project)

        # Parse recent exchanges
        exchanges = []
        exchange_pattern = r'## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\n(.*?)(?=\n## \d{4}-\d{2}-\d{2}|\Z)'

        for match in re.finditer(exchange_pattern, content, re.DOTALL):
            timestamp_str = match.group(1)
            exchange_content = match.group(2).strip()

            # Parse exchange content
            exchange = self._parse_exchange_content(exchange_content)
            if exchange:
                exchange['full_timestamp'] = timestamp_str
                exchanges.append(exchange)

        # Keep recent exchanges in context
        context.recent_exchanges = exchanges[-10:] if exchanges else []

        # Update session timing
        if exchanges:
            # Set session start to first exchange of the day
            try:
                last_timestamp = datetime.strptime(exchanges[-1]['full_timestamp'], '%Y-%m-%d %H:%M')
                context.last_activity = last_timestamp

                # Find first exchange of the current session
                session_start = last_timestamp
                for exchange in reversed(exchanges):
                    exchange_time = datetime.strptime(exchange['full_timestamp'], '%Y-%m-%d %H:%M')
                    if last_timestamp - exchange_time > timedelta(hours=1):
                        break
                    session_start = exchange_time

                context.session_start = session_start
            except ValueError:
                # If timestamp parsing fails, use current time
                pass

        return context

    def _parse_exchange_content(self, content: str) -> Optional[Dict]:
        """Parse individual conversation exchange from markdown content."""
        lines = content.split('\n')
        exchange = {}

        for line in lines:
            line = line.strip()
            if line.startswith('**User**:'):
                exchange['user_message'] = line[9:].strip()
            elif line.startswith('**Molty**:'):
                exchange['molty_response'] = line[10:].strip()
            elif line.startswith('**Civic Action**:'):
                if 'civic_action' not in exchange:
                    exchange['civic_action'] = {}
                exchange['civic_action']['description'] = line[17:].strip()
            elif line.startswith('**Job ID**:'):
                if 'civic_action' not in exchange:
                    exchange['civic_action'] = {}
                exchange['civic_action']['job_id'] = line[11:].strip()

        # Only return exchange if it has both user and molty messages
        if 'user_message' in exchange and 'molty_response' in exchange:
            return exchange

        return None

    def record_exchange(self, user_id: str, user_message: str, molty_response: str,
                       civic_action: Optional[Dict] = None):
        """
        Record a conversation exchange to persistent storage.

        Args:
            user_id: User identifier
            user_message: User's message
            molty_response: Molty's response
            civic_action: Optional civic action that was taken
        """
        # Update in-memory context
        context = self.get_context(user_id)
        context.add_exchange(user_message, molty_response, civic_action)

        # Append to markdown file
        self._append_to_conversation_file(user_id, user_message, molty_response, civic_action)

        # Update cache
        self._context_cache[user_id] = context

    def _append_to_conversation_file(self, user_id: str, user_message: str,
                                   molty_response: str, civic_action: Optional[Dict] = None):
        """Append conversation exchange to markdown file."""
        conversation_file = self.conversations_dir / f"{user_id}.md"
        timestamp = datetime.now()

        # Create or append to file
        with open(conversation_file, 'a', encoding='utf-8') as f:
            # Add header if file is new
            if conversation_file.stat().st_size == 0:
                f.write(f"# Conversation with {user_id}\n\n")
                f.write("## Preferences\n\n")
                f.write("(Learned preferences will appear here)\n\n")
                f.write("## Active Projects\n\n")
                f.write("(Recently discussed projects will appear here)\n\n")

            # Add exchange
            f.write(f"## {timestamp.strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"**User**: {user_message}\n\n")
            f.write(f"**Molty**: {molty_response}\n\n")

            if civic_action:
                f.write(f"**Civic Action**: {civic_action.get('description', 'Unknown action')}\n")
                if 'job_id' in civic_action:
                    f.write(f"**Job ID**: {civic_action['job_id']}\n")
                if civic_action.get('type'):
                    f.write(f"**Type**: {civic_action['type']}\n")
                f.write("\n")

    def save_context(self, user_id: str, context: ConversationContext):
        """
        Save updated context (preferences, projects) to disk.

        Args:
            user_id: User identifier
            context: Updated conversation context
        """
        conversation_file = self.conversations_dir / f"{user_id}.md"

        if conversation_file.exists():
            # Update preferences and projects sections in existing file
            self._update_context_sections(conversation_file, context)
        else:
            # Create new file with context
            self._create_context_file(conversation_file, context)

        # Update cache
        self._context_cache[user_id] = context

    def _update_context_sections(self, conversation_file: Path, context: ConversationContext):
        """Update preferences and projects sections in existing markdown file."""
        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Update preferences section
            prefs_lines = []
            for key, value in context.civic_preferences.items():
                prefs_lines.append(f"- {key}: {value}")

            prefs_text = "\n".join(prefs_lines) if prefs_lines else "(No preferences set yet)"

            # Update projects section
            projects_lines = []
            for project in context.active_civic_projects:
                projects_lines.append(f"- {project}")

            projects_text = "\n".join(projects_lines) if projects_lines else "(No active projects)"

            # Replace sections
            content = re.sub(
                r'## Preferences\s*\n.*?(?=\n## |\Z)',
                f"## Preferences\n\n{prefs_text}\n\n",
                content,
                flags=re.DOTALL
            )

            content = re.sub(
                r'## Active Projects\s*\n.*?(?=\n## |\Z)',
                f"## Active Projects\n\n{projects_text}\n\n",
                content,
                flags=re.DOTALL
            )

            with open(conversation_file, 'w', encoding='utf-8') as f:
                f.write(content)

        except Exception as e:
            print(f"Error updating context sections: {e}")

    def _create_context_file(self, conversation_file: Path, context: ConversationContext):
        """Create new conversation file with initial context."""
        with open(conversation_file, 'w', encoding='utf-8') as f:
            f.write(f"# Conversation with {context.user_id}\n\n")

            # Preferences
            f.write("## Preferences\n\n")
            if context.civic_preferences:
                for key, value in context.civic_preferences.items():
                    f.write(f"- {key}: {value}\n")
            else:
                f.write("(No preferences set yet)\n")
            f.write("\n")

            # Active projects
            f.write("## Active Projects\n\n")
            if context.active_civic_projects:
                for project in context.active_civic_projects:
                    f.write(f"- {project}\n")
            else:
                f.write("(No active projects)\n")
            f.write("\n")

    def get_civic_analysis_history(self, user_id: str, days: int = 7) -> List[Dict]:
        """
        Get recent civic analysis actions for context.

        Args:
            user_id: User identifier
            days: Number of days to look back

        Returns:
            List of recent civic actions with details
        """
        context = self.get_context(user_id)
        cutoff_date = datetime.now() - timedelta(days=days)

        civic_actions = []
        for exchange in context.recent_exchanges:
            if exchange.get('civic_action'):
                # Try to parse timestamp
                try:
                    if exchange.get('full_timestamp'):
                        exchange_time = datetime.strptime(exchange['full_timestamp'], '%Y-%m-%d %H:%M')
                        if exchange_time >= cutoff_date:
                            civic_actions.append({
                                'timestamp': exchange['full_timestamp'],
                                'description': exchange['civic_action']['description'],
                                'job_id': exchange['civic_action'].get('job_id'),
                                'type': exchange['civic_action'].get('type')
                            })
                except ValueError:
                    # If timestamp parsing fails, include anyway
                    civic_actions.append({
                        'timestamp': 'Unknown',
                        'description': exchange['civic_action']['description'],
                        'job_id': exchange['civic_action'].get('job_id'),
                        'type': exchange['civic_action'].get('type')
                    })

        return civic_actions

    def cleanup_old_conversations(self, days_to_keep: int = 30):
        """
        Clean up old conversation files for privacy.

        Args:
            days_to_keep: Number of days of conversations to retain
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        for conversation_file in self.conversations_dir.glob("*.md"):
            try:
                # Check file modification time
                if datetime.fromtimestamp(conversation_file.stat().st_mtime) < cutoff_date:
                    conversation_file.unlink()
                    print(f"Removed old conversation: {conversation_file.name}")

            except Exception as e:
                print(f"Error cleaning up {conversation_file}: {e}")


# Utility functions
def create_conversation_memory(jaxwatch_root: str) -> PersistentConversationMemory:
    """
    Factory function to create persistent conversation memory.

    Args:
        jaxwatch_root: Path to JaxWatch root directory

    Returns:
        Configured PersistentConversationMemory
    """
    conversations_dir = Path(jaxwatch_root) / "conversations"
    return PersistentConversationMemory(conversations_dir)


if __name__ == "__main__":
    # Test the conversation memory system
    memory = create_conversation_memory("/tmp/test_jaxwatch")

    # Test recording exchanges
    memory.record_exchange(
        user_id="test_user",
        user_message="verify 2026 transportation projects",
        molty_response="I'll verify all 2026 transportation projects for compliance.",
        civic_action={
            'description': 'Verify 2026 transportation projects',
            'job_id': 'jw_123456',
            'type': 'document_verify'
        }
    )

    # Test loading context
    context = memory.get_context("test_user")
    print("Recent exchanges:")
    print(context.get_recent_exchanges())

    # Test preferences
    context.add_civic_preference("focus_area", "transportation")
    memory.save_context("test_user", context)

    print(f"\nPreferences: {context.civic_preferences}")
    print(f"Session duration: {context.get_session_duration()}")

    print("\nConversation memory test completed!")