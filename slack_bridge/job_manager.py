#!/usr/bin/env python3
"""
Job Manager for Slack Bridge
Handles background execution of CLI commands
"""

import subprocess
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class JobManager:
    """Manage background CLI job execution and status tracking."""

    def __init__(self, slack_app=None):
        self.active_jobs = {}
        self.job_history = []
        self.slack_app = slack_app

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
        Execute CLI command in background thread.

        Args:
            job_id: ID of job to execute
        """
        job = self.active_jobs[job_id]

        try:
            # Split command into arguments
            cmd_args = job['command'].split()

            # Use dynamic working directory
            result = subprocess.run(
                cmd_args,
                cwd=job['jaxwatch_root'],
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )

            job['status'] = 'completed' if result.returncode == 0 else 'failed'
            job['completed_at'] = datetime.now()
            job['output'] = result.stdout
            job['error'] = result.stderr
            job['return_code'] = result.returncode

            # Notify Slack of completion
            self._notify_completion(job)

        except subprocess.TimeoutExpired:
            job['status'] = 'timeout'
            job['error'] = 'Job exceeded 30 minute timeout'
            job['completed_at'] = datetime.now()
            self._notify_completion(job)
        except Exception as e:
            job['status'] = 'error'
            job['error'] = str(e)
            job['completed_at'] = datetime.now()
            self._notify_completion(job)

        # Move to history and cleanup
        self.job_history.append(job.copy())
        del self.active_jobs[job_id]

        # Keep only last 50 jobs in history
        if len(self.job_history) > 50:
            self.job_history = self.job_history[-50:]

    def _notify_completion(self, job: Dict):
        """
        Send completion notification to Slack.

        Args:
            job: Job record with completion status
        """
        if not self.slack_app:
            return

        try:
            channel_id = job['channel_id']
            status = job['status']
            description = job['description']

            if status == 'completed':
                message = f"✅ {description} completed locally!"

                # Add brief output summary if available
                if job.get('output'):
                    output_lines = job['output'].strip().split('\n')
                    # Look for summary lines
                    for line in output_lines:
                        if 'enhanced' in line.lower() or 'processed' in line.lower():
                            message += f" {line.strip()}"
                            break

                message += " Check dashboard for details."

            elif status == 'failed':
                message = f"❌ {description} failed."
                if job.get('error'):
                    error_preview = job['error'][:200]
                    if len(job['error']) > 200:
                        error_preview += "..."
                    message += f"\n```{error_preview}```"

            elif status == 'timeout':
                message = f"⏱️ {description} timed out after 30 minutes."

            else:  # error
                message = f"💥 {description} encountered an error: {job.get('error', 'Unknown error')}"

            self.slack_app.client.chat_postMessage(
                channel=channel_id,
                text=message
            )

        except Exception as e:
            print(f"Error sending Slack notification: {e}")

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

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status of specific job."""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id].copy()

        # Check history
        for job in self.job_history:
            if job['id'] == job_id:
                return job.copy()

        return None