"""
Project data models for JaxWatch
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from .verification import DocumentVerification
from .reference import ProjectReference


@dataclass
class ProjectMention:
    """A mention of a project in a document"""
    id: str
    url: str
    title: str
    doc_type: str
    source: str
    source_name: str
    meeting_date: Optional[str] = None
    meeting_title: Optional[str] = None
    snippet: str = ""
    page: int = 1
    anchor_id: Optional[str] = None
    financials: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'ProjectMention':
        """Create ProjectMention from dictionary"""
        return cls(
            id=data.get('id', ''),
            url=data.get('url', ''),
            title=data.get('title', ''),
            doc_type=data.get('doc_type', ''),
            source=data.get('source', ''),
            source_name=data.get('source_name', ''),
            meeting_date=data.get('meeting_date'),
            meeting_title=data.get('meeting_title'),
            snippet=data.get('snippet', ''),
            page=data.get('page', 1),
            anchor_id=data.get('anchor_id'),
            financials=data.get('financials', [])
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'doc_type': self.doc_type,
            'source': self.source,
            'source_name': self.source_name,
            'meeting_date': self.meeting_date,
            'meeting_title': self.meeting_title,
            'snippet': self.snippet,
            'page': self.page,
            'anchor_id': self.anchor_id,
            'financials': self.financials
        }


@dataclass
class Project:
    """Base project model"""
    id: str
    title: str
    doc_type: str
    source: str
    meeting_date: Optional[str] = None
    meeting_title: Optional[str] = None
    mentions: List[ProjectMention] = field(default_factory=list)
    pending_review: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> 'Project':
        """Create Project from dictionary"""
        mentions = [ProjectMention.from_dict(m) for m in data.get('mentions', [])]
        return cls(
            id=data.get('id', ''),
            title=data.get('title', ''),
            doc_type=data.get('doc_type', ''),
            source=data.get('source', ''),
            meeting_date=data.get('meeting_date'),
            meeting_title=data.get('meeting_title'),
            mentions=mentions,
            pending_review=data.get('pending_review', True)
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'doc_type': self.doc_type,
            'source': self.source,
            'meeting_date': self.meeting_date,
            'meeting_title': self.meeting_title,
            'mentions': [m.to_dict() for m in self.mentions],
            'pending_review': self.pending_review
        }


@dataclass
class EnrichedProject:
    """Project with verification and reference data"""
    project: Project
    verification: Optional[DocumentVerification] = None
    references: List[ProjectReference] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def id(self) -> str:
        return self.project.id

    @property
    def title(self) -> str:
        return self.project.title

    @property
    def is_verified(self) -> bool:
        """Check if project has been verified"""
        return self.verification is not None

    @property
    def has_references(self) -> bool:
        """Check if project has reference data"""
        return len(self.references) > 0

    @classmethod
    def from_dict(cls, data: dict) -> 'EnrichedProject':
        """Create EnrichedProject from dictionary"""
        project = Project.from_dict(data)

        verification = None
        if 'document_verification' in data:
            verification = DocumentVerification.from_dict(data['document_verification'])

        references = []
        if 'references' in data:
            references = [ProjectReference.from_dict(r) for r in data['references']]

        last_updated = datetime.now()
        if 'last_updated' in data:
            try:
                last_updated = datetime.fromisoformat(data['last_updated'])
            except ValueError:
                pass

        return cls(
            project=project,
            verification=verification,
            references=references,
            last_updated=last_updated
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        result = self.project.to_dict()

        if self.verification:
            result['document_verification'] = self.verification.to_dict()

        if self.references:
            result['references'] = [r.to_dict() for r in self.references]

        result['last_updated'] = self.last_updated.isoformat()

        return result

    @classmethod
    def from_project(cls, project: Project) -> 'EnrichedProject':
        """Create EnrichedProject from base Project"""
        return cls(project=project)