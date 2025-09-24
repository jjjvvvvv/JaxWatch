#!/usr/bin/env python3
"""
Collection-first engine: fetch pages, extract links, keep everything that matches
configured patterns. No parsing or geocoding. Transparent logging.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup

from .retry_utils import HttpRetrySession
from .meeting_detail_scraper import scrape_meeting_attachments
import logging


DEFAULT_CONFIG_PATH = Path(__file__).parent / "sources.yaml"
RAW_OUT_DIR = Path("outputs/raw")
LOG_DIR = Path("outputs/logs")
# Note: no persistent state in MVP (only logs + raw outputs)


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


def _collect_city_council(source: Dict[str, Any], session: HttpRetrySession, logger: logging.Logger) -> Dict[str, Any]:
    name = source.get("name") or source.get("id") or "unknown"
    sid = source.get("id") or slugify(name)
    candidates = source.get("candidates")
    if not candidates:
        u = source.get("url")
        candidates = [u] if u else []
    patterns = source.get("patterns") or []

    discovered: List[Dict[str, Any]] = []
    local_seen: set[str] = set()
    pages_fetched = 0
    links_total = 0

    meeting_detail_links: List[str] = []

    # 1) Fetch calendar/meetings pages and harvest MeetingDetail.aspx links
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
            if not href:
                continue
            abs_url = absolute_link(url, href)
            if not abs_url:
                continue
            if "meetingdetail.aspx" in abs_url.lower():
                meeting_detail_links.append(abs_url)
                continue
            # Also capture direct Agenda/Minutes/Addendum/etc. links on the calendar rows
            title = a.get_text(strip=True) or ""
            title_l = title.lower()
            if 'view.ashx' in abs_url.lower():
                # Accept all direct Legistar document endpoints; many have empty text with only an icon
                if abs_url in local_seen:
                    continue
                filename = Path(urlparse(abs_url).path).name or 'document.pdf'
                already = False
                item = {
                    "url": abs_url,
                    "filename": filename,
                    "title": title,
                    "source": sid,
                    "source_name": name,
                    "date_collected": datetime.now().isoformat(),
                    "status": "discovered",
                    "http_status": "discovered",
                    "seen_before": already,
                }
                discovered.append(item)
                local_seen.add(abs_url)
                logger.info(f"Kept direct calendar link: {abs_url} title='{title}'")

    meeting_detail_links = list(dict.fromkeys(meeting_detail_links))  # de-dup preserve order
    logger.info(f"Found {len(meeting_detail_links)} MeetingDetail.aspx links to follow")

    # 2) For each meeting detail, scrape attachments and record them
    for detail_url in meeting_detail_links:
        try:
            atts = scrape_meeting_attachments(detail_url=detail_url, session=session)
            pages_fetched += 1  # one fetch inside scraper
        except Exception as e:
            logger.warning(f"Attachment scrape failed: {detail_url} err={e}")
            atts = []

        for att in atts:
            abs_url = att.get("url")
            title = att.get("title") or att.get("type") or ""
            if not abs_url:
                continue
            # Optional: enforce pattern match if patterns configured
            keep = is_match(abs_url, title, patterns) if patterns else True
            if not keep:
                continue
            if abs_url in local_seen:
                continue
            filename = Path(urlparse(abs_url).path).name
            already = False
            item = {
                "url": abs_url,
                "filename": filename,
                "title": title,
                "source": sid,
                "source_name": name,
                "date_collected": datetime.now().isoformat(),
                "status": "discovered",
                "http_status": "discovered",
                "seen_before": already,
            }
            discovered.append(item)
            local_seen.add(abs_url)
            logger.info(f"Kept attachment: {abs_url} title='{title}' from {detail_url}")

    return {
        "discovered": discovered,
        "pages_fetched": pages_fetched,
        "links_total": links_total,
    }


def _collect_ddrb(source: Dict[str, Any], session: HttpRetrySession, logger: logging.Logger) -> Dict[str, Any]:
    name = source.get("name") or source.get("id") or "unknown"
    sid = source.get("id") or slugify(name)
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

    def keep_doc(url: str, title: str) -> bool:
        u = url.lower()
        t = (title or "").lower()
        if u.endswith('.pdf'):
            return any(k in t or k in u for k in ["agenda", "minutes", "packet"])
        if "coj365-my.sharepoint.com" in u:
            return any(k in t or k in u for k in ["agenda", "minutes", "packet"])
        return False

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
            # Direct doc links on listing page
            if keep_doc(lu, title):
                if abs_url in local_seen:
                    continue
                filename = Path(urlparse(abs_url).path).name or 'document'
                already = False
                discovered.append({
                    "url": abs_url,
                    "filename": filename,
                    "title": title,
                    "source": sid,
                    "source_name": name,
                    "date_collected": datetime.now().isoformat(),
                    "status": "discovered",
                    "http_status": "discovered",
                    "seen_before": already,
                })
                local_seen.add(abs_url)
                continue
            # Collect internal meeting detail pages on dia.jacksonville.gov
            if lu.startswith("http") and "dia.jacksonville.gov" in lu and not lu.endswith('.pdf') and "coj365-my.sharepoint.com" not in lu:
                meeting_pages.append(abs_url)

    meeting_pages = list(dict.fromkeys(meeting_pages))
    logger.info(f"DDRB: following {len(meeting_pages)} meeting detail page(s)")

    # 2) Follow each meeting detail page to collect agenda/minutes/packet links
    for detail in meeting_pages:
        try:
            resp = session.get(detail)
            pages_fetched += 1
        except Exception as e:
            logger.warning(f"DDRB detail fetch failed: {detail} err={e}")
            continue
        soup = BeautifulSoup(resp.content, "html.parser")
        anchors = soup.find_all("a", href=True)
        for a in anchors:
            href = a.get("href", "").strip()
            title = a.get_text(strip=True) or ""
            abs_url = absolute_link(detail, href)
            if not abs_url:
                continue
            if abs_url in local_seen:
                continue
            if keep_doc(abs_url, title):
                filename = Path(urlparse(abs_url).path).name or 'document'
                already = False
                discovered.append({
                    "url": abs_url,
                    "filename": filename,
                    "title": title,
                    "source": sid,
                    "source_name": name,
                    "date_collected": datetime.now().isoformat(),
                    "status": "discovered",
                    "http_status": "discovered",
                    "seen_before": already,
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

    # Special-case handling: City Council Legistar attachments
    if sid == "city_council":
        logger.info("Special handling for City Council: following MeetingDetail.aspx to collect attachments")
        cc = _collect_city_council(source, session, logger)
        discovered = cc["discovered"]
        pages_fetched += cc["pages_fetched"]
        links_total += cc["links_total"]
    elif sid == "ddrb":
        logger.info("Special handling for DDRB: following meeting detail pages and collecting docs")
        dd = _collect_ddrb(source, session, logger)
        discovered = dd["discovered"]
        pages_fetched += dd["pages_fetched"]
        links_total += dd["links_total"]
    elif sid == "planning_commission":
        # Special handling: inclusive heuristics for AGENDA/RESULTS/STAFF REPORTS and filedrop links
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
                s = f"{title} {abs_url}".lower()
                keep = False
                if any(k in s for k in ["pc meeting agenda", "results agenda", "staff reports", "planning commission"]):
                    keep = True
                if "filedrop.coj.net" in s:
                    keep = True
                if abs_url.lower().endswith('.pdf') and any(k in s for k in ["agenda", "results", "minutes", "staff", "packet"]):
                    keep = True
                if not keep:
                    continue
                if abs_url in seen:
                    continue
                seen.add(abs_url)
                filename = Path(urlparse(abs_url).path).name or 'document'
                already = False
                discovered.append({
                    "url": abs_url,
                    "filename": filename,
                    "title": title,
                    "source": sid,
                    "source_name": name,
                    "date_collected": datetime.now().isoformat(),
                    "status": "discovered",
                    "http_status": "discovered",
                    "seen_before": already,
                })
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
                        "date_collected": datetime.now().isoformat(),
                        "status": "discovered",
                        "http_status": "discovered",
                        "seen_before": already,
                    }
                    discovered.append(item)
                    logger.info(f"Kept: {abs_url} title='{title}'")
                else:
                    logger.info(f"Skipped (no pattern match): {abs_url} title='{title}'")

    # Prefer known_layer for ArcGIS sources (e.g., capital_projects)
    # Prefer known_layer(s) for ArcGIS sources (e.g., capital_projects)
    known_layer = source.get("known_layer")
    known_layers = source.get("known_layers")
    layer_list: List[str] = []
    if isinstance(known_layers, list) and known_layers:
        layer_list.extend([str(u) for u in known_layers])
    if isinstance(known_layer, str) and known_layer:
        layer_list.append(known_layer)

    for layer_url in layer_list:
        try:
            resp = session.get(layer_url)
            pages_fetched += 1
            logger.info(f"Fetched known layer: {layer_url} status={resp.status_code} bytes={len(resp.content)}")
        except Exception as e:
            logger.warning(f"Known layer fetch failed: {layer_url} err={e}")
        filename = Path(urlparse(layer_url).path).name
        already = False
        discovered.append({
            "url": layer_url,
            "filename": filename,
            "title": "known_layer",
            "source": sid,
            "source_name": name,
            "date_collected": datetime.now().isoformat(),
            "status": "discovered",
            "http_status": "discovered",
            "seen_before": already,
        })
    if layer_list:
        logger.info(f"Recorded {len(layer_list)} known layer endpoint(s) for source {sid}")

    # Write output JSON

    # Write output JSON
    out_dir = RAW_OUT_DIR / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    date_key = datetime.now().strftime("%Y-%m-%d")
    out_path = out_dir / f"{date_key}.json"
    payload = {
        "source": sid,
        "source_name": name,
        "timestamp": datetime.now().isoformat(),
        "pages_fetched": pages_fetched,
        "links_discovered": links_total,
        "items": discovered,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"✅ Source finished: {name} saved={len(discovered)} file={out_path}")
    return payload


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
