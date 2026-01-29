#!/usr/bin/env python3
"""
Response Formatter for Slack Integration
Formats responses for consistent Slack presentation
"""

from typing import Dict, Any, List
from datetime import datetime


class ResponseFormatter:
    """Format responses for Slack consumption."""

    def __init__(self):
        self.emoji_map = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️',
            'status': '📊',
            'job': '🔧',
            'timeout': '⏱️',
            'thinking': '🤔',
            'robot': '🤖'
        }

    def format_status_response(self, status_data: Dict[str, Any]) -> str:
        """
        Format system status for Slack display.

        Args:
            status_data: Status data dictionary

        Returns:
            Formatted status message
        """
        lines = [f"{self.emoji_map['status']} JaxWatch Status (running locally):"]

        # Add main status items
        for item in status_data.get('items', []):
            lines.append(f"• {item}")

        # Add job information if available
        if status_data.get('active_jobs'):
            lines.append("")
            lines.append(f"Active jobs ({len(status_data['active_jobs'])}):")
            for job in status_data['active_jobs']:
                lines.append(f"• {job}")
        else:
            lines.append("")
            lines.append("No active background jobs")

        return "\n".join(lines)

    def format_job_start_response(self, description: str, job_id: str) -> str:
        """
        Format job start confirmation.

        Args:
            description: Job description
            job_id: Job identifier

        Returns:
            Formatted start message
        """
        return (
            f"{self.emoji_map['success']} Running locally on JaxWatch. "
            f"Started {description} (ID: {job_id}). I'll report back here when done."
        )

    def format_job_completion(self, job: Dict[str, Any]) -> str:
        """
        Format job completion notification.

        Args:
            job: Job record with completion status

        Returns:
            Formatted completion message
        """
        status = job.get('status', 'unknown')
        description = job.get('description', 'task')

        if status == 'completed':
            message = f"{self.emoji_map['success']} {description} completed locally!"

            # Add brief output summary if available
            if job.get('output'):
                output_lines = job['output'].strip().split('\n')
                # Look for summary lines
                for line in output_lines:
                    if any(keyword in line.lower() for keyword in ['enhanced', 'processed', 'found']):
                        message += f" {line.strip()}"
                        break

            message += " Check dashboard for details."

        elif status == 'failed':
            message = f"{self.emoji_map['error']} {description} failed."
            if job.get('error'):
                error_preview = job['error'][:200]
                if len(job['error']) > 200:
                    error_preview += "..."
                message += f"\n```{error_preview}```"

        elif status == 'timeout':
            message = f"{self.emoji_map['timeout']} {description} timed out after 30 minutes."

        else:  # error
            message = f"💥 {description} encountered an error: {job.get('error', 'Unknown error')}"

        return message

    def format_error_response(self, error_message: str, include_help: bool = False) -> str:
        """
        Format error response with optional help.

        Args:
            error_message: Error message to display
            include_help: Whether to include help text

        Returns:
            Formatted error message
        """
        message = f"{self.emoji_map['thinking']} {error_message}"

        if include_help:
            message += "\n\nTry 'help' for available commands."

        return message

    def format_help_response(self, commands: List[Dict[str, str]]) -> str:
        """
        Format help response with available commands.

        Args:
            commands: List of command dictionaries

        Returns:
            Formatted help message
        """
        lines = [f"{self.emoji_map['info']} Available commands:"]

        for cmd in commands:
            lines.append(f"• {cmd.get('description', 'No description')}")

        return "\n".join(lines)

    def format_immediate_success(self, output: str) -> str:
        """
        Format immediate command success.

        Args:
            output: Command output

        Returns:
            Formatted success message
        """
        # Limit output length for Slack
        if len(output) > 500:
            output = output[:500] + "..."

        return f"{self.emoji_map['job']} Executed locally: {output}"

    def format_immediate_error(self, error: str) -> str:
        """
        Format immediate command error.

        Args:
            error: Error message

        Returns:
            Formatted error message
        """
        # Limit error length for Slack
        if len(error) > 300:
            error = error[:300] + "..."

        return f"{self.emoji_map['error']} Command failed: {error}"

    def truncate_for_slack(self, text: str, max_length: int = 3000) -> str:
        """
        Truncate text for Slack message limits.

        Args:
            text: Text to truncate
            max_length: Maximum allowed length

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text

        # Find a good break point
        truncated = text[:max_length - 20]
        last_newline = truncated.rfind('\n')

        if last_newline > max_length * 0.8:  # If we have a good break point
            truncated = truncated[:last_newline]

        return truncated + "\n\n[Output truncated...]"