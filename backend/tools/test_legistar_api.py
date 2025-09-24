#!/usr/bin/env python3
"""
Quick Legistar API probe for Jacksonville.
Tests Events queries for a month using multiple filter syntaxes and prints results.

Usage:
  python3 backend/tools/test_legistar_api.py --year 2025 --month 8
"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any, Dict, List

import sys
from pathlib import Path

# Ensure repo root in path
THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.common.retry_utils import HttpRetrySession

BASE = "https://webapi.legistar.com/v1/jacksonville"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    return ap.parse_args()


def probe(session: HttpRetrySession, url: str, params: Dict[str, Any]):
    print(f"\nGET {url}")
    print(f"params={params}")
    try:
        r = session.get(url, params=params, headers={"Accept": "application/json"})
        print(f"status={r.status_code}")
        try:
            data = r.json()
        except Exception:
            data = None
        if isinstance(data, list):
            print(f"items={len(data)}")
            if data:
                keys = list(data[0].keys())
                print(f"first_keys={keys[:8]}")
                print(f"first={ {k: data[0].get(k) for k in keys[:5]} }")
        else:
            print(f"body={str(r.text)[:200]}")
    except Exception as e:
        print(f"probe_error={e}")


def main() -> int:
    args = parse_args()
    y, m = args.year, args.month

    start = datetime(y, m, 1)
    end = datetime(y + (1 if m == 12 else 0), (m % 12) + 1, 1)

    session = HttpRetrySession()
    # Test 1: simple date literals
    probe(session, f"{BASE}/Events", {
        "$filter": f"EventDate ge {start.date()} and EventDate lt {end.date()}",
        "$orderby": "EventDate desc",
        "$top": 50,
    })

    # Test 2: datetime'...' literals
    probe(session, f"{BASE}/Events", {
        "$filter": f"EventDate ge datetime'{start.strftime('%Y-%m-%dT00:00:00')}' and EventDate lt datetime'{end.strftime('%Y-%m-%dT00:00:00')}'",
        "$orderby": "EventDate desc",
        "$top": 50,
    })

    # Test 3: no filter (top few)
    probe(session, f"{BASE}/Events", {
        "$orderby": "EventDate desc",
        "$top": 10,
    })

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
