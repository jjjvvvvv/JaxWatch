#!/usr/bin/env python3

import json
import requests
import time
from pathlib import Path

def geocode_address_nominatim(address, city="Jacksonville", state="FL"):
    """Geocode an address using Nominatim API"""
    if not address or address.strip() == "" or address.startswith("0 "):
        return None, None

    full_address = f"{address}, {city}, {state}, USA"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': full_address,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1,
        'bounded': 1,
        'viewbox': '-81.9,30.1,-81.4,30.5',
    }

    headers = {'User-Agent': 'JacksonvillePlanningTracker/1.0 (civic transparency project)'}

    try:
        time.sleep(1.1)  # Rate limiting
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data and len(data) > 0:
            result = data[0]
            lat = float(result['lat'])
            lng = float(result['lon'])

            if 30.1 <= lat <= 30.5 and -81.9 <= lng <= -81.4:
                display_name = result.get('display_name', '').lower()
                if 'jacksonville' in display_name or 'duval' in display_name:
                    return lat, lng
        return None, None
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
        return None, None

def batch_geocode_projects(batch_size=10, start_index=0):
    """Process projects in batches"""
    # Load projects
    with open('all-projects.json', 'r') as f:
        projects = json.load(f)

    print(f"🚀 Processing {len(projects)} projects in batches of {batch_size}")
    print(f"▶️  Starting from index {start_index}")

    geocoded_count = 0

    for i in range(start_index, len(projects), batch_size):
        batch_end = min(i + batch_size, len(projects))
        print(f"\n📦 Processing batch {i//batch_size + 1}: projects {i+1}-{batch_end}")

        for j in range(i, batch_end):
            project = projects[j]
            print(f"  [{j+1}] {project.get('project_id', 'Unknown')}")

            # Skip if already has coordinates
            if project.get('latitude') and project.get('longitude'):
                print(f"    ⏭️  Already geocoded")
                continue

            location = project.get('location', '').strip()
            if not location or location == 'Location not specified':
                print(f"    ⚠️  No location")
                project['latitude'] = None
                project['longitude'] = None
                continue

            # Geocode
            lat, lng = geocode_address_nominatim(location)
            if lat and lng:
                project['latitude'] = lat
                project['longitude'] = lng
                geocoded_count += 1
                print(f"    ✅ ({lat:.6f}, {lng:.6f})")
            else:
                project['latitude'] = None
                project['longitude'] = None
                print(f"    ❌ Failed")

        # Save progress after each batch
        print(f"💾 Saving progress... ({geocoded_count} total geocoded)")
        with open('all-projects.json', 'w') as f:
            json.dump(projects, f, indent=2)

        print(f"✅ Batch {i//batch_size + 1} complete. Continuing...")

    print(f"\n🎉 Geocoding complete! Total geocoded: {geocoded_count}")

if __name__ == "__main__":
    batch_geocode_projects(batch_size=5, start_index=0)