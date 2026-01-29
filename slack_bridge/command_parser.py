#!/usr/bin/env python3
"""
Command Parser for Slack Bridge
Maps Slack messages to JaxWatch CLI commands using regex patterns
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Optional


class CommandParser:
    """Parse Slack messages into CLI commands using regex patterns."""

    def __init__(self):
        self.mappings = self._load_command_mappings()

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

    def get_help_text(self) -> str:
        """Generate help text from command mappings."""
        help_lines = ["Available commands:"]

        for mapping in self.mappings['commands']:
            if mapping.get('type') == 'direct_response' and 'help' in mapping.get('pattern', '').lower():
                continue  # Skip help command itself

            description = mapping.get('description', 'No description')
            help_lines.append(f"• {description}")

        return "\n".join(help_lines)