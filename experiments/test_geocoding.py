#!/usr/bin/env python3

import json
import requests
import time
from pathlib import Path

def geocode_address_nominatim(address, city="Jacksonville", state="FL"):
    """
    Geocode an address using the free Nominatim (OpenStreetMap) API
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

def test_first_five_projects():
    """
    Test geocoding on just the first 5 projects
    """
    # Load existing project data
    projects_file = Path('all-projects.json')
    if not projects_file.exists():
        print("❌ all-projects.json not found")
        return

    with open(projects_file, 'r') as f:
        projects = json.load(f)

    print(f"🧪 Testing geocoding on first 5 of {len(projects)} projects...")

    for i, project in enumerate(projects[:5]):
        print(f"\n[{i+1}/5] Testing: {project.get('project_id', 'Unknown')}")

        location = project.get('location', '').strip()
        if not location or location == 'Location not specified':
            print(f"   No location to geocode: '{location}'")
            continue

        print(f"   Address: {location}")
        lat, lng = geocode_address_nominatim(location)

        if lat and lng:
            print(f"   ✅ Success: ({lat:.6f}, {lng:.6f})")
        else:
            print(f"   ❌ Failed to geocode")

if __name__ == "__main__":
    test_first_five_projects()