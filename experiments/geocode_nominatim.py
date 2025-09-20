#!/usr/bin/env python3

import json
import requests
import time
import os
from pathlib import Path

def geocode_address_nominatim(address, city="Jacksonville", state="FL"):
    """
    Geocode an address using the free Nominatim (OpenStreetMap) API
    No API key required, unlimited usage for reasonable use
    """
    if not address or address.strip() == "" or address.startswith("0 "):
        return None, None

    # Clean up the address
    full_address = f"{address}, {city}, {state}, USA"

    # Use Nominatim API (OpenStreetMap)
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': full_address,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1,
        'bounded': 1,  # Restrict to bounding box
        'viewbox': '-81.9,30.1,-81.4,30.5',  # Jacksonville bounding box (west,south,east,north)
    }

    headers = {
        'User-Agent': 'JacksonvillePlanningTracker/1.0 (civic transparency project)'
    }

    try:
        # Rate limiting - Nominatim asks for max 1 request per second
        time.sleep(1.1)

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data and len(data) > 0:
            result = data[0]
            lat = float(result['lat'])
            lng = float(result['lon'])

            # Validate coordinates are in Jacksonville area (rough bounds)
            if 30.1 <= lat <= 30.5 and -81.9 <= lng <= -81.4:
                # Check if this is actually in Jacksonville (not just Duval County)
                display_name = result.get('display_name', '').lower()
                if 'jacksonville' in display_name or 'duval' in display_name:
                    print(f"✅ Geocoded: {address} -> ({lat:.6f}, {lng:.6f})")
                    return lat, lng
                else:
                    print(f"⚠️  Address found but not in Jacksonville: {address} -> {result.get('display_name', '')}")
                    return None, None
            else:
                print(f"⚠️  Coordinates outside Jacksonville area: {address} -> ({lat:.6f}, {lng:.6f})")
                return None, None
        else:
            print(f"❌ No results for: {address}")
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error geocoding {address}: {str(e)}")
        return None, None
    except (ValueError, KeyError) as e:
        print(f"❌ Data error geocoding {address}: {str(e)}")
        return None, None
    except Exception as e:
        print(f"❌ Unexpected error geocoding {address}: {str(e)}")
        return None, None

def test_sample_addresses():
    """
    Test geocoding on known Jacksonville addresses first
    """
    print("🧪 Testing geocoding on known Jacksonville addresses...")

    test_addresses = [
        "930 University Boulevard North",  # From our data
        "12800 Beach Boulevard",           # From our data
        "220 E Bay Street",                # City Hall
        "117 W Duval Street",              # Times-Union Center
        "1 Stadium Place",                 # TIAA Bank Field
    ]

    for addr in test_addresses:
        lat, lng = geocode_address_nominatim(addr)
        if lat and lng:
            print(f"   ✅ {addr}: ({lat:.6f}, {lng:.6f})")
        else:
            print(f"   ❌ {addr}: Failed to geocode")
        time.sleep(1.2)  # Extra delay for testing

def geocode_all_projects():
    """
    Add latitude and longitude coordinates to all projects using Nominatim
    """
    # Load existing project data
    projects_file = Path('all-projects.json')
    if not projects_file.exists():
        print("❌ all-projects.json not found")
        return

    print("📂 Loading project data...")
    with open(projects_file, 'r') as f:
        projects = json.load(f)

    print(f"🚀 Starting Nominatim geocoding for {len(projects)} projects...")
    print("🔄 Using OpenStreetMap Nominatim API (unlimited, no API key required)")
    print("⏳ Starting processing loop...")

    geocoded_count = 0
    skipped_count = 0
    error_count = 0

    for i, project in enumerate(projects):
        print(f"\n[{i+1}/{len(projects)}] Processing: {project.get('project_id', 'Unknown')}")

        # Skip if already has coordinates
        if project.get('latitude') and project.get('longitude'):
            print(f"   Already has coordinates, skipping")
            skipped_count += 1
            continue

        location = project.get('location', '').strip()
        if not location or location == 'Location not specified':
            print(f"   No location to geocode")
            project['latitude'] = None
            project['longitude'] = None
            skipped_count += 1
            continue

        # Geocode the address using Nominatim
        lat, lng = geocode_address_nominatim(location)

        if lat and lng:
            project['latitude'] = lat
            project['longitude'] = lng
            geocoded_count += 1
        else:
            project['latitude'] = None
            project['longitude'] = None
            error_count += 1

        # Save progress every 10 projects
        if (i + 1) % 10 == 0:
            print(f"💾 Saving progress... ({geocoded_count} geocoded, {error_count} failed so far)")
            with open(projects_file, 'w') as f:
                json.dump(projects, f, indent=2)

        # Rate limiting - Nominatim requests max 1 request per second
        time.sleep(1.1)

    # Save final results
    with open(projects_file, 'w') as f:
        json.dump(projects, f, indent=2)

    print(f"\n📊 NOMINATIM GEOCODING SUMMARY")
    print(f"   ✅ Successfully geocoded: {geocoded_count}")
    print(f"   ⏭️  Skipped (already had coords or no address): {skipped_count}")
    print(f"   ❌ Failed to geocode: {error_count}")
    print(f"   📄 Updated file: {projects_file}")
    if len(projects) - skipped_count > 0:
        print(f"   🎯 Success rate: {geocoded_count/(len(projects)-skipped_count)*100:.1f}% of processable addresses")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_sample_addresses()
    else:
        geocode_all_projects()