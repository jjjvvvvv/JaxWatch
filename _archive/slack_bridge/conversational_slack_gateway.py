#!/usr/bin/env python3
"""
Conversational Slack Gateway for JaxWatch Integration

Enhanced gateway that uses LLM-powered conversational AI for natural language
understanding while maintaining all civic integrity safeguards.
"""

import os
import sys
import yaml
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from slack_sdk import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Add parent directory to path for JaxWatch imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    # Try relative imports first (when run as module)
    from .conversational_agent import ConversationalCivicAgent, create_conversational_agent
    from .job_manager import JobManager
    from .status_collector import StatusCollector
    from .session_manager import SessionManager
    from .proactive_monitor import create_proactive_monitor
except ImportError:
    # Fall back to absolute imports (when run as script)
    from conversational_agent import ConversationalCivicAgent, create_conversational_agent
    from job_manager import JobManager
    from status_collector import StatusCollector
    from session_manager import SessionManager
    from proactive_monitor import create_proactive_monitor

# Import JaxWatch Core API
from jaxwatch.api import JaxWatchCore


class ConversationalSlackGateway:
    """
    Slack integration with full conversational AI capabilities.

    This gateway replaces regex-based command parsing with Claude-powered
    natural language understanding while maintaining civic integrity boundaries.
    """

    def __init__(self, slack_token: str = None, slack_signing_secret: str = None,
                 app_token: str = None, claude_api_key: str = None):
        """
        Initialize conversational Slack gateway.

        Args:
            slack_token: Slack bot token (or from SLACK_BOT_TOKEN env)
            slack_signing_secret: Slack signing secret (or from SLACK_SIGNING_SECRET env)
            app_token: Slack app token for Socket Mode (or from SLACK_APP_TOKEN env)
            claude_api_key: Claude API key (or from ANTHROPIC_API_KEY env)
        """
        # Get credentials from environment if not provided
        self.slack_token = slack_token or os.getenv('SLACK_BOT_TOKEN')
        self.app_token = app_token or os.getenv('SLACK_APP_TOKEN')
        self.claude_api_key = claude_api_key or os.getenv('ANTHROPIC_API_KEY')

        # Socket Mode configuration
        self.is_socket_mode = bool(self.app_token)

        if self.is_socket_mode:
            self.slack_signing_secret = None
        else:
            self.slack_signing_secret = slack_signing_secret or os.getenv('SLACK_SIGNING_SECRET')

        if not self.slack_token:
            raise ValueError("SLACK_BOT_TOKEN is required")

        # Initialize Slack app
        self.app = App(
            token=self.slack_token,
            signing_secret=self.slack_signing_secret
        )

        # Get JaxWatch root directory
        self.jaxwatch_root = self._get_jaxwatch_root()

        # Initialize JaxWatch Core API
        self.jaxwatch_core = JaxWatchCore()

        # Initialize conversational components
        self.civic_agent = create_conversational_agent(
            str(self.jaxwatch_root), self.claude_api_key
        )

        # Initialize supporting components
        self.session_manager = SessionManager()
        self.job_manager = JobManager(
            slack_app=self.app,
            session_manager=self.session_manager,
            jaxwatch_root=self.jaxwatch_root
        )
        self.status_collector = StatusCollector()

        # Initialize proactive monitoring (optional)
        self.proactive_monitor = None
        if self.claude_api_key:
            try:
                self.proactive_monitor = create_proactive_monitor(
                    str(self.jaxwatch_root), self.claude_api_key
                )
                print("✅ Proactive Monitor: Initialized")
            except Exception as e:
                print(f"⚠️ Proactive Monitor: Disabled ({e})")
                self.proactive_monitor = None

        # Load configuration
        self.config = self._load_config()

        # Set up event handlers
        self._setup_conversational_handlers()

    def _get_jaxwatch_root(self) -> Path:
        """Get JaxWatch root directory with env var fallback."""
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
            return {
                'slack': {
                    'socket_mode': True,
                    'respond_to_mentions': True,
                    'respond_to_dm': True,
                    'respond_to_keywords': ['molty', 'molt'],
                    'conversational_mode': True,
                    'proactive_suggestions': True
                }
            }

    def _setup_conversational_handlers(self):
        """Set up Slack handlers for natural conversation."""

        @self.app.event("app_mention")
        def handle_mention(event, say):
            # Handle mentions synchronously by running async code in thread
            import threading
            import asyncio

            def run_async():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._handle_conversational_message(event, say))
                    loop.close()
                except Exception as e:
                    print(f"Error in mention handler: {e}")

            thread = threading.Thread(target=run_async)
            thread.daemon = True
            thread.start()

        @self.app.event("message")
        def handle_message(event, say):
            # Avoid responding to our own messages or other bots
            if event.get('bot_id') or event.get('subtype') == 'bot_message':
                return

            text = event.get('text', '')
            channel_type = event.get('channel_type')

            should_respond = False

            # Always respond to Direct Messages
            if channel_type == 'im':
                should_respond = True

            # Respond to keywords in public/private channels
            if not should_respond:
                keywords = self.config.get('slack', {}).get('respond_to_keywords', [])
                if any(keyword in text.lower() for keyword in keywords):
                    should_respond = True

            if should_respond:
                # Handle messages synchronously by running async code in thread
                import threading
                import asyncio

                def run_async():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._handle_conversational_message(event, say))
                        loop.close()
                    except Exception as e:
                        print(f"Error in message handler: {e}")

                thread = threading.Thread(target=run_async)
                thread.daemon = True
                thread.start()

    async def _handle_conversational_message(self, event, say):
        """
        Process message through conversational AI.

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

            # Clean message (remove mentions)
            import re
            message_text = re.sub(r'^<@[UW]\w+>\s*', '', message_text)

            # Check if this is a clarification response
            session = self.session_manager.get_or_create_session(user_id)
            pending_clarification = session.get_pending_clarification()

            if pending_clarification:
                # Handle clarification response
                await self._handle_clarification_response(
                    message_text, pending_clarification, session, say, user_id
                )
                return

            # Use conversational agent to understand intent
            civic_intent = await self.civic_agent.understand_civic_intent(message_text, user_id)

            # Send conversational response immediately
            await say(civic_intent.user_response)

            # Execute civic action if needed
            if civic_intent.has_action:
                await self._execute_civic_action(civic_intent, user_id, channel_id, session)
            elif civic_intent.needs_clarification:
                # Store clarification context for follow-up
                session.set_pending_clarification({
                    'type': 'civic_clarification',
                    'context': {
                        'original_message': message_text,
                        'civic_intent': civic_intent.__dict__
                    }
                })

        except Exception as e:
            error_msg = f"I encountered an error processing your message: {str(e)}"
            await say(error_msg)
            print(f"Error in conversational message handling: {e}")

    async def _handle_clarification_response(self, message_text: str, clarification_context: Dict,
                                           session, say, user_id: str):
        """Handle user's response to a clarification request."""
        try:
            # Clear pending clarification first
            session.clear_pending_clarification()

            # Process follow-up with conversational agent
            civic_intent = await self.civic_agent.handle_follow_up(
                message_text, user_id, clarification_context
            )

            # Send response
            await say(civic_intent.user_response)

            # Execute action if needed
            if civic_intent.has_action:
                await self._execute_civic_action(civic_intent, user_id, None, session)

        except Exception as e:
            await say(f"Error processing your response: {str(e)}")

    async def _execute_civic_action(self, civic_intent, user_id: str, channel_id: str, session):
        """
        Execute the civic analysis action using JaxWatch Core API.

        Args:
            civic_intent: CivicIntent with action to execute
            user_id: Slack user ID
            channel_id: Slack channel ID
            session: User session object
        """
        try:
            if civic_intent.action_type == 'status_check':
                # Execute status check immediately using Core API
                stats = self.jaxwatch_core.get_project_stats()
                job_summary = self.status_collector.get_job_summary(self.job_manager)

                status_response = f"""📊 JaxWatch Status (Core API):
🗂️ Total Projects: {stats.get('total_projects', 0)}
✅ Verified: {stats.get('verified_projects', 0)}
📋 Pending Review: {stats.get('pending_review', 0)}
🏛️ DIA Resolutions: {stats.get('dia_resolutions', 0)}
🏗️ DDRB Cases: {stats.get('ddrb_cases', 0)}
🔗 With References: {stats.get('with_references', 0)}

{job_summary}"""

                await self.app.client.chat_postMessage(
                    channel=channel_id or user_id,
                    text=status_response
                )
                return

            # Handle quick operations directly with Core API
            if civic_intent.action_type == 'document_verify':
                # Check if this is a quick single-project verification
                project_id = civic_intent.parameters.get('project')
                if project_id:
                    # Quick verification - execute directly
                    await self._execute_quick_verification(
                        civic_intent, user_id, channel_id, session, project_id
                    )
                    return

            # For batch operations or complex tasks, use background jobs
            command = self._build_command_from_intent(civic_intent)

            if command:
                # Start background job
                job_id = self.job_manager.start_job(
                    command, user_id, channel_id, self.jaxwatch_root
                )

                # Record in session
                session.add_command(command, job_id)

                # Send job started confirmation
                await self.app.client.chat_postMessage(
                    channel=channel_id or user_id,
                    text=f"✅ Started {civic_intent.action_description} (Job ID: {job_id})\n🔄 Processing in background - you'll be notified when complete"
                )

        except Exception as e:
            await self.app.client.chat_postMessage(
                channel=channel_id or user_id,
                text=f"❌ Error executing civic action: {str(e)}"
            )

    async def _execute_quick_verification(self, civic_intent, user_id: str, channel_id: str,
                                        session, project_id: str):
        """Execute quick project verification using Core API."""
        try:
            # Send "working on it" message
            await self.app.client.chat_postMessage(
                channel=channel_id or user_id,
                text=f"🔍 Verifying project {project_id}..."
            )

            # Get project details first
            project = self.jaxwatch_core.get_project(project_id)
            if not project:
                await self.app.client.chat_postMessage(
                    channel=channel_id or user_id,
                    text=f"❌ Project {project_id} not found"
                )
                return

            # Run verification
            result = self.jaxwatch_core.verify_documents(project_id=project_id)

            if result.success:
                response = f"""✅ Verification Complete for {project_id}

📋 **Project:** {project.title}
🏛️ **Type:** {project.project.doc_type}
📊 **Status:** Verified
🔍 **Processed:** {result.projects_processed} project(s)

The verification data has been saved and is available in the dashboard."""
            else:
                response = f"""❌ Verification Failed for {project_id}

**Errors:** {', '.join(result.errors)}"""

            await self.app.client.chat_postMessage(
                channel=channel_id or user_id,
                text=response
            )

        except Exception as e:
            await self.app.client.chat_postMessage(
                channel=channel_id or user_id,
                text=f"❌ Error during quick verification: {str(e)}"
            )

    def _build_command_from_intent(self, civic_intent) -> Optional[Dict]:
        """
        Build CLI command from civic intent.

        Args:
            civic_intent: CivicIntent with action details

        Returns:
            Command dictionary for job manager
        """
        if civic_intent.action_type == 'document_verify':
            cmd_parts = ['python', 'document_verifier/document_verifier.py', 'document_verify']

            # Add parameters from intent
            for key, value in civic_intent.parameters.items():
                if key == 'project':
                    cmd_parts.extend(['--project', str(value)])
                elif key == 'active-year':
                    cmd_parts.extend(['--active-year', str(value)])
                elif key == 'document-type':
                    cmd_parts.extend(['--document-type', str(value)])

            return {
                'type': 'cli_execution',
                'cli_command': ' '.join(cmd_parts),
                'description': civic_intent.action_description or 'Document verification',
                'background': True
            }

        elif civic_intent.action_type == 'reference_scan':
            cmd_parts = ['python', 'reference_scanner/reference_scanner.py', 'run']

            # Add parameters from intent
            source = civic_intent.parameters.get('source', 'dia_board')
            cmd_parts.extend(['--source', source])

            for key, value in civic_intent.parameters.items():
                if key == 'year':
                    cmd_parts.extend(['--year', str(value)])
                elif key == 'project':
                    cmd_parts.extend(['--project', str(value)])

            return {
                'type': 'cli_execution',
                'cli_command': ' '.join(cmd_parts),
                'description': civic_intent.action_description or 'Reference scanning',
                'background': True
            }

        return None

    async def start_proactive_monitoring(self):
        """Start proactive document monitoring in the background."""
        if self.proactive_monitor:
            print("🔍 Starting proactive civic document monitoring...")

            # Run proactive monitoring in background
            asyncio.create_task(
                self.proactive_monitor.monitor_civic_activity(check_interval_minutes=5)
            )

            # Register notification users (could be extended to track active users)
            # For now, this is a placeholder for future notification features

    def start(self, socket_mode: bool = None, enable_proactive: bool = True):
        """
        Start the conversational Slack gateway.

        Args:
            socket_mode: Whether to use Socket Mode
            enable_proactive: Whether to enable proactive monitoring
        """
        # Auto-detect socket mode
        if socket_mode is None:
            socket_mode = self.is_socket_mode

        print("🤖 Starting JaxWatch Conversational Slack Gateway")

        # Verify connection and get bot identity
        try:
            auth_info = self.app.client.auth_test()
            bot_user_id = auth_info["user_id"]
            bot_name = auth_info["user"]
            print(f"   Bot Identity: {bot_name} ({bot_user_id})")
        except Exception as e:
            print(f"   ⚠️ Could not verify bot identity: {e}")

        print(f"   Mode: {'Socket Mode' if socket_mode else 'HTTP Mode'}")
        print(f"   JaxWatch Root: {self.jaxwatch_root}")
        print(f"   Conversational AI: {'✅ Claude Available' if self.civic_agent.claude_available else '⚠️ Fallback Mode'}")
        print(f"   Proactive Monitor: {'✅ Enabled' if self.proactive_monitor else '❌ Disabled'}")

        # Start proactive monitoring if enabled (disabled for now due to async issues)
        if enable_proactive and self.proactive_monitor:
            print("   Proactive Monitor: Temporarily disabled (async compatibility)")

        print("   Ready for natural conversation!")

        if socket_mode:
            if not self.app_token:
                raise ValueError("SLACK_APP_TOKEN is required for Socket Mode")

            handler = SocketModeHandler(self.app, self.app_token)
            handler.start()
        else:
            port = self.config.get('slack', {}).get('port', 3000)
            self.app.start(port=port)

    def test_connection(self):
        """Test Slack API connection and conversational components."""
        try:
            # Test Slack connection
            response = self.app.client.auth_test()
            print("✅ Slack connection successful!")
            print(f"   Bot User ID: {response['user_id']}")
            print(f"   Team: {response['team']}")

            # Test conversational agent
            print(f"✅ Conversational AI: {'Claude Available' if self.civic_agent.claude_available else 'Fallback Mode'}")

            # Test proactive monitoring
            if self.proactive_monitor:
                print("✅ Proactive monitoring available")
            else:
                print("⚠️ Proactive monitoring not available (no Claude API key)")

            return True

        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False

    async def test_conversational_intent(self, test_message: str = "verify documents") -> Dict:
        """
        Test conversational intent understanding.

        Args:
            test_message: Message to test with

        Returns:
            Intent parsing results
        """
        print(f"Testing conversational intent with: '{test_message}'")

        try:
            civic_intent = await self.civic_agent.understand_civic_intent(test_message, "test_user")

            result = {
                'input_message': test_message,
                'action_type': civic_intent.action_type,
                'parameters': civic_intent.parameters,
                'response': civic_intent.user_response,
                'needs_clarification': civic_intent.needs_clarification,
                'confidence': civic_intent.confidence
            }

            print("✅ Intent understanding test successful:")
            for key, value in result.items():
                print(f"   {key}: {value}")

            return result

        except Exception as e:
            print(f"❌ Intent understanding test failed: {e}")
            return {'error': str(e)}


def main():
    """Main entry point for conversational Slack gateway."""
    import argparse

    parser = argparse.ArgumentParser(description="JaxWatch Conversational Slack Gateway")
    parser.add_argument('--test-connection', action='store_true',
                       help='Test Slack API connection and exit')
    parser.add_argument('--test-intent', metavar='MESSAGE',
                       help='Test conversational intent understanding with a message')
    parser.add_argument('--socket-mode', action='store_true',
                       help='Use Socket Mode instead of HTTP')
    parser.add_argument('--http-mode', action='store_true',
                       help='Use HTTP Mode instead of Socket Mode')
    parser.add_argument('--disable-proactive', action='store_true',
                       help='Disable proactive document monitoring')

    args = parser.parse_args()

    try:
        # Determine socket mode preference
        forced_socket_mode = None
        if args.http_mode:
            forced_socket_mode = False
        elif args.socket_mode:
            forced_socket_mode = True

        gateway = ConversationalSlackGateway()

        if args.test_connection:
            gateway.test_connection()
            return

        if args.test_intent:
            asyncio.run(gateway.test_conversational_intent(args.test_intent))
            return

        # Start the gateway
        enable_proactive = not args.disable_proactive
        gateway.start(socket_mode=forced_socket_mode, enable_proactive=enable_proactive)

    except KeyboardInterrupt:
        print("\n👋 Shutting down conversational Slack gateway...")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())