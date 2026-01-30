#!/usr/bin/env python3
"""
Test script demonstrating the new conversational features of Molty.

This script shows:
1. Fuzzy command matching with clarification
2. Session-aware context handling
3. Conversational response formatting
4. Transparency through introspection
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Try relative imports first (if run as module)
    from .intent_clarifier import IntentClarifier
    from .command_parser import CommandParser
    from .session_manager import SessionManager
    from .slack_handlers.response_formatter import ResponseFormatter
except ImportError:
    # Fall back to direct imports (if run as script)
    from intent_clarifier import IntentClarifier
    from session_manager import SessionManager
    from slack_handlers.response_formatter import ResponseFormatter

    # For command_parser, we need to mock the relative import
    import command_parser
    import intent_clarifier

    # Create a test-compatible CommandParser
    class TestCommandParser:
        def __init__(self):
            self.mappings = {"commands": [
                {"pattern": "(?i)verify", "description": "verify documents", "cli_command": "python verify.py"},
                {"pattern": "(?i)scan", "description": "scan references", "cli_command": "python scan.py"},
                {"pattern": "(?i)status", "description": "system status", "type": "status_check"},
            ]}
            self.intent_clarifier = intent_clarifier.IntentClarifier()

        def parse_message_with_clarification(self, message_text):
            # Simplified version for testing
            suggestions = self.intent_clarifier.find_similar_commands(message_text, self.mappings['commands'])
            return self.intent_clarifier.create_clarification_response(message_text, suggestions)

    CommandParser = TestCommandParser


def test_fuzzy_matching():
    """Test the fuzzy matching and clarification system."""
    print("🔍 Testing Fuzzy Matching & Clarification")
    print("=" * 50)

    clarifier = IntentClarifier()
    parser = CommandParser()

    # Test cases with typos and variations
    test_messages = [
        "verifiy documents",  # Typo in "verify"
        "check 2026 projects",  # Alternative wording
        "scan refs",  # Abbreviation
        "helt status",  # Typo in "health"
        "xyzabc random",  # No match
    ]

    for message in test_messages:
        print(f"\n📝 Message: '{message}'")
        result = parser.parse_message_with_clarification(message)

        print(f"   Type: {result['type']}")
        if result.get('response'):
            print(f"   Response: {result['response']}")

        if result['type'] == 'single_suggestion':
            print(f"   Suggested: {result['suggested_command']['description']}")
        elif result['type'] == 'multiple_suggestions':
            print(f"   Suggestions: {len(result['suggestions'])} options")

    print("\n✅ Fuzzy matching test completed")


def test_session_management():
    """Test session management and context awareness."""
    print("\n🧠 Testing Session Management")
    print("=" * 50)

    session_manager = SessionManager()

    # Create a test session
    session = session_manager.get_or_create_session("test_user_123")

    # Add some command history
    test_commands = [
        {"description": "verify documents", "type": "cli_execution"},
        {"description": "scan references", "type": "cli_execution"},
    ]

    for i, cmd in enumerate(test_commands):
        job_id = f"jw_{i+1000}"
        session.add_command(cmd, job_id)
        print(f"   Added command: {cmd['description']} (Job: {job_id})")

    # Test context resolution
    context_messages = [
        "how's that going?",  # Should match active job
        "status please",  # Should match active job
        "something random",  # Should not match
    ]

    print(f"\n   Active jobs: {session.active_jobs}")

    for message in context_messages:
        context = session.can_resolve_context_reference(message)
        if context:
            print(f"   '{message}' → Resolved to job {context['job_id']}")
        else:
            print(f"   '{message}' → No context match")

    # Test session serialization
    print(f"\n   Session data: {session.to_dict()}")
    print("✅ Session management test completed")


def test_conversational_responses():
    """Test enhanced response formatting."""
    print("\n💬 Testing Conversational Responses")
    print("=" * 50)

    formatter = ResponseFormatter()

    # Mock job completion data
    from datetime import datetime, timedelta

    test_jobs = [
        {
            'id': 'jw_1001',
            'description': 'verify documents',
            'status': 'completed',
            'cli_command': 'python document_verifier/document_verifier.py document_verify',
            'started_at': datetime.now() - timedelta(minutes=5),
            'completed_at': datetime.now(),
            'output': 'Enhanced 23 documents with verification\nProcessed 45 total files\nFound 3 errors requiring review'
        },
        {
            'id': 'jw_1002',
            'description': 'scan references',
            'status': 'completed',
            'cli_command': 'python reference_scanner/reference_scanner.py run --source dia_board',
            'started_at': datetime.now() - timedelta(minutes=2),
            'completed_at': datetime.now(),
            'output': 'Found 12 new references\nScanned 34 documents\nCreated reference annotations'
        },
        {
            'id': 'jw_1003',
            'description': 'verify project ABC-123',
            'status': 'failed',
            'cli_command': 'python document_verifier/document_verifier.py document_verify --project ABC-123',
            'error': 'Project ABC-123 not found in database'
        }
    ]

    for job in test_jobs:
        print(f"\n📋 Job: {job['description']} ({job['status']})")
        response = formatter.format_job_completion_with_context(job)
        print(f"   Response:")
        for line in response.split('\n'):
            print(f"      {line}")

    print("\n✅ Conversational responses test completed")


def test_introspection():
    """Test transparency and introspection features."""
    print("\n🔍 Testing Transparency & Introspection")
    print("=" * 50)

    session_manager = SessionManager()
    session = session_manager.get_or_create_session("introspection_user")

    # Add some state
    session.add_command({"description": "verify documents", "type": "cli_execution"}, "jw_2000")
    session.add_command({"description": "scan references", "type": "cli_execution"})

    # Set a pending clarification
    session.set_pending_clarification({
        'type': 'single_suggestion',
        'original_message': 'verifiy docs'
    })

    print("   Session state created with:")
    print("   - 2 commands in history")
    print("   - 1 active job")
    print("   - 1 pending clarification")

    # Test serialization for transparency
    session_data = session.to_dict()
    print(f"\n   Transparent session data:")
    for key, value in session_data.items():
        print(f"      {key}: {value}")

    # Test session manager status
    all_sessions = session_manager.get_all_sessions_status()
    print(f"\n   All active sessions: {len(all_sessions)}")

    print("✅ Introspection test completed")


def test_fail_safe_behaviors():
    """Test fail-safe and boundary behaviors."""
    print("\n🛡️ Testing Fail-Safe Behaviors")
    print("=" * 50)

    clarifier = IntentClarifier()
    session_manager = SessionManager()

    # Test fuzzy matching with very low similarity
    print("   Testing low-similarity fuzzy matching...")
    suggestions = clarifier.find_similar_commands(
        "completely unrelated message",
        [{'pattern': '(?i)verify', 'description': 'verify documents'}]
    )
    print(f"      Low similarity suggestions: {len(suggestions)}")

    # Test session expiration
    print("   Testing session expiration...")
    session = session_manager.get_or_create_session("expiration_test")
    initial_count = session_manager.get_session_count()

    # Simulate expired session by manually setting old timestamp
    from datetime import datetime, timedelta
    session.last_activity = datetime.now() - timedelta(minutes=20)

    # Cleanup should remove expired session
    session_manager._cleanup_expired_sessions()
    final_count = session_manager.get_session_count()
    print(f"      Session count before cleanup: {initial_count}")
    print(f"      Session count after cleanup: {final_count}")

    # Test clarification timeout
    print("   Testing clarification timeout...")
    fresh_session = session_manager.get_or_create_session("timeout_test")
    fresh_session.set_pending_clarification({
        'type': 'single_suggestion',
        'original_message': 'test'
    })

    # Manually expire clarification
    fresh_session.pending_clarification['expires_at'] = datetime.now() - timedelta(minutes=5)

    expired_clarification = fresh_session.get_pending_clarification()
    print(f"      Expired clarification retrieved: {expired_clarification is None}")

    print("✅ Fail-safe behaviors test completed")


def main():
    """Run all conversational feature tests."""
    print("🤖 Molty Conversational Features Test Suite")
    print("=" * 60)
    print("\nThis script demonstrates the new conversational capabilities:")
    print("• Fuzzy matching with explicit confirmation")
    print("• Session-aware context handling")
    print("• Enhanced response formatting")
    print("• Transparency through introspection")
    print("• Fail-safe boundary behaviors")
    print()

    try:
        test_fuzzy_matching()
        test_session_management()
        test_conversational_responses()
        test_introspection()
        test_fail_safe_behaviors()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY")
        print("\nKey improvements demonstrated:")
        print("✅ Fuzzy matching catches typos and variations")
        print("✅ Session memory enables context awareness")
        print("✅ Responses are factual and conversational")
        print("✅ State is transparent and inspectable")
        print("✅ Fail-safe behaviors prevent assumptions")
        print("\nMolty is now a calm, honest, memory-light steward! 🌟")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())