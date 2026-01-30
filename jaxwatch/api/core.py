#!/usr/bin/env python3
"""
JaxWatch Core API
Central API layer for all JaxWatch functionality, replacing subprocess execution.
"""

import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jaxwatch.config.manager import JaxWatchConfig, get_config
from jaxwatch.models import Project, EnrichedProject, DocumentVerification, ProjectReference
from jaxwatch.enrichment import ProjectEnrichmentPipeline


class ProjectExtractionResult:
    """Result of project extraction operation"""

    def __init__(self, projects_created: int = 0, projects_updated: int = 0,
                 projects_total: int = 0, errors: List[str] = None):
        self.projects_created = projects_created
        self.projects_updated = projects_updated
        self.projects_total = projects_total
        self.errors = errors or []
        self.success = len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            'projects_created': self.projects_created,
            'projects_updated': self.projects_updated,
            'projects_total': self.projects_total,
            'errors': self.errors,
            'success': self.success
        }


class DocumentVerificationResult:
    """Result of document verification operation"""

    def __init__(self, projects_processed: int = 0, projects_verified: int = 0,
                 errors: List[str] = None):
        self.projects_processed = projects_processed
        self.projects_verified = projects_verified
        self.errors = errors or []
        self.success = len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            'projects_processed': self.projects_processed,
            'projects_verified': self.projects_verified,
            'errors': self.errors,
            'success': self.success
        }


class ReferenceScanResult:
    """Result of reference scanning operation"""

    def __init__(self, documents_processed: int = 0, references_detected: int = 0,
                 errors: List[str] = None):
        self.documents_processed = documents_processed
        self.references_detected = references_detected
        self.errors = errors or []
        self.success = len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            'documents_processed': self.documents_processed,
            'references_detected': self.references_detected,
            'errors': self.errors,
            'success': self.success
        }


class ProjectFilters:
    """Filters for project queries"""

    def __init__(self, source: Optional[str] = None, year: Optional[str] = None,
                 doc_type: Optional[str] = None, pending_review: Optional[bool] = None,
                 has_verification: Optional[bool] = None):
        self.source = source
        self.year = year
        self.doc_type = doc_type
        self.pending_review = pending_review
        self.has_verification = has_verification


class JaxWatchCore:
    """Core API for JaxWatch functionality"""

    def __init__(self, config: Optional[JaxWatchConfig] = None):
        self.config = config or get_config()
        self._projects_cache = None
        self._cache_timestamp = None
        self._enrichment_pipeline = None

    @property
    def enrichment_pipeline(self) -> ProjectEnrichmentPipeline:
        """Get enrichment pipeline instance"""
        if self._enrichment_pipeline is None:
            self._enrichment_pipeline = ProjectEnrichmentPipeline(self.config)
        return self._enrichment_pipeline

    def extract_projects(self, source: Optional[str] = None, year: Optional[str] = None,
                        reset: bool = False) -> ProjectExtractionResult:
        """
        Extract projects from collected civic documents.

        Args:
            source: Limit to specific source (e.g., 'dia_board', 'dia_ddrb')
            year: Limit to specific year
            reset: Reset projects index before extraction

        Returns:
            ProjectExtractionResult with statistics and any errors
        """
        try:
            # Import the extract_projects module
            from backend.tools.extract_projects import main as extract_main

            # Build arguments for the extraction tool
            args = []
            if source:
                args.extend(['--source', source])
            if year:
                args.extend(['--year', str(year)])
            if reset:
                args.append('--reset')

            # Capture initial project count
            initial_projects = self._load_projects_index()
            initial_count = len(initial_projects)

            # Run extraction
            result_code = extract_main(args)

            if result_code != 0:
                return ProjectExtractionResult(errors=[f"Extraction failed with exit code {result_code}"])

            # Calculate changes
            final_projects = self._load_projects_index()
            final_count = len(final_projects)

            # Clear cache to force reload
            self._projects_cache = None

            return ProjectExtractionResult(
                projects_created=max(0, final_count - initial_count),
                projects_total=final_count
            )

        except Exception as e:
            return ProjectExtractionResult(errors=[f"Extraction error: {str(e)}"])

    def verify_documents(self, project_id: Optional[str] = None, force: bool = False,
                        active_year: Optional[int] = None) -> DocumentVerificationResult:
        """
        Verify documents using AI analysis.

        Args:
            project_id: Process only specified project ID
            force: Force reprocessing even if already verified
            active_year: Filter by active year

        Returns:
            DocumentVerificationResult with statistics and any errors
        """
        try:
            # Import the document verifier
            from document_verifier.commands.summarize import main as verify_main

            # Build arguments
            args = []
            if project_id:
                args.extend(['--project', project_id])
            if force:
                args.append('--force')
            if active_year:
                args.extend(['--active-year', str(active_year)])

            # Run verification
            result_code = verify_main(args)

            if result_code != 0:
                return DocumentVerificationResult(errors=[f"Verification failed with exit code {result_code}"])

            # Count processed projects (simplified for now)
            processed = 1 if project_id else 0

            return DocumentVerificationResult(
                projects_processed=processed,
                projects_verified=processed
            )

        except Exception as e:
            return DocumentVerificationResult(errors=[f"Verification error: {str(e)}"])

    def scan_references(self, source: Optional[str] = None, year: Optional[str] = None,
                       force: bool = False) -> ReferenceScanResult:
        """
        Scan for references and relationships in documents.

        Args:
            source: Process specific source
            year: Process specific year
            force: Force reprocessing

        Returns:
            ReferenceScanResult with statistics and any errors
        """
        try:
            # Import the reference scanner
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'reference_scanner'))
            from reference_scanner import run_command
            from types import SimpleNamespace

            # Build arguments namespace
            args = SimpleNamespace(
                source=source,
                year=year,
                force=force,
                dry_run=False
            )

            # Run reference scanning
            result_code = run_command(args)

            if result_code != 0:
                return ReferenceScanResult(errors=[f"Reference scanning failed with exit code {result_code}"])

            return ReferenceScanResult(
                documents_processed=0,  # Would need to capture from actual run
                references_detected=0
            )

        except Exception as e:
            return ReferenceScanResult(errors=[f"Reference scanning error: {str(e)}"])

    def get_projects(self, filters: Optional[ProjectFilters] = None) -> List[EnrichedProject]:
        """
        Get projects with optional filtering.

        Args:
            filters: Optional filters to apply

        Returns:
            List of EnrichedProject objects
        """
        try:
            projects_data = self._load_projects_index()
            enhanced_data = self._load_enhanced_projects()

            # Create lookup for enhanced data
            enhanced_lookup = {p.get('id'): p for p in enhanced_data if p.get('id')}

            projects = []
            for project_data in projects_data:
                # Create base project
                project = Project.from_dict(project_data)

                # Check if we have enhanced data
                enhanced_project_data = enhanced_lookup.get(project.id, project_data)
                enriched = EnrichedProject.from_dict(enhanced_project_data)

                # Apply filters
                if filters and not self._matches_filters(enriched, filters):
                    continue

                projects.append(enriched)

            return projects

        except Exception as e:
            print(f"Error loading projects: {e}")
            return []

    def get_project(self, project_id: str) -> Optional[EnrichedProject]:
        """
        Get a specific project by ID.

        Args:
            project_id: The project ID to retrieve

        Returns:
            EnrichedProject if found, None otherwise
        """
        projects = self.get_projects()
        for project in projects:
            if project.id == project_id:
                return project
        return None

    def enrich_projects(self, project_ids: Optional[List[str]] = None,
                       force_reverify: bool = False, max_workers: int = 3) -> 'EnrichmentResult':
        """
        Enrich projects with unified verification and reference scanning.

        Args:
            project_ids: Specific project IDs to enrich, or None for all
            force_reverify: Force re-verification even if already verified
            max_workers: Maximum number of parallel workers

        Returns:
            EnrichmentResult with statistics and any errors
        """
        try:
            # Load projects to enrich
            projects_data = self._load_projects_index()
            projects = [Project.from_dict(p) for p in projects_data]

            # Filter to specific project IDs if requested
            if project_ids:
                projects = [p for p in projects if p.id in project_ids]

            # Run enrichment pipeline
            from jaxwatch.enrichment.pipeline import EnrichmentResult
            result = self.enrichment_pipeline.enrich_batch(
                projects=projects,
                max_workers=max_workers,
                force_reverify=force_reverify
            )

            # Clear cache to force reload
            self._projects_cache = None

            return result

        except Exception as e:
            from jaxwatch.enrichment.pipeline import EnrichmentResult
            result = EnrichmentResult()
            result.add_error(f"Enrichment error: {str(e)}")
            return result

    def get_project_stats(self) -> Dict[str, int]:
        """
        Get project statistics.

        Returns:
            Dictionary with project counts and statistics
        """
        try:
            projects = self.get_projects()

            stats = {
                'total_projects': len(projects),
                'verified_projects': sum(1 for p in projects if p.is_verified),
                'pending_review': sum(1 for p in projects if p.project.pending_review),
                'dia_resolutions': sum(1 for p in projects if p.project.doc_type == 'DIA-RES'),
                'ddrb_cases': sum(1 for p in projects if p.project.doc_type == 'DDRB'),
                'with_references': sum(1 for p in projects if p.has_references)
            }

            return stats

        except Exception as e:
            print(f"Error computing stats: {e}")
            return {}

    def _load_projects_index(self) -> List[dict]:
        """Load projects from the projects index file"""
        projects_path = self.config.paths.projects_index

        if not projects_path.exists():
            return []

        try:
            with open(projects_path, 'r') as f:
                return json.load(f)
        except Exception:
            return []

    def _load_enhanced_projects(self) -> List[dict]:
        """Load enhanced projects data"""
        enhanced_path = self.config.paths.enhanced_projects

        if not enhanced_path.exists():
            return []

        try:
            with open(enhanced_path, 'r') as f:
                return json.load(f)
        except Exception:
            return []

    def _matches_filters(self, project: EnrichedProject, filters: ProjectFilters) -> bool:
        """Check if project matches the given filters"""
        if filters.source and project.project.source != filters.source:
            return False

        if filters.doc_type and project.project.doc_type != filters.doc_type:
            return False

        if filters.pending_review is not None and project.project.pending_review != filters.pending_review:
            return False

        if filters.has_verification is not None and project.is_verified != filters.has_verification:
            return False

        # Year filter - check meeting_date or project ID for year
        if filters.year:
            year_found = False
            if project.project.meeting_date and filters.year in project.project.meeting_date:
                year_found = True
            elif filters.year in project.id:
                year_found = True

            if not year_found:
                return False

        return True


# Convenience functions for backward compatibility
def extract_projects(source: Optional[str] = None, year: Optional[str] = None) -> ProjectExtractionResult:
    """Extract projects using the core API"""
    core = JaxWatchCore()
    return core.extract_projects(source=source, year=year)


def verify_documents(project_id: Optional[str] = None, force: bool = False) -> DocumentVerificationResult:
    """Verify documents using the core API"""
    core = JaxWatchCore()
    return core.verify_documents(project_id=project_id, force=force)


def scan_references(source: Optional[str] = None, year: Optional[str] = None) -> ReferenceScanResult:
    """Scan references using the core API"""
    core = JaxWatchCore()
    return core.scan_references(source=source, year=year)