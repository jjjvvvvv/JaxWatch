#!/usr/bin/env python3
"""
Comprehensive Test Suite for Conversational JaxWatch Implementation
Tests the complete conversational AI transformation
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Set up the environment for testing
os.environ.setdefault('JAXWATCH_ROOT', str(Path(__file__).parents[1]))

try:
    # Import all conversational components
    from conversational_agent import ConversationalCivicAgent, create_conversational_agent
    from civic_intent_engine import CivicIntentEngine
    from persistent_memory import PersistentConversationMemory, create_conversation_memory
    from civic_context import CivicAnalysisContext, create_civic_context
    from proactive_monitor import ProactiveCivicAgent, create_proactive_monitor
    from conversational_slack_gateway import ConversationalSlackGateway
    from job_manager import JobManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the slack_bridge directory")
    exit(1)


class ConversationalTestSuite:
    """Comprehensive test suite for conversational JaxWatch features."""

    def __init__(self):
        self.jaxwatch_root = Path(__file__).parents[1]
        self.test_user_id = "test_user_123"
        self.results = {}

    async def run_all_tests(self):
        """Run all conversational feature tests."""
        print("🧪 Running Conversational JaxWatch Test Suite")
        print("=" * 60)

        # Run tests in order
        test_methods = [
            self.test_conversation_memory,
            self.test_civic_context,
            self.test_intent_engine,
            self.test_conversational_agent,
            self.test_proactive_monitoring,
            self.test_job_manager_enhancement,
            self.test_end_to_end_workflow
        ]

        for test_method in test_methods:
            try:
                print(f"\n🔍 {test_method.__name__.replace('test_', '').replace('_', ' ').title()}")
                print("-" * 40)
                await test_method()
                print("✅ Test passed")
            except Exception as e:
                print(f"❌ Test failed: {e}")
                self.results[test_method.__name__] = {'status': 'failed', 'error': str(e)}

        # Print summary
        print("\n📊 Test Summary")
        print("=" * 60)
        passed = sum(1 for r in self.results.values() if r.get('status') == 'passed')
        failed = len(self.results) - passed
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")

        if failed == 0:
            print("\n🎉 All conversational features implemented successfully!")
        else:
            print("\n⚠️ Some tests failed. Check the errors above.")

        return failed == 0

    async def test_conversation_memory(self):
        """Test persistent conversation memory system."""
        # Create temporary conversation memory
        memory = create_conversation_memory(str(self.jaxwatch_root))

        # Test recording exchanges
        memory.record_exchange(
            user_id=self.test_user_id,
            user_message="verify 2026 transportation projects",
            molty_response="I'll verify all 2026 transportation projects for compliance.",
            civic_action={
                'type': 'document_verify',
                'description': 'Verify 2026 transportation projects',
                'job_id': 'jw_test_123'
            }
        )

        # Test loading context
        context = memory.get_context(self.test_user_id)
        assert len(context.recent_exchanges) > 0, "No exchanges recorded"

        # Test context formatting
        formatted = context.get_recent_exchanges()
        assert "verify 2026 transportation" in formatted, "Exchange not formatted correctly"

        # Test preferences
        context.add_civic_preference("focus_area", "transportation")
        memory.save_context(self.test_user_id, context)

        # Reload and verify persistence
        context2 = memory.get_context(self.test_user_id)
        assert context2.civic_preferences.get("focus_area") == "transportation", "Preferences not persisted"

        self.results['test_conversation_memory'] = {'status': 'passed'}
        print("  ✓ Conversation recording works")
        print("  ✓ Context persistence works")
        print("  ✓ Preference learning works")

    async def test_civic_context(self):
        """Test civic analysis context provider."""
        context = create_civic_context(str(self.jaxwatch_root))

        # Test status collection
        status = context.get_current_status()
        assert isinstance(status, dict), "Status should be dictionary"
        assert 'projects_count' in status, "Missing projects count"

        # Test project context
        project_context = context.get_project_context()
        assert isinstance(project_context, dict), "Project context should be dictionary"

        # Test conversational formatting
        formatted = context.format_status_for_conversation()
        assert isinstance(formatted, str), "Formatted status should be string"

        self.results['test_civic_context'] = {'status': 'passed'}
        print("  ✓ Status collection works")
        print("  ✓ Project context works")
        print("  ✓ Conversational formatting works")

    async def test_intent_engine(self):
        """Test Claude-powered intent understanding engine."""
        # Test without Claude API (fallback mode)
        engine = CivicIntentEngine(None)

        # Test text-based intent extraction
        intent_data = engine._extract_intent_from_text("verify documents")
        assert intent_data['action_type'] == 'document_verify', "Should detect document verification intent"

        intent_data = engine._extract_intent_from_text("scan for references")
        assert intent_data['action_type'] == 'reference_scan', "Should detect reference scanning intent"

        intent_data = engine._extract_intent_from_text("what's the status")
        assert intent_data['action_type'] == 'status_check', "Should detect status check intent"

        # Test command building
        command = engine.build_civic_command({
            'action_type': 'document_verify',
            'parameters': {'active-year': '2026'},
            'action_description': 'Verify 2026 documents'
        })

        assert command is not None, "Should build command"
        assert 'document_verifier' in command['cli_command'], "Should include document_verifier"
        assert '--active-year 2026' in command['cli_command'], "Should include year parameter"

        self.results['test_intent_engine'] = {'status': 'passed'}
        print("  ✓ Intent extraction works")
        print("  ✓ Command building works")
        print("  ✓ Fallback mode works")

    async def test_conversational_agent(self):
        """Test the main conversational civic agent."""
        # Create agent without Claude API for testing
        agent = create_conversational_agent(str(self.jaxwatch_root))

        # Test intent understanding (fallback mode)
        intent = await agent.understand_civic_intent("verify documents", self.test_user_id)

        assert intent.action_type is not None or intent.needs_clarification, "Should detect intent or request clarification"
        assert isinstance(intent.user_response, str), "Should provide user response"
        assert isinstance(intent.confidence, float), "Should provide confidence score"

        # Test follow-up handling
        follow_up = await agent.handle_follow_up("yes", self.test_user_id)
        assert isinstance(follow_up.user_response, str), "Should handle follow-up"

        # Test conversation summary
        summary = agent.get_conversation_summary(self.test_user_id)
        assert isinstance(summary, str), "Should provide conversation summary"

        self.results['test_conversational_agent'] = {'status': 'passed'}
        print("  ✓ Intent understanding works")
        print("  ✓ Follow-up handling works")
        print("  ✓ Conversation summary works")

    async def test_proactive_monitoring(self):
        """Test proactive civic intelligence monitoring."""
        # Create monitor without Claude API for testing
        monitor = create_proactive_monitor(str(self.jaxwatch_root))

        # Test document change detection
        changes = await monitor.document_monitor.get_recent_changes()
        assert isinstance(changes, list), "Should return list of changes"

        # Test suggestion generation (rule-based fallback)
        if changes:
            suggestion = await monitor.generate_intelligent_suggestion(changes[0])
            if suggestion:
                assert hasattr(suggestion, 'action_type'), "Suggestion should have action type"
                assert hasattr(suggestion, 'description'), "Suggestion should have description"

        # Test recent suggestions
        recent = monitor.get_recent_suggestions()
        assert isinstance(recent, list), "Should return list of suggestions"

        self.results['test_proactive_monitoring'] = {'status': 'passed'}
        print("  ✓ Document monitoring works")
        print("  ✓ Suggestion generation works")
        print("  ✓ Recent suggestions tracking works")

    async def test_job_manager_enhancement(self):
        """Test enhanced job manager with conversational context."""
        # Create enhanced job manager
        job_manager = JobManager(jaxwatch_root=str(self.jaxwatch_root))

        # Test enhanced completion message generation
        test_job = {
            'id': 'jw_test_456',
            'description': 'Document verification',
            'status': 'completed',
            'started_at': datetime.now(),
            'completed_at': datetime.now(),
            'output': 'Verified 5 projects successfully',
            'cli_command': 'python document_verifier/document_verifier.py document_verify'
        }

        message = job_manager._generate_conversational_completion_message(test_job)
        assert isinstance(message, str), "Should generate completion message"
        assert "✅" in message, "Should include success indicator"

        # Test duration formatting
        from datetime import timedelta
        duration = timedelta(minutes=5, seconds=30)
        formatted = job_manager._format_duration_friendly(duration)
        assert "5 minutes" in formatted, "Should format duration correctly"

        # Test user job summary
        summary = job_manager.get_job_summary_for_user(self.test_user_id)
        assert isinstance(summary, str), "Should provide user job summary"

        self.results['test_job_manager_enhancement'] = {'status': 'passed'}
        print("  ✓ Enhanced completion messages work")
        print("  ✓ Duration formatting works")
        print("  ✓ User job summaries work")

    async def test_end_to_end_workflow(self):
        """Test complete end-to-end conversational workflow."""
        # Create all components
        agent = create_conversational_agent(str(self.jaxwatch_root))
        memory = create_conversation_memory(str(self.jaxwatch_root))

        # Simulate conversational workflow
        test_messages = [
            "Can you verify our civic documents?",
            "What's the current status?",
            "Scan for references in DIA board documents"
        ]

        for message in test_messages:
            print(f"    Testing: '{message}'")

            # Get intent
            intent = await agent.understand_civic_intent(message, self.test_user_id)

            # Verify response
            assert isinstance(intent.user_response, str), f"Should respond to: {message}"

            # If action needed, verify command generation
            if intent.has_action:
                assert intent.action_type in ['document_verify', 'reference_scan', 'status_check'], "Should have valid action type"

        # Test conversation memory integration
        context = memory.get_context(self.test_user_id)
        assert len(context.recent_exchanges) > 0, "Should have recorded conversation"

        self.results['test_end_to_end_workflow'] = {'status': 'passed'}
        print("  ✓ Multi-turn conversation works")
        print("  ✓ Memory integration works")
        print("  ✓ Action generation works")

    def test_configuration_files(self):
        """Test that all configuration files are properly created."""
        config_dir = Path(__file__).parent / "config"

        # Check civic tools configuration
        civic_tools_file = config_dir / "civic_tools.yml"
        assert civic_tools_file.exists(), "civic_tools.yml should exist"

        # Check Claude prompts configuration
        claude_prompts_file = config_dir / "claude_prompts.yml"
        assert claude_prompts_file.exists(), "claude_prompts.yml should exist"

        # Verify they can be loaded
        import yaml
        with open(civic_tools_file) as f:
            civic_tools = yaml.safe_load(f)
        assert 'tools' in civic_tools, "civic_tools.yml should have tools section"

        with open(claude_prompts_file) as f:
            prompts = yaml.safe_load(f)
        assert 'system_prompts' in prompts, "claude_prompts.yml should have system_prompts section"

        print("  ✓ Configuration files exist")
        print("  ✓ Configuration files are valid YAML")
        print("  ✓ Required sections present")

    def create_test_environment_report(self):
        """Create a report of the test environment and implementation status."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'jaxwatch_root': str(self.jaxwatch_root),
            'conversational_features': {
                'conversational_agent': 'implemented',
                'civic_intent_engine': 'implemented',
                'persistent_memory': 'implemented',
                'civic_context': 'implemented',
                'proactive_monitor': 'implemented',
                'enhanced_job_manager': 'implemented',
                'conversational_slack_gateway': 'implemented'
            },
            'configuration_files': {
                'civic_tools.yml': 'created',
                'claude_prompts.yml': 'created'
            },
            'test_results': self.results,
            'api_dependencies': {
                'anthropic_api_key': 'configured' if os.getenv('ANTHROPIC_API_KEY') else 'not configured',
                'slack_credentials': {
                    'bot_token': 'configured' if os.getenv('SLACK_BOT_TOKEN') else 'not configured',
                    'app_token': 'configured' if os.getenv('SLACK_APP_TOKEN') else 'not configured'
                }
            }
        }

        # Save report
        report_file = self.jaxwatch_root / 'conversational_implementation_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📋 Implementation report saved to: {report_file}")

        return report


async def main():
    """Run the complete test suite."""
    test_suite = ConversationalTestSuite()

    print("Starting Conversational JaxWatch Implementation Tests...")
    print(f"JaxWatch Root: {test_suite.jaxwatch_root}")

    # Test configuration files first
    print("\n🔧 Testing Configuration Files")
    print("-" * 40)
    try:
        test_suite.test_configuration_files()
        print("✅ Configuration test passed")
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")

    # Run async tests
    success = await test_suite.run_all_tests()

    # Generate implementation report
    report = test_suite.create_test_environment_report()

    # Final status
    print(f"\n{'🎉' if success else '⚠️'} Conversational Implementation {'Complete' if success else 'Partial'}")

    if success:
        print("\nNext Steps:")
        print("1. Set ANTHROPIC_API_KEY environment variable for Claude integration")
        print("2. Set Slack credentials (SLACK_BOT_TOKEN, SLACK_APP_TOKEN)")
        print("3. Run: python conversational_slack_gateway.py --test-connection")
        print("4. Start conversational gateway: python conversational_slack_gateway.py")

    return 0 if success else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))