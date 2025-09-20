#!/usr/bin/env python3
"""
JaxWatch Municipal Data Schema
Neutral schema for civic journalism - facts only, no interpretation
Covers layered municipal information:
- Zoning and Hearings
- Private Development
- Public Projects
- Infrastructure
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class ProjectLayer(str, Enum):
    """Information layers for civic data (no hierarchy implied)"""
    ZONING = "zoning"
    PRIVATE_DEV = "private_dev"
    PUBLIC_PROJECT = "public_project"
    INFRASTRUCTURE = "infrastructure"

class ProcessStage(str, Enum):
    """Current stage - factual only, no judgment"""
    FILED = "filed"
    REVIEW = "review"
    HEARING = "hearing"
    APPROVED = "approved"
    DENIED = "denied"
    CONSTRUCTION = "construction"
    COMPLETED = "completed"
    DEFERRED = "deferred"

class DecisionAuthority(str, Enum):
    """Who makes the decision (factual)"""
    STAFF = "staff"
    PLANNING_COMMISSION = "planning_commission"
    CITY_COUNCIL = "city_council"
    BOARD = "board"

class DataSource(str, Enum):
    """Source of the data (for transparency)"""
    PLANNING_COMMISSION = "planning_commission"
    CITY_COUNCIL = "city_council"
    PUBLIC_WORKS = "public_works"
    DEVELOPMENT_SERVICES = "development_services"

class CivicProject(BaseModel):
    """Neutral civic project schema - facts only, no interpretation"""

    # Core Identification
    slug: str = Field(..., description="URL-friendly unique identifier")
    project_id: str = Field(..., description="Official project/case number")
    title: str = Field(..., description="Project title/description")

    # Classification (descriptive, not hierarchical)
    layer: ProjectLayer = Field(..., description="Information layer")
    stage: ProcessStage = Field(..., description="Current factual stage")
    decision_authority: DecisionAuthority = Field(..., description="Decision maker")
    data_source: DataSource = Field(..., description="Data source for transparency")

    # Meeting/Process Information
    item_number: Optional[str] = None
    meeting_date: Optional[str] = None
    meeting_type: Optional[str] = None

    # Geographic Information (factual)
    location: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    council_district: Optional[str] = None
    planning_district: Optional[str] = None

    # Project Details (as stated in source)
    request: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # Free text status from source
    staff_recommendation: Optional[str] = None

    # Parties Involved
    applicant: Optional[str] = None
    owners: Optional[str] = None
    agent: Optional[str] = None

    # Financial Information (factual amounts only)
    estimated_value: Optional[float] = None
    funding_source: Optional[str] = None

    # Timeline (factual dates)
    proposed_start: Optional[str] = None
    proposed_completion: Optional[str] = None

    # Documentation (transparency)
    source_pdf: Optional[str] = None
    source_url: Optional[str] = None
    source_documents: List[str] = Field(default_factory=list)

    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.now)
    last_updated: Optional[datetime] = None

    # Descriptive tags (not ranking)
    descriptive_tags: List[str] = Field(default_factory=list)  # e.g., ">$10M", "Downtown", "Residential"

    # Related projects (cross-referencing)
    related_projects: List[Dict[str, Any]] = Field(default_factory=list)

    # Legacy Compatibility
    category: Optional[str] = None
    project_scale: Optional[str] = None
    completion_timeline: Optional[str] = None
    signs_posted: Optional[bool] = None
    tags: List[str] = Field(default_factory=list)  # For backward compatibility

class ProjectLayerMapping:
    """Simple mapping for organizing projects into information layers"""

    LAYER_KEYWORDS = {
        ProjectLayer.ZONING: ['zoning', 'variance', 'conditional', 'administrative deviation', 'land use'],
        ProjectLayer.PRIVATE_DEV: ['development', 'subdivision', 'site plan', 'pud', 'exception'],
        ProjectLayer.PUBLIC_PROJECT: ['public', 'municipal', 'park', 'recreation'],
        ProjectLayer.INFRASTRUCTURE: ['road', 'bridge', 'utility', 'transportation', 'water', 'sewer']
    }

    @classmethod
    def categorize_project(cls, project_type_str: str) -> ProjectLayer:
        """Simple categorization into information layers (no judgment)"""
        if not project_type_str:
            return ProjectLayer.ZONING  # Default for planning commission data

        project_type_lower = project_type_str.lower()

        for layer, keywords in cls.LAYER_KEYWORDS.items():
            if any(keyword in project_type_lower for keyword in keywords):
                return layer

        return ProjectLayer.ZONING  # Default

def generate_descriptive_tags(project: Dict[str, Any]) -> List[str]:
    """Generate descriptive tags without ranking or judgment"""
    tags = []

    # Financial descriptors (factual amounts)
    estimated_value = project.get('estimated_value')
    if estimated_value:
        if estimated_value >= 10_000_000:
            tags.append(">$10M project")
        elif estimated_value >= 1_000_000:
            tags.append("$1M+ project")
        elif estimated_value >= 100_000:
            tags.append("$100K+ project")

    # Geographic descriptors
    location = (project.get('location') or '').lower()
    if any(keyword in location for keyword in ['downtown', 'core', 'central']):
        tags.append("Downtown")
    elif any(keyword in location for keyword in ['riverside', 'avondale']):
        tags.append("Riverside/Avondale")
    elif any(keyword in location for keyword in ['beach', 'neptune', 'atlantic']):
        tags.append("Beaches")

    # Project type descriptors (plain English)
    project_type = (project.get('project_type') or '').lower()
    if 'residential' in project_type or 'housing' in project_type:
        tags.append("Residential")
    elif 'commercial' in project_type or 'retail' in project_type:
        tags.append("Commercial")
    elif 'industrial' in project_type:
        tags.append("Industrial")

    return tags

# Schema versioning and migration support
class SchemaVersion:
    """Schema version management"""
    CURRENT = "2.0"

    @classmethod
    def migrate_from_v1(cls, legacy_project: Dict[str, Any]) -> 'CivicProject':
        """Migrate from v1 schema to current schema"""
        return migrate_from_legacy(legacy_project)

class ProjectTypeMapping:
    """Legacy project type classification"""

    @classmethod
    def classify_project_type(cls, project_type_str: str) -> ProjectLayer:
        """Legacy method for project type classification"""
        return ProjectLayerMapping.categorize_project(project_type_str)

# Additional backward compatibility aliases
ProjectType = ProjectLayer  # Legacy enum name
MunicipalProject = CivicProject

def migrate_from_legacy(legacy_project: Dict[str, Any]) -> CivicProject:
    """Simple migration from legacy schema - direct translation only"""

    # Simple layer categorization
    legacy_type = legacy_project.get('project_type', '')
    layer = ProjectLayerMapping.categorize_project(legacy_type)

    # Simple stage mapping
    status = legacy_project.get('status', '').upper()
    if 'APPROVE' in status:
        stage = ProcessStage.APPROVED
    elif 'DEFER' in status:
        stage = ProcessStage.DEFERRED
    elif 'DENY' in status:
        stage = ProcessStage.DENIED
    else:
        stage = ProcessStage.REVIEW

    # Generate descriptive tags
    descriptive_tags = generate_descriptive_tags(legacy_project)

    return CivicProject(
        slug=legacy_project.get('slug', ''),
        project_id=legacy_project.get('project_id', ''),
        title=legacy_project.get('title', ''),
        layer=layer,
        stage=stage,
        decision_authority=DecisionAuthority.PLANNING_COMMISSION,
        data_source=DataSource.PLANNING_COMMISSION,

        # Direct mappings
        item_number=legacy_project.get('item_number'),
        meeting_date=legacy_project.get('meeting_date'),
        location=legacy_project.get('location'),
        latitude=legacy_project.get('latitude'),
        longitude=legacy_project.get('longitude'),
        council_district=legacy_project.get('council_district'),
        planning_district=legacy_project.get('planning_district'),
        request=legacy_project.get('request'),
        status=legacy_project.get('status'),
        staff_recommendation=legacy_project.get('staff_recommendation'),
        owners=legacy_project.get('owners'),
        agent=legacy_project.get('agent'),
        source_pdf=legacy_project.get('source_pdf'),
        estimated_value=legacy_project.get('estimated_value'),
        descriptive_tags=descriptive_tags,

        # Legacy compatibility
        category=legacy_project.get('category'),
        project_scale=legacy_project.get('project_scale'),
        completion_timeline=legacy_project.get('completion_timeline'),
        signs_posted=legacy_project.get('signs_posted'),
        tags=legacy_project.get('tags', [])
    )