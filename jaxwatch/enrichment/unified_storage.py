#!/usr/bin/env python3
"""
Unified Enrichment Storage
Manages storage of enriched project data in a unified format.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from jaxwatch.config.manager import JaxWatchConfig
from jaxwatch.models import EnrichedProject, Project


class UnifiedEnrichmentStorage:
    """Unified storage for enriched project data"""

    def __init__(self, config: JaxWatchConfig):
        self.config = config
        self.enriched_projects_path = config.paths.enhanced_projects
        self._cache = {}
        self._cache_timestamp = None

    def save_enriched_project(self, enriched_project: EnrichedProject):
        """
        Save an enriched project to unified storage.

        Args:
            enriched_project: EnrichedProject to save
        """
        # Load existing data
        enriched_projects = self._load_enriched_projects()

        # Find and update existing project or add new one
        updated = False
        for i, existing in enumerate(enriched_projects):
            if existing.get('id') == enriched_project.id:
                enriched_projects[i] = enriched_project.to_dict()
                updated = True
                break

        if not updated:
            enriched_projects.append(enriched_project.to_dict())

        # Save back to file
        self._save_enriched_projects(enriched_projects)

        # Clear cache to force reload
        self._cache = {}

    def get_enriched_project(self, project_id: str) -> Optional[EnrichedProject]:
        """
        Get an enriched project by ID.

        Args:
            project_id: Project ID to retrieve

        Returns:
            EnrichedProject if found, None otherwise
        """
        enriched_projects_data = self._load_enriched_projects()

        for project_data in enriched_projects_data:
            if project_data.get('id') == project_id:
                try:
                    return EnrichedProject.from_dict(project_data)
                except Exception as e:
                    print(f"Error loading enriched project {project_id}: {e}")
                    return None

        return None

    def get_all_enriched_projects(self) -> List[EnrichedProject]:
        """
        Get all enriched projects.

        Returns:
            List of EnrichedProject objects
        """
        enriched_projects_data = self._load_enriched_projects()
        enriched_projects = []

        for project_data in enriched_projects_data:
            try:
                enriched = EnrichedProject.from_dict(project_data)
                enriched_projects.append(enriched)
            except Exception as e:
                project_id = project_data.get('id', 'unknown')
                print(f"Error loading enriched project {project_id}: {e}")
                continue

        return enriched_projects

    def cleanup_old_enrichments(self, days_old: int = 30) -> int:
        """
        Remove enrichment data older than specified days.

        Args:
            days_old: Remove enrichments older than this many days

        Returns:
            Number of enrichments removed
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)
        enriched_projects_data = self._load_enriched_projects()

        initial_count = len(enriched_projects_data)
        filtered_projects = []

        for project_data in enriched_projects_data:
            last_updated_str = project_data.get('last_updated')
            if last_updated_str:
                try:
                    last_updated = datetime.fromisoformat(last_updated_str)
                    if last_updated >= cutoff_date:
                        filtered_projects.append(project_data)
                except ValueError:
                    # Keep projects with invalid timestamps
                    filtered_projects.append(project_data)
            else:
                # Keep projects without timestamps
                filtered_projects.append(project_data)

        removed_count = initial_count - len(filtered_projects)

        if removed_count > 0:
            self._save_enriched_projects(filtered_projects)
            # Clear cache
            self._cache = {}

        return removed_count

    def get_enrichment_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current enrichment data.

        Returns:
            Dictionary with enrichment summary statistics
        """
        enriched_projects = self.get_all_enriched_projects()

        summary = {
            'total_projects': len(enriched_projects),
            'verified_projects': sum(1 for p in enriched_projects if p.is_verified),
            'projects_with_references': sum(1 for p in enriched_projects if p.has_references),
            'total_references': sum(len(p.references) for p in enriched_projects),
            'last_updated': None,
            'project_types': {},
            'verification_stats': {
                'total_verifications': 0,
                'successful_verifications': 0,
                'average_confidence': 0.0
            }
        }

        # Find most recent update
        most_recent = None
        for project in enriched_projects:
            if most_recent is None or project.last_updated > most_recent:
                most_recent = project.last_updated

        if most_recent:
            summary['last_updated'] = most_recent.isoformat()

        # Count project types
        for project in enriched_projects:
            doc_type = project.project.doc_type
            summary['project_types'][doc_type] = summary['project_types'].get(doc_type, 0) + 1

        # Calculate verification stats
        total_verifications = 0
        successful_verifications = 0
        total_confidence = 0.0

        for project in enriched_projects:
            if project.verification and project.verification.results:
                for result in project.verification.results:
                    total_verifications += 1
                    if result.confidence_score > 0:
                        successful_verifications += 1
                        total_confidence += result.confidence_score

        summary['verification_stats']['total_verifications'] = total_verifications
        summary['verification_stats']['successful_verifications'] = successful_verifications

        if successful_verifications > 0:
            summary['verification_stats']['average_confidence'] = total_confidence / successful_verifications

        return summary

    def export_enrichment_data(self, output_path: Path, format_type: str = 'json') -> bool:
        """
        Export enrichment data to a file.

        Args:
            output_path: Path to save exported data
            format_type: Export format ('json' or 'csv')

        Returns:
            True if export successful, False otherwise
        """
        try:
            enriched_projects = self.get_all_enriched_projects()

            if format_type.lower() == 'json':
                export_data = {
                    'exported_at': datetime.now().isoformat(),
                    'total_projects': len(enriched_projects),
                    'projects': [p.to_dict() for p in enriched_projects]
                }

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w') as f:
                    json.dump(export_data, f, indent=2)

            elif format_type.lower() == 'csv':
                import csv

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', newline='') as f:
                    writer = csv.writer(f)

                    # Write header
                    writer.writerow([
                        'project_id', 'title', 'doc_type', 'source', 'meeting_date',
                        'is_verified', 'verification_confidence', 'reference_count',
                        'last_updated'
                    ])

                    # Write data rows
                    for project in enriched_projects:
                        confidence = 0.0
                        if project.verification and project.verification.latest_result:
                            confidence = project.verification.latest_result.confidence_score

                        writer.writerow([
                            project.id,
                            project.title,
                            project.project.doc_type,
                            project.project.source,
                            project.project.meeting_date or '',
                            project.is_verified,
                            confidence,
                            len(project.references),
                            project.last_updated.isoformat() if project.last_updated else ''
                        ])

            else:
                print(f"Unsupported export format: {format_type}")
                return False

            return True

        except Exception as e:
            print(f"Error exporting enrichment data: {e}")
            return False

    def _load_enriched_projects(self) -> List[Dict]:
        """Load enriched projects from file with caching"""
        # Check cache first
        if self._cache and self._cache_timestamp:
            # Cache for 5 minutes
            if (datetime.now() - self._cache_timestamp).total_seconds() < 300:
                return self._cache.get('projects', [])

        # Load from file
        if not self.enriched_projects_path.exists():
            return []

        try:
            with open(self.enriched_projects_path, 'r') as f:
                data = json.load(f)

            # Handle both new format (list) and legacy format (single dict)
            if isinstance(data, list):
                projects = data
            else:
                # Legacy format - wrap single project in list
                projects = [data] if data else []

            # Update cache
            self._cache = {'projects': projects}
            self._cache_timestamp = datetime.now()

            return projects

        except Exception as e:
            print(f"Error loading enriched projects: {e}")
            return []

    def _save_enriched_projects(self, projects_data: List[Dict]):
        """Save enriched projects to file"""
        try:
            # Ensure directory exists
            self.enriched_projects_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.enriched_projects_path, 'w') as f:
                json.dump(projects_data, f, indent=2)

        except Exception as e:
            print(f"Error saving enriched projects: {e}")
            raise