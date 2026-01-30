#!/usr/bin/env python3
"""
Command Parser for Slack Bridge
Maps Slack messages to JaxWatch CLI commands using regex patterns
Enhanced with fuzzy matching and intent clarification
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Optional

try:
    # Try relative import first (when run as module)
    from .intent_clarifier import IntentClarifier
except ImportError:
    # Fall back to absolute import (when run as script)
    from intent_clarifier import IntentClarifier


class CommandParser:
    """Parse Slack messages into CLI commands using regex patterns with fuzzy matching."""

    def __init__(self):
        self.mappings = self._load_command_mappings()
        self.intent_clarifier = IntentClarifier()

    def _load_command_mappings(self) -> Dict:
        """Load command mappings from YAML configuration."""
        config_path = Path(__file__).parent / "config" / "command_mappings.yml"
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except (FileNotFoundError, yaml.YAMLError) as e:
            print(f"Error loading command mappings: {e}")
            return {"commands": []}

    def parse_message(self, message_text: str) -> Optional[Dict]:
        """
        Parse Slack message into CLI command using regex patterns.

        Args:
            message_text: Raw Slack message text

        Returns:
            Command dictionary or None if no match found
        """
        message_text = message_text.strip()

        # Remove @mentions from the beginning of messages
        message_text = re.sub(r'^<@[UW]\w+>\s*', '', message_text)

        for mapping in self.mappings['commands']:
            pattern = mapping['pattern']
            match = re.search(pattern, message_text)

            if match:
                # Build command based on mapping type
                if mapping.get('type') == 'direct_response':
                    return {
                        'type': 'direct_response',
                        'response': mapping['response'],
                        'description': mapping['description']
                    }
                elif mapping.get('type') == 'status_check':
                    return {
                        'type': 'status_check',
                        'description': mapping['description'],
                        'background': mapping.get('background', False)
                    }
                elif 'cli_command' in mapping:
                    cli_command = mapping['cli_command']

                    # Substitute captured groups
                    for i, group in enumerate(match.groups(), 1):
                        cli_command = cli_command.replace(f'{{{i}}}', group)

                    return {
                        'type': 'cli_execution',
                        'cli_command': cli_command,
                        'description': mapping['description'],
                        'background': mapping.get('background', False)
                    }

        return None

    def parse_message_with_clarification(self, message_text: str) -> Dict:
        """
        Parse message with fuzzy matching and clarification.

        Args:
            message_text: Raw Slack message text

        Returns:
            Command dictionary with potential clarification request
        """
        # Try exact regex matching first (existing behavior)
        command = self.parse_message(message_text)
        if command:
            return {
                'type': 'exact_match',
                'command': command
            }

        # Fuzzy matching with explicit suggestions
        suggestions = self.intent_clarifier.find_similar_commands(
            message_text, self.mappings['commands']
        )

        # Create clarification response
        clarification = self.intent_clarifier.create_clarification_response(
            message_text, suggestions
        )

        return clarification

    def parse_clarification_response(self, response_text: str, clarification_context: Dict) -> Optional[Dict]:
        """
        Parse user's response to a clarification request.

        Args:
            response_text: User's response to clarification
            clarification_context: Original clarification context

        Returns:
            Command to execute or error response
        """
        return self.intent_clarifier.parse_clarification_response(
            response_text, clarification_context
        )

    def build_command_from_mapping(self, mapping: Dict, original_message: str = None) -> Dict:
        """
        Build command dictionary from mapping, optionally with parameter extraction.

        Args:
            mapping: Command mapping configuration
            original_message: Original message for parameter extraction

        Returns:
            Command dictionary ready for execution
        """
        if mapping.get('type') == 'direct_response':
            return {
                'type': 'direct_response',
                'response': mapping['response'],
                'description': mapping['description']
            }
        elif mapping.get('type') == 'status_check':
            return {
                'type': 'status_check',
                'description': mapping['description'],
                'background': mapping.get('background', False)
            }
        elif 'cli_command' in mapping:
            cli_command = mapping['cli_command']

            # Try to extract parameters from original message if provided
            if original_message:
                pattern = mapping.get('pattern', '')
                try:
                    # Clean message same way as in parse_message
                    clean_message = re.sub(r'^<@[UW]\w+>\s*', '', original_message.strip())
                    match = re.search(pattern, clean_message)
                    if match:
                        # Substitute captured groups
                        for i, group in enumerate(match.groups(), 1):
                            cli_command = cli_command.replace(f'{{{i}}}', group)
                except re.error:
                    # If pattern matching fails, use base command
                    pass

            return {
                'type': 'cli_execution',
                'cli_command': cli_command,
                'description': mapping['description'],
                'background': mapping.get('background', False)
            }

        return mapping

    def get_help_text(self) -> str:
        """Generate help text from command mappings."""
        help_lines = ["Available commands:"]

        for mapping in self.mappings['commands']:
            if mapping.get('type') == 'direct_response' and 'help' in mapping.get('pattern', '').lower():
                continue  # Skip help command itself

            description = mapping.get('description', 'No description')
            help_lines.append(f"• {description}")

        return "\n".join(help_lines)