#!/usr/bin/env python3
"""
Enhanced Job Manager for Slack Bridge
Handles background execution of CLI commands with conversational context
"""

import threading
import time
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for JaxWatch imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    # Try relative import first (when run as module)
    from .slack_handlers.response_formatter import ResponseFormatter
    from .persistent_memory import PersistentConversationMemory
    from .civic_context import CivicAnalysisContext
except ImportError:
    # Fall back to absolute import (when run as script)
    from slack_handlers.response_formatter import ResponseFormatter
    from persistent_memory import PersistentConversationMemory
    from civic_context import CivicAnalysisContext

# Import JaxWatch Core API
from jaxwatch.api import JaxWatchCore


class JobManager:
    """
    Enhanced job manager with conversational context and civic intelligence.

    Provides richer completion messages, conversation memory integration,
    and proactive suggestions for follow-up civic analysis actions.
    """

    def __init__(self, slack_app=None, session_manager=None, jaxwatch_root=None):
        self.active_jobs = {}
        self.job_history = []
        self.slack_app = slack_app
        self.session_manager = session_manager
        self.response_formatter = ResponseFormatter()

        # Conversational context components
        self.jaxwatch_root = jaxwatch_root
        if jaxwatch_root:
            self.conversation_memory = PersistentConversationMemory(
                Path(jaxwatch_root) / "conversations"
            )
            self.civic_context = CivicAnalysisContext(Path(jaxwatch_root))
        else:
            self.conversation_memory = None
            self.civic_context = None

    def start_job(self, command: Dict, user_id: str, channel_id: str, jaxwatch_root: Path) -> str:
        """
        Start background CLI job and return job ID.

        Args:
            command: Command dictionary from parser
            user_id: Slack user ID who initiated the job
            channel_id: Slack channel to send completion notification
            jaxwatch_root: JaxWatch root directory path

        Returns:
            Job ID for tracking
        """
        job_id = f"jw_{int(time.time())}"

        # Create job record
        job_record = {
            'id': job_id,
            'command': command['cli_command'],
            'cli_command': command['cli_command'],  # Store for ResponseFormatter
            'description': command['description'],
            'user_id': user_id,
            'channel_id': channel_id,
            'jaxwatch_root': str(jaxwatch_root),
            'started_at': datetime.now(),
            'status': 'running'
        }

        self.active_jobs[job_id] = job_record

        # Execute in background thread
        thread = threading.Thread(target=self._execute_job, args=(job_id,))
        thread.daemon = True
        thread.start()

        return job_id

    def _execute_job(self, job_id: str):
        """
        Execute job using JaxWatch Core API instead of subprocess.

        Args:
            job_id: ID of job to execute
        """
        job = self.active_jobs[job_id]

        try:
            # Initialize JaxWatch Core API
            core = JaxWatchCore()

            # Parse CLI command and execute via API
            command = job['command']
            result = self._execute_api_command(core, command)

            job['status'] = 'completed' if result['success'] else 'failed'
            job['completed_at'] = datetime.now()
            job['output'] = result['output']
            job['error'] = result.get('error', '')
            job['return_code'] = 0 if result['success'] else 1

            # Add API-specific metadata
            job['api_stats'] = result.get('stats', {})
            job['execution_method'] = 'jaxwatch_core_api'

            # Notify Slack of completion
            self._notify_completion(job)

        except Exception as e:
            job['status'] = 'error'
            job['error'] = f"API execution error: {str(e)}"
            job['completed_at'] = datetime.now()
            job['return_code'] = 1
            job['execution_method'] = 'jaxwatch_core_api'
            self._notify_completion(job)

        # Update session if available
        if self.session_manager:
            user_id = job.get('user_id')
            if user_id:
                session = self.session_manager.get_session(user_id)
                if session:
                    session.mark_job_completed(job_id)

        # Move to history and cleanup
        self.job_history.append(job.copy())
        del self.active_jobs[job_id]

        # Keep only last 50 jobs in history
        if len(self.job_history) > 50:
            self.job_history = self.job_history[-50:]

    def _execute_api_command(self, core: JaxWatchCore, command: str) -> Dict:
        """
        Execute a command using the JaxWatch Core API.

        Args:
            core: JaxWatchCore instance
            command: CLI command string

        Returns:
            Dict with 'success', 'output', 'error', and optional 'stats'
        """
        try:
            # Document verification commands
            if 'document_verifier.py document_verify' in command:
                if '--project' in command:
                    # Extract project ID
                    project_match = re.search(r'--project\s+([A-Z0-9-]+)', command)
                    project_id = project_match.group(1) if project_match else None
                    result = core.verify_documents(project_id=project_id)
                elif '--active-year' in command:
                    # Extract year
                    year_match = re.search(r'--active-year\s+(\d{4})', command)
                    year = int(year_match.group(1)) if year_match else None
                    result = core.verify_documents(active_year=year)
                else:
                    # Verify all documents
                    result = core.verify_documents()

                if result.success:
                    output = f"✅ Document Verification Complete\n"
                    output += f"📊 Projects processed: {result.projects_processed}\n"
                    output += f"🔍 Projects verified: {result.projects_verified}\n"
                    if result.projects_verified > 0:
                        output += "📋 Verification results available in enhanced projects data"
                    return {
                        'success': True,
                        'output': output,
                        'stats': {
                            'projects_processed': result.projects_processed,
                            'projects_verified': result.projects_verified
                        }
                    }
                else:
                    return {
                        'success': False,
                        'output': "❌ Document verification failed",
                        'error': ', '.join(result.errors)
                    }

            # Reference scanning commands
            elif 'reference_scanner.py run' in command:
                source = None
                year = None

                # Extract source
                source_match = re.search(r'--source\s+([a-z_]+)', command)
                if source_match:
                    source = source_match.group(1)

                # Extract year
                year_match = re.search(r'--year\s+(\d{4})', command)
                if year_match:
                    year = year_match.group(1)

                result = core.scan_references(source=source, year=year)

                if result.success:
                    output = f"✅ Reference Scanning Complete\n"
                    output += f"📄 Documents processed: {result.documents_processed}\n"
                    output += f"🔗 References detected: {result.references_detected}\n"
                    if source:
                        output += f"📂 Source: {source}\n"
                    if year:
                        output += f"📅 Year: {year}\n"
                    output += "📋 Reference data stored in annotations directory"
                    return {
                        'success': True,
                        'output': output,
                        'stats': {
                            'documents_processed': result.documents_processed,
                            'references_detected': result.references_detected
                        }
                    }
                else:
                    return {
                        'success': False,
                        'output': "❌ Reference scanning failed",
                        'error': ', '.join(result.errors)
                    }

            else:
                return {
                    'success': False,
                    'output': f"❌ Unknown command: {command}",
                    'error': f"Command not mapped to API: {command}"
                }

        except Exception as e:
            return {
                'success': False,
                'output': f"❌ API execution failed: {str(e)}",
                'error': str(e)
            }

    def _notify_completion(self, job: Dict):
        """
        Send enhanced completion notification with civic context and suggestions.

        Args:
            job: Job record with completion status
        """
        if not self.slack_app:
            return

        try:
            channel_id = job['channel_id']
            user_id = job['user_id']

            # Generate enhanced completion message with civic context
            message = self._generate_conversational_completion_message(job)

            self.slack_app.client.chat_postMessage(
                channel=channel_id,
                text=message
            )

            # Record completion in conversation memory
            if self.conversation_memory and user_id:
                self.conversation_memory.record_exchange(
                    user_id=user_id,
                    user_message=f"[Job {job['id']} completed]",
                    molty_response=message,
                    civic_action={
                        'type': 'job_completion',
                        'description': job['description'],
                        'job_id': job['id'],
                        'status': job['status'],
                        'duration': self._calculate_job_duration(job)
                    }
                )

        except Exception as e:
            print(f"Error sending Slack notification: {e}")

    def _generate_conversational_completion_message(self, job: Dict) -> str:
        """
        Generate enhanced completion message with civic context and suggestions.

        Args:
            job: Job record with completion details

        Returns:
            Rich completion message with context and suggestions
        """
        try:
            # Start with basic completion status
            if job['status'] == 'completed':
                status_emoji = "✅"
                status_text = "completed successfully"
            elif job['status'] == 'failed':
                status_emoji = "❌"
                status_text = "failed"
            elif job['status'] == 'timeout':
                status_emoji = "⏱️"
                status_text = "timed out"
            else:
                status_emoji = "⚠️"
                status_text = f"finished with status: {job['status']}"

            # Calculate duration
            duration = self._calculate_job_duration(job)
            duration_text = self._format_duration_friendly(duration)

            # Base message
            message = f"{status_emoji} Your {job['description']} {status_text}"
            if duration:
                message += f" (took {duration_text})"

            # Add civic analysis results if available
            if job['status'] == 'completed' and job.get('output'):
                civic_summary = self._extract_civic_summary(job)
                if civic_summary:
                    message += f"\n\n📋 **Analysis Results:**\n{civic_summary}"

            # Add proactive suggestions for successful jobs
            if job['status'] == 'completed':
                suggestions = self._generate_follow_up_suggestions(job)
                if suggestions:
                    message += f"\n\n❓ **Next steps you might consider:**\n{suggestions}"

            # Add error details for failed jobs
            if job['status'] in ['failed', 'error', 'timeout']:
                error_details = self._format_error_details(job)
                if error_details:
                    message += f"\n\n🔧 **Troubleshooting:**\n{error_details}"

            return message

        except Exception as e:
            # Fallback to basic message if enhancement fails
            print(f"Error generating enhanced completion message: {e}")
            return self.response_formatter.format_job_completion_with_context(job)

    def _calculate_job_duration(self, job: Dict) -> Optional[timedelta]:
        """Calculate job execution duration."""
        try:
            started_at = job.get('started_at')
            completed_at = job.get('completed_at')

            if started_at and completed_at:
                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at)
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at)

                return completed_at - started_at

        except Exception:
            pass

        return None

    def _format_duration_friendly(self, duration: Optional[timedelta]) -> str:
        """Format duration in a user-friendly way."""
        if not duration:
            return "unknown time"

        total_seconds = int(duration.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            if seconds > 0:
                return f"{minutes} minutes, {seconds} seconds"
            else:
                return f"{minutes} minutes"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes > 0:
                return f"{hours} hours, {minutes} minutes"
            else:
                return f"{hours} hours"

    def _extract_civic_summary(self, job: Dict) -> Optional[str]:
        """
        Extract civic analysis summary from job output.

        Args:
            job: Job record with output

        Returns:
            Formatted civic analysis summary or None
        """
        try:
            output = job.get('output', '')

            # Simple parsing for common civic analysis outputs
            summary_lines = []

            # Look for common civic analysis patterns in output
            if 'document_verifier' in job.get('cli_command', ''):
                # Document verification results
                if 'projects_enriched.json' in output:
                    # Count enhanced projects
                    import re
                    match = re.search(r'(\d+)\s+projects?\s+enriched', output, re.IGNORECASE)
                    if match:
                        count = match.group(1)
                        summary_lines.append(f"• Enhanced {count} civic documents with verification details")

                if 'compliance' in output.lower():
                    summary_lines.append("• Identified compliance areas requiring attention")

            elif 'reference_scanner' in job.get('cli_command', ''):
                # Reference scanning results
                if 'annotations' in output:
                    # Count reference annotations
                    import re
                    match = re.search(r'(\d+)\s+references?', output, re.IGNORECASE)
                    if match:
                        count = match.group(1)
                        summary_lines.append(f"• Found {count} cross-references between civic documents")

                if 'connections' in output.lower():
                    summary_lines.append("• Mapped document relationships for better transparency")

            # Add dashboard link if data was generated
            if summary_lines:
                summary_lines.append("• Dashboard: http://localhost:5000")

            return "\n".join(summary_lines) if summary_lines else None

        except Exception as e:
            print(f"Error extracting civic summary: {e}")
            return None

    def _generate_follow_up_suggestions(self, job: Dict) -> Optional[str]:
        """
        Generate intelligent follow-up suggestions based on job type and results.

        Args:
            job: Completed job record

        Returns:
            Formatted suggestions or None
        """
        try:
            suggestions = []
            cli_command = job.get('cli_command', '')

            if 'document_verifier' in cli_command:
                # Suggestions after document verification
                suggestions.append("• `scan references` - Find connections between verified documents")

                if '--project' in cli_command:
                    suggestions.append("• `verify documents` - Check other projects for compliance")
                else:
                    suggestions.append("• `status` - See overall civic analysis progress")

            elif 'reference_scanner' in cli_command:
                # Suggestions after reference scanning
                suggestions.append("• `verify documents` - Analyze any newly connected documents")
                suggestions.append("• `status` - Review the complete reference network")

            # Add civic context suggestions if available
            if self.civic_context:
                status = self.civic_context.get_current_status()

                if status.get('verified_count', 0) > 0 and 'document_verifier' not in cli_command:
                    suggestions.append("• Consider verifying recent documents for compliance")

                if status.get('projects_count', 0) > status.get('references_count', 0):
                    suggestions.append("• Scan for cross-references to improve civic transparency")

            return "\n".join(suggestions) if suggestions else None

        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return None

    def _format_error_details(self, job: Dict) -> Optional[str]:
        """Format error details for user troubleshooting."""
        try:
            error_lines = []

            if job['status'] == 'timeout':
                error_lines.append("• Job exceeded time limit (30 minutes)")
                error_lines.append("• Try processing smaller batches of documents")
                error_lines.append("• Check system resources and restart if needed")

            elif job['status'] == 'failed':
                error_msg = job.get('error', '').strip()
                if error_msg:
                    # Extract useful error information
                    if 'permission denied' in error_msg.lower():
                        error_lines.append("• File permission issue - check document access")
                    elif 'not found' in error_msg.lower():
                        error_lines.append("• File or directory not found - verify paths")
                    elif 'timeout' in error_msg.lower():
                        error_lines.append("• Operation timed out - try again or reduce scope")
                    else:
                        # Generic error guidance
                        error_lines.append(f"• Error: {error_msg[:100]}{'...' if len(error_msg) > 100 else ''}")

                error_lines.append("• Check the dashboard for more details")
                error_lines.append("• Try `status` to see system health")

            return "\n".join(error_lines) if error_lines else None

        except Exception:
            return None

    async def start_conversational_job(self, command: str, user_id: str, channel_id: str,
                                     intent_context: Dict) -> str:
        """
        Start a job with conversational context for enhanced completion messages.

        Args:
            command: CLI command to execute
            user_id: Slack user ID
            channel_id: Slack channel ID
            intent_context: Conversational intent context

        Returns:
            Job ID for tracking
        """
        # Build command dictionary from conversational context
        command_dict = {
            'cli_command': command,
            'description': intent_context.get('action_description', 'Civic analysis task'),
            'type': 'cli_execution',
            'background': True,
            'conversational_context': {
                'action_type': intent_context.get('action_type'),
                'parameters': intent_context.get('parameters', {}),
                'confidence': intent_context.get('confidence', 0.0),
                'user_message': intent_context.get('user_message', ''),
                'reasoning': intent_context.get('reasoning', '')
            }
        }

        # Use existing start_job method with enhanced context
        job_id = self.start_job(
            command_dict, user_id, channel_id,
            Path(self.jaxwatch_root) if self.jaxwatch_root else Path.cwd()
        )

        return job_id

    def get_job_summary_for_user(self, user_id: str) -> str:
        """
        Get a conversational summary of jobs for a specific user.

        Args:
            user_id: Slack user ID

        Returns:
            Formatted job summary
        """
        try:
            user_active_jobs = {
                job_id: job for job_id, job in self.active_jobs.items()
                if job.get('user_id') == user_id
            }

            user_recent_jobs = [
                job for job in self.job_history[-10:]  # Last 10 jobs
                if job.get('user_id') == user_id and
                job.get('completed_at') and
                (datetime.now() - job['completed_at']).days < 1  # Last 24 hours
            ]

            summary_lines = []

            if user_active_jobs:
                summary_lines.append(f"🔄 **Active Jobs ({len(user_active_jobs)}):**")
                for job_id, job in user_active_jobs.items():
                    elapsed = datetime.now() - job['started_at']
                    duration_str = self._format_duration_friendly(elapsed)
                    summary_lines.append(f"• {job_id}: {job['description']} (running {duration_str})")

            if user_recent_jobs:
                summary_lines.append(f"\n📋 **Recent Completions ({len(user_recent_jobs)}):**")
                for job in user_recent_jobs[-3:]:  # Last 3 completed
                    duration = self._calculate_job_duration(job)
                    duration_str = self._format_duration_friendly(duration) if duration else "unknown time"
                    status_emoji = "✅" if job['status'] == 'completed' else "❌"
                    summary_lines.append(f"{status_emoji} {job['description']} (took {duration_str})")

            if not user_active_jobs and not user_recent_jobs:
                summary_lines.append("No recent civic analysis activity.")

            return "\n".join(summary_lines)

        except Exception as e:
            print(f"Error generating user job summary: {e}")
            return "Unable to retrieve job summary at this time."

    def execute_immediate(self, command: Dict, jaxwatch_root: Path) -> Dict:
        """
        Execute command immediately and return result.

        Args:
            command: Command dictionary from parser
            jaxwatch_root: JaxWatch root directory path

        Returns:
            Execution result dictionary
        """
        try:
            if command.get('type') == 'direct_response':
                return {
                    'status': 'success',
                    'output': command['response']
                }

            cmd_args = command['cli_command'].split()
            result = subprocess.run(
                cmd_args,
                cwd=jaxwatch_root,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout for immediate commands
            )

            return {
                'status': 'success' if result.returncode == 0 else 'failed',
                'output': result.stdout,
                'error': result.stderr,
                'return_code': result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'error': 'Command timed out after 1 minute'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def get_active_jobs(self) -> Dict:
        """Get currently running jobs."""
        return self.active_jobs.copy()

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID (alias for get_job_status)."""
        return self.get_job_status(job_id)

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status of specific job."""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id].copy()

        # Check history
        for job in self.job_history:
            if job['id'] == job_id:
                return job.copy()

        return None