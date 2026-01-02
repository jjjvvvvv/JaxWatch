#!/usr/bin/env python3
"""
Collection-first engine: fetch pages, extract links, keep everything that matches
configured patterns. No parsing or geocoding. Transparent logging.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

import yaml
from bs4 import BeautifulSoup

from .retry_utils import HttpRetrySession
from .dia_meeting_scraper import scrape_dia_meeting_detail
import logging


DEFAULT_CONFIG_PATH = Path(__file__).parent / "sources.yaml"
RAW_OUT_DIR = Path("outputs/raw")
LOG_DIR = Path("outputs/logs")
# Note: no persistent state in MVP (only logs + raw outputs)

try:  # pragma: no cover - optional dependency
    from dateutil import parser as dateparser  # type: ignore
except Exception:  # pragma: no cover
    dateparser = None

DATE_WITH_SEPARATORS_RE = re.compile(r"(20\d{2})[-_/](\d{1,2})[-_/](\d{1,2})")
DATE_CONTIGUOUS_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")
US_NUMERIC_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](20\d{2})")
MONTH_NAME_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})",
    re.IGNORECASE,
)
DAY_MONTH_NAME_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(20\d{2})",
    re.IGNORECASE,
)

MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _reasonable_year(year: int) -> bool:
    current_year = datetime.now().year
    return 2000 <= year <= current_year + 1


def _coerce_iso_date(year: int, month: int, day: int) -> Optional[str]:
    if not _reasonable_year(year):
        return None
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _parse_month_name(name: str) -> Optional[int]:
    if not name:
        return None
    return MONTH_MAP.get(name.strip().lower())


def extract_date_from_text(value: Optional[str]) -> Optional[str]:
    """Extract an ISO YYYY-MM-DD date from free-form text if present."""
    if not value:
        return None
    text = str(value)

    for match in DATE_WITH_SEPARATORS_RE.finditer(text):
        year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        iso = _coerce_iso_date(year, month, day)
        if iso:
            return iso

    for match in DATE_CONTIGUOUS_RE.finditer(text):
        year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        iso = _coerce_iso_date(year, month, day)
        if iso:
            return iso

    for match in US_NUMERIC_RE.finditer(text):
        month, day, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        iso = _coerce_iso_date(year, month, day)
        if iso:
            return iso

    for match in MONTH_NAME_RE.finditer(text):
        month = _parse_month_name(match.group(1))
        if month is None:
            continue
        day = int(match.group(2))
        year = int(match.group(3))
        iso = _coerce_iso_date(year, month, day)
        if iso:
            return iso

    for match in DAY_MONTH_NAME_RE.finditer(text):
        day = int(match.group(1))
        month = _parse_month_name(match.group(2))
        if month is None:
            continue
        year = int(match.group(3))
        iso = _coerce_iso_date(year, month, day)
        if iso:
            return iso

    if dateparser is not None:
        try:
            dt = dateparser.parse(text, fuzzy=True, dayfirst=False)
            if dt and _reasonable_year(dt.year):
                return dt.date().isoformat()
        except Exception:  # pragma: no cover - guard against unexpected parse errors
            pass

    return None


def normalize_meeting_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            year, month, day = (int(value[0:4]), int(value[5:7]), int(value[8:10]))
        except ValueError:
            return None
        return _coerce_iso_date(year, month, day)
    return extract_date_from_text(value)


def determine_item_year(item: Dict[str, Any]) -> str:
    meeting_date = normalize_meeting_date(item.get("meeting_date"))
    if meeting_date:
        item["meeting_date"] = meeting_date
        return meeting_date[:4]

    for key in ("meeting_title", "title", "filename", "url"):
        candidate = extract_date_from_text(item.get(key))
        if candidate:
            item.setdefault("meeting_date", candidate)
            return candidate[:4]

    collected = item.get("date_collected") or ""
    if collected and re.match(r"\d{4}", collected):
        return collected[:4]

    return datetime.now().strftime("%Y")


def enrich_item_metadata(item: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Ensure meeting_date is populated when possible and return the storage year."""
    notes: List[str] = []

    normalized = normalize_meeting_date(item.get("meeting_date"))
    if normalized:
        item["meeting_date"] = normalized
    else:
        for key in ("meeting_title", "title", "filename", "url"):
            candidate = extract_date_from_text(item.get(key))
            if candidate:
                item["meeting_date"] = candidate
                notes.append(f"inferred meeting_date={candidate} from {key}")
                break

    storage_year = determine_item_year(item)

    meeting_date = item.get("meeting_date")
    collected = item.get("date_collected") or ""
    if meeting_date and collected and re.match(r"\d{4}", collected):
        try:
            meeting_year = int(meeting_date[:4])
            collected_year = int(collected[:4])
            if meeting_year - collected_year > 2:
                notes.append(
                    f"meeting_date {meeting_date} is more than 2 years after date_collected {collected}"
                )
            elif collected_year - meeting_year > 20:
                notes.append(
                    f"meeting_date {meeting_date} is more than 20 years before date_collected {collected}"
                )
        except ValueError:
            pass

    return storage_year, notes


def setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("collector")
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers if re-invoked
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        date_str = datetime.now().strftime("%Y-%m-%d")
        fh = logging.FileHandler(LOG_DIR / f"{date_str}.log")
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger


def slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


def load_sources(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# Removed seen-links persistence for simplified MVP


def is_match(url: str, title: str, patterns: List[str]) -> bool:
    s = f"{title} {url}".lower()
    for pat in patterns:
        if not pat:
            continue
        # Regex-style if wrapped with /.../
        if isinstance(pat, str) and pat.startswith("/") and pat.endswith("/"):
            import re
            try:
                rx = re.compile(pat[1:-1], re.I)
                if rx.search(s):
                    return True
            except Exception:
                pass
            continue
        # Heuristic: treat commonly-regex-like strings as regex (e.g., "\\.pdf")
        if isinstance(pat, str):
            import re
            regex_like = any(tok in pat for tok in ["\\", "^", "$", "[", "(", "|"])
            if regex_like:
                try:
                    rx = re.compile(pat, re.I)
                    if rx.search(s):
                        return True
                    continue
                except Exception:
                    # Fall back to substring
                    pass
            if pat.lower() in s:
                return True
    return False


def absolute_link(page_url: str, href: str) -> str:
    if not href:
        return href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(page_url, href)


def classify_doc_type(source_id: str, url: str, title: str) -> str:
    u = (url or "").lower()
    t = (title or "").lower()
    sid = (source_id or "").lower()


    if sid in ("dia_ddrb", "dia_board", "dia_transcripts", "dia_resolutions"):
        # Normalize combined string for keyword checks
        s = f"{t} {u}"
        if "agenda" in s:
            return "agenda"
        if "packet" in s:
            return "packet"
        if "minutes" in s:
            return "minutes"
        if "transcript" in s:
            return "transcript"
        # Treat DIA CMS attachments under the resolutions archive as resolutions
        if "cms/getattachment" in u and sid == "dia_resolutions":
            return "resolution"
        # Common supporting document types
        if "addendum" in s:
            return "addendum"
        if "presentation" in s:
            return "presentation"
        if "staff" in s:
            return "staff_report"
        if "exhibit" in s:
            return "exhibit"
        if "resolution" in s or " res " in f" {t} ":
            return "resolution"
        return "other"


    return "other"


def load_year_store(source_id: str) -> Tuple[Dict[str, List[dict]], Dict[str, Tuple[str, dict]]]:
    base = RAW_OUT_DIR / source_id
    items_by_year: Dict[str, List[dict]] = {}
    url_index: Dict[str, Tuple[str, dict]] = {}
    if not base.exists():
        return items_by_year, url_index

    year_dirs = sorted([p for p in base.iterdir() if p.is_dir() and p.name.isdigit()])
    for year_dir in year_dirs:
        year = year_dir.name
        path = year_dir / f"{source_id}.json"
        if not path.exists():
            continue
        try:
            data = json.load(path.open("r"))
            items = data.get("items", [])
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
        items_by_year[year] = items
        for item in items:
            url = item.get("url")
            if url:
                url_index[url] = (year, item)

    legacy_path = base / f"{source_id}.json"
    if legacy_path.exists():
        try:
            data = json.load(legacy_path.open("r"))
            items = data.get("items", [])
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
        legacy_year = str(data.get("year") or datetime.now().year)
        bucket = items_by_year.setdefault(legacy_year, [])
        bucket.extend(items)
        for item in items:
            url = item.get("url")
            if url and url not in url_index:
                url_index[url] = (legacy_year, item)

    return items_by_year, url_index


def sort_items_for_storage(items: List[dict]) -> List[dict]:
    def _key(it: dict) -> Tuple[str, str, str]:
        return (
            (it.get("meeting_date") or ""),
            (it.get("date_collected") or ""),
            (it.get("title") or ""),
        )

    return sorted(items, key=_key)


def save_year_store(
    source_id: str,
    source_name: str,
    items_by_year: Dict[str, List[dict]],
    root_url: str | None = None,
) -> Dict[str, Path]:
    saved: Dict[str, Path] = {}
    now_iso = datetime.now().isoformat()
    for year, items in sorted(items_by_year.items()):
        year_dir = RAW_OUT_DIR / source_id / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        path = year_dir / f"{source_id}.json"
        payload = {
            "source": source_id,
            "source_name": source_name,
            "year": str(year),
            "updated_at": now_iso,
            "last_collected_at": now_iso,
            "root_url": root_url,
            "items": sort_items_for_storage(items),
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        saved[str(year)] = path
    return saved




def _collect_ddrb(source: Dict[str, Any], session: HttpRetrySession, logger: logging.Logger) -> Dict[str, Any]:
    name = source.get("name") or source.get("id") or "unknown"
    sid = source.get("id") or slugify(name)
    root_url = source.get("root_url") or ""
    candidates = source.get("candidates")
    if not candidates:
        u = source.get("url")
        candidates = [u] if u else []
    patterns = source.get("patterns") or []

    discovered: List[Dict[str, Any]] = []
    pages_fetched = 0
    links_total = 0
    local_seen: set[str] = set()

    def is_preferred_doc(url: str) -> bool:
        lu = url.lower()
        if "coj365-my.sharepoint.com" in lu:
            return False
        return lu.endswith(".pdf") or "cms/getattachment" in lu

    meeting_pages: List[str] = []

    # 1) Fetch listing page(s) and gather meeting detail links + direct docs
    for url in candidates:
        if not url:
            continue
        try:
            resp = session.get(url)
            pages_fetched += 1
            logger.info(f"Fetched page: {url} status={resp.status_code} bytes={len(resp.content)}")
        except Exception as e:
            logger.warning(f"Page fetch failed: {url} err={e}")
            continue

        soup = BeautifulSoup(resp.content, "html.parser")
        anchors = soup.find_all("a", href=True)
        links_total += len(anchors)
        for a in anchors:
            href = a.get("href", "").strip()
            title = a.get_text(strip=True) or ""
            abs_url = absolute_link(url, href)
            if not abs_url:
                continue
            lu = abs_url.lower()
            if is_preferred_doc(abs_url):
                if abs_url in local_seen:
                    continue
                if patterns and not is_match(abs_url, title, patterns):
                    continue
                filename = Path(urlparse(abs_url).path).name or 'document.pdf'
                discovered.append({
                    "url": abs_url,
                    "filename": filename,
                    "title": title,
                    "source": sid,
                    "source_name": name,
                    "root_url": root_url,
                    "date_collected": datetime.now().isoformat(),
                    "status": "discovered",
                    "http_status": "discovered",
                    "seen_before": False,
                    "doc_type": classify_doc_type(sid, abs_url, title),
                })
                local_seen.add(abs_url)
                continue
            if lu.startswith("http") and "dia.jacksonville.gov" in lu and not lu.endswith('.pdf'):
                meeting_pages.append(abs_url)

    meeting_pages = list(dict.fromkeys(meeting_pages))
    logger.info(f"DDRB: following {len(meeting_pages)} meeting detail page(s)")

    # 2) Follow each meeting detail page to collect agenda/minutes/packet links
    for detail in meeting_pages:
        try:
            atts = scrape_dia_meeting_detail(detail)
            pages_fetched += 1
        except Exception as e:
            logger.warning(f"DDRB detail scrape failed: {detail} err={e}")
            atts = []
        for att in atts:
            abs_url = att.get("url")
            title = att.get("title") or ""
            if not abs_url or abs_url in local_seen:
                continue
            if not is_preferred_doc(abs_url):
                continue
            if patterns and not is_match(abs_url, title, patterns):
                continue
            filename = Path(urlparse(abs_url).path).name or 'document.pdf'
            discovered.append({
                "url": abs_url,
                "filename": filename,
                "title": title,
                "source": sid,
                "source_name": name,
                "root_url": root_url,
                "date_collected": datetime.now().isoformat(),
                "status": "discovered",
                "http_status": "discovered",
                "seen_before": False,
                "doc_type": att.get("doc_type") or classify_doc_type(sid, abs_url, title),
                "meeting_url": detail,
                "meeting_title": att.get("meeting_title"),
                "meeting_date": att.get("meeting_date"),
            })
            local_seen.add(abs_url)

    return {
        "discovered": discovered,
        "pages_fetched": pages_fetched,
        "links_total": links_total,
    }


def _collect_dia_board(source: Dict[str, Any], session: HttpRetrySession, logger: logging.Logger) -> Dict[str, Any]:
    name = source.get("name") or source.get("id") or "unknown"
    sid = source.get("id") or slugify(name)
    root_url = source.get("root_url") or ""
    candidates = source.get("candidates")
    if not candidates:
        u = source.get("url")
        candidates = [u] if u else []
    patterns = source.get("patterns") or []

    discovered: List[Dict[str, Any]] = []
    pages_fetched = 0
    links_total = 0
    local_seen: set[str] = set()

    meeting_pages: List[str] = []

    # 1) Fetch listing page(s) and gather meeting detail links + direct PDFs
    for url in candidates:
        if not url:
            continue
        try:
            resp = session.get(url)
            pages_fetched += 1
            logger.info(f"Fetched page: {url} status={resp.status_code} bytes={len(resp.content)}")
        except Exception as e:
            logger.warning(f"Page fetch failed: {url} err={e}")
            continue

        soup = BeautifulSoup(resp.content, "html.parser")
        anchors = soup.find_all("a", href=True)
        links_total += len(anchors)
        for a in anchors:
            href = a.get("href", "").strip()
            title = a.get_text(strip=True) or ""
            abs_url = absolute_link(url, href)
            if not abs_url:
                continue
            lu = abs_url.lower()
            # Capture direct PDFs on listing page
            if lu.endswith(".pdf"):
                if abs_url in local_seen:
                    continue
                keep = is_match(abs_url, title, patterns) if patterns else True
                if not keep:
                    continue
                filename = Path(urlparse(abs_url).path).name or 'document.pdf'
                already = False
                discovered.append({
                    "url": abs_url,
                    "filename": filename,
                    "title": title,
                    "source": sid,
                    "source_name": name,
                    "root_url": root_url,
                    "date_collected": datetime.now().isoformat(),
                    "status": "discovered",
                    "http_status": "discovered",
                    "seen_before": already,
                    "doc_type": classify_doc_type(sid, abs_url, title),
                })
                local_seen.add(abs_url)
                continue
            # Collect meeting detail pages within dia.jacksonville.gov
            if lu.startswith("http") and "dia.jacksonville.gov" in lu and not lu.endswith('.pdf'):
                meeting_pages.append(abs_url)

    meeting_pages = list(dict.fromkeys(meeting_pages))
    logger.info(f"DIA Board: following {len(meeting_pages)} meeting detail page(s)")

    # 2) Follow each meeting detail page to collect agenda/minutes/packet links
    for detail in meeting_pages:
        try:
            atts = scrape_dia_meeting_detail(detail)
            pages_fetched += 1  # one fetch per detail page inside scraper
        except Exception as e:
            logger.warning(f"DIA Board detail scrape failed: {detail} err={e}")
            atts = []
        for att in atts:
            abs_url = att.get("url")
            title = att.get("title") or ""
            if not abs_url or abs_url in local_seen:
                continue
            keep = is_match(abs_url, title, patterns) if patterns else True
            if not keep:
                continue
            filename = Path(urlparse(abs_url).path).name or 'document.pdf'
            already = False
            discovered.append({
                "url": abs_url,
                "filename": filename,
                "title": title,
                "source": sid,
                "source_name": name,
                "root_url": root_url,
                "date_collected": datetime.now().isoformat(),
                "status": "discovered",
                "http_status": "discovered",
                "seen_before": already,
                "doc_type": att.get("doc_type") or classify_doc_type(sid, abs_url, title),
                "meeting_url": detail,
                "meeting_title": att.get("meeting_title"),
                "meeting_date": att.get("meeting_date"),
            })
            local_seen.add(abs_url)

    return {
        "discovered": discovered,
        "pages_fetched": pages_fetched,
        "links_total": links_total,
    }


def _collect_dia_archive(source: Dict[str, Any], session: HttpRetrySession, logger: logging.Logger) -> Dict[str, Any]:
    """Generic DIA archive collector for transcripts/resolutions-like pages.

    - Fetch listing pages
    - Collect direct .pdf and cms/getattachment links
    - Follow detail pages on dia.jacksonville.gov and collect same
    """
    name = source.get("name") or source.get("id") or "unknown"
    sid = source.get("id") or slugify(name)
    root_url = source.get("root_url") or ""
    candidates = source.get("candidates")
    if not candidates:
        u = source.get("url")
        candidates = [u] if u else []
    patterns = source.get("patterns") or []

    discovered: List[Dict[str, Any]] = []
    pages_fetched = 0
    links_total = 0
    local_seen: set[str] = set()
    detail_pages: List[str] = []

    def is_doc(u: str) -> bool:
        lu = u.lower()
        return lu.endswith(".pdf") or ("cms/getattachment" in lu)

    # 1) Scan listing page(s)
    for url in candidates:
        if not url:
            continue
        try:
            resp = session.get(url)
            pages_fetched += 1
            logger.info(f"Fetched page: {url} status={resp.status_code} bytes={len(resp.content)}")
        except Exception as e:
            logger.warning(f"Page fetch failed: {url} err={e}")
            continue
        soup = BeautifulSoup(resp.content, "html.parser")
        anchors = soup.find_all("a", href=True)
        links_total += len(anchors)
        for a in anchors:
            href = a.get("href", "").strip()
            title = a.get_text(strip=True) or ""
            abs_url = absolute_link(url, href)
            if not abs_url:
                continue
            lu = abs_url.lower()
            if is_doc(lu):
                if abs_url in local_seen:
                    continue
                if patterns and not is_match(abs_url, title, patterns):
                    continue
                filename = Path(urlparse(abs_url).path).name or 'document.pdf'
                discovered.append({
                    "url": abs_url,
                    "filename": filename,
                    "title": title,
                    "source": sid,
                    "source_name": name,
                    "root_url": root_url,
                    "date_collected": datetime.now().isoformat(),
                    "status": "discovered",
                    "http_status": "discovered",
                    "seen_before": False,
                    "doc_type": classify_doc_type(sid, abs_url, title),
                })
                local_seen.add(abs_url)
                continue
            # Collect detail pages on dia domain
            if lu.startswith("http") and "dia.jacksonville.gov" in lu and not lu.endswith('.pdf'):
                detail_pages.append(abs_url)

    detail_pages = list(dict.fromkeys(detail_pages))
    logger.info(f"DIA Archive: following {len(detail_pages)} detail page(s)")

    # 2) Follow details
    for detail in detail_pages:
        try:
            resp = session.get(detail)
            pages_fetched += 1
        except Exception as e:
            logger.warning(f"DIA detail fetch failed: {detail} err={e}")
            continue
        soup = BeautifulSoup(resp.content, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            title = a.get_text(strip=True) or ""
            abs_url = absolute_link(detail, href)
            if not abs_url:
                continue
            lu = abs_url.lower()
            if not is_doc(lu):
                continue
            if abs_url in local_seen:
                continue
            if patterns and not is_match(abs_url, title, patterns):
                continue
            filename = Path(urlparse(abs_url).path).name or 'document.pdf'
            discovered.append({
                "url": abs_url,
                "filename": filename,
                "title": title,
                "source": sid,
                "source_name": name,
                "root_url": root_url,
                "date_collected": datetime.now().isoformat(),
                "status": "discovered",
                "http_status": "discovered",
                "seen_before": False,
                "doc_type": classify_doc_type(sid, abs_url, title),
            })
            local_seen.add(abs_url)

    return {
        "discovered": discovered,
        "pages_fetched": pages_fetched,
        "links_total": links_total,
    }


def collect_source(source: Dict[str, Any], session: HttpRetrySession, logger: logging.Logger) -> Dict[str, Any]:
    name = source.get("name") or source.get("id") or "unknown"
    sid = source.get("id") or slugify(name)
    root_url = source.get("root_url") or ""
    candidates = source.get("candidates")
    if not candidates:
        u = source.get("url")
        candidates = [u] if u else []
    patterns = source.get("patterns") or []

    logger.info(f"▶️ Source start: {name} (id={sid}) candidates={len(candidates)} patterns={patterns}")

    discovered: List[Dict[str, Any]] = []
    seen: set[str] = set()
    pages_fetched = 0
    links_total = 0

    # Special-case handling for DIA sources
    if sid == "dia_ddrb":
        logger.info("Special handling for DDRB: following meeting detail pages and collecting docs")
        dd = _collect_ddrb(source, session, logger)
        discovered = dd["discovered"]
        pages_fetched += dd["pages_fetched"]
        links_total += dd["links_total"]
    elif sid == "dia_board":
        logger.info("Special handling for DIA Board: follow meeting pages and collect PDFs")
        db = _collect_dia_board(source, session, logger)
        discovered = db["discovered"]
        pages_fetched += db["pages_fetched"]
        links_total += db["links_total"]
    elif sid in ("dia_transcripts", "dia_resolutions"):
        logger.info(f"Special handling for {sid}: DIA archive collector")
        da = _collect_dia_archive(source, session, logger)
        discovered = da["discovered"]
        pages_fetched += da["pages_fetched"]
        links_total += da["links_total"]
    else:
        # Normal generic collection from candidate pages
        for url in candidates:
            if not url:
                continue
            try:
                resp = session.get(url)
                pages_fetched += 1
                logger.info(f"Fetched page: {url} status={resp.status_code} bytes={len(resp.content)}")
            except Exception as e:
                logger.warning(f"Page fetch failed: {url} err={e}")
                continue

            soup = BeautifulSoup(resp.content, "html.parser")
            anchors = soup.find_all("a", href=True)
            links_total += len(anchors)
            logger.info(f"Discovered {len(anchors)} links on {url}")

            for a in anchors:
                href = a.get("href", "").strip()
                title = a.get_text(strip=True) or ""
                abs_url = absolute_link(url, href)
                if not abs_url:
                    logger.info("Skipped link: empty href")
                    continue
                if abs_url in seen:
                    logger.info(f"Skipped duplicate: {abs_url}")
                    continue
                keep = is_match(abs_url, title, patterns) if patterns else True
                if keep:
                    seen.add(abs_url)
                    filename = Path(urlparse(abs_url).path).name
                    already = False
                    item = {
                        "url": abs_url,
                        "filename": filename,
                        "title": title,
                        "source": sid,
                        "source_name": name,
                        "root_url": root_url,
                        "date_collected": datetime.now().isoformat(),
                        "status": "discovered",
                        "http_status": "discovered",
                        "seen_before": already,
                        "doc_type": classify_doc_type(sid, abs_url, title),
                    }
                    discovered.append(item)
                    logger.info(f"Kept: {abs_url} title='{title}'")
                else:
                    logger.info(f"Skipped (no pattern match): {abs_url} title='{title}'")


    # Merge with year-based store and write
    items_by_year, existing_index = load_year_store(sid)
    existing_total = sum(len(values) for values in items_by_year.values())
    rebucketed = 0

    # Revisit previously saved items so legacy runs benefit from improved metadata
    for year, items in list(items_by_year.items()):
        for item in list(items):
            url = item.get("url")
            storage_year, notes = enrich_item_metadata(item)
            for note in notes:
                level = logging.WARNING if "more than" in note else logging.DEBUG
                logger.log(level, f"{sid}: {note} url={url}")
            if storage_year != year and url:
                try:
                    items.remove(item)
                except ValueError:
                    pass
                target_bucket = items_by_year.setdefault(storage_year, [])
                target_bucket.append(item)
                existing_index[url] = (storage_year, item)
                rebucketed += 1

    run_seen: set[str] = set()
    new_count = 0
    moved_count = 0

    for it in discovered:
        url = it.get("url")
        if not url:
            continue
        if url in run_seen:
            continue
        run_seen.add(url)

        storage_year, notes = enrich_item_metadata(it)
        for note in notes:
            level = logging.WARNING if "more than" in note else logging.DEBUG
            logger.log(level, f"{sid}: {note} url={url}")

        existing_entry = existing_index.get(url)
        if existing_entry:
            current_year, existing_item = existing_entry
            existing_item["seen_before"] = True
            for key in ["title", "doc_type", "filename", "meeting_date", "meeting_title", "root_url"]:
                if not existing_item.get(key) and it.get(key):
                    existing_item[key] = it[key]
            if storage_year != current_year:
                try:
                    items_by_year[current_year].remove(existing_item)
                except (ValueError, KeyError):
                    pass
                bucket = items_by_year.setdefault(storage_year, [])
                bucket.append(existing_item)
                existing_index[url] = (storage_year, existing_item)
                moved_count += 1
            continue

        it["seen_before"] = False
        bucket = items_by_year.setdefault(storage_year, [])
        bucket.append(it)
        existing_index[url] = (storage_year, it)
        new_count += 1

    # Drop empty buckets to avoid writing hollow years
    items_by_year = {year: items for year, items in items_by_year.items() if items}
    saved_paths = save_year_store(sid, name, items_by_year, root_url=root_url)
    total_after = sum(len(values) for values in items_by_year.values())
    logger.info(
        "✅ Source finished: %s added=%s moved=%s rebucketed=%s total=%s years=%s",
        name,
        new_count,
        moved_count,
        rebucketed,
        total_after,
        ",".join(sorted(saved_paths.keys())) or "-",
    )
    return {
        "source": sid,
        "source_name": name,
        "files": {year: str(path) for year, path in saved_paths.items()},
        "added": new_count,
        "existing": existing_total,
        "rebucketed": rebucketed,
        "moved": moved_count,
        "pages_fetched": pages_fetched,
        "links_discovered": links_total,
    }


def collect_all(config_path: Optional[str] = None, only_source: Optional[str] = None) -> int:
    logger = setup_logger()
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    try:
        cfg = load_sources(cfg_path)
    except Exception as e:
        logger.error(f"Failed to load sources.yaml: {e}")
        return 2

    session = HttpRetrySession()
    sources = cfg.get("sources", [])
    ran = 0
    for src in sources:
        sid = src.get("id") or slugify(src.get("name", ""))
        if only_source and only_source not in (sid, src.get("name")):
            continue
        collect_source(src, session, logger)
        ran += 1

    logger.info(f"🏁 Collection complete. Sources run: {ran}")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="Path to sources.yaml")
    ap.add_argument("--source", help="Run only a specific source (name or id)")
    args = ap.parse_args()
    raise SystemExit(collect_all(config_path=args.config, only_source=args.source))
