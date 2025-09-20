#!/usr/bin/env python3
"""
Aggregate latest data from each source into a single file for frontend consumption
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import glob


def get_latest_file_for_source(source_id: str, data_dir: Path) -> str:
    """Get the latest file for a given source"""
    pattern = str(data_dir / f"{source_id}_*.json")
    files = glob.glob(pattern)
    if not files:
        return None
    # Sort by filename (which includes timestamp) and get the latest
    return sorted(files)[-1]


def aggregate_municipal_data(data_dir: Path = None, output_file: Path = None):
    """Aggregate the latest data from each municipal source"""
    if data_dir is None:
        data_dir = Path(__file__).parent.parent.parent / "data" / "outputs"

    if output_file is None:
        output_file = Path(__file__).parent.parent.parent / "frontend" / "municipal-data.json"

    # Define source IDs from sources.yaml
    source_ids = [
        "planning_commission",
        "infrastructure_committee",
        "private_development",
        "public_projects",
        "city_council",
        "ddrb"
    ]

    aggregated_items = []
    source_summary = {}

    for source_id in source_ids:
        latest_file = get_latest_file_for_source(source_id, data_dir)
        if not latest_file:
            print(f"⚠️ No data found for source: {source_id}")
            continue

        try:
            with open(latest_file, 'r') as f:
                source_data = json.load(f)

            items = source_data.get("items", [])
            aggregated_items.extend(items)

            source_summary[source_id] = {
                "total_items": len(items),
                "timestamp": source_data.get("timestamp"),
                "file": os.path.basename(latest_file)
            }

            print(f"✅ {source_id}: {len(items)} items from {os.path.basename(latest_file)}")

        except Exception as e:
            print(f"❌ Error loading {latest_file}: {e}")

    # Sort by date (newest first)
    aggregated_items.sort(key=lambda x: x.get("date", "1900-01-01"), reverse=True)

    # Create aggregated output
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total_items": len(aggregated_items),
        "sources": source_summary,
        "projects": aggregated_items,  # Use 'projects' key for frontend compatibility
        "summary": {
            "total_projects": len(aggregated_items),
            "flagged_count": sum(1 for item in aggregated_items if item.get("flagged", False)),
            "boards": list(set(item.get("board") for item in aggregated_items if item.get("board"))),
            "date_range": {
                "earliest": min((item.get("date", "9999-12-31") for item in aggregated_items if item.get("date")), default="N/A"),
                "latest": max((item.get("date", "1900-01-01") for item in aggregated_items if item.get("date")), default="N/A")
            }
        }
    }

    # Write aggregated data
    os.makedirs(output_file.parent, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n📊 AGGREGATION COMPLETE")
    print(f"   📄 Output file: {output_file}")
    print(f"   📋 Total items: {len(aggregated_items)}")
    print(f"   🚩 Flagged items: {output_data['summary']['flagged_count']}")
    print(f"   🏛️ Boards represented: {len(output_data['summary']['boards'])}")

    return output_data


if __name__ == "__main__":
    aggregate_municipal_data()