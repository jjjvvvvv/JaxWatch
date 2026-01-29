"""
Reference Scanner - Custodial Document Enrichment Agent

Local autonomous agent for detecting references and relationships in civic documents.
Operates as AI teammate following reference scanning principles:

- Local control (runs on your machine)
- AI as teammate, not tool
- Append-only, attributed outputs
- Maintains document immutability
- Idempotent operation (safe to re-run)

Usage:
    python reference_scanner/reference_scanner.py run --source dia_board --year 2025
"""

__version__ = "0.1.0"

from .detector import ReferenceDetector

__all__ = ["ReferenceDetector"]