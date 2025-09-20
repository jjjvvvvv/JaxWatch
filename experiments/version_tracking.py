#!/usr/bin/env python3
"""
JaxWatch Version Tracking System
Tracks amendments, corrections, and versions of municipal documents
Principles: Transparency, auditability, version lineage
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re

logger = logging.getLogger(__name__)

class VersionType(str, Enum):
    """Types of document versions"""
    ORIGINAL = "original"
    AMENDMENT = "amendment"
    CORRECTION = "correction"
    REVISION = "revision"
    SUPPLEMENT = "supplement"
    REPLACEMENT = "replacement"

class VersionStatus(str, Enum):
    """Status of a document version"""
    CURRENT = "current"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"

@dataclass
class VersionMetadata:
    """Metadata for a document version"""
    version_id: str
    version_number: str  # e.g., "1.0", "1.1", "2.0"
    version_type: VersionType
    status: VersionStatus
    created_at: datetime
    title: str
    description: str
    changes_summary: Optional[str] = None
    supersedes: Optional[str] = None  # Previous version ID
    superseded_by: Optional[str] = None  # Next version ID
    source_file: Optional[str] = None
    file_hash: Optional[str] = None

@dataclass
class DocumentVersion:
    """A specific version of a document"""
    metadata: VersionMetadata
    content_hash: str
    projects: List[Dict[str, Any]]
    processing_metadata: Dict[str, Any]

class VersionTracker:
    """Tracks document versions and their relationships"""

    def __init__(self, storage_dir: str = "data/versions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.versions_file = self.storage_dir / "document_versions.json"
        self.versions: Dict[str, Dict[str, Any]] = self._load_versions()

        self.lineage_file = self.storage_dir / "version_lineage.json"
        self.lineage: Dict[str, List[str]] = self._load_lineage()

        self.logger = logging.getLogger(__name__)

    def _load_versions(self) -> Dict[str, Dict[str, Any]]:
        """Load version metadata from storage"""
        if self.versions_file.exists():
            try:
                with open(self.versions_file, 'r') as f:
                    data = json.load(f)
                    # Convert ISO strings back to datetime objects
                    for version_data in data.values():
                        if 'metadata' in version_data and 'created_at' in version_data['metadata']:
                            version_data['metadata']['created_at'] = datetime.fromisoformat(
                                version_data['metadata']['created_at']
                            )
                    return data
            except Exception as e:
                self.logger.error(f"Error loading versions: {e}")
                return {}
        return {}

    def _save_versions(self):
        """Save version metadata to storage"""
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            serializable_data = {}
            for version_id, version_data in self.versions.items():
                serializable_data[version_id] = dict(version_data)
                if ('metadata' in serializable_data[version_id] and
                    'created_at' in serializable_data[version_id]['metadata']):
                    serializable_data[version_id]['metadata']['created_at'] = (
                        serializable_data[version_id]['metadata']['created_at'].isoformat()
                    )

            with open(self.versions_file, 'w') as f:
                json.dump(serializable_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving versions: {e}")

    def _load_lineage(self) -> Dict[str, List[str]]:
        """Load version lineage relationships"""
        if self.lineage_file.exists():
            try:
                with open(self.lineage_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading lineage: {e}")
                return {}
        return {}

    def _save_lineage(self):
        """Save version lineage relationships"""
        try:
            with open(self.lineage_file, 'w') as f:
                json.dump(self.lineage, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving lineage: {e}")

    def detect_version_type(self, title: str, description: str,
                           filename: str = "") -> VersionType:
        """Automatically detect version type from document metadata"""

        text_to_analyze = f"{title} {description} {filename}".lower()

        # Patterns for different version types
        if any(pattern in text_to_analyze for pattern in [
            'amend', 'amended', 'amendment', 'modify', 'modified', 'modification'
        ]):
            return VersionType.AMENDMENT

        if any(pattern in text_to_analyze for pattern in [
            'correct', 'corrected', 'correction', 'errata', 'fix', 'fixed'
        ]):
            return VersionType.CORRECTION

        if any(pattern in text_to_analyze for pattern in [
            'revised', 'revision', 'update', 'updated', 'revise'
        ]):
            return VersionType.REVISION

        if any(pattern in text_to_analyze for pattern in [
            'supplement', 'supplemental', 'additional', 'addendum'
        ]):
            return VersionType.SUPPLEMENT

        if any(pattern in text_to_analyze for pattern in [
            'replacement', 'replace', 'supersede', 'superseded', 'new version'
        ]):
            return VersionType.REPLACEMENT

        return VersionType.ORIGINAL

    def extract_version_number(self, title: str, description: str,
                              filename: str = "") -> str:
        """Extract version number from document metadata"""

        text_to_analyze = f"{title} {description} {filename}"

        # Look for version patterns
        version_patterns = [
            r'v(\d+(?:\.\d+)*)',  # v1.0, v2.1.3
            r'version\s+(\d+(?:\.\d+)*)',  # version 1.0
            r'rev\s+(\d+(?:\.\d+)*)',  # rev 1.0
            r'(\d+(?:\.\d+)*)\s*(?:st|nd|rd|th)?\s*(?:revision|version|rev)',  # 1st revision
        ]

        for pattern in version_patterns:
            match = re.search(pattern, text_to_analyze, re.IGNORECASE)
            if match:
                return match.group(1)

        # Look for amendment/correction numbers
        amendment_patterns = [
            r'amendment\s+(\d+)',
            r'correction\s+(\d+)',
            r'revision\s+(\d+)'
        ]

        base_version = "1.0"
        for pattern in amendment_patterns:
            match = re.search(pattern, text_to_analyze, re.IGNORECASE)
            if match:
                amendment_num = match.group(1)
                return f"{base_version}.{amendment_num}"

        # Default version number
        return "1.0"

    def find_related_versions(self, title: str, metadata: Dict[str, Any]) -> List[str]:
        """Find related versions of the same document"""

        related_versions = []

        # Normalize title for comparison
        normalized_title = self._normalize_document_title(title)

        for version_id, version_data in self.versions.items():
            existing_title = version_data.get('metadata', {}).get('title', '')
            existing_normalized = self._normalize_document_title(existing_title)

            # Check if titles are similar
            if self._titles_are_related(normalized_title, existing_normalized):
                # Additional checks for same meeting/date
                if self._same_meeting_context(metadata, version_data.get('processing_metadata', {})):
                    related_versions.append(version_id)

        return related_versions

    def _normalize_document_title(self, title: str) -> str:
        """Normalize document title for comparison"""
        if not title:
            return ""

        normalized = title.lower().strip()

        # Remove version indicators
        normalized = re.sub(r'\b(?:v\d+(?:\.\d+)*|version\s+\d+(?:\.\d+)*|rev\s+\d+(?:\.\d+)*)\b', '', normalized)
        normalized = re.sub(r'\b(?:amendment|correction|revision|supplement)\s*\d*\b', '', normalized)

        # Remove dates
        normalized = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', '', normalized)

        # Clean up whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def _titles_are_related(self, title1: str, title2: str) -> bool:
        """Check if two normalized titles refer to the same document"""
        if not title1 or not title2:
            return False

        # Simple similarity check - at least 70% of words in common
        words1 = set(title1.split())
        words2 = set(title2.split())

        if not words1 or not words2:
            return False

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        similarity = intersection / union if union > 0 else 0
        return similarity >= 0.7

    def _same_meeting_context(self, metadata1: Dict[str, Any],
                             metadata2: Dict[str, Any]) -> bool:
        """Check if two documents are from the same meeting context"""

        # Check meeting date
        date1 = metadata1.get('meeting_date', '')
        date2 = metadata2.get('meeting_date', '')
        if date1 and date2 and date1 == date2:
            return True

        # Check department
        dept1 = metadata1.get('department', '')
        dept2 = metadata2.get('department', '')
        if dept1 and dept2 and dept1 == dept2:
            return True

        return False

    def register_version(self, title: str, description: str, content_hash: str,
                        projects: List[Dict[str, Any]],
                        processing_metadata: Dict[str, Any],
                        filename: str = "") -> str:
        """Register a new document version"""

        # Detect version type and number
        version_type = self.detect_version_type(title, description, filename)
        version_number = self.extract_version_number(title, description, filename)

        # Find related versions
        related_versions = self.find_related_versions(title, processing_metadata)

        # Determine if this supersedes an existing version
        supersedes = None
        if related_versions:
            # Find the most recent current version
            for version_id in related_versions:
                version_data = self.versions[version_id]
                if version_data['metadata']['status'] == VersionStatus.CURRENT.value:
                    supersedes = version_id
                    break

        # Generate version ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_id = re.sub(r'[^\w]', '_', title.lower()[:30])
        version_id = f"{base_id}_{timestamp}"

        # Create version metadata
        metadata = VersionMetadata(
            version_id=version_id,
            version_number=version_number,
            version_type=version_type,
            status=VersionStatus.CURRENT,
            created_at=datetime.now(),
            title=title,
            description=description,
            changes_summary=self._generate_changes_summary(version_type, description),
            supersedes=supersedes,
            source_file=filename,
            file_hash=processing_metadata.get('file_hash')
        )

        # Create document version
        document_version = DocumentVersion(
            metadata=metadata,
            content_hash=content_hash,
            projects=projects,
            processing_metadata=processing_metadata
        )

        # Store version
        self.versions[version_id] = asdict(document_version)

        # Update lineage
        if supersedes:
            # Mark superseded version as superseded
            if supersedes in self.versions:
                self.versions[supersedes]['metadata']['status'] = VersionStatus.SUPERSEDED.value
                self.versions[supersedes]['metadata']['superseded_by'] = version_id

            # Update lineage chain
            lineage_key = self._get_lineage_key(title, processing_metadata)
            if lineage_key in self.lineage:
                self.lineage[lineage_key].append(version_id)
            else:
                self.lineage[lineage_key] = [supersedes, version_id]
        else:
            # Start new lineage
            lineage_key = self._get_lineage_key(title, processing_metadata)
            self.lineage[lineage_key] = [version_id]

        # Save to storage
        self._save_versions()
        self._save_lineage()

        self.logger.info(f"Registered version {version_id} ({version_type.value}, v{version_number})")

        return version_id

    def _generate_changes_summary(self, version_type: VersionType, description: str) -> str:
        """Generate a summary of changes based on version type and description"""

        if version_type == VersionType.AMENDMENT:
            return f"Document amended: {description[:100]}..."
        elif version_type == VersionType.CORRECTION:
            return f"Corrections made: {description[:100]}..."
        elif version_type == VersionType.REVISION:
            return f"Document revised: {description[:100]}..."
        elif version_type == VersionType.SUPPLEMENT:
            return f"Supplemental information: {description[:100]}..."
        elif version_type == VersionType.REPLACEMENT:
            return f"Document replaced: {description[:100]}..."
        else:
            return f"Original document: {description[:100]}..."

    def _get_lineage_key(self, title: str, metadata: Dict[str, Any]) -> str:
        """Generate a key for tracking document lineage"""

        normalized_title = self._normalize_document_title(title)
        meeting_date = metadata.get('meeting_date', '')
        department = metadata.get('department', '')

        key_parts = [normalized_title]
        if meeting_date:
            key_parts.append(meeting_date)
        if department:
            key_parts.append(department)

        return "_".join(key_parts).replace(" ", "_")

    def get_version_history(self, version_id: str) -> List[Dict[str, Any]]:
        """Get the complete version history for a document lineage"""

        # Find the lineage containing this version
        for lineage_key, version_list in self.lineage.items():
            if version_id in version_list:
                # Return all versions in this lineage with their metadata
                history = []
                for vid in version_list:
                    if vid in self.versions:
                        history.append(self.versions[vid])
                return sorted(history, key=lambda x: x['metadata']['created_at'])

        # Single version with no lineage
        if version_id in self.versions:
            return [self.versions[version_id]]

        return []

    def get_current_version(self, lineage_key: str) -> Optional[Dict[str, Any]]:
        """Get the current version of a document lineage"""

        if lineage_key in self.lineage:
            # Find the current version in the lineage
            for version_id in reversed(self.lineage[lineage_key]):
                if version_id in self.versions:
                    version_data = self.versions[version_id]
                    if version_data['metadata']['status'] == VersionStatus.CURRENT.value:
                        return version_data

        return None

    def check_for_newer_version(self, version_id: str) -> Optional[str]:
        """Check if there's a newer version of this document"""

        if version_id not in self.versions:
            return None

        version_data = self.versions[version_id]
        return version_data['metadata'].get('superseded_by')

    def get_version_stats(self) -> Dict[str, Any]:
        """Get statistics about version tracking"""

        stats = {
            "total_versions": len(self.versions),
            "total_lineages": len(self.lineage),
            "version_types": {},
            "version_statuses": {},
            "last_updated": datetime.now().isoformat()
        }

        for version_data in self.versions.values():
            version_type = version_data['metadata']['version_type']
            status = version_data['metadata']['status']

            stats["version_types"][version_type] = stats["version_types"].get(version_type, 0) + 1
            stats["version_statuses"][status] = stats["version_statuses"].get(status, 0) + 1

        return stats

# Integration functions
def register_document_version(title: str, description: str, content_hash: str,
                            projects: List[Dict[str, Any]],
                            processing_metadata: Dict[str, Any],
                            filename: str = "") -> str:
    """Convenience function to register a document version"""
    tracker = VersionTracker()
    return tracker.register_version(title, description, content_hash,
                                   projects, processing_metadata, filename)

def get_document_history(version_id: str) -> List[Dict[str, Any]]:
    """Convenience function to get document version history"""
    tracker = VersionTracker()
    return tracker.get_version_history(version_id)

if __name__ == "__main__":
    # Example usage and testing
    tracker = VersionTracker()
    stats = tracker.get_version_stats()

    print("📋 JaxWatch Version Tracking System")
    print(f"📄 Total versions: {stats['total_versions']}")
    print(f"🔗 Document lineages: {stats['total_lineages']}")
    print(f"📊 Version types: {stats['version_types']}")
    print(f"📈 Version statuses: {stats['version_statuses']}")