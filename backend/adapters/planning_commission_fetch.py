#!/usr/bin/env python3
"""
Planning Commission Adapter - Real Implementation
Single-purpose: fetch and parse agenda items, return standardized dicts
"""

import logging
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

from ..common.retry_utils import WEB_SCRAPING_RETRY, HttpRetrySession, ErrorContext

logger = logging.getLogger(__name__)


@WEB_SCRAPING_RETRY
def fetch() -> List[Dict[str, Any]]:
    """
    Fetch Planning Commission agenda items from Jacksonville website
    Returns list of dicts matching AgendaItem schema
    """
    logger.info("🏛️ Fetching Planning Commission data from Jacksonville website...")

    with ErrorContext("Planning Commission data fetch", "Jacksonville website"):
        # Use retry-enabled HTTP session
        session = HttpRetrySession()
        url = "https://www.jacksonville.gov/departments/planning-and-development/planning-commission.aspx"

        response = session.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for agenda PDF links
        agenda_items = []
        pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))

        for link in pdf_links:
            href = link.get('href')
            text = link.get_text(strip=True)

            # Skip if not a planning commission document
            if not any(keyword in text.lower() for keyword in ['pc', 'planning', 'agenda', 'commission']):
                continue

            # Extract date from filename or text
            date_match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text)
            if date_match:
                date_str = date_match.group(1)
                # Convert to standard format
                try:
                    if '/' in date_str:
                        date_obj = datetime.strptime(date_str, '%m/%d/%y')
                    else:
                        date_obj = datetime.strptime(date_str, '%m-%d-%y')
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                except:
                    formatted_date = datetime.now().strftime('%Y-%m-%d')
            else:
                formatted_date = datetime.now().strftime('%Y-%m-%d')

            # Make URL absolute if relative
            if href.startswith('/'):
                href = f"https://www.jacksonville.gov{href}"
            elif not href.startswith('http'):
                href = f"https://www.jacksonville.gov/departments/planning-and-development/{href}"

            agenda_item = {
                "board": "Planning Commission",
                "date": formatted_date,
                "title": f"Planning Commission Meeting - {text}",
                "url": href,
                "notes": [
                    "Meeting held at Edward Ball Building, 1st Floor, Hearing Room 1002",
                    "214 North Hogan Street, Jacksonville, FL 32202",
                    "Typical meeting time: 1:00 PM"
                ],
                "item_number": f"PC-{formatted_date}",
                "parcel_address": "214 North Hogan Street, Jacksonville, FL 32202",
                "parcel_lat": 30.3369,
                "parcel_lon": -81.6557,
                "council_district": "7",
                "status": "Posted" if "agenda" in text.lower() else "Completed",
                "flagged": False
            }

            agenda_items.append(agenda_item)

        # If no real agenda items found, return empty list (don't show unprofessional messages)

        logger.info(f"📋 Found {len(agenda_items)} Planning Commission items")
        return agenda_items


def get_fallback_mock_data() -> List[Dict[str, Any]]:
    """Fallback mock data if real scraping fails"""
    logger.warning("Using fallback mock data for Planning Commission")

    mock_items = [
        {
            "board": "Planning Commission",
            "date": "2025-09-25",
            "title": "Fallback: Planning Commission data unavailable",
            "url": "https://www.jacksonville.gov/departments/planning-and-development/planning-commission.aspx",
            "notes": ["Real scraping failed, using fallback data"],
            "status": "Scraping Failed",
            "flagged": True
        }
    ]

    return mock_items


def fetch_real():
    """
    TODO: Enhanced Planning Commission scraping
    Future improvements:
    - Parse actual PDF content to extract individual agenda items
    - Extract case numbers, addresses, applicant information
    - Geocode addresses to get coordinates
    - Parse staff recommendations and conditions
    """
    pass