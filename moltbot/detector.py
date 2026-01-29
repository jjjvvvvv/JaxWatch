#!/usr/bin/env python3
"""
Reference Detection Module for Molt Bot

Detects references to other resolutions, ordinances, and amendments in civic documents.
Operates with strict boundaries: no summaries, no inference beyond citation detection.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class ReferenceDetector:
    """
    Autonomous reference detection agent.

    Follows molt.bot principles:
    - Local operation with no cloud dependencies
    - Append-only, attributed outputs
    - Clear boundaries (citation detection only)
    - Idempotent operation (safe to re-run)
    """

    def __init__(self):
        self.outputs_dir = Path("outputs/annotations/molt")
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

        # Patterns for detecting civic document references
        self.patterns = {
            'ordinance': [
                r'ORDINANCE\s+(\d{4}-\d+-[A-Z]?\d*)',
                r'Ordinance\s+(\d{4}-\d+-[A-Z]?\d*)',
                r'ORD\.\s*(\d{4}-\d+-[A-Z]?\d*)'
            ],
            'resolution': [
                r'RESOLUTION\s+(\d{4}-\d+-\d+)',
                r'Resolution\s+(\d{4}-\d+-\d+)',
                r'RES\.\s*(\d{4}-\d+-\d+)'
            ],
            'amendment': [
                r'amended?\s+by\s+(ORDINANCE|RESOLUTION|ORD\.|RES\.)\s*(\d{4}-\d+-[A-Z]?\d*)',
                r'as\s+amended\s+by\s+(\w+\s+\d{4}-\d+-[A-Z]?\d*)'
            ],
            'section': [
                r'Section\s+(\d+(?:\.\d+)*)',
                r'SECTION\s+(\d+(?:\.\d+)*)',
                r'§\s*(\d+(?:\.\d+)*)'
            ]
        }

    def process_documents(self, source: str = None, year: str = None,
                         force: bool = False, dry_run: bool = False) -> Dict:
        """
        Process documents for reference detection.

        Args:
            source: Document source (e.g., 'dia_board')
            year: Year to process (e.g., '2025')
            force: Reprocess existing annotations
            dry_run: Show what would be processed without changes

        Returns:
            Dict with processing statistics
        """
        files_dir = Path("outputs/files")
        if not files_dir.exists():
            raise FileNotFoundError("No extracted document files found. Run PDF extractor first.")

        documents_processed = 0
        references_detected = 0

        # Find document files to process
        if source and year:
            search_path = files_dir / source / year / "*.txt"
        elif source:
            search_path = files_dir / source / "**" / "*.txt"
        else:
            search_path = files_dir / "**" / "*.txt"

        document_files = list(Path(".").glob(str(search_path)))

        print(f"Found {len(document_files)} documents to process")

        for doc_path in document_files:
            if dry_run:
                print(f"Would process: {doc_path}")
                continue

            references = self._detect_references_in_file(doc_path)
            if references:
                documents_processed += 1
                references_detected += len(references)

                for ref in references:
                    self._store_annotation(ref, force=force)

        return {
            'documents_processed': documents_processed,
            'references_detected': references_detected
        }

    def _detect_references_in_file(self, file_path: Path) -> List[Dict]:
        """
        Detect references in a single document file.

        Args:
            file_path: Path to the document text file

        Returns:
            List of reference annotations
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, FileNotFoundError):
            return []

        references = []

        # Extract source document URL from file path
        # Expected pattern: outputs/files/{source}/{year}/{filename}.pdf.txt
        path_parts = file_path.parts
        if len(path_parts) >= 4:
            source = path_parts[-3]
            year = path_parts[-2]
            filename = path_parts[-1].replace('.pdf.txt', '')

            # Reconstruct likely URL (this is a heuristic)
            if 'getattachment' in filename:
                # DIA Board pattern
                attachment_parts = filename.split('_')
                if len(attachment_parts) >= 2:
                    attachment_id = attachment_parts[1]
                    # Insert hyphens back into UUID format
                    if len(attachment_id) == 32:
                        formatted_id = f"{attachment_id[:8]}-{attachment_id[8:12]}-{attachment_id[12:16]}-{attachment_id[16:20]}-{attachment_id[20:]}"
                        doc_name = '_'.join(attachment_parts[2:])
                        source_url = f"https://dia.jacksonville.gov/cms/getattachment/{formatted_id}/{doc_name}"
                    else:
                        source_url = f"unknown://{source}/{year}/{filename}"
                else:
                    source_url = f"unknown://{source}/{year}/{filename}"
            else:
                source_url = f"unknown://{source}/{year}/{filename}"
        else:
            source_url = f"unknown:///{file_path}"

        # Detect different types of references
        for ref_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Extract context around the match
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end].strip()

                    # Determine confidence based on context
                    confidence = self._assess_confidence(match, context, ref_type)

                    if confidence != "low":  # Skip low-confidence matches
                        reference = {
                            "type": "reference",
                            "reference_type": ref_type,
                            "source_document_url": source_url,
                            "target_identifier": match.group(1) if match.groups() else match.group(0),
                            "evidence_excerpt": context,
                            "confidence": confidence,
                            "detected_at": datetime.now().isoformat(),
                            "molt_version": "0.1.0"
                        }
                        references.append(reference)

        return references

    def _assess_confidence(self, match, context: str, ref_type: str) -> str:
        """
        Assess confidence level of a detected reference.

        Args:
            match: Regex match object
            context: Text context around the match
            ref_type: Type of reference detected

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        context_lower = context.lower()

        # High confidence indicators
        high_indicators = [
            'as amended by',
            'pursuant to',
            'in accordance with',
            'authorized by',
            'subject to',
            'whereas'
        ]

        if any(indicator in context_lower for indicator in high_indicators):
            return "high"

        # Medium confidence indicators
        medium_indicators = [
            'resolution',
            'ordinance',
            'section',
            'adopted',
            'approved'
        ]

        if any(indicator in context_lower for indicator in medium_indicators):
            return "medium"

        return "low"

    def _store_annotation(self, reference: Dict, force: bool = False):
        """
        Store a reference annotation to disk.

        Args:
            reference: Reference annotation dict
            force: Overwrite existing annotation
        """
        # Create filename based on source URL and target
        source_url = reference['source_document_url']
        target = reference['target_identifier']

        # Create safe filename
        safe_source = re.sub(r'[^\w\-_.]', '_', source_url.split('/')[-1])
        safe_target = re.sub(r'[^\w\-_.]', '_', target)
        filename = f"{safe_source}_ref_{safe_target}_{reference['reference_type']}.json"

        output_path = self.outputs_dir / filename

        # Check if annotation already exists (idempotent operation)
        if output_path.exists() and not force:
            return

        # Store annotation
        with open(output_path, 'w') as f:
            json.dump(reference, f, indent=2)

    def get_references_for_document(self, document_url: str) -> List[Dict]:
        """
        Get all references detected for a specific document.

        Args:
            document_url: Source document URL

        Returns:
            List of reference annotations
        """
        references = []

        for annotation_file in self.outputs_dir.glob("*.json"):
            try:
                with open(annotation_file, 'r') as f:
                    annotation = json.load(f)
                    if annotation.get('source_document_url') == document_url:
                        references.append(annotation)
            except (json.JSONDecodeError, KeyError):
                continue

        return references