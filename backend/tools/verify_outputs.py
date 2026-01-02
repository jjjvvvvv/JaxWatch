#!/usr/bin/env python3
"""
Verify collected outputs under outputs/raw/*.

Features:
- Summarize counts per file and per doc_type
- Validate required item fields (including doc_type)
- Optional HEAD checks for URLs

CLI:
  python3 -m backend.tools.verify_outputs [--check-urls] [--source ID] [--date YYYY|YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

ROOT_RAW = Path("outputs/raw")
FILES_DIR = Path("outputs/files")


REQUIRED_FIELDS = [
    "url",
    "source",
    "date_collected",
    "status",
    "http_status",
    "seen_before",
    "doc_type",
]


@dataclass
class FileResult:
    source: str
    date_key: str
    file_path: Path
    item_count: int
    missing_field_items: int
    bad_urls: int


def iter_source_files(source_id: Optional[str], date_key: Optional[str]) -> List[Path]:
    files: List[Path] = []
    if source_id:
        src_dir = ROOT_RAW / source_id
        if not src_dir.exists():
            return []
        if date_key:
            # Support year-based store: outputs/raw/<src>/<YYYY>/<src>.json
            year_dir = src_dir / date_key
            legacy_path = src_dir / f"{date_key}.json"
            if year_dir.exists():
                files.extend(sorted(year_dir.glob("*.json")))
            elif legacy_path.exists():
                files.append(legacy_path)
        else:
            # Prefer year-based files; fallback to legacy flat files
            year_files = list(src_dir.glob("[0-9][0-9][0-9][0-9]/*.json"))
            if year_files:
                files.extend(sorted(year_files))
            else:
                files.extend(sorted(src_dir.glob("*.json")))
        return files

    # All sources
    if not ROOT_RAW.exists():
        return []
    for src_dir in sorted(ROOT_RAW.iterdir()):
        if not src_dir.is_dir():
            continue
        if date_key:
            year_dir = src_dir / date_key
            legacy_path = src_dir / f"{date_key}.json"
            if year_dir.exists():
                files.extend(sorted(year_dir.glob("*.json")))
            elif legacy_path.exists():
                files.append(legacy_path)
        else:
            year_files = list(src_dir.glob("[0-9][0-9][0-9][0-9]/*.json"))
            if year_files:
                files.extend(sorted(year_files))
            else:
                files.extend(sorted(src_dir.glob("*.json")))
    return files


def is_cms_getattachment(url: str) -> bool:
    return bool(url and "cms/getattachment" in url.lower())


def check_url_head(url: str, timeout: float = 15.0) -> int:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        return resp.status_code
    except Exception:
        return -1


def check_cms_pdf(url: str, timeout: float = 15.0) -> Tuple[int, str]:
    """For cms/getattachment URLs, prefer HEAD; if not 200, try a ranged GET.
    Returns (status_code, content_type)."""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        if resp.status_code == 200:
            return 200, resp.headers.get("Content-Type", "") or ""
    except Exception:
        pass
    # Some servers disallow HEAD; try a tiny GET
    try:
        resp = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=timeout)
        return resp.status_code, resp.headers.get("Content-Type", "") or ""
    except Exception:
        return -1, ""


def load_meta_map(source: str, year: str) -> Dict[str, dict]:
    meta_dir = FILES_DIR / source / year / "meta"
    out: Dict[str, dict] = {}
    if not meta_dir.exists():
        return out
    for j in meta_dir.glob("*.json"):
        try:
            data = json.load(j.open("r"))
            url = data.get("url")
            if url:
                out[url] = data
        except Exception:
            continue
    return out


def verify_file(fp: Path, do_head: bool = False, warn_nonpdf: bool = False) -> FileResult:
    try:
        data = json.load(fp.open("r"))
    except Exception as e:
        print(f"⚠️  Failed to read JSON: {fp} err={e}")
        return FileResult(source=fp.parent.name, date_key=fp.stem, file_path=fp, item_count=0, missing_field_items=0, bad_urls=0)

    items = data.get("items", [])
    # Path layout: outputs/raw/<src>/<YYYY>/<src>.json OR legacy outputs/raw/<src>/<date>.json
    source = data.get("source") or (fp.parent.parent.name if fp.parent.name.isdigit() else fp.parent.name)
    date_key = data.get("year") or (fp.parent.name if fp.parent.name.isdigit() else fp.stem)
    missing_field_items = 0
    bad_urls = 0
    meta_map = load_meta_map(source, date_key)
    pdf_types = {"agenda", "minutes", "packet", "resolution", "transcript", "addendum", "amendments", "staff_report", "presentation", "exhibit"}

    # Summary
    print(f"{date_key}  {source}  count={len(items)}  file={fp}")
    if len(items) == 0:
        print(f"⚠️  Zero items in {fp}")

    # Validate required fields
    for idx, it in enumerate(items):
        missing = [k for k in REQUIRED_FIELDS if k not in it or it.get(k) in (None, "")]
        if missing:
            missing_field_items += 1
            print(f"⚠️  Missing fields in item {idx} of {fp.name}: {', '.join(missing)}")

        # Warn if meta exists but content-type is not PDF for PDF-like types
        if warn_nonpdf:
            dt = (it.get("doc_type") or "").lower()
            if dt in pdf_types:
                meta = meta_map.get(it.get("url") or "")
                if meta:
                    ctype = (meta.get("content_type") or "").lower()
                    if ctype and "pdf" not in ctype:
                        print(f"⚠️  Non-PDF content-type '{ctype}' for {dt} url={it.get('url')}")

        # Only run HEAD when meta is missing
        if do_head and not meta_map.get(it.get("url") or ""):
            url = it.get("url")
            if not url:
                bad_urls += 1
                continue
            if is_cms_getattachment(url):
                status, ctype = check_cms_pdf(url)
                if status != 200 or (ctype and "pdf" not in ctype.lower()):
                    bad_urls += 1
                    print(f"⚠️  CMS getattachment check failed (status={status} ctype='{ctype}') for {url}")
            else:
                status = check_url_head(url)
                if status != 200:
                    bad_urls += 1
                    print(f"⚠️  URL HEAD non-200 ({status}) for {url}")

    return FileResult(
        source=source,
        date_key=date_key,
        file_path=fp,
        item_count=len(items),
        missing_field_items=missing_field_items,
        bad_urls=bad_urls,
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Verify outputs/raw/* JSON files")
    ap.add_argument("--check-urls", action="store_true", help="Only run HEAD for items missing meta")
    ap.add_argument("--warn-nonpdf", action="store_true", help="Warn if PDF-like doc_type has non-PDF content-type in meta")
    ap.add_argument("--source", help="Limit to a single source id", default=None)
    ap.add_argument("--date", help="Limit to a single date YYYY-MM-DD", default=None)
    args = ap.parse_args(argv)

    files = iter_source_files(args.source, args.date)
    if not files:
        print("⚠️  No files found under outputs/raw with given filters")
        return 1

    per_source_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    doc_type_totals: Dict[str, int] = defaultdict(int)
    any_warnings = False

    for fp in files:
        res = verify_file(fp, do_head=args.check_urls, warn_nonpdf=args.warn_nonpdf)
        t = per_source_totals[res.source]
        t["files"] += 1
        t["items"] += res.item_count
        t["zeros"] += 1 if res.item_count == 0 else 0
        t["missing_fields"] += res.missing_field_items
        t["bad_urls"] += res.bad_urls
        if res.item_count == 0 or res.missing_field_items > 0 or res.bad_urls > 0:
            any_warnings = True
        # Aggregate doc_type totals for this file
        try:
            data = json.load(fp.open("r"))
            for it in data.get("items", []):
                dt = (it.get("doc_type") or "").strip() or "(missing)"
                doc_type_totals[dt] += 1
        except Exception:
            pass

    print("\nTotals by source:")
    for src, t in sorted(per_source_totals.items()):
        print(
            f"  {src}: files={t['files']} items={t['items']} zeros={t['zeros']} "
            f"missing_fields={t['missing_fields']} bad_urls={t['bad_urls']}"
        )

    print("\nItems by doc_type:")
    for dt, n in sorted(doc_type_totals.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {dt}: {n}")

    if any_warnings:
        print("\n⚠️  Verification completed with warnings.")
        return 2
    else:
        print("\n✅ Verification passed with no issues.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
