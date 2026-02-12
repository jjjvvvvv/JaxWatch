from __future__ import annotations

import logging
import re
from typing import Dict, List, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .retry_utils import HttpRetrySession

# Configure logger
logger = logging.getLogger("collector.dia_scraper")

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def _extract_page_metadata(url: str, soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract meeting title and date from URL and page headings."""
    # Parse date from URL slug: .../20260218_dia-board-meeting
    parsed = urlparse(url)
    slug = parsed.path.rstrip('/').rsplit('/', 1)[-1]
    meeting_date = None
    m = re.match(r'^(\d{4})(\d{2})(\d{2})_', slug)
    if m:
        try:
            meeting_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        except ValueError:
            pass

    # Get title from H1, strip leading date prefix
    meeting_title = None
    h1 = soup.find('h1')
    if h1:
        title_text = h1.get_text(strip=True)
        # Strip "YYYYMMDD_" prefix if present
        meeting_title = re.sub(r'^\d{8}_\s*', '', title_text) or title_text

    return {"meeting_title": meeting_title, "meeting_date": meeting_date}


def scrape_dia_meeting_detail(url: str) -> List[Dict]:
    """Fetch a DIA meeting detail page and extract attachment links."""
    try:
        session = HttpRetrySession()
        resp = session.get(url, headers={"User-Agent": DESKTOP_UA})
        soup = BeautifulSoup(resp.content, "html.parser")

        meta = _extract_page_metadata(url, soup)

        results = []
        seen = set()
        base_url = resp.url

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            hl = href.lower()
            if not (hl.endswith(".pdf") or "cms/getattachment" in hl):
                continue
            abs_url = urljoin(base_url, href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            text = a.get_text(strip=True) or ""
            results.append({
                "url": abs_url,
                "title": text,
                "meeting_title": meta.get("meeting_title"),
                "meeting_date": meta.get("meeting_date"),
            })

        return results

    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return []
