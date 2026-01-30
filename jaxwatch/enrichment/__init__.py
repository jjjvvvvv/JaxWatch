"""
JaxWatch Enrichment Pipeline
Unified document verification and reference scanning.
"""

from .pipeline import ProjectEnrichmentPipeline, EnrichmentResult
from .unified_storage import UnifiedEnrichmentStorage

__all__ = [
    'ProjectEnrichmentPipeline',
    'EnrichmentResult',
    'UnifiedEnrichmentStorage'
]