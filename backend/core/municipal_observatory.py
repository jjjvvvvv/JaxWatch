#!/usr/bin/env python3
"""
JaxWatch Municipal Observatory
Master orchestrator for coordinating municipal data collection from multiple sources
"""

import yaml
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import time

from .agenda_schema import AgendaItem, NoticeItem, validate_agenda_item, validate_notice_item
from ..common.alerts import alert_validation_failure, alert_pipeline_failure, alert_system_health, alert_rare_document, AlertLevel, AlertType, get_alerter
from ..common.geocode_client import geocode_address
from ..common.retry_utils import safe_execute, ErrorContext
from urllib.parse import urlparse
from ..adapters import get_adapter as registry_get_adapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_sources():
    """Load source configuration from sources.yaml"""
    yaml_path = Path(__file__).parent / "sources.yaml"
    try:
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
            return config["sources"], config.get("config", {})
    except Exception as e:
        logger.error(f"Failed to load sources.yaml: {e}")
        return [], {}


def get_adapter_function(adapter_name: str):
    """Return adapter function from central registry"""
    func = registry_get_adapter(adapter_name)
    if not func:
        logger.error(f"Unknown adapter: {adapter_name}")
    return func


def geocode_agenda_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Geocode an agenda item if it has an address but missing coordinates"""
    # Check if item already has coordinates
    if item.get("parcel_lat") and item.get("parcel_lon"):
        return item

    # Try to get address from various fields
    address = None
    if item.get("parcel_address"):
        address = item["parcel_address"]
    elif item.get("location"):
        address = item["location"]
    elif item.get("address"):
        address = item["address"]

    if not address or address.strip() == "":
        return item

    # Use safe_execute for geocoding with fallback
    def _geocode():
        # Clean address (remove city/state if already included)
        clean_address = address.strip()
        if "Jacksonville" in clean_address and "FL" in clean_address:
            # Already has city/state, use as-is
            return geocode_address(clean_address, city="", state="")
        else:
            # Add Jacksonville, FL
            return geocode_address(clean_address)

    # Try geocoding with fallback to None, None
    lat, lon = safe_execute(_geocode, fallback_value=(None, None))

    if lat and lon:
        item["parcel_lat"] = lat
        item["parcel_lon"] = lon
        logger.info(f"🗺️ Geocoded: {address} -> ({lat:.6f}, {lon:.6f})")
        # Small delay to respect free API rate limits
        time.sleep(1)

    return item


def write_to_firestore(validated_items: List[Dict[str, Any]], source_id: str):
    """Write validated items to Firestore"""
    from ..common.firestore_client import write_municipal_items

    success = write_municipal_items(validated_items, source_id)
    if not success:
        logger.error(f"❌ Failed to write {len(validated_items)} items from {source_id}")
        alert_system_health(f"Failed to write data from {source_id} to storage")
    else:
        logger.info(f"✅ Successfully wrote {len(validated_items)} items from {source_id}")


def run_observatory():
    """Main orchestrator function - reads config and runs all enabled sources"""
    start_time = time.time()
    logger.info("🏛️ Starting JaxWatch Municipal Observatory")

    sources, config = load_sources()
    if not sources:
        alert_system_health("No sources loaded from configuration", severity="critical")
        return

    logger.info(f"Loaded {len(sources)} sources from configuration")

    total_processed = 0
    total_flagged = 0

    for source in sources:
        if not source.get("enabled", False):
            logger.info(f"⏭️ Skipping disabled source: {source['name']}")
            continue

        source_id = source["id"]
        source_name = source["name"]
        adapter_name = source["adapter"]
        source_type = source.get("type", "agenda")

        logger.info(f"📡 Processing source: {source_name} ({source_id})")

        # Get adapter function
        adapter_func = get_adapter_function(adapter_name)
        if not adapter_func:
            alert_pipeline_failure(source_name, f"No adapter found for {adapter_name}")
            continue

        with ErrorContext(f"Processing {source_name}", source_id):
            # Run adapter to get raw items
            raw_items = adapter_func()
            logger.info(f"📋 Fetched {len(raw_items)} raw items from {source_name}")

            # Validate each item according to schema
            validated_items = []
            flagged_count = 0

            for item in raw_items:
                # Add source metadata
                item["source_id"] = source_id
                # Add provenance hostname if URL is present
                try:
                    if item.get("url") and not item.get("source"):
                        item["source"] = urlparse(item["url"]).netloc or None
                except Exception:
                    pass
                # Last updated timestamp for each item
                item["last_updated"] = datetime.now().isoformat()

                # Geocode item if it has address but missing coordinates
                item = geocode_agenda_item(item)

                # Validate based on source type
                if source_type == "agenda":
                    validated_item = validate_agenda_item(item)
                elif source_type == "notice":
                    validated_item = validate_notice_item(item)
                else:
                    # Default to agenda item
                    validated_item = validate_agenda_item(item)

                # Check if item was flagged during validation
                if validated_item.flagged:
                    flagged_count += 1

                    # Alert for validation errors
                    if hasattr(validated_item, 'validation_error'):
                        alert_validation_failure(
                            source=source_name,
                            project_id=getattr(validated_item, 'item_number', 'unknown'),
                            error=validated_item.validation_error
                        )

                    # Individual flagged item alerts disabled for MVP - only daily summary sent
                    # alert_rare_document(
                    #     source=source_name,
                    #     document_type="Flagged Municipal Project",
                    #     link=validated_item.url if hasattr(validated_item, 'url') and validated_item.url else None,
                    #     date=validated_item.date if hasattr(validated_item, 'date') else None,
                    #     metadata={
                    #         "title": getattr(validated_item, 'title', 'Unknown'),
                    #         "board": getattr(validated_item, 'board', source_name),
                    #         "item_number": getattr(validated_item, 'item_number', None),
                    #         "address": getattr(validated_item, 'parcel_address', None),
                    #         "council_district": getattr(validated_item, 'council_district', None)
                    #     }
                    # )

                validated_items.append(validated_item.dict())

            # Write validated items to storage
            if validated_items:
                write_to_firestore(validated_items, source_id)

            logger.info(f"✅ {source_name}: {len(validated_items)} items processed, {flagged_count} flagged")
            total_processed += len(validated_items)
            total_flagged += flagged_count

    logger.info(f"🏁 Observatory run complete: {total_processed} items processed, {total_flagged} flagged")

    # Send success summary to Slack
    alerter = get_alerter()
    if total_processed > 0:
        # Success notification with summary
        summary_msg = f"Municipal Observatory completed successfully: {total_processed} items processed"
        if total_flagged > 0:
            summary_msg += f", {total_flagged} flagged for attention"

        alerter.send_alert(
            level=AlertLevel.INFO,
            alert_type=AlertType.SYSTEM_HEALTH,
            message=summary_msg,
            metadata={
                "total_processed": total_processed,
                "total_flagged": total_flagged,
                "run_duration": f"{time.time() - start_time:.1f}s",
                "sources_processed": len([s for s in sources if s.get('enabled', False)])
            }
        )
    else:
        # Warning if no data was processed
        alerter.send_alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.SYSTEM_HEALTH,
            message="Municipal Observatory completed but no data was processed",
            metadata={"sources_checked": len([s for s in sources if s.get('enabled', False)])}
        )

    return {
        "total_processed": total_processed,
        "total_flagged": total_flagged,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    run_observatory()
