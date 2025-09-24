from __future__ import annotations

from typing import Dict, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def scrape_meeting_attachments(detail_url: str, session) -> List[Dict[str, str]]:
    """
    Minimal scraper for Legistar MeetingDetail.aspx pages.
    Returns list of attachments with url and title where available.
    """
    resp = session.get(detail_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    out: List[Dict[str, str]] = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue
        # Accept common Legistar document links and PDFs
        href_l = href.lower()
        if ("view.ashx" in href_l) or href_l.endswith(".pdf"):
            abs_url = urljoin(detail_url, href)
            title = a.get_text(strip=True) or ""
            out.append({
                "url": abs_url,
                "title": title,
            })
    return out

