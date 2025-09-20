#!/usr/bin/env python3

import json
import requests
import time
import sys

def geocode_address(address):
    """Geocode a single address using Nominatim"""
    if not address or address.strip() == "" or address.startswith("0 "):
        return None, None

    full_address = f"{address}, Jacksonville, FL, USA"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': full_address,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1,
        'bounded': 1,
        'viewbox': '-81.9,30.1,-81.4,30.5',
    }

    headers = {'User-Agent': 'JacksonvillePlanningTracker/1.0'}

    try:
        time.sleep(1.1)  # Rate limiting
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data and len(data) > 0:
            result = data[0]
            lat = float(result['lat'])
            lng = float(result['lon'])

            # Validate coordinates are in Jacksonville area
            if 30.1 <= lat <= 30.5 and -81.9 <= lng <= -81.4:
                display_name = result.get('display_name', '').lower()
                if 'jacksonville' in display_name or 'duval' in display_name:
                    return lat, lng
        return None, None
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
        return None, None

def main():
    print("🚀 Starting comprehensive geocoding...")

    # Load projects
    with open('all-projects.json', 'r') as f:
        projects = json.load(f)

    geocoded = 0
    already_done = 0
    no_address = 0
    failed = 0

    for i, project in enumerate(projects):
        pid = project.get('project_id', 'Unknown')

        # Skip if already has coordinates
        if project.get('latitude') and project.get('longitude'):
            already_done += 1
            continue

        location = project.get('location', '').strip()
        if not location or location == 'Location not specified' or location.startswith('0 '):
            project['latitude'] = None
            project['longitude'] = None
            no_address += 1
            continue

        print(f"[{i+1}/{len(projects)}] {pid}: {location}")
        lat, lng = geocode_address(location)

        if lat and lng:
            project['latitude'] = lat
            project['longitude'] = lng
            geocoded += 1
            print(f"  ✅ Success: ({lat:.6f}, {lng:.6f})")
        else:
            project['latitude'] = None
            project['longitude'] = None
            failed += 1
            print(f"  ❌ Failed")

        # Save every 10 projects
        if (geocoded + failed) % 10 == 0:
            print(f"💾 Saving... (geocoded: {geocoded}, failed: {failed})")
            with open('all-projects.json', 'w') as f:
                json.dump(projects, f, indent=2)

    # Final save
    with open('all-projects.json', 'w') as f:
        json.dump(projects, f, indent=2)

    print(f"\n🎉 COMPLETE!")
    print(f"✅ Geocoded: {geocoded}")
    print(f"⏭️  Already done: {already_done}")
    print(f"⚠️  No address: {no_address}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total with coords: {already_done + geocoded}")

if __name__ == "__main__":
    main()