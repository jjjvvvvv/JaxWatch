#!/usr/bin/env python3
"""
Public Projects Adapter - Simplified
Single-purpose: fetch public project data, return standardized dicts
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def fetch() -> List[Dict[str, Any]]:
    """
    Fetch Public Projects data (parks, recreation, municipal facilities)
    Returns list of dicts matching AgendaItem schema
    """
    logger.info("🏛️ Fetching Public Projects data...")

    # TODO: Replace with real data from Jacksonville departments
    mock_items = [
        {
            "board": "Parks and Recreation",
            "date": "2025-09-22",
            "title": "Memorial Park Playground Renovation",
            "url": "https://www.jacksonville.gov/departments/parks-recreation-community-services/",
            "notes": [
                "ADA-compliant playground equipment",
                "New safety surfacing",
                "Estimated completion: December 2025"
            ],
            "item_number": "PARK-2025-23",
            "parcel_address": "Memorial Park, 1060 Riverside Avenue, Jacksonville, FL",
            "parcel_lat": 30.3156,
            "parcel_lon": -81.6834,
            "council_district": "14",
            "status": "Design Phase",
            "flagged": False
        },
        {
            "board": "Public Works",
            "date": "2025-09-22",
            "title": "Downtown Library Roof Replacement",
            "url": "https://www.jacksonville.gov/departments/public-works/",
            "notes": [
                "Emergency roof repair due to storm damage",
                "Temporary closure of north wing",
                "Alternative locations available"
            ],
            "item_number": "PW-2025-087",
            "parcel_address": "303 N Laura Street, Jacksonville, FL 32202",
            "parcel_lat": 30.3369,
            "parcel_lon": -81.6557,
            "council_district": "7",
            "status": "Emergency Repair",
            "flagged": True  # Flagged due to emergency nature
        },
        {
            "board": "Transportation",
            "date": "2025-09-25",
            "title": "Beach Boulevard Intersection Improvement",
            "url": "https://www.jacksonville.gov/departments/public-works/",
            "notes": [
                "Traffic signal upgrades",
                "Pedestrian crossing improvements",
                "Construction begins October 2025"
            ],
            "item_number": "TRANS-2025-045",
            "parcel_address": "9851 Beach Boulevard, Jacksonville, FL",
            "council_district": "4",
            "status": "Planning",
            "flagged": False
        }
    ]

    logger.info(f"🏗️ Returning {len(mock_items)} Public Projects items")
    return mock_items