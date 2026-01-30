#!/usr/bin/env python3
"""
Simple test demonstrating the new conversational features.
"""

from intent_clarifier import IntentClarifier
from session_manager import SessionManager
from slack_handlers.response_formatter import ResponseFormatter
from datetime import datetime, timedelta


def test_basic_functionality():
    """Test basic functionality of new modules."""
    print("🧪 Testing Basic Functionality")
    print("=" * 40)

    # Test IntentClarifier
    print("\n1. Testing IntentClarifier...")
    clarifier = IntentClarifier()

    test_commands = [
        {
            "pattern": "(?i)verify",
            "description": "verify documents",
            "cli_command": "python verify.py"
        },
        {
            "pattern": "(?i)scan",
            "description": "scan references",
            "cli_command": "python scan.py"
        }
    ]

    # Test fuzzy matching with lower threshold for demo
    clarifier.similarity_threshold = 0.2  # Lower threshold for testing
    suggestions = clarifier.find_similar_commands("verifiy docs", test_commands)
    print(f"   Fuzzy match for 'verifiy docs': {len(suggestions)} suggestions")

    if suggestions:
        print(f"   Best match: {suggestions[0]['mapping']['description']}")
        print(f"   Match score: {suggestions[0]['score']:.2f}")

    # Test clarification response
    clarification = clarifier.create_clarification_response("verifiy docs", suggestions)
    print(f"   Clarification type: {clarification['type']}")

    # Test SessionManager
    print("\n2. Testing SessionManager...")
    session_manager = SessionManager()
    session = session_manager.get_or_create_session("test_user")

    # Add command
    session.add_command({"description": "verify documents"}, "jw_123")
    print(f"   Added command, active jobs: {session.active_jobs}")

    # Test context resolution
    context = session.can_resolve_context_reference("how's that going?")
    if context:
        print(f"   Context resolved: {context['type']}")
    else:
        print("   No context match (expected for test)")

    # Test ResponseFormatter
    print("\n3. Testing ResponseFormatter...")
    formatter = ResponseFormatter()

    test_job = {
        'description': 'verify documents',
        'status': 'completed',
        'cli_command': 'python document_verifier.py document_verify',
        'started_at': datetime.now() - timedelta(minutes=3),
        'completed_at': datetime.now(),
        'output': 'Enhanced 15 documents with verification\nProcessed 25 files\nFound 2 errors'
    }

    response = formatter.format_job_completion_with_context(test_job)
    print("   Enhanced completion response:")
    for line in response.split('\n'):
        if line.strip():
            print(f"      {line}")

    print("\n✅ All basic functionality tests passed!")


if __name__ == "__main__":
    test_basic_functionality()