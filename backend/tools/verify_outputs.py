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
from typing import Dict, List, Optional

import requests

ROOT_RAW = Path("outputs/raw")


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


def check_url_head(url: str, timeout: float = 15.0) -> int:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        return resp.status_code
    except Exception:
        return -1


def verify_file(fp: Path, do_head: bool = False) -> FileResult:
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

        if do_head:
            url = it.get("url")
            if not url:
                bad_urls += 1
                continue
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
    ap.add_argument("--check-urls", action="store_true", help="Issue HEAD requests for each URL and log non-200 responses")
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
        res = verify_file(fp, do_head=args.check_urls)
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
