"""
Project reference data models
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class ProjectReference:
    """Reference to another project or document"""
    type: str  # 'ordinance', 'resolution', 'project', 'meeting'
    id: str
    title: Optional[str] = None
    confidence: float = 0.0
    context: str = ""
    source_document: str = ""
    discovered_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def from_dict(cls, data: dict) -> 'ProjectReference':
        """Create ProjectReference from dictionary"""
        discovered_at = None
        if 'discovered_at' in data:
            try:
                discovered_at = datetime.fromisoformat(data['discovered_at'])
            except ValueError:
                pass

        return cls(
            type=data.get('type', ''),
            id=data.get('id', ''),
            title=data.get('title'),
            confidence=data.get('confidence', 0.0),
            context=data.get('context', ''),
            source_document=data.get('source_document', ''),
            discovered_at=discovered_at,
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        result = {
            'type': self.type,
            'id': self.id,
            'confidence': self.confidence,
            'context': self.context,
            'source_document': self.source_document,
            'metadata': self.metadata
        }

        if self.title:
            result['title'] = self.title

        if self.discovered_at:
            result['discovered_at'] = self.discovered_at.isoformat()

        return result