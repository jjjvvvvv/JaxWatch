#!/usr/bin/env python3
"""
Civic Intent Engine for JaxWatch
Claude-powered natural language understanding for civic analysis commands
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

import anthropic

try:
    # Try relative import first (when run as module)
    from .persistent_memory import ConversationContext
    from .civic_context import CivicAnalysisContext
except ImportError:
    # Fall back to absolute import (when run as script)
    from persistent_memory import ConversationContext
    from civic_context import CivicAnalysisContext


class CivicIntentEngine:
    """
    Claude-powered intent understanding engine for civic analysis tasks.

    This engine replaces regex pattern matching with intelligent natural language
    understanding while maintaining strict civic integrity safeguards.
    """

    def __init__(self, claude_client: Optional[anthropic.Anthropic]):
        """
        Initialize the civic intent engine.

        Args:
            claude_client: Configured Anthropic client (None for testing mode)
        """
        self.claude_client = claude_client
        self.system_prompt = self._load_civic_system_prompt()

    def _load_civic_system_prompt(self) -> str:
        """Load the civic analysis system prompt for Claude."""
        return """You are Molty, a civic analysis assistant for JaxWatch.

ROLE: Help users analyze civic documents through natural conversation while maintaining strict boundaries.

AVAILABLE CIVIC TOOLS:
- document_verify: Check civic documents for compliance and standards
  - Parameters: --project (project ID), --active-year (year), --document-type
  - Use for: "verify documents", "check compliance", "analyze projects"

- reference_scan: Find cross-references between civic documents
  - Parameters: --source (data source), --year (year), --project (project ID)
  - Use for: "scan references", "find connections", "cross-reference analysis"

- status_check: Get system health and current analysis status
  - No parameters, immediate execution
  - Use for: "status", "health check", "what's happening"

CIVIC INTEGRITY BOUNDARIES (NEVER VIOLATE):
- You NEVER see document content - only metadata and file paths
- You NEVER perform document analysis - only route to CLI tools
- You NEVER modify civic data - only read and analyze
- You NEVER hallucinate civic facts or outcomes
- You ALWAYS require explicit confirmation for civic actions

CONVERSATION STYLE:
- Be helpful but calm and factual
- Ask clarifying questions when intent is ambiguous
- Explain what civic tools will do before running them
- Acknowledge when you need more information
- Focus on civic transparency and compliance goals

RESPONSE FORMAT:
Always respond with JSON containing:
{
  "action_type": "document_verify|reference_scan|status_check|null",
  "parameters": {"key": "value"},
  "user_response": "What to tell the user in natural language",
  "needs_clarification": true/false,
  "action_description": "Human readable description of the civic action",
  "confidence": 0.0-1.0
}

EXAMPLES:

User: "Can you check if our 2026 transportation projects are compliant?"
Response: {
  "action_type": "document_verify",
  "parameters": {"active-year": "2026", "document-type": "transportation"},
  "user_response": "I'll verify all 2026 transportation projects for compliance. This will check documents against current civic standards and identify any issues that need attention.",
  "needs_clarification": false,
  "action_description": "Verify 2026 transportation projects for compliance",
  "confidence": 0.9
}

User: "What's going on?"
Response: {
  "action_type": "status_check",
  "parameters": {},
  "user_response": "Let me check the current status of civic analysis work.",
  "needs_clarification": false,
  "action_description": "Check system status and recent activity",
  "confidence": 1.0
}

User: "Make the documents better"
Response: {
  "action_type": null,
  "parameters": {},
  "user_response": "I can't modify civic documents, but I can help you analyze them. Would you like me to verify documents for compliance or scan for cross-references?",
  "needs_clarification": true,
  "action_description": null,
  "confidence": 0.1
}"""

    async def understand_intent(self, message: str, conversation_context: ConversationContext,
                              civic_status: Dict, civic_tools: Dict) -> 'CivicIntent':
        """
        Use Claude to understand civic analysis intent from natural language.

        Args:
            message: User's natural language message
            conversation_context: Recent conversation history
            civic_status: Current civic analysis status
            civic_tools: Available civic tools catalog

        Returns:
            Parsed CivicIntent with action and response
        """
        if not self.claude_client:
            # Return basic fallback intent
            from conversational_agent import CivicIntent
            return CivicIntent(
                action_type=None,
                parameters={},
                user_response="Claude API not available. Please use specific commands like 'verify documents' or 'scan references'.",
                needs_clarification=True,
                confidence=0.0
            )

        # Prepare context for Claude
        context_summary = self._prepare_context_for_claude(
            conversation_context, civic_status, civic_tools
        )

        # Build the user prompt
        user_prompt = f"""
User message: "{message}"

Current conversation context:
{context_summary['conversation']}

Current civic analysis status:
{context_summary['civic_status']}

Available civic tools:
{context_summary['tools']}

Please analyze this message and determine:
1. What civic analysis action (if any) the user wants
2. What parameters are needed for that action
3. Whether clarification is required
4. An appropriate conversational response

Remember: Be helpful but maintain civic integrity boundaries. Never guess at civic facts or outcomes.
"""

        try:
            # Call Claude for intent understanding
            response = await self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Parse Claude's response
            claude_response = response.content[0].text.strip()
            intent_data = self._parse_claude_response(claude_response)

            # Convert to CivicIntent object
            from conversational_agent import CivicIntent
            return CivicIntent(
                action_type=intent_data.get('action_type'),
                parameters=intent_data.get('parameters', {}),
                user_response=intent_data.get('user_response', ''),
                needs_clarification=intent_data.get('needs_clarification', False),
                action_description=intent_data.get('action_description'),
                confidence=intent_data.get('confidence', 0.0)
            )

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            # Fallback response
            from conversational_agent import CivicIntent
            return CivicIntent(
                action_type=None,
                parameters={},
                user_response="I'm having trouble understanding your request right now. Please try again or use specific commands like 'verify documents' or 'scan references'.",
                needs_clarification=True,
                confidence=0.0
            )

    def _prepare_context_for_claude(self, conversation_context: ConversationContext,
                                  civic_status: Dict, civic_tools: Dict) -> Dict[str, str]:
        """Prepare context information for Claude in a structured format."""

        # Format recent conversation exchanges
        conversation_text = conversation_context.get_recent_exchanges(limit=3)
        if not conversation_text:
            conversation_text = "No recent conversation history."

        # Format civic status
        status_lines = []
        if civic_status.get('projects_count'):
            status_lines.append(f"Total projects: {civic_status['projects_count']}")
        if civic_status.get('verified_count'):
            status_lines.append(f"Verified documents: {civic_status['verified_count']}")
        if civic_status.get('references_count'):
            status_lines.append(f"Reference annotations: {civic_status['references_count']}")
        if civic_status.get('last_activity'):
            status_lines.append(f"Last activity: {civic_status['last_activity']}")

        civic_status_text = "\n".join(status_lines) if status_lines else "No recent civic analysis activity."

        # Format tools catalog
        tools_text = ""
        for tool in civic_tools.get('tools', []):
            tools_text += f"- {tool['name']}: {tool['description']}\n"

        return {
            'conversation': conversation_text,
            'civic_status': civic_status_text,
            'tools': tools_text
        }

    def _parse_claude_response(self, claude_response: str) -> Dict[str, Any]:
        """
        Parse Claude's JSON response into intent data.

        Args:
            claude_response: Raw response text from Claude

        Returns:
            Parsed intent data dictionary
        """
        try:
            # Try to extract JSON from Claude's response
            # Claude might wrap JSON in code blocks or add explanation text
            json_match = re.search(r'\{.*\}', claude_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                intent_data = json.loads(json_text)

                # Validate required fields
                if not isinstance(intent_data, dict):
                    raise ValueError("Response is not a dictionary")

                # Ensure required fields are present
                intent_data.setdefault('action_type', None)
                intent_data.setdefault('parameters', {})
                intent_data.setdefault('user_response', 'I need to think about that.')
                intent_data.setdefault('needs_clarification', True)
                intent_data.setdefault('action_description', None)
                intent_data.setdefault('confidence', 0.5)

                # Validate action_type
                valid_actions = ['document_verify', 'reference_scan', 'status_check', None]
                if intent_data['action_type'] not in valid_actions:
                    intent_data['action_type'] = None
                    intent_data['needs_clarification'] = True

                return intent_data

            else:
                # If no JSON found, create a basic response
                return {
                    'action_type': None,
                    'parameters': {},
                    'user_response': claude_response,
                    'needs_clarification': True,
                    'action_description': None,
                    'confidence': 0.3
                }

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing Claude response: {e}")
            print(f"Raw response: {claude_response}")

            # Fallback: extract intent from text
            return self._extract_intent_from_text(claude_response)

    def _extract_intent_from_text(self, response_text: str) -> Dict[str, Any]:
        """
        Extract intent from Claude's text response when JSON parsing fails.

        Args:
            response_text: Raw text response from Claude

        Returns:
            Basic intent data extracted from text
        """
        response_lower = response_text.lower()

        # Try to detect action type from text
        action_type = None
        parameters = {}

        if 'verify' in response_lower or 'check' in response_lower:
            action_type = 'document_verify'

            # Extract year if mentioned
            year_match = re.search(r'(20\d{2})', response_text)
            if year_match:
                parameters['active-year'] = year_match.group(1)

        elif 'scan' in response_lower or 'reference' in response_lower:
            action_type = 'reference_scan'

        elif 'status' in response_lower or 'health' in response_lower:
            action_type = 'status_check'

        # Determine if clarification is needed
        needs_clarification = any(phrase in response_lower for phrase in [
            'need more', 'clarify', 'which', 'what', 'unclear', 'ambiguous', 'specify'
        ])

        return {
            'action_type': action_type,
            'parameters': parameters,
            'user_response': response_text,
            'needs_clarification': needs_clarification,
            'action_description': f"Civic analysis task" if action_type else None,
            'confidence': 0.6 if action_type else 0.2
        }

    def build_civic_command(self, intent_data: Dict) -> Optional[Dict]:
        """
        Build CLI command from parsed intent data.

        Args:
            intent_data: Parsed intent information

        Returns:
            Command dictionary for job manager or None
        """
        action_type = intent_data.get('action_type')
        parameters = intent_data.get('parameters', {})

        if action_type == 'document_verify':
            # Build document verification command
            cmd_parts = ['python', 'document_verifier/document_verifier.py', 'document_verify']

            if parameters.get('project'):
                cmd_parts.extend(['--project', parameters['project']])
            if parameters.get('active-year'):
                cmd_parts.extend(['--active-year', parameters['active-year']])
            if parameters.get('document-type'):
                cmd_parts.extend(['--document-type', parameters['document-type']])

            return {
                'type': 'cli_execution',
                'cli_command': ' '.join(cmd_parts),
                'description': intent_data.get('action_description', 'Document verification'),
                'background': True
            }

        elif action_type == 'reference_scan':
            # Build reference scanning command
            cmd_parts = ['python', 'reference_scanner/reference_scanner.py', 'run']

            if parameters.get('source'):
                cmd_parts.extend(['--source', parameters['source']])
            else:
                cmd_parts.extend(['--source', 'dia_board'])  # Default source

            if parameters.get('year'):
                cmd_parts.extend(['--year', parameters['year']])
            if parameters.get('project'):
                cmd_parts.extend(['--project', parameters['project']])

            return {
                'type': 'cli_execution',
                'cli_command': ' '.join(cmd_parts),
                'description': intent_data.get('action_description', 'Reference scanning'),
                'background': True
            }

        elif action_type == 'status_check':
            return {
                'type': 'status_check',
                'description': intent_data.get('action_description', 'System status check'),
                'background': False
            }

        return None


# Utility function for testing
def test_intent_engine():
    """Test the civic intent engine with sample messages."""
    engine = CivicIntentEngine(None)  # No Claude client for testing

    test_messages = [
        "verify documents",
        "check 2026 transportation projects",
        "scan for references in DIA board minutes",
        "what's the status?",
        "make documents better",
        "I need help with civic analysis"
    ]

    print("Testing Civic Intent Engine (fallback mode):")
    for message in test_messages:
        print(f"\nUser: {message}")
        # Would normally call understand_intent, but testing text extraction
        intent_data = engine._extract_intent_from_text(message)
        print(f"Action: {intent_data['action_type']}")
        print(f"Confidence: {intent_data['confidence']}")
        print(f"Response: {intent_data['user_response'][:100]}...")


if __name__ == "__main__":
    test_intent_engine()