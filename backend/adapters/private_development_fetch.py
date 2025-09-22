#!/usr/bin/env python3
"""
Private Development Adapter - Simplified
Single-purpose: fetch development notices, return standardized dicts
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def fetch() -> List[Dict[str, Any]]:
    """
    Fetch Private Development notices and permits
    Returns list of dicts matching NoticeItem schema
    """
    logger.info("🏢 Fetching Private Development data...")

    # TODO: Replace with real data from jaxepics.coj.net
    mock_items = [
        {
            "board": "Development Services",
            "date": "2025-09-23",
            "title": "New residential subdivision permit application",
            "url": "https://www.jacksonville.gov/departments/planning-and-development/development-services-division/",
            "notes": [
                "45-lot subdivision",
                "Single-family homes",
                "Public review period: 30 days"
            ],
            "item_number": "DEV-2025-0892",
            "parcel_address": "10000 Block Heckscher Drive, Jacksonville, FL",
            "parcel_lat": 30.4738,
            "parcel_lon": -81.4321,
            "council_district": "2",
            "status": "Under Review",
            "flagged": False
        },
        {
            "board": "Development Services",
            "date": "2025-09-23",
            "title": "Commercial plaza development permit",
            "url": "https://www.jacksonville.gov/departments/planning-and-development/development-services-division/",
            "notes": [
                "15,000 sq ft retail plaza",
                "Includes restaurant and retail spaces",
                "Traffic impact study required"
            ],
            "item_number": "DEV-2025-0901",
            "parcel_address": "Beach Boulevard & Kernan Boulevard, Jacksonville, FL",
            "parcel_lat": 30.2984,
            "parcel_lon": -81.4209,
            "council_district": "4",
            "status": "Pending Documentation",
            "flagged": False
        }
    ]

    logger.info(f"🏗️ Returning {len(mock_items)} Private Development items")
    return mock_items