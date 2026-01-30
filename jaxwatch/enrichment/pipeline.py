#!/usr/bin/env python3
"""
Unified Project Enrichment Pipeline
Coordinates document verification and reference scanning for projects.
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jaxwatch.config.manager import JaxWatchConfig, get_config
from jaxwatch.models import Project, EnrichedProject, DocumentVerification, ProjectReference, VerificationResult
from .unified_storage import UnifiedEnrichmentStorage


class EnrichmentResult:
    """Result of project enrichment operation"""

    def __init__(self):
        self.projects_processed = 0
        self.projects_verified = 0
        self.references_detected = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.processing_time_seconds = 0.0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, error: str):
        self.errors.append(error)

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'projects_processed': self.projects_processed,
            'projects_verified': self.projects_verified,
            'references_detected': self.references_detected,
            'errors': self.errors,
            'warnings': self.warnings,
            'success': self.success,
            'processing_time_seconds': self.processing_time_seconds
        }


class DocumentVerifierWrapper:
    """Wrapper for document verifier functionality"""

    def __init__(self, config: JaxWatchConfig):
        self.config = config

    def verify_project(self, project: Project) -> Optional[VerificationResult]:
        """
        Verify a single project using the document verifier.

        Args:
            project: Project to verify

        Returns:
            VerificationResult or None if verification fails
        """
        try:
            # Import document verifier components
            from document_verifier.commands.summarize import (
                load_config, call_llm, load_prompt_template, extract_key_sections
            )

            # Load document verifier config
            verifier_config = load_config()

            # For now, create a mock verification result since we'd need to
            # fully integrate the document verifier logic here
            # In a production implementation, this would extract and analyze
            # the actual document content for this project

            verification = VerificationResult(
                processed_at=datetime.now(),
                authorization=f"Mock authorization analysis for {project.id}",
                actors=f"Mock actors analysis for {project.title}",
                financial_mentions="Mock financial analysis",
                summary=f"Mock verification summary for project: {project.title}",
                confidence_score=0.85,
                raw_response="Mock LLM response"
            )

            return verification

        except Exception as e:
            print(f"Warning: Document verification failed for {project.id}: {e}")
            return None


class ReferenceScannerWrapper:
    """Wrapper for reference scanner functionality"""

    def __init__(self, config: JaxWatchConfig):
        self.config = config

    def scan_project_references(self, project: Project) -> List[ProjectReference]:
        """
        Scan for references in a project.

        Args:
            project: Project to scan for references

        Returns:
            List of ProjectReference objects
        """
        try:
            # Import reference scanner components if available
            # For now, return mock references since we'd need to
            # fully integrate the reference scanner logic

            references = []

            # Mock some reference detection based on project type
            if project.doc_type == "DIA-RES":
                # Mock ordinance reference
                ref = ProjectReference(
                    type="ordinance",
                    id=f"ORD-{project.id.replace('DIA-RES-', '')}",
                    title=f"Related ordinance for {project.title}",
                    confidence=0.75,
                    context=f"Referenced in resolution {project.id}",
                    source_document=project.id
                )
                references.append(ref)

            elif project.doc_type == "DDRB":
                # Mock project reference
                ref = ProjectReference(
                    type="project",
                    id=f"PROJ-{project.id.replace('DDRB-', '')}",
                    title=f"Related development project",
                    confidence=0.80,
                    context=f"DDRB case {project.id}",
                    source_document=project.id
                )
                references.append(ref)

            return references

        except Exception as e:
            print(f"Warning: Reference scanning failed for {project.id}: {e}")
            return []


class ProjectEnrichmentPipeline:
    """Unified pipeline for enriching projects with verification and references"""

    def __init__(self, config: Optional[JaxWatchConfig] = None):
        self.config = config or get_config()
        self.storage = UnifiedEnrichmentStorage(self.config)
        self.verifier = DocumentVerifierWrapper(self.config)
        self.scanner = ReferenceScannerWrapper(self.config)

    def enrich_project(self, project: Project, force_reverify: bool = False) -> EnrichedProject:
        """
        Enrich a single project with verification and reference data.

        Args:
            project: Project to enrich
            force_reverify: Force re-verification even if already verified

        Returns:
            EnrichedProject with enrichment data
        """
        enriched = EnrichedProject.from_project(project)

        # Check if project is already enriched and we're not forcing
        existing = self.storage.get_enriched_project(project.id)
        if existing and not force_reverify:
            return existing

        # Perform verification
        try:
            verification_result = self.verifier.verify_project(project)
            if verification_result:
                enriched.verification = DocumentVerification.from_legacy_format(
                    project.id, verification_result.to_dict()
                )
        except Exception as e:
            print(f"Verification failed for {project.id}: {e}")

        # Perform reference scanning
        try:
            references = self.scanner.scan_project_references(project)
            enriched.references = references
        except Exception as e:
            print(f"Reference scanning failed for {project.id}: {e}")

        # Update timestamp
        enriched.last_updated = datetime.now()

        # Store enriched project
        self.storage.save_enriched_project(enriched)

        return enriched

    def enrich_batch(self, projects: List[Project], max_workers: int = 3,
                    force_reverify: bool = False) -> EnrichmentResult:
        """
        Enrich multiple projects in parallel.

        Args:
            projects: List of projects to enrich
            max_workers: Maximum number of parallel workers
            force_reverify: Force re-verification even if already verified

        Returns:
            EnrichmentResult with statistics and errors
        """
        result = EnrichmentResult()
        start_time = datetime.now()

        # Filter projects that need enrichment if not forcing
        if not force_reverify:
            projects_to_process = []
            for project in projects:
                existing = self.storage.get_enriched_project(project.id)
                if not existing or not existing.is_verified:
                    projects_to_process.append(project)
            projects = projects_to_process

        result.projects_processed = len(projects)

        # Process projects in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all enrichment tasks
            future_to_project = {
                executor.submit(self.enrich_project, project, force_reverify): project
                for project in projects
            }

            # Collect results
            for future in as_completed(future_to_project):
                project = future_to_project[future]
                try:
                    enriched = future.result()
                    if enriched.is_verified:
                        result.projects_verified += 1
                    result.references_detected += len(enriched.references)
                except Exception as e:
                    error_msg = f"Failed to enrich {project.id}: {str(e)}"
                    result.add_error(error_msg)
                    print(f"Error: {error_msg}")

        # Calculate processing time
        end_time = datetime.now()
        result.processing_time_seconds = (end_time - start_time).total_seconds()

        return result

    def get_enrichment_stats(self) -> Dict[str, int]:
        """
        Get statistics about enriched projects.

        Returns:
            Dictionary with enrichment statistics
        """
        try:
            enriched_projects = self.storage.get_all_enriched_projects()

            stats = {
                'total_enriched': len(enriched_projects),
                'verified_projects': sum(1 for p in enriched_projects if p.is_verified),
                'projects_with_references': sum(1 for p in enriched_projects if p.has_references),
                'total_references': sum(len(p.references) for p in enriched_projects),
                'dia_resolutions': sum(1 for p in enriched_projects if p.project.doc_type == 'DIA-RES'),
                'ddrb_cases': sum(1 for p in enriched_projects if p.project.doc_type == 'DDRB'),
            }

            # Calculate reference types
            reference_types = {}
            for project in enriched_projects:
                for ref in project.references:
                    ref_type = ref.type
                    reference_types[ref_type] = reference_types.get(ref_type, 0) + 1

            stats['reference_types'] = reference_types

            return stats

        except Exception as e:
            print(f"Error calculating enrichment stats: {e}")
            return {}

    def cleanup_old_enrichments(self, days_old: int = 30) -> int:
        """
        Remove old enrichment data.

        Args:
            days_old: Remove enrichments older than this many days

        Returns:
            Number of enrichments removed
        """
        try:
            return self.storage.cleanup_old_enrichments(days_old)
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return 0