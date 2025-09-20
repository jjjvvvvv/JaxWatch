#!/usr/bin/env python3
"""
City Council Adapter - Real Implementation
Single-purpose: fetch City Council agenda items, return standardized dicts
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
    Fetch City Council agenda items from Jacksonville website
    Returns list of dicts matching AgendaItem schema
    """
    logger.info("🏛️ Fetching City Council data from Jacksonville website...")

    with ErrorContext("City Council data fetch", "Jacksonville website"):
        # Use retry-enabled HTTP session
        session = HttpRetrySession()

        # Try multiple potential URLs for City Council meetings
        potential_urls = [
            "https://www.jacksonville.gov/departments/city-council/meetings.aspx",
            "https://www.jacksonville.gov/city-council/meetings",
            "https://www.coj.net/city-council/meetings",
            "https://jaxcityc.legistar.com/Calendar.aspx"
        ]

        agenda_items = []
        soup = None
        working_url = None

        for url in potential_urls:
            try:
                response = session.get(url)
                soup = BeautifulSoup(response.content, 'html.parser')
                working_url = url
                logger.info(f"Successfully connected to {url}")
                break  # Success, use this URL
            except Exception as e:
                logger.warning(f"Failed to fetch from {url}: {e}")
                continue

        # If all URLs failed, fall back to Legistar directly
        if not soup:
            agenda_items = _fetch_from_legistar(session)
            if agenda_items:
                return agenda_items

            # If everything failed, return fallback
            return get_fallback_mock_data()

        # Search for PDF links that might be agendas or meeting documents
        pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))

        # Also look for links to meeting pages or Legistar
        meeting_links = soup.find_all('a', href=re.compile(r'(legistar|meeting|agenda)', re.I))

        all_links = pdf_links + meeting_links

        for link in all_links:
            href = link.get('href')
            text = link.get_text(strip=True)

            # Skip JavaScript URLs and empty hrefs
            if not href or href.startswith('javascript:'):
                continue

            # Skip if not related to City Council
            if not any(keyword in text.lower() for keyword in [
                'council', 'agenda', 'meeting', 'minutes', 'city council'
            ]):
                continue

            # Skip if link text is too generic or empty
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
                # Try to extract year from context
                year_match = re.search(r'20\d{2}', text)
                if year_match:
                    formatted_date = f"{year_match.group()}-01-01"  # Default to Jan 1
                else:
                    formatted_date = datetime.now().strftime('%Y-%m-%d')

            # Make URL absolute if relative
            if href.startswith('/'):
                href = f"https://www.jacksonville.gov{href}"
            elif not href.startswith('http'):
                href = f"https://www.jacksonville.gov/departments/city-council/{href}"

            # Determine status based on content
            status = "Posted"
            if "minute" in text.lower():
                status = "Completed"
            elif "draft" in text.lower():
                status = "Draft"
            elif "agenda" in text.lower():
                status = "Posted"

            # Check if we should flag this item
            flagged = False
            notes = []

            # Flag if critical information is missing
            if not date_match:
                flagged = True
                notes.append("Date extracted from context or defaulted")

            # Add meeting location info
            notes.extend([
                "City Council meetings held at City Hall",
                "117 West Duval Street, Jacksonville, FL 32202",
                "Typical meeting time: 5:00 PM on Tuesdays"
            ])

            agenda_item = {
                "board": "City Council",
                "date": formatted_date,
                "title": f"City Council Meeting - {text}",
                "url": href,
                "notes": notes,
                "item_number": f"CC-{formatted_date}",
                "parcel_address": "117 West Duval Street, Jacksonville, FL 32202",
                "parcel_lat": 30.3370,  # Jacksonville City Hall coordinates
                "parcel_lon": -81.6557,
                "council_district": "7",  # City Hall is in District 7
                "status": status,
                "flagged": flagged
            }

            agenda_items.append(agenda_item)

        # Try alternative: Check for Legistar calendar link
        if not agenda_items:
            agenda_items.extend(_fetch_from_legistar(session))

        # If still no items found, return empty list instead of unprofessional message

        logger.info(f"📋 Found {len(agenda_items)} City Council items")
        return agenda_items


def _fetch_from_legistar(session: HttpRetrySession) -> List[Dict[str, Any]]:
    """Try to fetch from Jacksonville's Legistar system"""
    items = []
    try:
        # Jacksonville uses Legistar for legislative management
        legistar_url = "https://jaxcityc.legistar.com/Calendar.aspx"

        response = session.get(legistar_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for meeting entries in the calendar
        meeting_rows = soup.find_all('tr', class_=re.compile(r'rgRow|rgAltRow', re.I))

        for row in meeting_rows[:5]:  # Limit to recent meetings
            cells = row.find_all('td')
            if len(cells) >= 3:
                # Extract meeting info from table cells
                date_cell = cells[0].get_text(strip=True) if cells[0] else ""
                meeting_cell = cells[1].get_text(strip=True) if cells[1] else ""

                # Look for agenda links
                agenda_links = row.find_all('a', href=re.compile(r'(agenda|pdf)', re.I))

                if agenda_links and date_cell:
                    link = agenda_links[0]
                    href = link.get('href')

                    # Parse date
                    try:
                        date_obj = datetime.strptime(date_cell, '%m/%d/%Y')
                        formatted_date = date_obj.strftime('%Y-%m-%d')
                    except:
                        formatted_date = datetime.now().strftime('%Y-%m-%d')

                    # Skip JavaScript and invalid URLs
                    if href and href.startswith('javascript:'):
                        continue

                    # Make URL absolute
                    if not href.startswith('http'):
                        href = f"https://jaxcityc.legistar.com/{href}"

                    items.append({
                        "board": "City Council",
                        "date": formatted_date,
                        "title": f"City Council Meeting - {meeting_cell or 'Regular Meeting'}",
                        "url": href,
                        "notes": [
                            "Retrieved from Legistar legislative management system",
                            "City Council meetings held at City Hall",
                            "117 West Duval Street, Jacksonville, FL 32202"
                        ],
                        "item_number": f"CC-{formatted_date}",
                        "parcel_address": "117 West Duval Street, Jacksonville, FL 32202",
                        "parcel_lat": 30.3370,
                        "parcel_lon": -81.6557,
                        "council_district": "7",
                        "status": "Posted",
                        "flagged": False
                    })

        logger.info(f"📋 Found {len(items)} items from Legistar")

    except Exception as e:
        logger.warning(f"Failed to fetch from Legistar: {e}")

    return items


def get_fallback_mock_data() -> List[Dict[str, Any]]:
    """Fallback mock data if real scraping fails"""
    logger.warning("Using fallback mock data for City Council")

    mock_items = [
        {
            "board": "City Council",
            "date": "2025-09-23",
            "title": "Fallback: City Council data collection in progress",
            "url": "https://www.jacksonville.gov/departments/city-council/meetings.aspx",
            "notes": ["Real City Council data collection being developed"],
            "item_number": f"FALLBACK-{datetime.now().strftime('%Y%m%d')}",
            "parcel_address": "117 West Duval Street, Jacksonville, FL 32202",
            "parcel_lat": 30.3370,
            "parcel_lon": -81.6557,
            "council_district": "7",
            "status": "Data Collection Development",
            "flagged": True
        }
    ]

    return mock_items