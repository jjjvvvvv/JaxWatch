#!/usr/bin/env python3
"""
Slack Gateway for JaxWatch Integration

Main entry point for Slack-first molt.bot integration.
Acts as command router + job orchestrator + status reporter.
NO analysis - all processing delegated to JaxWatch CLI tools.
"""

import os
import yaml
import re
from pathlib import Path
from datetime import datetime
from typing import Dict
from slack_sdk import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

try:
    # Try relative imports first (when run as module)
    from .command_parser import CommandParser
    from .job_manager import JobManager
    from .status_collector import StatusCollector
    from .session_manager import SessionManager
except ImportError:
    # Fall back to absolute imports (when run as script)
    from command_parser import CommandParser
    from job_manager import JobManager
    from status_collector import StatusCollector
    from session_manager import SessionManager


class SlackGateway:
    """
    Main Slack integration gateway.

    Architecture: Slack → molt.bot (gateway only) → JaxWatch CLI → Local Analysis → Results

    molt.bot role: Command router + job orchestrator + status reporter (NO analysis)
    JaxWatch role: All document processing, AI operations, data storage
    """

    def __init__(self, slack_token: str = None, slack_signing_secret: str = None,
                 app_token: str = None):
        """
        Initialize Slack gateway.

        Args:
            slack_token: Slack bot token (or from SLACK_BOT_TOKEN env)
            slack_signing_secret: Slack signing secret (or from SLACK_SIGNING_SECRET env)
            app_token: Slack app token for Socket Mode (or from SLACK_APP_TOKEN env)
        """
        # Get credentials from environment if not provided
        self.slack_token = slack_token or os.getenv('SLACK_BOT_TOKEN')
        self.app_token = app_token or os.getenv('SLACK_APP_TOKEN')
        
        # Decide if we are in Socket Mode early to handle signing_secret correctly
        # Socket Mode is preferred if app_token is provided
        self.is_socket_mode = bool(self.app_token)
        
        # If Socket Mode, we explicitly do NOT want to use signing_secret
        if self.is_socket_mode:
            self.slack_signing_secret = None
        else:
            self.slack_signing_secret = slack_signing_secret or os.getenv('SLACK_SIGNING_SECRET')

        if not self.slack_token:
            raise ValueError("SLACK_BOT_TOKEN is required")

        # Initialize Slack app - signing_secret is omitted for Socket Mode
        # to prevent unnecessary signature verification middleware
        self.app = App(
            token=self.slack_token, 
            signing_secret=self.slack_signing_secret
        )

        # Initialize components
        self.command_parser = CommandParser()
        self.session_manager = SessionManager()
        self.job_manager = JobManager(slack_app=self.app, session_manager=self.session_manager)
        self.status_collector = StatusCollector()

        # Robust working directory resolution
        self.jaxwatch_root = self._get_jaxwatch_root()

        # Load configuration
        self.config = self._load_config()

        # Set up event handlers
        self._setup_handlers()

    def _get_jaxwatch_root(self) -> Path:
        """Get JaxWatch root directory with env var fallback."""
        # Try environment variable first
        env_path = os.getenv('JAXWATCH_ROOT')
        if env_path and Path(env_path).exists():
            return Path(env_path)

        # Fallback: assume slack_bridge is in JaxWatch root
        return Path(__file__).parents[1]

    def _load_config(self) -> dict:
        """Load Slack bridge configuration."""
        config_path = Path(__file__).parent / "config" / "slack_config.yml"
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except (FileNotFoundError, yaml.YAMLError):
            # Return default config
            return {
                'slack': {
                    'socket_mode': True,
                    'respond_to_mentions': True,
                    'respond_to_dm': True,
                    'respond_to_keywords': ['molty', 'molt']
                }
            }

    def _setup_handlers(self):
        """Set up Slack event handlers."""
        # Handle app mentions - critical for bot interaction in channels
        @self.app.event("app_mention")
        def handle_app_mention(event, say):
            self._handle_message(event, say)

        # Handle message events for DMs and keywords
        @self.app.event("message")
        def handle_message(event, say):
            # Avoid responding to our own messages or other bots
            if event.get('bot_id') or event.get('subtype') == 'bot_message':
                return

            text = event.get('text', '')
            channel_type = event.get('channel_type')
            
            # 1. Always respond to Direct Messages
            if channel_type == 'im':
                self._handle_message(event, say)
                return

            # 2. Respond to keywords in public/private channels
            keywords = self.config.get('slack', {}).get('respond_to_keywords', [])
            if any(keyword in text.lower() for keyword in keywords):
                self._handle_message(event, say)

    def _handle_message(self, event, say):
        """
        Handle incoming Slack message with fuzzy matching and session awareness.

        Args:
            event: Slack event data
            say: Slack say function for responses
        """
        try:
            message_text = event.get('text', '').strip()
            user_id = event.get('user', '')
            channel_id = event.get('channel', '')

            if not message_text:
                return

            # Get or create user session
            session = self.session_manager.get_or_create_session(user_id)

            # Check for pending clarification response first
            pending_clarification = session.get_pending_clarification()
            if pending_clarification:
                return self._handle_clarification_response(
                    message_text, pending_clarification, session, say
                )

            # Check for context references (like "how's that going?")
            context_command = session.can_resolve_context_reference(message_text)
            if context_command:
                return self._handle_context_reference(context_command, session, say)

            # Try exact command parsing first
            parse_result = self.command_parser.parse_message_with_clarification(message_text)

            if parse_result['type'] == 'exact_match':
                # Execute exact match immediately
                command = parse_result['command']
                return self._execute_command(command, user_id, channel_id, session, say)

            elif parse_result['type'] in ['single_suggestion', 'multiple_suggestions']:
                # Store clarification context and respond
                session.set_pending_clarification(parse_result)
                say(parse_result['response'])
                return

            elif parse_result['type'] == 'no_matches':
                # Only reply for DMs or explicit mentions to avoid channel noise
                is_dm = event.get('channel_type') == 'im'
                is_mention = event.get('type') == 'app_mention'

                if is_dm or is_mention:
                    say(parse_result['response'])
                return

            else:
                # Fallback - should not reach here
                if event.get('channel_type') == 'im' or event.get('type') == 'app_mention':
                    say("🤔 I don't understand that command. Try 'help' for available commands.")

        except Exception as e:
            error_msg = f"💥 Error processing command: {str(e)}"
            say(error_msg)

    def _handle_clarification_response(self, message_text: str, clarification_context: Dict,
                                     session, say) -> None:
        """Handle user's response to a clarification request."""
        try:
            response_result = self.command_parser.parse_clarification_response(
                message_text, clarification_context
            )

            if response_result is None:
                # User cancelled
                session.clear_pending_clarification()
                say("👍 Cancelled.")
                return

            if response_result.get('type') == 'invalid_response':
                # Invalid response - ask again but don't clear context
                say(response_result['message'])
                return

            # Valid selection - build and execute command
            session.clear_pending_clarification()

            # Build command from selected mapping
            command = self.command_parser.build_command_from_mapping(
                response_result, clarification_context.get('original_message')
            )

            # Execute the confirmed command
            user_id = session.user_id
            channel_id = None  # Will be available in event context if needed
            self._execute_command(command, user_id, channel_id, session, say)

        except Exception as e:
            session.clear_pending_clarification()
            say(f"💥 Error processing confirmation: {str(e)}")

    def _handle_context_reference(self, context_command: Dict, session, say) -> None:
        """Handle context-aware references like 'how's that going?'."""
        if context_command['type'] == 'job_status_request':
            job_id = context_command['job_id']
            job = self.job_manager.get_job(job_id)

            if job:
                if job['status'] == 'running':
                    elapsed = datetime.now() - context_command['started_at']
                    elapsed_str = self._format_duration(elapsed)
                    say(f"🔧 Your {context_command['original_command']} is still running (started {elapsed_str} ago).")
                elif job['status'] == 'completed':
                    say(f"✅ Your {context_command['original_command']} finished successfully!")
                else:
                    say(f"❌ Your {context_command['original_command']} failed: {job.get('error', 'Unknown error')}")
            else:
                say("🤔 I couldn't find that job. It may have finished already.")

    def _execute_command(self, command: Dict, user_id: str, channel_id: str, session, say) -> None:
        """Execute a parsed command."""
        # Record command in session
        job_id = None

        if command.get('type') == 'direct_response':
            say(command['response'])

        elif command.get('type') == 'status_check':
            status = self.status_collector.get_system_status(self.jaxwatch_root)
            job_summary = self.status_collector.get_job_summary(self.job_manager)
            response = f"📊 JaxWatch Status (running locally):\n{status}\n\n{job_summary}"
            say(response)

        elif command.get('type') == 'introspection':
            response = self._handle_introspection_command(session)
            say(response)

        elif command.get('background', False):
            # Queue background job
            job_id = self.job_manager.start_job(
                command, user_id, channel_id, self.jaxwatch_root
            )
            response = (
                f"✅ Running locally on JaxWatch. Started {command['description']} "
                f"(ID: {job_id}). I'll report back here when done."
            )
            say(response)

        else:
            # Execute immediately
            result = self.job_manager.execute_immediate(command, self.jaxwatch_root)

            if result['status'] == 'success':
                response = f"🔧 Executed locally: {result.get('output', 'Command completed')}"
            else:
                response = f"❌ Command failed: {result.get('error', 'Unknown error')}"

            say(response)

        # Record command in session
        session.add_command(command, job_id)

    def _handle_introspection_command(self, session) -> str:
        """Show transparent view of Molty's current state."""
        response = "🔍 **Molty State Inspection**\n\n"

        # Session info
        session_data = session.to_dict()
        response += f"**Session Info:**\n"
        response += f"• User: {session.user_id}\n"
        response += f"• Active for: {self._format_duration(datetime.now() - session.last_activity)}\n"
        response += f"• Expires in: {session_data['expires_in_minutes']} minutes\n\n"

        # Active jobs
        if session.active_jobs:
            response += f"**Active Jobs ({len(session.active_jobs)}):**\n"
            for job_id in session.active_jobs:
                job = self.job_manager.get_job(job_id)
                if job:
                    elapsed = datetime.now() - job['started_at']
                    response += f"• {job_id}: {job['description']} (running {self._format_duration(elapsed)})\n"
            response += "\n"
        else:
            response += "**Active Jobs:** None\n\n"

        # Recent commands
        if session.command_history:
            response += f"**Recent Commands ({len(session.command_history)}):**\n"
            for entry in session.command_history[-3:]:  # Show last 3 only
                timestamp = entry['timestamp'].strftime('%H:%M:%S')
                status = entry['status']
                response += f"• {timestamp}: {entry['command']['description']} ({status})\n"
            response += "\n"
        else:
            response += "**Recent Commands:** None\n\n"

        # Pending clarifications
        if session.pending_clarification:
            response += f"**Pending Clarification:**\n"
            original = session.pending_clarification['context'].get('original_message', 'Unknown')
            response += f"• Waiting for response to: '{original}'\n\n"
        else:
            response += "**Pending Clarification:** None\n\n"

        # What Molty can/cannot do
        response += "**Boundaries:**\n"
        response += "• ✅ Execute JaxWatch CLI commands\n"
        response += "• ✅ Track active jobs and provide status\n"
        response += "• ✅ Remember last 3 commands for 15 minutes\n"
        response += "• ✅ Provide fuzzy matching with explicit confirmation\n"
        response += "• ❌ Never analyzes documents directly\n"
        response += "• ❌ Never stores preferences or user profiles\n"
        response += "• ❌ Never executes commands without explicit confirmation\n"
        response += "• ❌ Never auto-executes fuzzy matches\n"

        return response

    def _format_duration(self, duration) -> str:
        """Format duration for human readability."""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def start(self, socket_mode: bool = None):
        """
        Start the Slack gateway.

        Args:
            socket_mode: Whether to use Socket Mode (True) or HTTP mode (False)
        """
        # Automatic detection: If SLACK_APP_TOKEN is present, default to Socket Mode
        # unless explicitly overridden by the socket_mode argument
        if socket_mode is None:
            if self.app_token:
                socket_mode = True
            else:
                socket_mode = self.config.get('slack', {}).get('socket_mode', False)

        print("🤖 Starting JaxWatch Slack Gateway")
        
        # Verify connection and get bot identity
        try:
            auth_info = self.app.client.auth_test()
            bot_user_id = auth_info["user_id"]
            bot_name = auth_info["user"]
            print(f"   Bot Identity: {bot_name} ({bot_user_id})")
        except Exception as e:
            print(f"   ⚠️ Could not verify bot identity: {e}")
            bot_user_id = "unknown"

        print(f"   Mode: {'Socket Mode' if socket_mode else 'HTTP Mode'}")
        print(f"   JaxWatch Root: {self.jaxwatch_root}")

        print(f"   Ready to receive commands!")

        if socket_mode:
            if not self.app_token:
                raise ValueError("SLACK_APP_TOKEN is required for Socket Mode")

            handler = SocketModeHandler(self.app, self.app_token)
            handler.start()
        else:
            port = self.config.get('slack', {}).get('port', 3000)
            self.app.start(port=port)

    def test_connection(self):
        """Test Slack API connection."""
        try:
            # Use the app's client to test
            response = self.app.client.auth_test()

            print("✅ Slack connection successful!")
            print(f"   Bot User ID: {response['user_id']}")
            print(f"   Team: {response['team']}")
            return True

        except Exception as e:
            print(f"❌ Slack connection failed: {e}")
            return False


def main():
    """Main entry point for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="JaxWatch Slack Gateway")
    parser.add_argument('--test-connection', action='store_true',
                       help='Test Slack API connection and exit')
    parser.add_argument('--socket-mode', action='store_true',
                       help='Use Socket Mode instead of HTTP')
    parser.add_argument('--http-mode', action='store_true',
                       help='Use HTTP Mode instead of Socket Mode')

    args = parser.parse_args()

    try:
        # Determine initial socket mode preference from args
        forced_socket_mode = None
        if args.http_mode:
            forced_socket_mode = False
        elif args.socket_mode:
            forced_socket_mode = True

        gateway = SlackGateway()

        if args.test_connection:
            gateway.test_connection()
            return

        gateway.start(socket_mode=forced_socket_mode)

    except KeyboardInterrupt:
        print("\n👋 Shutting down Slack gateway...")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())