#!/usr/bin/env python3
"""
JaxWatch Agenda Item Schema
Simplified schema for agenda items and municipal notices
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from urllib.parse import urlparse

def _hostname_from_url(url: Optional[str]) -> Optional[str]:
    try:
        if not url:
            return None
        return urlparse(url).netloc or None
    except Exception:
        return None


class AgendaItem(BaseModel):
    """Standard schema for agenda items across all municipal sources"""

    # Core identification
    board: str = Field(..., description="Board or committee name")
    date: str = Field(..., description="Meeting or notice date (YYYY-MM-DD)")
    title: str = Field(..., description="Item title or description")
    url: Optional[str] = Field(None, description="Source document URL")
    source: Optional[str] = Field(None, description="Hostname of the source URL for provenance")

    # Content details
    notes: List[str] = Field(default_factory=list, description="Additional details or conditions")
    item_number: Optional[str] = Field(None, description="Agenda item number")

    # Geographic information
    parcel_address: Optional[str] = Field(None, description="Project address if applicable")
    parcel_lat: Optional[float] = Field(None, description="Latitude coordinate")
    parcel_lon: Optional[float] = Field(None, description="Longitude coordinate")
    council_district: Optional[str] = Field(None, description="City council district")

    # Status and flags
    flagged: bool = Field(default=False, description="Flagged for review or attention")
    status: Optional[str] = Field(None, description="Current status (approved, denied, etc.)")

    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.now, description="When data was extracted")
    source_id: Optional[str] = Field(None, description="Source identifier from sources.yaml")
    last_updated: Optional[str] = Field(None, description="ISO timestamp when this item was last updated in pipeline")

    class Config:
        # Allow extra fields for flexibility
        extra = "allow"


class NoticeItem(BaseModel):
    """Schema for public notices and announcements"""

    # Core identification
    board: str = Field(..., description="Issuing department or board")
    date: str = Field(..., description="Notice date (YYYY-MM-DD)")
    title: str = Field(..., description="Notice title")
    url: Optional[str] = Field(None, description="Source document URL")

    # Notice details
    summary: Optional[str] = Field(None, description="Brief summary of notice")
    deadline: Optional[str] = Field(None, description="Response or action deadline")
    contact: Optional[str] = Field(None, description="Contact information")

    # Geographic information
    location: Optional[str] = Field(None, description="Location affected")
    parcel_lat: Optional[float] = Field(None, description="Latitude coordinate")
    parcel_lon: Optional[float] = Field(None, description="Longitude coordinate")

    # Status and flags
    flagged: bool = Field(default=False, description="Flagged for review")

    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.now, description="When data was extracted")
    source_id: Optional[str] = Field(None, description="Source identifier from sources.yaml")

    class Config:
        extra = "allow"


def validate_agenda_item(data: dict) -> AgendaItem:
    """Validate and clean agenda item data with error handling"""
    # Derive source hostname if possible
    if not data.get("source") and data.get("url"):
        data["source"] = _hostname_from_url(data.get("url"))

    try:
        item = AgendaItem(**data)
    except Exception as e:
        # Set flagged=True for validation failures
        data["flagged"] = True
        data["validation_error"] = str(e)

        # Ensure required fields have defaults
        if not data.get("board"):
            data["board"] = "Unknown Board"
        if not data.get("date"):
            data["date"] = datetime.now().strftime("%Y-%m-%d")
        if not data.get("title"):
            data["title"] = "Untitled Item"

        # Derive source field again after defaults
        if not data.get("source") and data.get("url"):
            data["source"] = _hostname_from_url(data.get("url"))

        return AgendaItem(**data)

    # MVP policy: if key fields like parcel_address are missing, keep the item but flag it
    needs_flag = False
    if not (getattr(item, "parcel_address", None)):
        needs_flag = True

    # If URL exists but has no hostname, flag
    if getattr(item, "url", None) and not getattr(item, "source", None):
        needs_flag = True

    if needs_flag and not item.flagged:
        item.flagged = True

    return item


def validate_notice_item(data: dict) -> NoticeItem:
    """Validate and clean notice item data with error handling"""
    try:
        return NoticeItem(**data)
    except Exception as e:
        # Set flagged=True for validation failures
        data["flagged"] = True
        data["validation_error"] = str(e)

        # Ensure required fields have defaults
        if not data.get("board"):
            data["board"] = "Unknown Department"
        if not data.get("date"):
            data["date"] = datetime.now().strftime("%Y-%m-%d")
        if not data.get("title"):
            data["title"] = "Untitled Notice"

        return NoticeItem(**data)
