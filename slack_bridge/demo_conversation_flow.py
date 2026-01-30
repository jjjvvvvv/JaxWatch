#!/usr/bin/env python3
"""
Demonstration of complete conversational flow in enhanced Molty.
Shows the full user experience from typo to completion.
"""

from intent_clarifier import IntentClarifier
from session_manager import SessionManager
from slack_handlers.response_formatter import ResponseFormatter
from datetime import datetime, timedelta
import time


def simulate_conversation_flow():
    """Simulate a complete conversation flow demonstrating all improvements."""
    print("🤖 Molty Conversational Flow Demonstration")
    print("=" * 55)
    print("\nThis demonstrates the full conversational experience:")
    print("• Fuzzy matching catches typos")
    print("• Session memory provides continuity")
    print("• Rich responses with factual details")
    print("• Transparent state inspection")
    print()

    # Initialize components
    clarifier = IntentClarifier()
    clarifier.similarity_threshold = 0.2  # More lenient for demo
    session_manager = SessionManager()
    formatter = ResponseFormatter()

    # Mock command mappings
    commands = [
        {
            "pattern": "(?i)verify\\s+documents?",
            "description": "verify documents",
            "cli_command": "python document_verifier/document_verifier.py document_verify",
            "background": True
        },
        {
            "pattern": "(?i)scan\\s+references?",
            "description": "scan references",
            "cli_command": "python reference_scanner/reference_scanner.py run",
            "background": True
        },
        {
            "pattern": "(?i)molty\\s+inspect",
            "type": "introspection",
            "description": "Show Molty's current state and memory"
        }
    ]

    session = session_manager.get_or_create_session("demo_user")

    print("🎬 CONVERSATION SIMULATION")
    print("-" * 30)

    # Step 1: User makes typo
    print("\n👤 User: 'verifiy documents'")
    suggestions = clarifier.find_similar_commands("verifiy documents", commands)
    clarification = clarifier.create_clarification_response("verifiy documents", suggestions)

    print("🤖 Molty:")
    print(f"   {clarification['response']}")

    # Step 2: User confirms
    print("\n👤 User: 'yes'")

    if clarification['type'] == 'single_suggestion':
        selected_command = clarification['suggested_command']
        job_id = f"jw_{int(time.time())}"

        # Record command in session
        session.add_command(selected_command, job_id)

        print("🤖 Molty:")
        print(f"   ✅ Running locally on JaxWatch. Started {selected_command['description']} (ID: {job_id}). I'll report back here when done.")

    # Step 3: User asks about progress (context awareness)
    print("\n👤 User: 'how's that going?'")
    context = session.can_resolve_context_reference("how's that going?")

    if context and context['type'] == 'job_status_request':
        print("🤖 Molty:")
        print(f"   🔧 Your {context['original_command']} is still running (started 2 minutes ago).")

    # Step 4: Job completes (rich response)
    print("\n[5 minutes later - job completes]")

    # Mock completed job
    completed_job = {
        'id': job_id,
        'description': 'verify documents',
        'status': 'completed',
        'cli_command': 'python document_verifier/document_verifier.py document_verify',
        'started_at': datetime.now() - timedelta(minutes=5),
        'completed_at': datetime.now(),
        'output': 'Enhanced 23 documents with verification\nProcessed 45 total files\nFound 3 errors requiring review\nCompleted successfully'
    }

    # Update session
    session.mark_job_completed(job_id)

    # Generate rich completion response
    completion_response = formatter.format_job_completion_with_context(completed_job)

    print("🤖 Molty:")
    for line in completion_response.split('\n'):
        if line.strip():
            print(f"   {line}")

    # Step 5: User responds to suggestion
    print("\n👤 User: 'yes, scan those'")
    scan_suggestions = clarifier.find_similar_commands("scan those", commands)

    if scan_suggestions:
        scan_command = scan_suggestions[0]['mapping']
        scan_job_id = f"jw_{int(time.time()) + 1}"
        session.add_command(scan_command, scan_job_id)

        print("🤖 Molty:")
        print(f"   ✅ Running locally on JaxWatch. Started {scan_command['description']} (ID: {scan_job_id}). I'll report back here when done.")

    # Step 6: User requests state inspection (transparency)
    print("\n👤 User: 'molty inspect'")

    # Generate inspection response
    print("🤖 Molty:")
    print("   🔍 **Molty State Inspection**")
    print()
    print("   **Session Info:**")
    print(f"   • User: {session.user_id}")
    print("   • Active for: 7 minutes")
    print("   • Expires in: 8 minutes")
    print()

    if session.active_jobs:
        print(f"   **Active Jobs ({len(session.active_jobs)}):**")
        for job in session.active_jobs:
            print(f"   • {job}: scan references (running 30s)")
        print()

    if session.command_history:
        print(f"   **Recent Commands ({len(session.command_history)}):**")
        for i, entry in enumerate(session.command_history[-3:]):
            timestamp = entry['timestamp'].strftime('%H:%M:%S')
            status = entry['status']
            print(f"   • {timestamp}: {entry['command']['description']} ({status})")
        print()

    print("   **Boundaries:**")
    print("   • ✅ Execute JaxWatch CLI commands")
    print("   • ✅ Track active jobs and provide status")
    print("   • ✅ Remember last 3 commands for 15 minutes")
    print("   • ✅ Provide fuzzy matching with explicit confirmation")
    print("   • ❌ Never analyzes documents directly")
    print("   • ❌ Never stores preferences or user profiles")
    print("   • ❌ Never executes commands without explicit confirmation")

    # Summary
    print("\n" + "=" * 55)
    print("🎉 CONVERSATION FLOW COMPLETE")
    print("\nKey improvements demonstrated:")
    print("✅ Typo caught with fuzzy matching")
    print("✅ Explicit confirmation required")
    print("✅ Context awareness ('how's that going?')")
    print("✅ Rich completion with extracted details")
    print("✅ Optional next step suggestion")
    print("✅ Natural follow-up workflow")
    print("✅ Transparent state inspection")
    print("\nMolty is now conversational while remaining:")
    print("🔒 Deterministic • 🔍 Transparent • 🏠 Local-first • ⚖️ Civically honest")


if __name__ == "__main__":
    simulate_conversation_flow()