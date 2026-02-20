#!/usr/bin/env python3
"""
Message Handler for Slack Integration
Processes incoming Slack messages and routes them to appropriate handlers
"""

from typing import Dict, Any


class MessageHandler:
    """Handle and route incoming Slack messages."""

    def __init__(self, command_parser, job_manager, status_collector, jaxwatch_root):
        """
        Initialize message handler.

        Args:
            command_parser: CommandParser instance
            job_manager: JobManager instance
            status_collector: StatusCollector instance
            jaxwatch_root: Path to JaxWatch root directory
        """
        self.command_parser = command_parser
        self.job_manager = job_manager
        self.status_collector = status_collector
        self.jaxwatch_root = jaxwatch_root

    def process_message(self, event: Dict[str, Any]) -> Dict[str, str]:
        """
        Process incoming Slack message and return response.

        Args:
            event: Slack event data

        Returns:
            Dictionary with response data
        """
        try:
            message_text = event.get('text', '').strip()
            user_id = event.get('user', '')
            channel_id = event.get('channel', '')

            if not message_text:
                return {'response': 'Empty message received', 'type': 'error'}

            # Parse command (NO AI, regex only)
            command = self.command_parser.parse_message(message_text)

            if not command:
                return {
                    'response': "🤔 I don't understand that command. Try 'help' for available commands.",
                    'type': 'error'
                }

            # Route command based on type
            return self._route_command(command, user_id, channel_id)

        except Exception as e:
            return {
                'response': f"💥 Error processing command: {str(e)}",
                'type': 'error'
            }

    def _route_command(self, command: Dict[str, Any], user_id: str, channel_id: str) -> Dict[str, str]:
        """
        Route command to appropriate handler.

        Args:
            command: Parsed command dictionary
            user_id: Slack user ID
            channel_id: Slack channel ID

        Returns:
            Response dictionary
        """
        command_type = command.get('type', 'unknown')

        if command_type == 'direct_response':
            return {
                'response': command['response'],
                'type': 'direct'
            }

        elif command_type == 'status_check':
            status = self.status_collector.get_system_status(self.jaxwatch_root)
            job_summary = self.status_collector.get_job_summary(self.job_manager)

            response = f"📊 JaxWatch Status (running locally):\n{status}\n\n{job_summary}"
            return {
                'response': response,
                'type': 'status'
            }

        elif command.get('background', False):
            # Queue background job
            job_id = self.job_manager.start_job(
                command, user_id, channel_id, self.jaxwatch_root
            )
            response = (
                f"✅ Running locally on JaxWatch. Started {command['description']} "
                f"(ID: {job_id}). I'll report back here when done."
            )
            return {
                'response': response,
                'type': 'background_job',
                'job_id': job_id
            }

        elif command_type == 'cli_execution':
            # Execute immediately
            result = self.job_manager.execute_immediate(command, self.jaxwatch_root)

            if result['status'] == 'success':
                response = f"🔧 Executed locally: {result.get('output', 'Command completed')}"
                response_type = 'immediate_success'
            else:
                response = f"❌ Command failed: {result.get('error', 'Unknown error')}"
                response_type = 'immediate_error'

            return {
                'response': response,
                'type': response_type
            }

        else:
            return {
                'response': f"Unknown command type: {command_type}",
                'type': 'error'
            }