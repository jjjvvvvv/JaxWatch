#!/usr/bin/env python3
"""
Status Collector for Slack Bridge
Lightweight status aggregation without subprocess calls
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict


class StatusCollector:
    """Collect system status using file system inspection only."""

    def __init__(self):
        pass

    def get_system_status(self, jaxwatch_root: Path = None) -> str:
        """
        Lightweight status aggregation without subprocess calls.

        Args:
            jaxwatch_root: JaxWatch root directory path

        Returns:
            Formatted status string for Slack
        """
        if not jaxwatch_root:
            jaxwatch_root = Path(__file__).parents[1]

        status_lines = []

        try:
            # Count projects
            projects_file = jaxwatch_root / 'admin_ui' / 'data' / 'projects_index.json'
            if projects_file.exists():
                try:
                    with open(projects_file) as f:
                        projects = json.load(f)
                    status_lines.append(f"• Total projects: {len(projects)}")
                except (json.JSONDecodeError, FileNotFoundError):
                    status_lines.append("• Total projects: Unable to read")
            else:
                status_lines.append("• Total projects: No data found")

            # Count verified projects (try both locations)
            verified_count = 0
            enriched_paths = [
                jaxwatch_root / 'admin_ui' / 'data' / 'projects_enriched.json',
                jaxwatch_root / 'document_verifier' / 'demo_output.json'
            ]

            for enriched_file in enriched_paths:
                if enriched_file.exists():
                    try:
                        with open(enriched_file) as f:
                            enriched = json.load(f)
                        verified_count = max(verified_count, len(enriched))
                    except (json.JSONDecodeError, FileNotFoundError):
                        continue

            if verified_count > 0:
                status_lines.append(f"• Verified documents: {verified_count}")
            else:
                status_lines.append("• Verified documents: None")

            # Count reference annotations
            annotations_dir = jaxwatch_root / 'outputs' / 'annotations' / 'reference_scanner'
            if annotations_dir.exists():
                try:
                    annotation_files = list(annotations_dir.glob('*.json'))
                    status_lines.append(f"• Reference annotations: {len(annotation_files)}")
                except Exception:
                    status_lines.append("• Reference annotations: Unable to count")
            else:
                status_lines.append("• Reference annotations: 0")

            # Dashboard status
            status_lines.append("• Dashboard: http://localhost:5000")

            # Last activity (based on file modification times)
            self._add_activity_status(jaxwatch_root, status_lines)

        except Exception as e:
            status_lines.append(f"• Status check error: {str(e)}")

        return "\n".join(status_lines)

    def _add_activity_status(self, jaxwatch_root: Path, status_lines: list):
        """Add last activity information based on file modification times."""
        try:
            recent_files = []

            # Check for recent files in various locations
            patterns = [
                'admin_ui/data/*.json',
                'document_verifier/*.json',
                'outputs/annotations/*/*.json',
                'outputs/projects/*.json'
            ]

            for pattern in patterns:
                try:
                    recent_files.extend(jaxwatch_root.glob(pattern))
                except Exception:
                    continue

            if recent_files:
                # Find the most recently modified file
                latest_mod = max(f.stat().st_mtime for f in recent_files if f.exists())
                latest_time = datetime.fromtimestamp(latest_mod)
                time_diff = datetime.now() - latest_time

                if time_diff.days > 0:
                    status_lines.append(f"• Last activity: {time_diff.days} days ago")
                elif time_diff.seconds > 3600:
                    hours = time_diff.seconds // 3600
                    status_lines.append(f"• Last activity: {hours} hours ago")
                else:
                    minutes = time_diff.seconds // 60
                    status_lines.append(f"• Last activity: {minutes} minutes ago")
            else:
                status_lines.append("• Last activity: No recent files found")

        except Exception as e:
            status_lines.append(f"• Last activity: Unable to determine ({str(e)})")

    def get_job_summary(self, job_manager) -> str:
        """
        Get summary of active jobs.

        Args:
            job_manager: JobManager instance

        Returns:
            Formatted job status string
        """
        try:
            active_jobs = job_manager.get_active_jobs()

            if not active_jobs:
                return "No active background jobs"

            job_lines = [f"Active jobs ({len(active_jobs)}):"]
            for job_id, job in active_jobs.items():
                elapsed = datetime.now() - job['started_at']
                elapsed_str = f"{elapsed.seconds // 60}m{elapsed.seconds % 60}s"
                job_lines.append(f"• {job['description']} ({elapsed_str})")

            return "\n".join(job_lines)

        except Exception as e:
            return f"Job status error: {str(e)}"