#!/usr/bin/env python3
"""
Civic Analysis Context for JaxWatch
Provides current status and context information for conversational AI
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any


class CivicAnalysisContext:
    """
    Provides civic analysis context and current status information.

    This class aggregates information about current civic analysis work
    to provide context for the conversational AI without performing
    any analysis itself.
    """

    def __init__(self, jaxwatch_root: Path):
        """
        Initialize civic analysis context.

        Args:
            jaxwatch_root: Path to JaxWatch root directory
        """
        self.jaxwatch_root = jaxwatch_root
        self.outputs_dir = jaxwatch_root / "outputs"
        self.inputs_dir = jaxwatch_root / "inputs"

    def get_current_status(self) -> Dict[str, Any]:
        """
        Get current civic analysis status for conversational context.

        Returns:
            Dictionary with current status information
        """
        status = {
            'projects_count': 0,
            'verified_count': 0,
            'references_count': 0,
            'last_activity': None,
            'recent_files': [],
            'active_sources': []
        }

        try:
            # Count total projects
            projects_index = self.outputs_dir / "projects" / "projects_index.json"
            if projects_index.exists():
                with open(projects_index, 'r') as f:
                    projects = json.load(f)
                status['projects_count'] = len(projects)

            # Count verified documents
            enriched_projects = self.outputs_dir / "projects" / "projects_enriched.json"
            if enriched_projects.exists():
                with open(enriched_projects, 'r') as f:
                    enriched = json.load(f)
                status['verified_count'] = len(enriched)

            # Count reference annotations
            annotations_dir = self.outputs_dir / "annotations" / "reference_scanner"
            if annotations_dir.exists():
                annotation_files = list(annotations_dir.glob("*.json"))
                status['references_count'] = len(annotation_files)

            # Find last activity
            status['last_activity'] = self._get_last_activity_time()

            # Get recent files
            status['recent_files'] = self._get_recent_files(limit=5)

            # Get active sources
            status['active_sources'] = self._get_active_data_sources()

        except Exception as e:
            print(f"Error getting civic analysis status: {e}")

        return status

    def _get_last_activity_time(self) -> Optional[str]:
        """Get human-readable last activity time."""
        try:
            # Check for recent file modifications in outputs
            recent_files = []

            if self.outputs_dir.exists():
                for pattern in ["projects/*.json", "annotations/*/*.json", "dashboard_data/*.json"]:
                    recent_files.extend(self.outputs_dir.glob(pattern))

            if not recent_files:
                return None

            # Find most recent modification
            latest_mod = max(f.stat().st_mtime for f in recent_files)
            latest_time = datetime.fromtimestamp(latest_mod)

            # Calculate time difference
            time_diff = datetime.now() - latest_time

            if time_diff.days > 0:
                return f"{time_diff.days} days ago"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                return f"{hours} hours ago"
            else:
                minutes = max(1, time_diff.seconds // 60)
                return f"{minutes} minutes ago"

        except Exception as e:
            print(f"Error calculating last activity: {e}")
            return None

    def _get_recent_files(self, limit: int = 5) -> List[Dict]:
        """Get information about recently modified files."""
        try:
            file_info = []

            if self.outputs_dir.exists():
                # Check various output directories
                for directory in ["projects", "annotations", "dashboard_data"]:
                    dir_path = self.outputs_dir / directory
                    if dir_path.exists():
                        for file_path in dir_path.rglob("*.json"):
                            if file_path.is_file():
                                stat = file_path.stat()
                                file_info.append({
                                    'path': str(file_path.relative_to(self.jaxwatch_root)),
                                    'modified': datetime.fromtimestamp(stat.st_mtime),
                                    'size': stat.st_size
                                })

            # Sort by modification time and return recent files
            file_info.sort(key=lambda x: x['modified'], reverse=True)

            # Format for human consumption
            recent = []
            for info in file_info[:limit]:
                time_diff = datetime.now() - info['modified']
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}d ago"
                elif time_diff.seconds > 3600:
                    hours = time_diff.seconds // 3600
                    time_str = f"{hours}h ago"
                else:
                    minutes = max(1, time_diff.seconds // 60)
                    time_str = f"{minutes}m ago"

                recent.append({
                    'file': info['path'],
                    'modified': time_str,
                    'size_kb': round(info['size'] / 1024, 1)
                })

            return recent

        except Exception as e:
            print(f"Error getting recent files: {e}")
            return []

    def _get_active_data_sources(self) -> List[str]:
        """Get list of active data sources with recent content."""
        sources = []

        try:
            if self.inputs_dir.exists():
                # Check for directories with recent content
                for source_dir in self.inputs_dir.iterdir():
                    if source_dir.is_dir() and not source_dir.name.startswith('.'):
                        # Check for recent files in this source
                        recent_cutoff = datetime.now() - timedelta(days=7)
                        has_recent = False

                        for file_path in source_dir.rglob("*"):
                            if file_path.is_file():
                                mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                                if mod_time >= recent_cutoff:
                                    has_recent = True
                                    break

                        if has_recent:
                            sources.append(source_dir.name)

        except Exception as e:
            print(f"Error getting active sources: {e}")

        return sorted(sources)

    def get_project_context(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get context information about civic projects.

        Args:
            project_id: Optional specific project to focus on

        Returns:
            Project context information
        """
        context = {
            'total_projects': 0,
            'verified_projects': 0,
            'pending_verification': 0,
            'recent_activity': [],
            'project_types': []
        }

        try:
            # Load project index
            projects_index = self.outputs_dir / "projects" / "projects_index.json"
            if projects_index.exists():
                with open(projects_index, 'r') as f:
                    projects = json.load(f)

                context['total_projects'] = len(projects)

                # Analyze project types
                project_types = {}
                for project in projects:
                    # Extract project type from project ID or metadata
                    if isinstance(project, dict):
                        proj_type = project.get('type', 'unknown')
                    else:
                        # Try to infer from project ID
                        if 'transportation' in str(project).lower():
                            proj_type = 'transportation'
                        elif 'housing' in str(project).lower():
                            proj_type = 'housing'
                        elif 'infrastructure' in str(project).lower():
                            proj_type = 'infrastructure'
                        else:
                            proj_type = 'general'

                    project_types[proj_type] = project_types.get(proj_type, 0) + 1

                context['project_types'] = project_types

            # Load enriched projects (verified)
            enriched_projects = self.outputs_dir / "projects" / "projects_enriched.json"
            if enriched_projects.exists():
                with open(enriched_projects, 'r') as f:
                    enriched = json.load(f)
                context['verified_projects'] = len(enriched)

            context['pending_verification'] = context['total_projects'] - context['verified_projects']

            # Get recent verification activity
            context['recent_activity'] = self._get_recent_verification_activity()

        except Exception as e:
            print(f"Error getting project context: {e}")

        return context

    def _get_recent_verification_activity(self) -> List[Dict]:
        """Get recent document verification activity."""
        activity = []

        try:
            # Check enriched projects file for recent modifications
            enriched_file = self.outputs_dir / "projects" / "projects_enriched.json"
            if enriched_file.exists():
                mod_time = datetime.fromtimestamp(enriched_file.stat().st_mtime)
                time_diff = datetime.now() - mod_time

                if time_diff.days == 0:  # Today
                    activity.append({
                        'type': 'verification',
                        'description': 'Document verification completed',
                        'time': f"{time_diff.seconds // 60} minutes ago" if time_diff.seconds > 60 else "recently"
                    })

            # Check for recent annotation files
            annotations_dir = self.outputs_dir / "annotations"
            if annotations_dir.exists():
                recent_cutoff = datetime.now() - timedelta(hours=24)

                for annotation_file in annotations_dir.rglob("*.json"):
                    mod_time = datetime.fromtimestamp(annotation_file.stat().st_mtime)
                    if mod_time >= recent_cutoff:
                        time_diff = datetime.now() - mod_time
                        activity.append({
                            'type': 'annotation',
                            'description': f'Reference scanning in {annotation_file.parent.name}',
                            'time': f"{time_diff.seconds // 3600}h ago" if time_diff.seconds > 3600 else "recently"
                        })

        except Exception as e:
            print(f"Error getting recent activity: {e}")

        return activity[-5:]  # Return last 5 activities

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get summary of compliance status for civic transparency."""
        summary = {
            'verified_documents': 0,
            'pending_review': 0,
            'compliance_issues': 0,
            'last_verification': None
        }

        try:
            # This would integrate with actual compliance checking results
            # For now, provide basic summary from available data

            enriched_file = self.outputs_dir / "projects" / "projects_enriched.json"
            if enriched_file.exists():
                with open(enriched_file, 'r') as f:
                    enriched = json.load(f)

                summary['verified_documents'] = len(enriched)

                # Check for compliance indicators in enriched data
                issues_count = 0
                for project in enriched:
                    if isinstance(project, dict):
                        # Look for compliance issues in analysis
                        analysis = project.get('document_verification', {})
                        if isinstance(analysis, dict):
                            enhanced_summary = analysis.get('enhanced_summary', '')
                            if any(term in enhanced_summary.lower() for term in
                                   ['missing', 'incomplete', 'issue', 'concern', 'problem']):
                                issues_count += 1

                summary['compliance_issues'] = issues_count

                # Last verification time
                mod_time = datetime.fromtimestamp(enriched_file.stat().st_mtime)
                summary['last_verification'] = mod_time.strftime('%Y-%m-%d %H:%M')

        except Exception as e:
            print(f"Error getting compliance summary: {e}")

        return summary

    def get_reference_network_status(self) -> Dict[str, Any]:
        """Get status of document reference network analysis."""
        status = {
            'total_references': 0,
            'cross_references': 0,
            'unresolved_references': 0,
            'reference_sources': []
        }

        try:
            annotations_dir = self.outputs_dir / "annotations"
            if annotations_dir.exists():
                reference_count = 0
                sources = set()

                # Count reference annotations
                for source_dir in annotations_dir.iterdir():
                    if source_dir.is_dir():
                        sources.add(source_dir.name)
                        annotation_files = list(source_dir.glob("*.json"))
                        reference_count += len(annotation_files)

                status['total_references'] = reference_count
                status['reference_sources'] = sorted(list(sources))

            # Additional analysis would require parsing annotation content
            # For basic implementation, provide what we can determine from file structure

        except Exception as e:
            print(f"Error getting reference network status: {e}")

        return status

    def format_status_for_conversation(self) -> str:
        """Format current status in a conversational way for LLM context."""
        status = self.get_current_status()
        project_context = self.get_project_context()

        lines = []

        # Project summary
        if status['projects_count'] > 0:
            lines.append(f"• {status['projects_count']} civic projects in database")

        if status['verified_count'] > 0:
            lines.append(f"• {status['verified_count']} documents verified for compliance")

        if status['references_count'] > 0:
            lines.append(f"• {status['references_count']} reference annotations available")

        # Activity summary
        if status['last_activity']:
            lines.append(f"• Last analysis activity: {status['last_activity']}")

        # Active sources
        if status['active_sources']:
            sources_text = ", ".join(status['active_sources'])
            lines.append(f"• Active data sources: {sources_text}")

        # Project types
        if project_context['project_types']:
            types_text = ", ".join(f"{count} {ptype}" for ptype, count in project_context['project_types'].items())
            lines.append(f"• Project types: {types_text}")

        return "\n".join(lines) if lines else "No civic analysis activity yet."


# Utility functions
def create_civic_context(jaxwatch_root: str) -> CivicAnalysisContext:
    """
    Factory function to create civic analysis context.

    Args:
        jaxwatch_root: Path to JaxWatch root directory

    Returns:
        Configured CivicAnalysisContext
    """
    return CivicAnalysisContext(Path(jaxwatch_root))


if __name__ == "__main__":
    # Test civic context
    context = create_civic_context("/Users/jjjvvvvv/Desktop/JaxWatch")

    print("Current Civic Analysis Status:")
    print("=" * 40)

    status = context.get_current_status()
    for key, value in status.items():
        print(f"{key}: {value}")

    print("\nProject Context:")
    print("=" * 40)

    project_context = context.get_project_context()
    for key, value in project_context.items():
        print(f"{key}: {value}")

    print("\nConversational Status:")
    print("=" * 40)
    print(context.format_status_for_conversation())

    print("\nCivic context test completed!")