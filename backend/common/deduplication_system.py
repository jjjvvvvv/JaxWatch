#!/usr/bin/env python3
"""
JaxWatch Deduplication System
Prevents reprocessing of identical documents and duplicate project entries
Principles: Content-aware, version-sensitive, audit-friendly
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import re
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class DocumentFingerprint:
    """Digital fingerprint of a document for deduplication"""
    file_hash: str  # SHA-256 of file content
    content_hash: str  # SHA-256 of normalized text content
    structural_hash: str  # Hash of document structure (page count, etc.)
    metadata_hash: str  # Hash of key metadata (date, title, etc.)
    size: int
    page_count: int
    created_at: datetime
    source_path: str

@dataclass
class ProjectSignature:
    """Signature of a project for duplicate detection"""
    project_id: str
    location_normalized: str
    request_fingerprint: str
    meeting_date: str
    department: str
    signature_hash: str  # Combined hash of key fields

@dataclass
class DeduplicationResult:
    """Result of deduplication check"""
    is_duplicate: bool
    duplicate_type: str  # 'file', 'content', 'project'
    existing_entry: Optional[Dict[str, Any]] = None
    confidence: float = 0.0  # 0.0 to 1.0
    reasons: List[str] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []

class DocumentDeduplicator:
    """Handles document-level deduplication"""

    def __init__(self, storage_dir: str = "data/deduplication"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.fingerprints_file = self.storage_dir / "document_fingerprints.json"
        self.fingerprints: Dict[str, Dict[str, Any]] = self._load_fingerprints()

        self.logger = logging.getLogger(__name__)

    def _load_fingerprints(self) -> Dict[str, Dict[str, Any]]:
        """Load existing document fingerprints"""
        if self.fingerprints_file.exists():
            try:
                with open(self.fingerprints_file, 'r') as f:
                    data = json.load(f)
                    # Convert ISO strings back to datetime objects where needed
                    for fp_data in data.values():
                        if 'created_at' in fp_data:
                            fp_data['created_at'] = datetime.fromisoformat(fp_data['created_at'])
                    return data
            except Exception as e:
                self.logger.error(f"Error loading fingerprints: {e}")
                return {}
        return {}

    def _save_fingerprints(self):
        """Save document fingerprints to file"""
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            serializable_data = {}
            for key, fp_data in self.fingerprints.items():
                serializable_data[key] = dict(fp_data)
                if 'created_at' in serializable_data[key]:
                    serializable_data[key]['created_at'] = serializable_data[key]['created_at'].isoformat()

            with open(self.fingerprints_file, 'w') as f:
                json.dump(serializable_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving fingerprints: {e}")

    def calculate_content_hash(self, text_content: str) -> str:
        """Calculate normalized content hash"""
        if not text_content:
            return ""

        # Normalize text for content comparison
        normalized = text_content.lower()
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = normalized.strip()

        return hashlib.sha256(normalized.encode()).hexdigest()

    def calculate_structural_hash(self, metadata: Dict[str, Any]) -> str:
        """Calculate hash of document structure"""
        structural_data = {
            'page_count': metadata.get('page_count', 0),
            'file_size_kb': metadata.get('file_size', 0) // 1024,  # Rounded to KB
            'has_text': metadata.get('text_length', 0) > 100
        }

        structural_str = json.dumps(structural_data, sort_keys=True)
        return hashlib.sha256(structural_str.encode()).hexdigest()

    def calculate_metadata_hash(self, metadata: Dict[str, Any]) -> str:
        """Calculate hash of key metadata fields"""
        key_metadata = {}

        # Extract key fields that should be consistent across versions
        for field in ['department', 'document_type', 'meeting_date']:
            if field in metadata:
                key_metadata[field] = str(metadata[field]).lower().strip()

        # Add title/subject if available
        for field in ['title', 'subject', 'filename']:
            if field in metadata:
                # Extract meaningful parts from filename/title
                value = str(metadata[field]).lower()
                # Remove date patterns, extensions, etc.
                value = re.sub(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', '', value)
                value = re.sub(r'\.(pdf|doc|docx)$', '', value)
                value = re.sub(r'[^\w\s]', ' ', value)
                value = re.sub(r'\s+', ' ', value).strip()
                if value:
                    key_metadata['title_clean'] = value
                break

        metadata_str = json.dumps(key_metadata, sort_keys=True)
        return hashlib.sha256(metadata_str.encode()).hexdigest()

    def create_fingerprint(self, file_path: Path, text_content: str,
                          metadata: Dict[str, Any]) -> DocumentFingerprint:
        """Create a complete fingerprint for a document"""

        # Calculate file hash
        with open(file_path, 'rb') as f:
            file_content = f.read()
            file_hash = hashlib.sha256(file_content).hexdigest()

        # Calculate other hashes
        content_hash = self.calculate_content_hash(text_content)
        structural_hash = self.calculate_structural_hash(metadata)
        metadata_hash = self.calculate_metadata_hash(metadata)

        return DocumentFingerprint(
            file_hash=file_hash,
            content_hash=content_hash,
            structural_hash=structural_hash,
            metadata_hash=metadata_hash,
            size=len(file_content),
            page_count=metadata.get('page_count', 0),
            created_at=datetime.now(),
            source_path=str(file_path)
        )

    def check_duplicate(self, file_path: Path, text_content: str,
                       metadata: Dict[str, Any]) -> DeduplicationResult:
        """Check if document is a duplicate"""

        fingerprint = self.create_fingerprint(file_path, text_content, metadata)

        # Check for exact file duplicate
        for fp_id, fp_data in self.fingerprints.items():
            if fp_data['file_hash'] == fingerprint.file_hash:
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_type='file',
                    existing_entry=fp_data,
                    confidence=1.0,
                    reasons=['Identical file hash (exact same file)']
                )

        # Check for content duplicate (same content, possibly different file)
        for fp_id, fp_data in self.fingerprints.items():
            if (fp_data['content_hash'] == fingerprint.content_hash and
                fingerprint.content_hash != ""):  # Only if we have content

                confidence = 0.9
                reasons = ['Identical content hash']

                # Increase confidence if metadata also matches
                if fp_data['metadata_hash'] == fingerprint.metadata_hash:
                    confidence = 0.95
                    reasons.append('Identical metadata')

                # Decrease confidence if structure is very different
                if fp_data['structural_hash'] != fingerprint.structural_hash:
                    confidence *= 0.8
                    reasons.append('Different document structure')

                if confidence >= 0.8:  # High confidence threshold
                    return DeduplicationResult(
                        is_duplicate=True,
                        duplicate_type='content',
                        existing_entry=fp_data,
                        confidence=confidence,
                        reasons=reasons
                    )

        # Check for near-duplicate (similar metadata + structure)
        for fp_id, fp_data in self.fingerprints.items():
            reasons = []
            confidence = 0.0

            # Same metadata
            if fp_data['metadata_hash'] == fingerprint.metadata_hash:
                confidence += 0.4
                reasons.append('Same metadata (department, type, date)')

            # Same structure
            if fp_data['structural_hash'] == fingerprint.structural_hash:
                confidence += 0.3
                reasons.append('Same document structure')

            # Similar size
            size_ratio = min(fp_data['size'], fingerprint.size) / max(fp_data['size'], fingerprint.size)
            if size_ratio >= 0.9:
                confidence += 0.2
                reasons.append('Similar file size')

            # If we have high similarity but different content, it might be an amended version
            if confidence >= 0.7 and fp_data['content_hash'] != fingerprint.content_hash:
                return DeduplicationResult(
                    is_duplicate=False,  # Not a duplicate, but worth noting
                    duplicate_type='potential_amendment',
                    existing_entry=fp_data,
                    confidence=confidence,
                    reasons=reasons + ['Different content - possible amendment']
                )

        return DeduplicationResult(is_duplicate=False, duplicate_type='unique')

    def register_document(self, file_path: Path, text_content: str,
                         metadata: Dict[str, Any]) -> str:
        """Register a new document fingerprint"""

        fingerprint = self.create_fingerprint(file_path, text_content, metadata)
        fingerprint_id = fingerprint.file_hash[:16]  # Use first 16 chars as ID

        self.fingerprints[fingerprint_id] = asdict(fingerprint)
        self._save_fingerprints()

        self.logger.info(f"Registered document fingerprint: {fingerprint_id}")
        return fingerprint_id

class ProjectDeduplicator:
    """Handles project-level deduplication"""

    def __init__(self, storage_dir: str = "data/deduplication"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.signatures_file = self.storage_dir / "project_signatures.json"
        self.signatures: Dict[str, Dict[str, Any]] = self._load_signatures()

        self.logger = logging.getLogger(__name__)

    def _load_signatures(self) -> Dict[str, Dict[str, Any]]:
        """Load existing project signatures"""
        if self.signatures_file.exists():
            try:
                with open(self.signatures_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading project signatures: {e}")
                return {}
        return {}

    def _save_signatures(self):
        """Save project signatures to file"""
        try:
            with open(self.signatures_file, 'w') as f:
                json.dump(self.signatures, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving project signatures: {e}")

    def normalize_location(self, location: str) -> str:
        """Normalize location string for comparison"""
        if not location:
            return ""

        normalized = location.lower().strip()

        # Remove common variations
        normalized = re.sub(r'\b(street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd)\b', '', normalized)
        normalized = re.sub(r'\b(north|south|east|west|n|s|e|w)\b', '', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def create_request_fingerprint(self, request: str) -> str:
        """Create fingerprint of project request"""
        if not request:
            return ""

        # Normalize the request text
        normalized = request.lower().strip()

        # Extract key concepts (remove common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}

        words = re.findall(r'\w+', normalized)
        meaningful_words = [w for w in words if w not in stop_words and len(w) > 2]

        # Sort words to make fingerprint order-independent
        meaningful_words.sort()

        fingerprint_text = ' '.join(meaningful_words)
        return hashlib.sha256(fingerprint_text.encode()).hexdigest()

    def create_project_signature(self, project: Dict[str, Any]) -> ProjectSignature:
        """Create signature for a project"""

        project_id = project.get('project_id', '').strip()
        location = self.normalize_location(project.get('location', ''))
        request_fp = self.create_request_fingerprint(project.get('request', ''))
        meeting_date = project.get('meeting_date', '').strip()
        department = project.get('metadata', {}).get('department', '').strip()

        # Create combined signature hash
        signature_data = {
            'project_id': project_id.lower(),
            'location_normalized': location,
            'request_fingerprint': request_fp,
            'meeting_date': meeting_date,
            'department': department.lower()
        }

        signature_str = json.dumps(signature_data, sort_keys=True)
        signature_hash = hashlib.sha256(signature_str.encode()).hexdigest()

        return ProjectSignature(
            project_id=project_id,
            location_normalized=location,
            request_fingerprint=request_fp,
            meeting_date=meeting_date,
            department=department,
            signature_hash=signature_hash
        )

    def check_project_duplicate(self, project: Dict[str, Any]) -> DeduplicationResult:
        """Check if project is a duplicate"""

        signature = self.create_project_signature(project)

        # Check for exact signature match
        for sig_id, sig_data in self.signatures.items():
            if sig_data['signature_hash'] == signature.signature_hash:
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_type='project',
                    existing_entry=sig_data,
                    confidence=1.0,
                    reasons=['Identical project signature']
                )

        # Check for partial matches
        for sig_id, sig_data in self.signatures.items():
            confidence = 0.0
            reasons = []

            # Same project ID
            if (signature.project_id and sig_data['project_id'] and
                signature.project_id.lower() == sig_data['project_id'].lower()):
                confidence += 0.5
                reasons.append('Same project ID')

            # Same location
            if (signature.location_normalized and sig_data['location_normalized'] and
                signature.location_normalized == sig_data['location_normalized']):
                confidence += 0.3
                reasons.append('Same location')

            # Same request fingerprint
            if (signature.request_fingerprint and sig_data['request_fingerprint'] and
                signature.request_fingerprint == sig_data['request_fingerprint']):
                confidence += 0.3
                reasons.append('Same request description')

            # Same meeting date (could indicate duplicate entry)
            if (signature.meeting_date and sig_data['meeting_date'] and
                signature.meeting_date == sig_data['meeting_date']):
                confidence += 0.2
                reasons.append('Same meeting date')

            # Different department reduces confidence (might be cross-referenced)
            if (signature.department and sig_data['department'] and
                signature.department != sig_data['department']):
                confidence *= 0.7
                reasons.append('Different department - possible cross-reference')

            if confidence >= 0.8:  # High confidence threshold
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_type='project',
                    existing_entry=sig_data,
                    confidence=confidence,
                    reasons=reasons
                )

        return DeduplicationResult(is_duplicate=False, duplicate_type='unique')

    def register_project(self, project: Dict[str, Any]) -> str:
        """Register a new project signature"""

        signature = self.create_project_signature(project)
        signature_id = signature.signature_hash[:16]  # Use first 16 chars as ID

        self.signatures[signature_id] = asdict(signature)
        self._save_signatures()

        self.logger.info(f"Registered project signature: {signature_id} ({signature.project_id})")
        return signature_id

class DeduplicationManager:
    """Main deduplication manager coordinating document and project deduplication"""

    def __init__(self, storage_dir: str = "data/deduplication"):
        self.document_deduplicator = DocumentDeduplicator(storage_dir)
        self.project_deduplicator = ProjectDeduplicator(storage_dir)
        self.logger = logging.getLogger(__name__)

    def check_document(self, file_path: Path, text_content: str,
                      metadata: Dict[str, Any]) -> DeduplicationResult:
        """Check if document is a duplicate"""
        return self.document_deduplicator.check_duplicate(file_path, text_content, metadata)

    def check_projects(self, projects: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], DeduplicationResult]]:
        """Check list of projects for duplicates"""
        results = []
        for project in projects:
            duplicate_result = self.project_deduplicator.check_project_duplicate(project)
            results.append((project, duplicate_result))
        return results

    def register_document(self, file_path: Path, text_content: str,
                         metadata: Dict[str, Any]) -> str:
        """Register document for future deduplication"""
        return self.document_deduplicator.register_document(file_path, text_content, metadata)

    def register_projects(self, projects: List[Dict[str, Any]]) -> List[str]:
        """Register projects for future deduplication"""
        signature_ids = []
        for project in projects:
            sig_id = self.project_deduplicator.register_project(project)
            signature_ids.append(sig_id)
        return signature_ids

    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get statistics about deduplication database"""
        return {
            "document_fingerprints": len(self.document_deduplicator.fingerprints),
            "project_signatures": len(self.project_deduplicator.signatures),
            "storage_dir": str(self.document_deduplicator.storage_dir),
            "last_updated": datetime.now().isoformat()
        }

# Convenience functions
def check_document_duplicate(file_path: Path, text_content: str,
                           metadata: Dict[str, Any]) -> DeduplicationResult:
    """Convenience function to check document duplication"""
    manager = DeduplicationManager()
    return manager.check_document(file_path, text_content, metadata)

def register_processed_document(file_path: Path, text_content: str,
                              metadata: Dict[str, Any], projects: List[Dict[str, Any]]):
    """Convenience function to register a processed document and its projects"""
    manager = DeduplicationManager()

    # Register document
    doc_id = manager.register_document(file_path, text_content, metadata)

    # Register projects
    project_ids = manager.register_projects(projects)

    logger.info(f"Registered document {doc_id} with {len(project_ids)} projects")
    return doc_id, project_ids

if __name__ == "__main__":
    # Example usage and testing
    manager = DeduplicationManager()
    stats = manager.get_deduplication_stats()

    print("🔍 JaxWatch Deduplication System")
    print(f"📄 Documents tracked: {stats['document_fingerprints']}")
    print(f"🏗️  Projects tracked: {stats['project_signatures']}")
    print(f"📁 Storage: {stats['storage_dir']}")