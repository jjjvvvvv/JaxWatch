#!/usr/bin/env python3
"""
One-Month Batch Test runner for JaxWatch (new schema)

- Fetches sources for a target month (City Council, Planning Commission, DDRB)
- Includes CIP snapshot regardless of month
- Normalizes items to the new schema: {meeting, legislation, vote, project}
- Performs light geocoding on projects with addresses but missing coords
- Writes consolidated JSON and a QA text report

Usage:
  python3 backend/tools/batch_test.py --month YYYY-MM
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path for `backend` imports
THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Adapters (fetch functions)
from backend.adapters import (
    city_council_fetch,
    planning_commission_fetch,
    ddrb_fetch,
    infrastructure_fetch,
)

# Geocoding helper (best-effort)
from backend.common.geocode_client import geocode_address


OUTPUT_DIR = Path("outputs")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run one-month batch test")
    ap.add_argument(
        "--month",
        required=False,
        help="Target month in YYYY-MM format (e.g., 2025-08)",
    )
    ap.add_argument(
        "--months",
        help="Comma-separated list of months (YYYY-MM,YYYY-MM)",
    )
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 even if no real items were produced",
    )
    return ap.parse_args()


def is_in_month(date_str: Optional[str], month: str) -> bool:
    if not date_str:
        return False
    # Accept 'YYYY-MM-DD' or 'YYYY-MM' strings
    return date_str.startswith(month)


def norm_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    try:
        # Try many likely date formats; output YYYY-MM-DD
        fmts = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%m-%d-%Y",
            "%m-%d-%y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y-%m",
        ]
        for fmt in fmts:
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
    except Exception:
        pass
    # If it looks like YYYY-MM-DD already or YYYY-MM, keep as-is
    if len(s) in (7, 10) and s[4] == "-":
        return s
    return None


def ensure_geocoded(project: Dict[str, Any]) -> Dict[str, Any]:
    # Only attempt if no coordinates but we have an address
    lat = project.get("latitude")
    lon = project.get("longitude")
    addr = project.get("address")
    if (lat is None or lon is None) and addr:
        try:
            g_lat, g_lon = geocode_address(addr)
            if g_lat and g_lon:
                project["latitude"] = g_lat
                project["longitude"] = g_lon
        except Exception:
            # Network or API failure is fine in batch test context
            pass
    return project


def to_new_schema_from_cip(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize legacy CIP/infrastructure item to new schema."""
    date = norm_date(item.get("date")) or datetime.now().strftime("%Y-%m-%d")
    meeting_id = f"infrastructure-{date}"
    file_number = str(item.get("item_number") or f"CIP-{date}")

    project_flags = []
    if item.get("flagged"):
        project_flags.append("source_flagged")
    if item.get("mock"):
        project_flags.append("mock_data")

    project: Dict[str, Any] = {
        "project_id": file_number,
        "title": item.get("title") or "Capital Improvement Project",
        "address": None,
        "re_number": None,
        "council_district": item.get("council_district"),
        "location_status": "parcel" if (item.get("parcel_lat") and item.get("parcel_lon")) else "unknown",
        "latitude": item.get("parcel_lat"),
        "longitude": item.get("parcel_lon"),
        "flags": project_flags,
    }

    project = ensure_geocoded(project)

    return {
        "meeting": {
            "id": meeting_id,
            "body": "Infrastructure Committee",
            "date": date,
            "source_url": item.get("url") or "https://maps.coj.net/capitalprojects/",
        },
        "legislation": {
            "file_number": file_number,
            "title": item.get("title") or "Capital Improvement Project",
            "status": item.get("status") or "Unknown",
            "meeting_id": meeting_id,
        },
        "vote": None,
        "project": project,
    }


def gather_sources(month: str) -> List[Dict[str, Any]]:
    """Fetch and normalize items from target sources."""
    items: List[Dict[str, Any]] = []

    # City Council (filter to month)
    try:
        council_raw = city_council_fetch()
        for it in council_raw:
            meeting = it.get("meeting", {})
            date = norm_date(meeting.get("date"))
            if is_in_month(date, month):
                # augment ambiguous_vote if vote missing
                if not it.get("vote"):
                    # Safe place to surface a QA flag associated with project if present
                    proj = it.get("project") or {"project_id": f"council-{date}", "title": it.get("legislation", {}).get("title", "Council Item"), "location_status": "unknown", "flags": []}
                    proj.setdefault("flags", [])
                    if "ambiguous_vote" not in proj["flags"]:
                        proj["flags"].append("ambiguous_vote")
                    it["project"] = proj
                items.append(it)
    except Exception:
        pass

    # Planning Commission (filter to month)
    try:
        planning_raw = planning_commission_fetch()
        for it in planning_raw:
            meeting = it.get("meeting", {})
            date = norm_date(meeting.get("date"))
            if is_in_month(date, month):
                # geocode best-effort
                proj = it.get("project")
                if proj:
                    it["project"] = ensure_geocoded(proj)
                items.append(it)
    except Exception:
        pass

    # DDRB (filter to month)
    try:
        ddrb_raw = ddrb_fetch()
        for it in ddrb_raw:
            meeting = it.get("meeting", {})
            date = norm_date(meeting.get("date"))
            if is_in_month(date, month):
                proj = it.get("project")
                if proj:
                    it["project"] = ensure_geocoded(proj)
                items.append(it)
    except Exception:
        pass

    # CIP snapshot (no month restriction)
    try:
        cip_raw = infrastructure_fetch()
        for legacy in cip_raw:
            items.append(to_new_schema_from_cip(legacy))
    except Exception:
        pass

    # Filter out any adapter fallback/mock items to honor "only real numbers"
    def is_fallback(it: Dict[str, Any]) -> bool:
        leg = (it.get("legislation", {}) or {}).get("title", "")
        leg_l = leg.lower()
        if any(tok in leg_l for tok in ["fallback", "in development", "data collection"]):
            return True
        proj = it.get("project") or {}
        flags = [f.lower() for f in (proj.get("flags") or [])]
        if any(f in flags for f in ["fallback_data", "development_data", "mock_data", "source_flagged"]):
            return True
        return False

    real_items = [it for it in items if not is_fallback(it)]
    return real_items


def compute_stats(items: List[Dict[str, Any]], month: str) -> Dict[str, Any]:
    meetings = {it.get("meeting", {}).get("id") for it in items if it.get("meeting")}
    meetings = {m for m in meetings if m}

    # Legislation items: count where legislation exists
    legislation_count = sum(1 for it in items if it.get("legislation"))

    # Focus council subset for vote stats
    council_items = [it for it in items if (it.get("meeting", {}).get("body", "").lower().find("council") >= 0)]
    votes_extracted = sum(1 for it in council_items if it.get("vote"))
    votes_total = len(council_items) or 1
    votes_pct = int(round(100 * votes_extracted / votes_total))

    # Project-based stats
    projects = [it.get("project") for it in items if it.get("project")]
    with_re = sum(1 for p in projects if p.get("re_number"))
    with_cd = sum(1 for p in projects if p.get("council_district") is not None)
    proj_total = len(projects) or 1

    # Flags
    flag_counts: Dict[str, int] = {}
    for p in projects:
        for flag in p.get("flags", []) or []:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    # Attachment counts (from meeting.attachments when present)
    attachment_counts: Dict[str, int] = {}
    for it in items:
        mtg = it.get("meeting") or {}
        atts = mtg.get("attachments") or []
        if isinstance(atts, list):
            for a in atts:
                atype = (a or {}).get("type") or "other"
                attachment_counts[atype] = attachment_counts.get(atype, 0) + 1

    return {
        "month": month,
        "meetings_parsed": len(meetings),
        "legislation_items": legislation_count,
        "votes": {
            "extracted": votes_extracted,
            "total_council_items": votes_total,
            "percent": votes_pct,
        },
        "projects": {
            "total": len(projects),
            "with_re": with_re,
            "with_re_percent": int(round(100 * with_re / (proj_total)) if proj_total else 0),
            "with_council_district": with_cd,
            "with_council_district_percent": int(round(100 * with_cd / (proj_total)) if proj_total else 0),
        },
        "flags": flag_counts,
        "attachments": attachment_counts,
    }


def write_json(items: List[Dict[str, Any]], month: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"batch_{month}.json"
    payload = {
        "generated_at": datetime.now().isoformat(),
        "month": month,
        "count": len(items),
        "items": items,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    return out_path


def write_report(stats: Dict[str, Any], items: List[Dict[str, Any]], month: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / f"batch_{month}_report.txt"

    # Spot-check selection (IDs and URLs only; manual verification expected)
    council_samples = [it for it in items if it.get("meeting", {}).get("body", "").lower().find("council") >= 0]
    planning_samples = [it for it in items if it.get("meeting", {}).get("body", "").lower().find("planning commission") >= 0]

    council_samples = council_samples[:3]
    planning_samples = planning_samples[:2]

    lines: List[str] = []
    lines.append("Jacksonville Observer — One-Month Batch Test Report")
    lines.append("")
    lines.append(f"Month: {month}")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append("Summary:")
    lines.append(f"  Meetings parsed: {stats['meetings_parsed']}")
    lines.append(f"  Legislation items: {stats['legislation_items']}")
    lines.append(
        f"  Votes extracted: {stats['votes']['extracted']} ({stats['votes']['percent']}%)"
    )
    lines.append(
        f"  Projects with RE#: {stats['projects']['with_re']} ({stats['projects']['with_re_percent']}%)"
    )
    lines.append(
        f"  Projects with council district: {stats['projects']['with_council_district']} ({stats['projects']['with_council_district_percent']}%)"
    )
    lines.append("  Flags raised:")
    if stats.get("flags"):
        for k, v in sorted(stats["flags"].items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"    - {k}: {v}")
    else:
        lines.append("    - none")

    # Attachments summary
    lines.append("  Attachments:")
    atts = stats.get("attachments") or {}
    if atts:
        for k, v in sorted(atts.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"    - {k}: {v}")
    else:
        lines.append("    - none")

    lines.append("")
    lines.append("Spot-Checks (manual):")
    lines.append("  Council votes (3):")
    if council_samples:
        for it in council_samples:
            mtg = it.get("meeting", {})
            leg = it.get("legislation", {})
            vote = it.get("vote") or {}
            lines.append(
                f"    - {mtg.get('date')} | {leg.get('file_number')} | tally: {vote.get('tally', 'N/A')} | URL: {mtg.get('source_url')} | RESULT: PENDING"
            )
    else:
        lines.append("    - none available")

    lines.append("  Planning cases (2):")
    if planning_samples:
        for it in planning_samples:
            mtg = it.get("meeting", {})
            leg = it.get("legislation", {})
            proj = it.get("project") or {}
            lines.append(
                f"    - {mtg.get('date')} | {leg.get('file_number')} | title: {leg.get('title', '')[:60]} | URL: {mtg.get('source_url')} | RESULT: PENDING"
            )
    else:
        lines.append("    - none available")

    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return report_path


def main() -> int:
    args = parse_args()

    # Build month list
    month_list: List[str] = []
    if args.month:
        month_list = [args.month]
    if args.months:
        month_list = [m.strip() for m in args.months.split(',') if m.strip()]
    if not month_list:
        print("Usage: --month YYYY-MM or --months YYYY-MM,YYYY-MM")
        return 2

    # Validate
    for m in month_list:
        try:
            datetime.strptime(m + "-01", "%Y-%m-%d")
        except Exception:
            print(f"Invalid month: {m}. Expected YYYY-MM.")
            return 2

    empty_months: List[str] = []
    for month in month_list:
        items = gather_sources(month)
        stats = compute_stats(items, month)
        out_json = write_json(items, month)
        out_report = write_report(stats, items, month)

        print(f"\n✅ Batch test complete for {month}")
        print(f"  JSON:   {out_json}")
        print(f"  Report: {out_report}")

        if len(items) == 0:
            empty_months.append(month)

    if empty_months and not args.allow_empty:
        print(f"\n⚠️ No real data produced for: {', '.join(empty_months)}")
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
