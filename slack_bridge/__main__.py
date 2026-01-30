#!/usr/bin/env python3
"""
JaxWatch Slack Bridge - Simplified Entry Point

Uses ConversationalSlackGateway (Claude-powered) by default.
Legacy SlackGateway (regex-based) is deprecated.

Architecture (Simplified):
Slack Message → ConversationalSlackGateway → JaxWatchCore API → Response

Usage:
    python -m slack_bridge [--legacy]

Environment Variables Required:
    SLACK_BOT_TOKEN - Slack bot token
    SLACK_APP_TOKEN - Slack app token (for Socket Mode)
    ANTHROPIC_API_KEY - Claude API key (optional, enables AI features)
"""

import os
import sys
import argparse
import warnings
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_files = [
        Path('.env'),
        Path('../.env'),
        Path(__file__).parent / '.env',
        Path(__file__).parent.parent / '.env'
    ]

    for env_file in env_files:
        if env_file.exists():
            print(f"📄 Loading environment from {env_file}")
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Remove quotes if present
                            value = value.strip('"\'')
                            os.environ[key.strip()] = value
                            print(f"✅ Loaded {key.strip()}")
                return True
            except Exception as e:
                print(f"⚠️ Error reading {env_file}: {e}")

    return False

def main():
    # Load .env file first
    load_env_file()
    parser = argparse.ArgumentParser(description="JaxWatch Slack Bridge")
    parser.add_argument(
        '--legacy',
        action='store_true',
        help='Use legacy SlackGateway (deprecated, regex-based)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Check required environment variables
    required_env = ['SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN']
    missing_env = [var for var in required_env if not os.getenv(var)]

    if missing_env:
        print("❌ Missing required environment variables:")
        for var in missing_env:
            print(f"   - {var}")
        print("\nPlease set these environment variables and try again.")
        sys.exit(1)

    # Optional Claude API key
    claude_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not claude_api_key and not args.legacy:
        print("⚠️  ANTHROPIC_API_KEY not set - AI features will be limited")
        print("   Set ANTHROPIC_API_KEY for full conversational capabilities")

    if args.legacy:
        # Use deprecated legacy gateway
        print("⚠️  Using DEPRECATED legacy SlackGateway")
        print("   Please migrate to ConversationalSlackGateway for better functionality")

        warnings.warn(
            "Legacy SlackGateway is deprecated. Use ConversationalSlackGateway instead.",
            DeprecationWarning,
            stacklevel=2
        )

        from slack_bridge.slack_gateway import SlackGateway

        gateway = SlackGateway()
        print("🔗 Starting legacy Slack gateway...")

    else:
        # Use modern conversational gateway
        print("🚀 Starting ConversationalSlackGateway...")
        print("   Enhanced with Claude-powered natural language understanding")

        from slack_bridge.conversational_slack_gateway import ConversationalSlackGateway

        gateway = ConversationalSlackGateway()

    # Set debug mode if requested
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        print("🐛 Debug logging enabled")

    try:
        print("✅ Gateway initialized successfully")
        print("🔌 Starting Socket Mode connection...")
        print("📱 Ready to receive Slack messages")
        print("⏹️  Press Ctrl+C to stop")

        # Start the gateway
        gateway.start()

    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()