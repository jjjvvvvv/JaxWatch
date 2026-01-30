"""
Document verification data models
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


@dataclass
class VerificationResult:
    """Result of document verification analysis"""
    processed_at: datetime
    authorization: str = ""
    actors: str = ""
    financial_mentions: str = ""
    summary: str = ""
    confidence_score: float = 0.0
    raw_response: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> 'VerificationResult':
        """Create VerificationResult from dictionary"""
        processed_at = datetime.now()
        if 'processed_at' in data:
            try:
                processed_at = datetime.fromisoformat(data['processed_at'])
            except ValueError:
                pass

        return cls(
            processed_at=processed_at,
            authorization=data.get('authorization', ''),
            actors=data.get('actors', ''),
            financial_mentions=data.get('financial_mentions', ''),
            summary=data.get('summary', ''),
            confidence_score=data.get('confidence_score', 0.0),
            raw_response=data.get('raw_response', '')
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'processed_at': self.processed_at.isoformat(),
            'authorization': self.authorization,
            'actors': self.actors,
            'financial_mentions': self.financial_mentions,
            'summary': self.summary,
            'confidence_score': self.confidence_score,
            'raw_response': self.raw_response
        }


@dataclass
class DocumentVerification:
    """Document verification data for a project"""
    project_id: str
    results: List[VerificationResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def latest_result(self) -> Optional[VerificationResult]:
        """Get the most recent verification result"""
        if not self.results:
            return None
        return max(self.results, key=lambda r: r.processed_at)

    @property
    def is_verified(self) -> bool:
        """Check if project has been verified"""
        return len(self.results) > 0

    def add_result(self, result: VerificationResult):
        """Add a new verification result"""
        self.results.append(result)

    @classmethod
    def from_dict(cls, data: dict) -> 'DocumentVerification':
        """Create DocumentVerification from dictionary"""
        results = []

        # Handle legacy format where verification data is stored directly
        if 'results' in data:
            results = [VerificationResult.from_dict(r) for r in data['results']]
        elif 'processed_at' in data or 'authorization' in data:
            # Legacy format - convert to new format
            results = [VerificationResult.from_dict(data)]

        return cls(
            project_id=data.get('project_id', ''),
            results=results,
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        result = {
            'project_id': self.project_id,
            'metadata': self.metadata
        }

        if self.results:
            result['results'] = [r.to_dict() for r in self.results]

        return result

    @classmethod
    def from_legacy_format(cls, project_id: str, legacy_data: dict) -> 'DocumentVerification':
        """Create DocumentVerification from legacy format"""
        result = VerificationResult.from_dict(legacy_data)
        return cls(project_id=project_id, results=[result])