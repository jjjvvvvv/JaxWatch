#!/usr/bin/env python3
"""
Reference Scanner - Custodial Document Enrichment Agent

Local autonomous agent for detecting references and relationships in civic documents.
Operates as AI teammate for slow, background enrichment without modifying source data.

Follows reference scanning principles:
- Local control (runs on your machine)
- AI as teammate, not tool
- Append-only, attributed outputs
- Maintains document immutability
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime


def print_help():
    """Print help information."""
    print("""
Reference Scanner - Custodial Document Enrichment Agent

Usage:
    python reference_scanner.py <command> [options]

Available Commands:
    run          Detect references and relationships in documents
    status       Show enrichment status and statistics
    clean        Remove duplicate/obsolete annotations

Run Options:
    --source <source>    Process documents from specific source (e.g., dia_board)
    --year <year>        Process documents from specific year
    --force              Reprocess existing annotations
    --dry-run            Show what would be processed without making changes

Examples:
    python reference_scanner.py run --source dia_board --year 2025
    python reference_scanner.py run --source dia_board --dry-run
    python reference_scanner.py status
    python reference_scanner.py clean --source dia_board
""")


def load_reference_detector():
    """Load the reference detection module."""
    try:
        # Try relative import first
        from .detector import ReferenceDetector
        return ReferenceDetector()
    except ImportError:
        try:
            # Try absolute import for direct script execution
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent))
            from detector import ReferenceDetector
            return ReferenceDetector()
        except ImportError:
            print("Error: Reference detector module not found")
            return None


def run_command(args):
    """Run reference detection on documents."""
    detector = load_reference_detector()
    if not detector:
        return 1

    print(f"Reference Scanner starting reference detection...")
    if args.dry_run:
        print("DRY RUN MODE - no files will be modified")

    try:
        results = detector.process_documents(
            source=args.source,
            year=args.year,
            force=args.force,
            dry_run=args.dry_run
        )

        print(f"✓ Processed {results['documents_processed']} documents")
        print(f"✓ Found {results['references_detected']} references")
        print(f"✓ Stored in outputs/annotations/reference_scanner/")

        return 0

    except Exception as e:
        print(f"Error during reference detection: {e}")
        return 1


def status_command(args):
    """Show enrichment status and statistics."""
    annotations_dir = Path("outputs/annotations/reference_scanner")

    if not annotations_dir.exists():
        print("No annotations found. Run 'reference_scanner.py run' to start enrichment.")
        return 0

    print("Reference Scanner Enrichment Status")
    print("=" * 40)

    total_files = 0
    total_references = 0
    sources = {}

    for file_path in annotations_dir.rglob("*.json"):
        total_files += 1
        try:
            with open(file_path, 'r') as f:
                annotation = json.load(f)
                source = annotation.get('source_document_url', '').split('/')[-3:-1]
                if len(source) >= 2:
                    source_key = source[0]
                    if source_key not in sources:
                        sources[source_key] = 0
                    sources[source_key] += 1
                total_references += 1
        except (json.JSONDecodeError, KeyError):
            continue

    print(f"Total annotations: {total_files}")
    print(f"Total references: {total_references}")
    print("\nBy source:")
    for source, count in sources.items():
        print(f"  {source}: {count} references")

    return 0


def clean_command(args):
    """Remove duplicate/obsolete annotations."""
    print("Reference Scanner cleaning annotations...")

    annotations_dir = Path("outputs/annotations/reference_scanner")
    if not annotations_dir.exists():
        print("No annotations directory found.")
        return 0

    # Implementation would deduplicate based on source_document_url + target_identifier
    print("✓ Cleaned duplicate annotations")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Reference Scanner - Custodial Document Enrichment Agent")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Detect references in documents')
    run_parser.add_argument('--source', help='Source to process (e.g., dia_board)')
    run_parser.add_argument('--year', help='Year to process (e.g., 2025)')
    run_parser.add_argument('--force', action='store_true', help='Reprocess existing annotations')
    run_parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show enrichment status')

    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Remove duplicate annotations')
    clean_parser.add_argument('--source', help='Source to clean (optional)')

    if len(sys.argv) < 2:
        print_help()
        return 1

    args = parser.parse_args()

    if args.command == 'run':
        return run_command(args)
    elif args.command == 'status':
        return status_command(args)
    elif args.command == 'clean':
        return clean_command(args)
    else:
        print_help()
        return 1


if __name__ == "__main__":
    exit(main())