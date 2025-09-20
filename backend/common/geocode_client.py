#!/usr/bin/env python3
"""
Geocoding client for MVP with caching, respectful UA, and bbox.
Uses Nominatim (via openstreetmap.org) style endpoint with simple cache to avoid rate pressure.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Tuple, Optional

import requests

from .retry_utils import retry_with_backoff, RetryStrategy


CACHE_PATH = Path("data/runtime/geocode_cache.json")
CACHE_TTL_SECONDS = int(os.getenv("JAXWATCH_GEOCODE_TTL", str(30*24*3600)))  # 30 days
MAX_CACHE_ENTRIES = int(os.getenv("JAXWATCH_GEOCODE_MAX", "5000"))
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

USER_AGENT = os.getenv(
    "JAXWATCH_UA",
    "Mozilla/5.0 (compatible; JaxWatch/1.0; +https://github.com/jjjvvvvv/JaxWatch)"
)

# Rough Jacksonville bounding box (min_lon, min_lat, max_lon, max_lat)
JAX_BBOX = (-82.5, 29.5, -80.5, 31.0)


def _load_cache() -> dict:
    try:
        if CACHE_PATH.exists():
            with open(CACHE_PATH, "r") as f:
                data = json.load(f)
                # prune expired entries
                now = time.time()
                cleaned = {}
                for k, v in data.items():
                    try:
                        ts = float(v.get("last", v.get("ts", 0)))
                    except Exception:
                        ts = 0
                    if ts and (now - ts) <= CACHE_TTL_SECONDS:
                        cleaned[k] = v
                return cleaned
    except Exception:
        pass
    return {}


def _save_cache(cache: dict) -> None:
    try:
        # Enforce LRU cap
        if len(cache) > MAX_CACHE_ENTRIES:
            # sort by 'last' timestamp ascending and keep newest MAX_CACHE_ENTRIES
            items = sorted(cache.items(), key=lambda kv: float(kv[1].get("last", kv[1].get("ts", 0)) or 0))
            cache = dict(items[-MAX_CACHE_ENTRIES:])
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def _in_bbox(lat: float, lon: float) -> bool:
    return (JAX_BBOX[1] <= lat <= JAX_BBOX[3]) and (JAX_BBOX[0] <= lon <= JAX_BBOX[2])


@retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
def _geocode_nominatim(query: str) -> Tuple[Optional[float], Optional[float]]:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US"}
    params = {
        "format": "json",
        "q": query,
        "limit": 1,
        "countrycodes": "us",
        # Note: Can't pass bbox as filter for regular search; we'll post-filter
    }
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None, None
    try:
        lat = float(data[0]["lat"])  # type: ignore
        lon = float(data[0]["lon"])  # type: ignore
    except Exception:
        return None, None
    if not _in_bbox(lat, lon):
        return None, None
    return lat, lon


def geocode_address(address: Optional[str], city: str = "Jacksonville", state: str = "FL") -> Tuple[Optional[float], Optional[float]]:
    if not address or not address.strip():
        return None, None

    full_query = address.strip()
    # Add city/state if not present already
    if not ("jacksonville" in full_query.lower() and "fl" in full_query.lower()):
        full_query = f"{full_query}, {city}, {state}"

    cache = _load_cache()
    if full_query in cache:
        entry = cache[full_query]
        lat, lon = entry.get("lat"), entry.get("lon")
        entry["last"] = time.time()
        _save_cache(cache)
        return lat, lon  # type: ignore

    lat, lon = _geocode_nominatim(full_query)

    # Respect rate limits
    time.sleep(1.0)

    # Cache result (even misses) to reduce repeated attempts
    cache[full_query] = {"lat": lat, "lon": lon, "ts": time.time(), "last": time.time()}
    _save_cache(cache)
    return lat, lon
