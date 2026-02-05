"""
JaxWatch - Jacksonville Civic Transparency Platform
A unified platform for extracting, verifying, and analyzing civic documents.
"""

from .api import JaxWatchCore
from .config.manager import get_config, JaxWatchConfig
from .llm import get_llm_client, LLMClient
from .pipeline import CivicPipeline, run_pipeline
from .state import CollectionManifest, get_manifest

__version__ = "0.1.0"
__all__ = [
    'JaxWatchCore',
    'get_config',
    'JaxWatchConfig',
    'get_llm_client',
    'LLMClient',
    'CivicPipeline',
    'run_pipeline',
    'CollectionManifest',
    'get_manifest',
]