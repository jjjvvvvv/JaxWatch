from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .retry_utils import HttpRetrySession

# Add parent path for jaxwatch imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jaxwatch.llm import get_llm_client

# Configure logger
logger = logging.getLogger("collector.dia_scraper")

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def _call_llm(prompt: str, json_mode: bool = True) -> Any:
    """Helper to call LLM using unified JaxWatch client."""
    client = get_llm_client()

    try:
        if json_mode:
            return client.chat_json(prompt)
        else:
            return client.chat(prompt)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


def _extract_page_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract meeting title and date from the page content using LLM."""
    # Heuristic: Get headers and first few paragraphs to capture context
    # Limiting text to avoid context window issues, though 8b has decent window.
    text_content = ""
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'div']):
        t = tag.get_text(" ", strip=True)
        if len(t) > 5: # clean up noise, but allow short titles
            text_content += t + "\n"
    
    text_content = text_content[:4000] # Cap input

    prompt = f"""
    You are an extractor bot. Analyze the text below from a meeting webpage.
    Extract:
    1. 'meeting_title': The official name/title of the meeting (e.g. "DIA Board Meeting"). Look for the main heading or the most prominent text.
    2. 'meeting_date': The date of the meeting in ISO format YYYY-MM-DD. If ambiguous or not found, return null.

    Ignore dates related to budgets (e.g. "2024 Budget"), copyrights, or unrelated events.
    
    Text:
    {text_content}

    Return JSON object: {{ "meeting_title": string | null, "meeting_date": string | null }}
    """
    
    result = _call_llm(prompt)
    if not result:
        return {"meeting_title": None, "meeting_date": None}
    
    return {
        "meeting_title": result.get("meeting_title"),
        "meeting_date": result.get("meeting_date"),
    }


def _classify_documents(links: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Classify a batch of links (text + url) using LLM."""
    if not links:
        return []

    # Prepare input for LLM
    links_text = json.dumps(links, indent=1)
    
    prompt = f"""
    You are a classifier bot. Classify the following document links based on their text and URL.
    Possible doc_types: "agenda", "minutes", "packet", "resolution", "presentation", "staff_report", "exhibit", "addendum", "other".
    
    Rules:
    - "Board Book" -> "packet"
    - "Meeting Materials" -> "packet"
    - "Res 2023-01" -> "resolution"
    
    Input Links:
    {links_text}

    Return a JSON object where keys are the indices (0 to N) and values are the doc_types.
    Example: {{ "0": "agenda", "1": "other" }}
    """

    result = _call_llm(prompt)
    if not result:
        # Fallback to 'other' if LLM fails, preserving original structure
        return [{
            "url": link["url"],
            "title": link["text"],
            "doc_type": "other"
        } for link in links]

    output = []
    for i, link in enumerate(links):
        doc_type = result.get(str(i), "other")
        output.append({
            "url": link['url'],
            "title": link['text'],
            "doc_type": doc_type
        })
    return output


def scrape_dia_meeting_detail(url: str) -> List[Dict]:
    """Fetch a DIA meeting detail page and extract attachment links using LLM for parsing."""
    try:
        session = HttpRetrySession()
        resp = session.get(url, headers={"User-Agent": DESKTOP_UA})
        soup = BeautifulSoup(resp.content, "html.parser")

        # 1. Extract Meeting Metadata (Date/Title)
        meta = _extract_page_metadata(soup)
        meeting_title = meta.get("meeting_title")
        meeting_date = meta.get("meeting_date")

        # 2. Collect Candidate Links
        candidates = []
        seen = set()
        
        # Determine base URL for absolute linking
        # Note: input url might be different from actual response url if redirected
        base_url = resp.url

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            
            # Simple pre-filter for PDFs or CMS links to save tokens
            hl = href.lower()
            if not (hl.endswith(".pdf") or "cms/getattachment" in hl):
                continue

            abs_url = urljoin(base_url, href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            
            text = a.get_text(strip=True) or ""
            candidates.append({"text": text, "url": abs_url, "href": href})

        if not candidates:
            return []

        # 3. Classify Links in Batch (to save time)
        # We pass only text and partial url specific to identification to save tokens if needed, 
        # but passing full url is safer for context.
        # Chunking: If there are too many links, we might need to chunk. 
        # For now, assuming < 50 links per page, 8k context is plenty.
        
        classified_docs = _classify_documents(candidates)

        # 4. Merge Data
        out: List[Dict] = []
        for doc in classified_docs:
            out.append({
                "url": doc["url"],
                "title": doc["title"],
                "doc_type": doc["doc_type"],
                "meeting_title": meeting_title,
                "meeting_date": meeting_date,
            })
            
        return out

    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        # Return empty list on failure so the engine continues
        return []
