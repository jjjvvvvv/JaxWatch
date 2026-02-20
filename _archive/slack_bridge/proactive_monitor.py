#!/usr/bin/env python3
"""
Proactive Civic Intelligence Monitor for JaxWatch
Monitors filesystem for civic document changes and provides intelligent suggestions
"""

import asyncio
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
import hashlib
import anthropic

try:
    # Try relative import first (when run as module)
    from .civic_context import CivicAnalysisContext
    from .persistent_memory import PersistentConversationMemory, ConversationContext
except ImportError:
    # Fall back to absolute import (when run as script)
    from civic_context import CivicAnalysisContext
    from persistent_memory import PersistentConversationMemory, ConversationContext


@dataclass
class DocumentChange:
    """Represents a detected change to a civic document."""
    path: Path
    change_type: str  # 'added', 'modified', 'moved'
    detected_at: datetime
    file_size: int
    document_type: Optional[str] = None
    project_id: Optional[str] = None
    priority: str = 'medium'  # 'low', 'medium', 'high'


@dataclass
class ProactiveSuggestion:
    """Represents an intelligent suggestion for civic analysis."""
    suggestion_id: str
    document_change: DocumentChange
    action_type: str  # 'document_verify', 'reference_scan', 'status_check'
    description: str
    reasoning: str
    parameters: Dict
    priority: str
    should_notify: bool = True
    confidence: float = 0.5


class CivicDocumentMonitor:
    """
    Monitor JaxWatch directories for new or changed civic documents.

    This component watches the inputs/ directories for civic document changes
    and classifies them for intelligent analysis suggestions.
    """

    def __init__(self, jaxwatch_root: Path):
        """
        Initialize document monitor.

        Args:
            jaxwatch_root: Path to JaxWatch root directory
        """
        self.jaxwatch_root = jaxwatch_root
        self.inputs_dir = jaxwatch_root / "inputs"

        # Watch these directories for civic documents
        self.watch_paths = [
            self.inputs_dir / "documents",
            self.inputs_dir / "meeting_minutes",
            self.inputs_dir / "projects",
            self.inputs_dir / "dia_board",
            self.inputs_dir / "city_council",
            self.inputs_dir / "planning_commission"
        ]

        # State tracking
        self._file_states: Dict[str, Dict] = {}
        self._last_scan: Optional[datetime] = None

        # Load existing state if available
        self._load_file_states()

    def _load_file_states(self):
        """Load previous file states for change detection."""
        state_file = self.jaxwatch_root / ".proactive_monitor_state.json"

        try:
            if state_file.exists():
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    self._file_states = data.get('file_states', {})

                    last_scan_str = data.get('last_scan')
                    if last_scan_str:
                        self._last_scan = datetime.fromisoformat(last_scan_str)

        except Exception as e:
            print(f"Warning: Could not load monitor state: {e}")

    def _save_file_states(self):
        """Save current file states for next scan."""
        state_file = self.jaxwatch_root / ".proactive_monitor_state.json"

        try:
            data = {
                'file_states': self._file_states,
                'last_scan': self._last_scan.isoformat() if self._last_scan else None,
                'updated_at': datetime.now().isoformat()
            }

            with open(state_file, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"Warning: Could not save monitor state: {e}")

    async def get_recent_changes(self) -> List[DocumentChange]:
        """
        Detect new or modified civic documents since last scan.

        Returns:
            List of detected document changes
        """
        changes = []
        current_states = {}

        # Scan all watch paths
        for watch_path in self.watch_paths:
            if not watch_path.exists():
                continue

            for file_path in watch_path.rglob("*"):
                if file_path.is_file() and self._is_civic_document(file_path):
                    # Calculate file state
                    file_key = str(file_path.relative_to(self.jaxwatch_root))
                    file_stat = file_path.stat()

                    current_state = {
                        'size': file_stat.st_size,
                        'modified': file_stat.st_mtime,
                        'path': file_key
                    }

                    current_states[file_key] = current_state

                    # Check for changes
                    previous_state = self._file_states.get(file_key)

                    if not previous_state:
                        # New file
                        change = self._create_document_change(
                            file_path, 'added', file_stat
                        )
                        changes.append(change)

                    elif (current_state['size'] != previous_state['size'] or
                          current_state['modified'] != previous_state['modified']):
                        # Modified file
                        change = self._create_document_change(
                            file_path, 'modified', file_stat
                        )
                        changes.append(change)

        # Update state
        self._file_states = current_states
        self._last_scan = datetime.now()
        self._save_file_states()

        return changes

    def _is_civic_document(self, file_path: Path) -> bool:
        """Check if a file is a civic document worth monitoring."""
        # File extension check
        civic_extensions = {'.pdf', '.doc', '.docx', '.txt', '.md', '.json', '.csv'}
        if file_path.suffix.lower() not in civic_extensions:
            return False

        # Skip temporary and system files
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return False

        # Skip very small files (likely empty or temp)
        try:
            if file_path.stat().st_size < 100:  # Less than 100 bytes
                return False
        except OSError:
            return False

        return True

    def _create_document_change(self, file_path: Path, change_type: str,
                              file_stat: os.stat_result) -> DocumentChange:
        """Create a DocumentChange object from file information."""

        # Classify document type and extract project info
        document_type = self._classify_document(file_path)
        project_id = self._extract_project_id(file_path)
        priority = self._determine_priority(file_path, document_type)

        return DocumentChange(
            path=file_path,
            change_type=change_type,
            detected_at=datetime.now(),
            file_size=file_stat.st_size,
            document_type=document_type,
            project_id=project_id,
            priority=priority
        )

    def _classify_document(self, file_path: Path) -> Optional[str]:
        """Classify document type based on path and name."""
        path_str = str(file_path).lower()
        name_str = file_path.name.lower()

        # Check parent directory for clues
        if 'meeting_minutes' in path_str or 'minutes' in name_str:
            return 'meeting_minutes'
        elif 'budget' in path_str or 'financial' in name_str:
            return 'budget'
        elif 'transport' in path_str or 'transit' in name_str:
            return 'transportation'
        elif 'housing' in path_str or 'residential' in name_str:
            return 'housing'
        elif 'environment' in path_str or 'environmental' in name_str:
            return 'environmental'
        elif 'dia_board' in path_str:
            return 'dia_board'
        elif 'city_council' in path_str:
            return 'city_council'
        elif 'planning' in path_str:
            return 'planning'
        else:
            return 'general_civic'

    def _extract_project_id(self, file_path: Path) -> Optional[str]:
        """Try to extract project ID from file path or name."""
        import re

        path_str = str(file_path)

        # Common project ID patterns
        patterns = [
            r'\b([A-Z]{2,5}-\d{4}-\d{2,4})\b',  # DEN-2026-001 format
            r'\b(DEN\d{4}\w*)\b',                # DENXXXX format
            r'\b(\d{4}-\d{2,4})\b'               # Year-number format
        ]

        for pattern in patterns:
            match = re.search(pattern, path_str)
            if match:
                return match.group(1)

        return None

    def _determine_priority(self, file_path: Path, document_type: Optional[str]) -> str:
        """Determine priority level for document change."""

        # High priority indicators
        high_priority_indicators = ['budget', 'environmental', 'compliance', 'urgent']
        medium_priority_indicators = ['meeting_minutes', 'dia_board', 'transportation']

        path_str = str(file_path).lower()

        if any(indicator in path_str for indicator in high_priority_indicators):
            return 'high'
        elif any(indicator in path_str for indicator in medium_priority_indicators):
            return 'medium'
        else:
            return 'low'


class ProactiveCivicAgent:
    """
    Monitor civic documents and proactively suggest analysis actions.

    This component combines file system monitoring with Claude-powered
    intelligence to suggest relevant civic analysis workflows.
    """

    def __init__(self, jaxwatch_root: Path, claude_client: Optional[anthropic.Anthropic] = None):
        """
        Initialize proactive civic agent.

        Args:
            jaxwatch_root: Path to JaxWatch root directory
            claude_client: Optional Claude client for intelligent suggestions
        """
        self.jaxwatch_root = jaxwatch_root
        self.claude_client = claude_client

        # Initialize components
        self.document_monitor = CivicDocumentMonitor(jaxwatch_root)
        self.civic_context = CivicAnalysisContext(jaxwatch_root)
        self.conversation_memory = PersistentConversationMemory(
            jaxwatch_root / "conversations"
        )

        # Suggestion tracking
        self._recent_suggestions: List[ProactiveSuggestion] = []
        self._notification_users: Set[str] = set()

    async def monitor_civic_activity(self, check_interval_minutes: int = 5):
        """
        Continuously monitor for civic document changes and generate suggestions.

        Args:
            check_interval_minutes: How often to check for changes
        """
        print(f"Starting proactive civic monitoring (checking every {check_interval_minutes} minutes)")

        while True:
            try:
                # Check for document changes
                changes = await self.document_monitor.get_recent_changes()

                if changes:
                    print(f"Detected {len(changes)} document changes")

                    # Generate suggestions for each change
                    for change in changes:
                        suggestion = await self.generate_intelligent_suggestion(change)

                        if suggestion and suggestion.should_notify:
                            self._recent_suggestions.append(suggestion)

                            # Notify relevant users
                            await self._notify_users_of_suggestion(suggestion)

                # Sleep until next check
                await asyncio.sleep(check_interval_minutes * 60)

            except KeyboardInterrupt:
                print("Stopping proactive monitoring")
                break
            except Exception as e:
                print(f"Error in proactive monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def generate_intelligent_suggestion(self, change: DocumentChange) -> Optional[ProactiveSuggestion]:
        """
        Use Claude to generate intelligent suggestions for document changes.

        Args:
            change: Detected document change

        Returns:
            ProactiveSuggestion or None if no suggestion needed
        """
        if not self.claude_client:
            # Fallback to rule-based suggestions
            return self._generate_rule_based_suggestion(change)

        try:
            # Prepare context for Claude
            civic_status = self.civic_context.get_current_status()

            system_prompt = """You are a proactive civic analysis assistant.

When new civic documents appear or existing ones change, you help users by suggesting appropriate analysis actions.

Consider:
- Document type and likely content based on file path
- Current civic analysis status
- Civic compliance requirements
- Analysis workflow best practices

Be helpful but not pushy. Focus on civic transparency and compliance.

Respond with JSON containing:
{
  "action_type": "document_verify|reference_scan|status_check|none",
  "description": "Brief description of suggested action",
  "reasoning": "Why this action would be helpful",
  "parameters": {"key": "value"},
  "priority": "low|medium|high",
  "should_notify": true/false,
  "confidence": 0.0-1.0
}"""

            user_prompt = f"""
Document change detected:
- Path: {change.path}
- Change type: {change.change_type}
- Document type: {change.document_type}
- Project ID: {change.project_id}
- File size: {change.file_size} bytes
- Priority: {change.priority}

Current civic analysis status:
- Total projects: {civic_status.get('projects_count', 0)}
- Verified documents: {civic_status.get('verified_count', 0)}
- Reference annotations: {civic_status.get('references_count', 0)}
- Last activity: {civic_status.get('last_activity', 'Unknown')}

Should I suggest any civic analysis actions? If yes, what specific suggestion and why?
"""

            response = await self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Parse Claude's response
            claude_response = response.content[0].text.strip()
            suggestion_data = self._parse_suggestion_response(claude_response)

            if suggestion_data.get('action_type') == 'none':
                return None

            # Create suggestion object
            suggestion_id = hashlib.md5(
                f"{change.path}_{change.detected_at}".encode()
            ).hexdigest()[:8]

            return ProactiveSuggestion(
                suggestion_id=suggestion_id,
                document_change=change,
                action_type=suggestion_data.get('action_type', 'document_verify'),
                description=suggestion_data.get('description', 'Analyze new civic document'),
                reasoning=suggestion_data.get('reasoning', 'New civic document detected'),
                parameters=suggestion_data.get('parameters', {}),
                priority=suggestion_data.get('priority', 'medium'),
                should_notify=suggestion_data.get('should_notify', True),
                confidence=suggestion_data.get('confidence', 0.5)
            )

        except Exception as e:
            print(f"Error generating intelligent suggestion: {e}")
            return self._generate_rule_based_suggestion(change)

    def _parse_suggestion_response(self, claude_response: str) -> Dict:
        """Parse Claude's JSON response for suggestion data."""
        try:
            import re

            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', claude_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                return json.loads(json_text)
            else:
                # Fallback: extract key information from text
                return self._extract_suggestion_from_text(claude_response)

        except json.JSONDecodeError:
            return self._extract_suggestion_from_text(claude_response)

    def _extract_suggestion_from_text(self, text: str) -> Dict:
        """Extract suggestion data from Claude's text response."""
        text_lower = text.lower()

        # Default suggestion data
        suggestion_data = {
            'action_type': 'document_verify',
            'description': 'Analyze new civic document',
            'reasoning': text,
            'parameters': {},
            'priority': 'medium',
            'should_notify': True,
            'confidence': 0.4
        }

        # Try to determine action type from text
        if 'verify' in text_lower or 'check' in text_lower:
            suggestion_data['action_type'] = 'document_verify'
        elif 'scan' in text_lower or 'reference' in text_lower:
            suggestion_data['action_type'] = 'reference_scan'
        elif 'none' in text_lower or 'no action' in text_lower:
            suggestion_data['action_type'] = 'none'

        # Try to determine priority
        if any(word in text_lower for word in ['urgent', 'important', 'critical']):
            suggestion_data['priority'] = 'high'
        elif any(word in text_lower for word in ['minor', 'routine', 'optional']):
            suggestion_data['priority'] = 'low'

        return suggestion_data

    def _generate_rule_based_suggestion(self, change: DocumentChange) -> Optional[ProactiveSuggestion]:
        """Generate suggestion using rule-based logic when Claude is unavailable."""

        # Basic rules for civic document analysis
        if change.document_type in ['meeting_minutes', 'budget', 'environmental']:
            action_type = 'document_verify'
            description = f"Verify new {change.document_type} document for compliance"
            reasoning = f"New {change.document_type} documents should be verified for civic compliance"
            priority = 'high' if change.document_type == 'budget' else 'medium'

        elif change.document_type in ['dia_board', 'city_council']:
            action_type = 'reference_scan'
            description = f"Scan new {change.document_type} document for references"
            reasoning = f"Meeting documents often contain references to other civic documents"
            priority = 'medium'

        else:
            # General civic documents
            action_type = 'document_verify'
            description = "Verify new civic document"
            reasoning = "New civic documents should be analyzed for transparency"
            priority = 'low'

        # Build parameters
        parameters = {}
        if change.project_id:
            parameters['project'] = change.project_id
        if change.document_type:
            parameters['document-type'] = change.document_type

        suggestion_id = hashlib.md5(
            f"{change.path}_{change.detected_at}".encode()
        ).hexdigest()[:8]

        return ProactiveSuggestion(
            suggestion_id=suggestion_id,
            document_change=change,
            action_type=action_type,
            description=description,
            reasoning=reasoning,
            parameters=parameters,
            priority=priority,
            should_notify=True,
            confidence=0.6  # Rule-based confidence
        )

    async def _notify_users_of_suggestion(self, suggestion: ProactiveSuggestion):
        """Notify registered users about a new suggestion."""

        # For now, just log the suggestion
        # In full implementation, this would integrate with Slack notifications
        print(f"📋 Proactive Suggestion [{suggestion.suggestion_id}]:")
        print(f"   Document: {suggestion.document_change.path}")
        print(f"   Action: {suggestion.description}")
        print(f"   Reasoning: {suggestion.reasoning}")
        print(f"   Priority: {suggestion.priority}")
        print(f"   Confidence: {suggestion.confidence:.1f}")

        # TODO: Integrate with Slack gateway for actual user notifications
        # This would require coordination with the main Slack gateway

    def register_notification_user(self, user_id: str):
        """Register a user to receive proactive notifications."""
        self._notification_users.add(user_id)

    def get_recent_suggestions(self, hours: int = 24) -> List[Dict]:
        """Get recent suggestions for user display."""
        cutoff = datetime.now() - timedelta(hours=hours)

        recent = []
        for suggestion in self._recent_suggestions:
            if suggestion.document_change.detected_at >= cutoff:
                recent.append({
                    'id': suggestion.suggestion_id,
                    'description': suggestion.description,
                    'reasoning': suggestion.reasoning,
                    'priority': suggestion.priority,
                    'confidence': suggestion.confidence,
                    'document_path': str(suggestion.document_change.path),
                    'detected_at': suggestion.document_change.detected_at.isoformat(),
                    'action_type': suggestion.action_type,
                    'parameters': suggestion.parameters
                })

        return recent


# Utility functions
def create_proactive_monitor(jaxwatch_root: str, claude_api_key: Optional[str] = None) -> ProactiveCivicAgent:
    """
    Factory function to create a proactive civic agent.

    Args:
        jaxwatch_root: Path to JaxWatch root directory
        claude_api_key: Optional Claude API key

    Returns:
        Configured ProactiveCivicAgent
    """
    claude_client = None
    if claude_api_key:
        claude_client = anthropic.Anthropic(api_key=claude_api_key)

    return ProactiveCivicAgent(Path(jaxwatch_root), claude_client)


async def main():
    """Test the proactive monitoring system."""
    print("Testing Proactive Civic Intelligence Monitor")
    print("=" * 50)

    # Create monitor
    monitor = create_proactive_monitor("/Users/jjjvvvvv/Desktop/JaxWatch")

    # Test document change detection
    changes = await monitor.document_monitor.get_recent_changes()
    print(f"Detected {len(changes)} recent document changes:")

    for change in changes[:5]:  # Show first 5
        print(f"  - {change.path} ({change.change_type})")
        print(f"    Type: {change.document_type}, Priority: {change.priority}")

    # Test suggestion generation
    if changes:
        print(f"\nGenerating suggestion for first change...")
        suggestion = await monitor.generate_intelligent_suggestion(changes[0])

        if suggestion:
            print(f"Suggestion: {suggestion.description}")
            print(f"Reasoning: {suggestion.reasoning}")
            print(f"Action: {suggestion.action_type}")
            print(f"Priority: {suggestion.priority}")
        else:
            print("No suggestion generated")

    print("\nProactive monitor test completed!")


if __name__ == "__main__":
    asyncio.run(main())