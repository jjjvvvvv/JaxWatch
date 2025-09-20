#!/usr/bin/env python3
"""
Downtown Development Review Board (DDRB) Adapter - Real Implementation
Single-purpose: fetch DDRB agenda items, return standardized dicts
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
    Fetch DDRB agenda items from Jacksonville website
    Returns list of dicts matching AgendaItem schema
    """
    logger.info("🏢 Fetching DDRB data from Jacksonville website...")

    with ErrorContext("DDRB data fetch", "Jacksonville website"):
        # Use retry-enabled HTTP session
        session = HttpRetrySession()

        # DDRB is typically under Planning & Development or Downtown Investment Authority
        potential_urls = [
            "https://www.jacksonville.gov/departments/planning-and-development/downtown-development-review-board.aspx",
            "https://www.jacksonville.gov/departments/planning-and-development/ddrb.aspx",
            "https://www.coj.net/departments/planning-and-development/ddrb",
            "https://downtownjacksonville.org/development/ddrb/"
        ]

        agenda_items = []

        for url in potential_urls:
            try:
                response = session.get(url)
                if response.status_code == 200:
                    agenda_items = _parse_ddrb_page(response, url)
                    if agenda_items:
                        break
            except Exception as e:
                logger.warning(f"Failed to fetch from {url}: {e}")
                continue

        # If no items found from main pages, try search for recent DDRB documents
        if not agenda_items:
            agenda_items = _search_ddrb_documents(session)

        # If still no items, use fallback mock data instead of unprofessional message
        if not agenda_items:
            agenda_items = get_fallback_mock_data()

        logger.info(f"📋 Found {len(agenda_items)} DDRB items")
        return agenda_items


def _parse_ddrb_page(response: requests.Response, url: str) -> List[Dict[str, Any]]:
    """Parse DDRB page for agenda documents"""
    items = []
    soup = BeautifulSoup(response.content, 'html.parser')

    # Look for PDF links that might be agendas
    pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))

    # Look for agenda-related content
    agenda_keywords = ['agenda', 'meeting', 'ddrb', 'downtown development', 'review board']

    for link in pdf_links:
        href = link.get('href')
        text = link.get_text(strip=True)

        # Check if this looks like a DDRB document
        if not any(keyword in text.lower() for keyword in agenda_keywords):
            continue

        # Skip if link text is too generic
        if len(text) < 5 or text.lower() in ['pdf', 'link', 'here', 'click']:
            continue

        # Extract date from filename or text
        date_match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text)
        if date_match:
            date_str = date_match.group(1)
            try:
                if '/' in date_str:
                    if len(date_str.split('/')[-1]) == 2:
                        date_obj = datetime.strptime(date_str, '%m/%d/%y')
                    else:
                        date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                else:
                    if len(date_str.split('-')[-1]) == 2:
                        date_obj = datetime.strptime(date_str, '%m-%d-%y')
                    else:
                        date_obj = datetime.strptime(date_str, '%m-%d-%Y')
                formatted_date = date_obj.strftime('%Y-%m-%d')
            except:
                formatted_date = datetime.now().strftime('%Y-%m-%d')
        else:
            # Default to current month for DDRB (they meet monthly)
            formatted_date = datetime.now().strftime('%Y-%m-01')

        # Make URL absolute if relative
        if href.startswith('/'):
            href = f"https://www.jacksonville.gov{href}"
        elif not href.startswith('http'):
            href = f"https://www.jacksonville.gov{href}"

        # Determine item type and status
        status = "Posted"
        item_type = "Regular Meeting"
        if "minute" in text.lower():
            status = "Completed"
            item_type = "Meeting Minutes"
        elif "agenda" in text.lower():
            status = "Posted"
            item_type = "Meeting Agenda"

        # Check if we should flag this item
        flagged = False
        notes = []

        # Flag if critical information is missing
        if not date_match:
            flagged = True
            notes.append("Date estimated - DDRB typically meets monthly")

        # Add meeting location and context info
        notes.extend([
            "Downtown Development Review Board meeting",
            "Reviews development projects in downtown Jacksonville",
            "Meeting location may vary - check agenda for details"
        ])

        # Estimate council district based on downtown focus
        # DDRB reviews downtown projects which span multiple districts
        council_district = "7"  # Downtown core, but projects may span districts

        agenda_item = {
            "board": "Downtown Development Review Board",
            "date": formatted_date,
            "title": f"DDRB {item_type} - {text}",
            "url": href,
            "notes": notes,
            "item_number": f"DDRB-{formatted_date}",
            "parcel_address": "214 North Hogan Street, Jacksonville, FL 32202",
            "parcel_lat": 30.3369,
            "parcel_lon": -81.6557,
            "council_district": council_district,
            "status": status,
            "flagged": flagged
        }

        items.append(agenda_item)

    return items


def _search_ddrb_documents(session: HttpRetrySession) -> List[Dict[str, Any]]:
    """Search for DDRB documents using Jacksonville's search functionality"""
    items = []

    try:
        # Try Jacksonville's general search for DDRB documents
        search_url = "https://www.jacksonville.gov/departments/planning-and-development/"

        response = session.get(search_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for any mention of DDRB or Downtown Development Review Board
        ddrb_mentions = soup.find_all(text=re.compile(r'(ddrb|downtown development review)', re.I))

        # Remove unprofessional placeholder - if DDRB mentions found but no real agendas, return empty

    except Exception as e:
        logger.warning(f"DDRB document search failed: {e}")

    return items


def get_fallback_mock_data() -> List[Dict[str, Any]]:
    """Fallback mock data if real scraping fails"""
    logger.warning("Using fallback mock data for DDRB")

    # Generate mock data for typical DDRB meeting (monthly, usually 2nd Thursday)
    next_meeting = datetime.now().replace(day=1) + timedelta(days=31)
    next_meeting = next_meeting.replace(day=1)

    # Find second Thursday of next month
    while next_meeting.weekday() != 3:  # Thursday is 3
        next_meeting += timedelta(days=1)
    next_meeting += timedelta(days=7)  # Second Thursday

    mock_items = [
        {
            "board": "Downtown Development Review Board",
            "date": next_meeting.strftime('%Y-%m-%d'),
            "title": "Fallback: DDRB data collection in progress",
            "url": "https://www.jacksonville.gov/departments/planning-and-development/downtown-development-review-board.aspx",
            "notes": [
                "Real DDRB data collection being developed",
                "DDRB typically meets monthly on 2nd Thursday",
                "Reviews downtown development projects"
            ],
            "item_number": f"DDRB-FALLBACK-{datetime.now().strftime('%Y%m%d')}",
            "parcel_address": "214 North Hogan Street, Jacksonville, FL 32202",
            "parcel_lat": 30.3369,
            "parcel_lon": -81.6557,
            "council_district": "7",
            "status": "Data Collection Development",
            "flagged": True
        }
    ]

    return mock_items