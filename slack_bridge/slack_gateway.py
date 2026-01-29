#!/usr/bin/env python3
"""
Slack Gateway for JaxWatch Integration

Main entry point for Slack-first molt.bot integration.
Acts as command router + job orchestrator + status reporter.
NO analysis - all processing delegated to JaxWatch CLI tools.
"""

import os
import yaml
from pathlib import Path
from slack_sdk import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .command_parser import CommandParser
from .job_manager import JobManager
from .status_collector import StatusCollector


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
        self.slack_signing_secret = slack_signing_secret or os.getenv('SLACK_SIGNING_SECRET')
        self.app_token = app_token or os.getenv('SLACK_APP_TOKEN')

        if not self.slack_token:
            raise ValueError("SLACK_BOT_TOKEN is required")

        # Initialize Slack app
        self.app = App(token=self.slack_token, signing_secret=self.slack_signing_secret)

        # Initialize components
        self.command_parser = CommandParser()
        self.job_manager = JobManager(slack_app=self.app)
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
        # Handle app mentions
        @self.app.event("app_mention")
        def handle_app_mention(event, say):
            self._handle_message(event, say)

        # Handle direct messages
        @self.app.event("message")
        def handle_message(event, say):
            # Only respond to DMs or messages with keywords
            if event.get('channel_type') == 'im':
                self._handle_message(event, say)
            elif any(keyword in event.get('text', '').lower()
                    for keyword in self.config.get('slack', {}).get('respond_to_keywords', [])):
                self._handle_message(event, say)

    def _handle_message(self, event, say):
        """
        Handle incoming Slack message.

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

            # Parse command (NO AI, regex only)
            command = self.command_parser.parse_message(message_text)

            if not command:
                response = "🤔 I don't understand that command. Try 'help' for available commands."
                say(response)
                return

            # Execute command based on type
            if command.get('type') == 'direct_response':
                say(command['response'])

            elif command.get('type') == 'status_check':
                status = self.status_collector.get_system_status(self.jaxwatch_root)
                job_summary = self.status_collector.get_job_summary(self.job_manager)

                response = f"📊 JaxWatch Status (running locally):\n{status}\n\n{job_summary}"
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

        except Exception as e:
            error_msg = f"💥 Error processing command: {str(e)}"
            say(error_msg)

    def start(self, socket_mode: bool = None):
        """
        Start the Slack gateway.

        Args:
            socket_mode: Whether to use Socket Mode (True) or HTTP mode (False)
        """
        # Use config default if not specified
        if socket_mode is None:
            socket_mode = self.config.get('slack', {}).get('socket_mode', True)

        print("🤖 Starting JaxWatch Slack Gateway")
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
            client = WebClient(token=self.slack_token)
            response = client.auth_test()

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
        gateway = SlackGateway()

        if args.test_connection:
            gateway.test_connection()
            return

        # Determine mode
        if args.http_mode:
            socket_mode = False
        elif args.socket_mode:
            socket_mode = True
        else:
            socket_mode = None  # Use config default

        gateway.start(socket_mode=socket_mode)

    except KeyboardInterrupt:
        print("\n👋 Shutting down Slack gateway...")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())