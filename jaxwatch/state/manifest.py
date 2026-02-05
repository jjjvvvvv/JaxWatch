#!/usr/bin/env python3
"""
JaxWatch Collection Manifest
Tracks processed URLs across runs for incremental collection.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from jaxwatch.config.manager import get_config, JaxWatchConfig

logger = logging.getLogger("jaxwatch.state")

# Global manifest instance
_global_manifest: Optional['CollectionManifest'] = None


@dataclass
class URLEntry:
    """Entry for a processed URL."""
    url: str
    first_seen: str
    last_seen: str
    source: str
    status: str = "processed"  # processed, failed, skipped
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "source": self.source,
            "status": self.status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'URLEntry':
        return cls(
            url=data.get("url", ""),
            first_seen=data.get("first_seen", ""),
            last_seen=data.get("last_seen", ""),
            source=data.get("source", ""),
            status=data.get("status", "processed"),
            error=data.get("error"),
        )


@dataclass
class CollectionRun:
    """Record of a collection run."""
    started_at: str
    completed_at: Optional[str] = None
    source: Optional[str] = None
    urls_processed: int = 0
    urls_new: int = 0
    urls_failed: int = 0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "source": self.source,
            "urls_processed": self.urls_processed,
            "urls_new": self.urls_new,
            "urls_failed": self.urls_failed,
            "success": self.success,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CollectionRun':
        return cls(
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            source=data.get("source"),
            urls_processed=data.get("urls_processed", 0),
            urls_new=data.get("urls_new", 0),
            urls_failed=data.get("urls_failed", 0),
            success=data.get("success", True),
            error=data.get("error"),
        )


class CollectionManifest:
    """Persistent manifest for tracking collection state.

    Stores:
    - URLs processed with timestamps and status
    - Collection run history
    - Failed URLs for retry

    Enables:
    - Incremental collection (skip already-processed URLs)
    - Failed URL retry
    - Collection statistics
    """

    def __init__(self, config: Optional[JaxWatchConfig] = None):
        self.config = config or get_config()
        self._manifest_path = self.config.paths.outputs_dir / "state" / "collection_manifest.json"
        self._urls: Dict[str, URLEntry] = {}
        self._runs: List[CollectionRun] = []
        self._failed_urls: Dict[str, URLEntry] = {}
        self._dirty = False
        self._load()

    def _load(self):
        """Load manifest from disk."""
        if not self._manifest_path.exists():
            return

        try:
            with open(self._manifest_path, 'r') as f:
                data = json.load(f)

            # Load URL entries
            for url, entry_data in data.get("urls", {}).items():
                self._urls[url] = URLEntry.from_dict(entry_data)

            # Load run history
            for run_data in data.get("runs", []):
                self._runs.append(CollectionRun.from_dict(run_data))

            # Load failed URLs
            for url, entry_data in data.get("failed_urls", {}).items():
                self._failed_urls[url] = URLEntry.from_dict(entry_data)

            logger.debug(f"Loaded manifest: {len(self._urls)} URLs, {len(self._runs)} runs")

        except Exception as e:
            logger.warning(f"Could not load manifest: {e}")

    def save(self):
        """Save manifest to disk."""
        if not self._dirty:
            return

        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "updated_at": datetime.now().isoformat(),
            "urls": {url: entry.to_dict() for url, entry in self._urls.items()},
            "runs": [run.to_dict() for run in self._runs[-100:]],  # Keep last 100 runs
            "failed_urls": {url: entry.to_dict() for url, entry in self._failed_urls.items()},
        }

        with open(self._manifest_path, 'w') as f:
            json.dump(data, f, indent=2)

        self._dirty = False
        logger.debug(f"Saved manifest: {len(self._urls)} URLs")

    def is_url_processed(self, url: str) -> bool:
        """Check if URL has been successfully processed."""
        return url in self._urls and self._urls[url].status == "processed"

    def is_url_failed(self, url: str) -> bool:
        """Check if URL previously failed."""
        return url in self._failed_urls

    def get_url_entry(self, url: str) -> Optional[URLEntry]:
        """Get entry for a URL if it exists."""
        return self._urls.get(url) or self._failed_urls.get(url)

    def mark_url_processed(self, url: str, source: str):
        """Mark URL as successfully processed."""
        now = datetime.now().isoformat()

        if url in self._urls:
            self._urls[url].last_seen = now
        else:
            self._urls[url] = URLEntry(
                url=url,
                first_seen=now,
                last_seen=now,
                source=source,
                status="processed"
            )

        # Remove from failed if it was there
        if url in self._failed_urls:
            del self._failed_urls[url]

        self._dirty = True

    def mark_url_failed(self, url: str, source: str, error: str):
        """Mark URL as failed."""
        now = datetime.now().isoformat()

        entry = URLEntry(
            url=url,
            first_seen=now,
            last_seen=now,
            source=source,
            status="failed",
            error=error
        )

        self._failed_urls[url] = entry
        self._dirty = True

    def mark_url_skipped(self, url: str, source: str):
        """Mark URL as skipped (e.g., already processed)."""
        if url in self._urls:
            self._urls[url].last_seen = datetime.now().isoformat()
            self._dirty = True

    def start_run(self, source: Optional[str] = None) -> CollectionRun:
        """Start a new collection run."""
        run = CollectionRun(
            started_at=datetime.now().isoformat(),
            source=source
        )
        self._runs.append(run)
        self._dirty = True
        return run

    def end_run(self, run: CollectionRun, success: bool = True, error: Optional[str] = None):
        """End a collection run."""
        run.completed_at = datetime.now().isoformat()
        run.success = success
        run.error = error
        self._dirty = True
        self.save()

    def get_processed_urls(self, source: Optional[str] = None) -> Set[str]:
        """Get set of processed URLs, optionally filtered by source."""
        urls = set()
        for url, entry in self._urls.items():
            if entry.status == "processed":
                if source is None or entry.source == source:
                    urls.add(url)
        return urls

    def get_failed_urls(self, source: Optional[str] = None) -> List[URLEntry]:
        """Get list of failed URLs for retry."""
        entries = []
        for entry in self._failed_urls.values():
            if source is None or entry.source == source:
                entries.append(entry)
        return entries

    def get_last_run(self, source: Optional[str] = None) -> Optional[CollectionRun]:
        """Get the most recent collection run."""
        for run in reversed(self._runs):
            if source is None or run.source == source:
                return run
        return None

    def get_stats(self) -> dict:
        """Get manifest statistics."""
        return {
            "total_urls": len(self._urls),
            "processed_urls": sum(1 for e in self._urls.values() if e.status == "processed"),
            "failed_urls": len(self._failed_urls),
            "total_runs": len(self._runs),
            "last_run": self._runs[-1].to_dict() if self._runs else None,
        }

    def clear_failed(self, source: Optional[str] = None):
        """Clear failed URLs for retry."""
        if source:
            self._failed_urls = {
                url: entry for url, entry in self._failed_urls.items()
                if entry.source != source
            }
        else:
            self._failed_urls.clear()
        self._dirty = True


def get_manifest(config: Optional[JaxWatchConfig] = None) -> CollectionManifest:
    """Get global manifest instance."""
    global _global_manifest
    if _global_manifest is None or config is not None:
        _global_manifest = CollectionManifest(config)
    return _global_manifest
