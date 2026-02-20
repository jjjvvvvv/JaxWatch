#!/usr/bin/env python3
"""
Conversational Agent for JaxWatch Civic Analysis
LLM-powered civic analysis assistant with natural language understanding
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import anthropic
from dataclasses import dataclass

try:
    # Try relative import first (when run as module)
    from .civic_intent_engine import CivicIntentEngine
    from .persistent_memory import PersistentConversationMemory, ConversationContext
    from .civic_context import CivicAnalysisContext
except ImportError:
    # Fall back to absolute import (when run as script)
    from civic_intent_engine import CivicIntentEngine
    from persistent_memory import PersistentConversationMemory, ConversationContext
    from civic_context import CivicAnalysisContext


@dataclass
class CivicIntent:
    """Structured representation of civic analysis intent from user message."""
    action_type: Optional[str]  # 'document_verify', 'reference_scan', 'status_check', None
    parameters: Dict  # Parameters for the civic action
    user_response: str  # Conversational response to send to user
    needs_clarification: bool  # Whether more info is needed from user
    action_description: Optional[str] = None  # Human readable action description
    confidence: float = 0.0  # Confidence level from LLM (0.0-1.0)

    @property
    def has_action(self) -> bool:
        """Check if this intent contains an actionable civic command."""
        return self.action_type is not None and not self.needs_clarification


class ConversationalCivicAgent:
    """
    LLM-powered civic analysis agent for natural conversation.

    Replaces regex-based command parsing with Claude-powered natural language
    understanding while maintaining all civic integrity safeguards.
    """

    def __init__(self, jaxwatch_root: Path, claude_api_key: Optional[str] = None):
        """
        Initialize conversational civic agent.

        Args:
            jaxwatch_root: Path to JaxWatch root directory
            claude_api_key: Claude API key (can also be set via ANTHROPIC_API_KEY env var)
        """
        self.jaxwatch_root = jaxwatch_root

        # Initialize Claude client
        api_key = claude_api_key or os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            self.claude_client = anthropic.Anthropic(api_key=api_key)
            self.claude_available = True
        else:
            self.claude_client = None
            self.claude_available = False
            print("Warning: No Claude API key found. Falling back to regex-based parsing.")

        # Initialize components
        self.intent_engine = CivicIntentEngine(self.claude_client)
        self.conversation_memory = PersistentConversationMemory(
            jaxwatch_root / "conversations"
        )
        self.civic_context = CivicAnalysisContext(jaxwatch_root)

        # Load civic tools catalog
        self.civic_tools = self._load_civic_tools_catalog()

    def _load_civic_tools_catalog(self) -> Dict:
        """Load civic tools catalog for LLM understanding."""
        config_path = Path(__file__).parent / "config" / "civic_tools.yml"
        try:
            import yaml
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except (FileNotFoundError, ImportError):
            # Fallback catalog
            return {
                "tools": [
                    {
                        "name": "document_verify",
                        "command": "python document_verifier/document_verifier.py document_verify",
                        "description": "Verify civic documents for compliance and standards",
                        "parameters": ["--project", "--active-year", "--document-type"],
                        "background": True
                    },
                    {
                        "name": "reference_scan",
                        "command": "python reference_scanner/reference_scanner.py run",
                        "description": "Scan for cross-references between civic documents",
                        "parameters": ["--source", "--year", "--project"],
                        "background": True
                    },
                    {
                        "name": "status_check",
                        "description": "Get system health and analysis status",
                        "background": False,
                        "type": "status_check"
                    }
                ]
            }

    async def understand_civic_intent(self, message: str, user_id: str) -> CivicIntent:
        """
        Use Claude to understand civic analysis intent from natural language.

        Args:
            message: User's natural language message
            user_id: User identifier for conversation context

        Returns:
            CivicIntent with action to take and conversational response
        """
        if not self.claude_available:
            # Fallback to regex parsing for backwards compatibility
            return await self._fallback_regex_parsing(message)

        try:
            # Load conversation context
            context = self.conversation_memory.get_context(user_id)

            # Get current civic analysis status for context
            civic_status = self.civic_context.get_current_status()

            # Use Claude to understand intent
            intent = await self.intent_engine.understand_intent(
                message, context, civic_status, self.civic_tools
            )

            # Record the interaction in memory
            if intent.user_response:
                self.conversation_memory.record_exchange(
                    user_id=user_id,
                    user_message=message,
                    molty_response=intent.user_response,
                    civic_action={
                        'type': intent.action_type,
                        'description': intent.action_description,
                        'parameters': intent.parameters
                    } if intent.has_action else None
                )

            return intent

        except Exception as e:
            print(f"Error in Claude intent understanding: {e}")
            # Fallback to regex parsing
            return await self._fallback_regex_parsing(message)

    async def _fallback_regex_parsing(self, message: str) -> CivicIntent:
        """
        Fallback to regex-based command parsing when Claude is unavailable.

        Args:
            message: User message to parse

        Returns:
            CivicIntent derived from regex patterns
        """
        # Import the existing command parser for fallback
        try:
            from .command_parser import CommandParser
            parser = CommandParser()

            # Try to parse with existing regex system
            result = parser.parse_message_with_clarification(message)

            if result.get('type') == 'exact_match':
                command = result['command']
                return CivicIntent(
                    action_type=self._map_command_type(command),
                    parameters=self._extract_parameters_from_command(command),
                    user_response="✅ I understand. Running your civic analysis request...",
                    needs_clarification=False,
                    action_description=command.get('description', 'Civic analysis task'),
                    confidence=1.0
                )
            elif result.get('type') == 'clarification_needed':
                return CivicIntent(
                    action_type=None,
                    parameters={},
                    user_response=result.get('response', "I need clarification on your request."),
                    needs_clarification=True,
                    confidence=0.5
                )
            else:
                return CivicIntent(
                    action_type=None,
                    parameters={},
                    user_response="I don't understand that command. Try 'help' for available commands.",
                    needs_clarification=True,
                    confidence=0.0
                )

        except ImportError:
            return CivicIntent(
                action_type=None,
                parameters={},
                user_response="I'm having trouble understanding your request. Please try again.",
                needs_clarification=True,
                confidence=0.0
            )

    def _map_command_type(self, command: Dict) -> Optional[str]:
        """Map command dictionary to civic action type."""
        if command.get('type') == 'cli_execution':
            cli_command = command.get('cli_command', '')
            if 'document_verifier' in cli_command:
                return 'document_verify'
            elif 'reference_scanner' in cli_command:
                return 'reference_scan'
        elif command.get('type') == 'status_check':
            return 'status_check'
        return None

    def _extract_parameters_from_command(self, command: Dict) -> Dict:
        """Extract parameters from legacy command structure."""
        parameters = {}

        if command.get('type') == 'cli_execution':
            cli_command = command.get('cli_command', '')

            # Extract common parameters from CLI command
            if '--project' in cli_command:
                # Extract project ID
                import re
                match = re.search(r'--project\s+([^\s]+)', cli_command)
                if match:
                    parameters['project'] = match.group(1)

            if '--active-year' in cli_command:
                # Extract year
                import re
                match = re.search(r'--active-year\s+(\d{4})', cli_command)
                if match:
                    parameters['year'] = match.group(1)

            if '--source' in cli_command:
                # Extract source
                import re
                match = re.search(r'--source\s+([^\s]+)', cli_command)
                if match:
                    parameters['source'] = match.group(1)

            # Store the full CLI command for execution
            parameters['cli_command'] = cli_command

        return parameters

    async def handle_follow_up(self, message: str, user_id: str,
                              previous_context: Optional[Dict] = None) -> CivicIntent:
        """
        Handle follow-up questions or responses in conversation context.

        Args:
            message: User's follow-up message
            user_id: User identifier
            previous_context: Context from previous interaction

        Returns:
            CivicIntent for follow-up action
        """
        # Load full conversation context
        context = self.conversation_memory.get_context(user_id)

        # Check if this is a response to a clarification request
        if previous_context and previous_context.get('waiting_for_clarification'):
            return await self._handle_clarification_response(
                message, user_id, previous_context
            )

        # Otherwise, treat as new intent with conversation context
        return await self.understand_civic_intent(message, user_id)

    async def _handle_clarification_response(self, message: str, user_id: str,
                                           clarification_context: Dict) -> CivicIntent:
        """Handle user's response to a clarification request."""
        message_lower = message.lower().strip()

        # Simple yes/no handling
        if message_lower in ['yes', 'y', 'ok', 'okay', 'sure', 'proceed']:
            # Execute the suggested action
            suggested_action = clarification_context.get('suggested_action')
            if suggested_action:
                return CivicIntent(
                    action_type=suggested_action.get('type'),
                    parameters=suggested_action.get('parameters', {}),
                    user_response="✅ Proceeding with your civic analysis request...",
                    needs_clarification=False,
                    action_description=suggested_action.get('description')
                )

        elif message_lower in ['no', 'n', 'cancel', 'stop', 'nevermind']:
            return CivicIntent(
                action_type=None,
                parameters={},
                user_response="Understood. Let me know if you need help with civic analysis.",
                needs_clarification=False
            )

        # If not a simple yes/no, re-analyze with Claude
        return await self.understand_civic_intent(message, user_id)

    def get_conversation_summary(self, user_id: str) -> str:
        """Get a summary of recent conversation for transparency."""
        context = self.conversation_memory.get_context(user_id)
        return context.get_recent_exchanges(limit=3)

    def get_civic_preferences(self, user_id: str) -> Dict:
        """Get learned civic analysis preferences for this user."""
        context = self.conversation_memory.get_context(user_id)
        return context.civic_preferences

    def update_civic_preference(self, user_id: str, preference_type: str, value: str):
        """Update a civic analysis preference for better future assistance."""
        context = self.conversation_memory.get_context(user_id)
        context.add_civic_preference(preference_type, value)

        # Save updated preferences
        self.conversation_memory.save_context(user_id, context)


# Utility functions for integration
def create_conversational_agent(jaxwatch_root: str, claude_api_key: str = None) -> ConversationalCivicAgent:
    """
    Factory function to create a conversational civic agent.

    Args:
        jaxwatch_root: Path to JaxWatch root directory
        claude_api_key: Optional Claude API key

    Returns:
        Configured ConversationalCivicAgent
    """
    return ConversationalCivicAgent(Path(jaxwatch_root), claude_api_key)


if __name__ == "__main__":
    # Test the conversational agent
    import sys

    if len(sys.argv) < 2:
        print("Usage: python conversational_agent.py '<message>' [user_id]")
        sys.exit(1)

    message = sys.argv[1]
    user_id = sys.argv[2] if len(sys.argv) > 2 else 'test_user'

    # Create agent
    agent = create_conversational_agent('/Users/jjjvvvvv/Desktop/JaxWatch')

    # Test intent understanding
    async def test_intent():
        intent = await agent.understand_civic_intent(message, user_id)
        print(f"User message: {message}")
        print(f"Molty response: {intent.user_response}")
        print(f"Action type: {intent.action_type}")
        print(f"Parameters: {intent.parameters}")
        print(f"Needs clarification: {intent.needs_clarification}")
        print(f"Confidence: {intent.confidence}")

    # Run test
    asyncio.run(test_intent())