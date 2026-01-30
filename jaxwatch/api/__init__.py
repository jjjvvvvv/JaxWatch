"""
JaxWatch API
Core API layer for JaxWatch functionality.
"""

from .core import (
    JaxWatchCore,
    ProjectExtractionResult,
    DocumentVerificationResult,
    ReferenceScanResult,
    ProjectFilters,
    extract_projects,
    verify_documents,
    scan_references
)

__all__ = [
    'JaxWatchCore',
    'ProjectExtractionResult',
    'DocumentVerificationResult',
    'ReferenceScanResult',
    'ProjectFilters',
    'extract_projects',
    'verify_documents',
    'scan_references'
]