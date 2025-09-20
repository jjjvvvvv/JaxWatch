#!/usr/bin/env python3

import json
import requests
import time
import sys
from pathlib import Path


def geocode_address(address, city="Jacksonville", state="FL"):
    """
    Geocode an address using the free geocode.maps.co API.
    Returns (lat, lon) or (None, None) if not found/invalid.
    """
    if not address or address.strip() == "":
        return None, None

    full_address = f"{address}, {city}, {state}"

    url = "https://geocode.maps.co/search"
    params = {
        "q": full_address,
        "limit": 1,
        "format": "json",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data:
            result = data[0]
            lat = float(result.get("lat", 0))
            lng = float(result.get("lon", 0))

            # Rough Jacksonville bounds
            if 29.5 <= lat <= 31.0 and -82.5 <= lng <= -80.5:
                print(f"✅ Geocoded: {address} -> ({lat:.6f}, {lng:.6f})")
                return lat, lng
            else:
                print(
                    f"⚠️  Coordinates outside Jacksonville area: {address} -> ({lat:.6f}, {lng:.6f})"
                )
                return None, None
        else:
            print(f"❌ No results for: {address}")
            return None, None

    except Exception as e:
        print(f"❌ Error geocoding {address}: {str(e)}")
        return None, None


def _geocode_project_list(projects):
    """Mutates a list of project dicts by setting latitude/longitude where missing."""
    geocoded_count = 0
    skipped_count = 0
    error_count = 0

    for i, project in enumerate(projects):
        proj_id = project.get("project_id") or project.get("slug") or f"{i+1}"
        print(f"\n[{i+1}/{len(projects)}] Processing: {proj_id}")

        # Skip if already has coordinates
        if project.get("latitude") and project.get("longitude"):
            print("   Already has coordinates, skipping")
            skipped_count += 1
            continue

        location = (project.get("location") or "").strip()
        if not location or location == "Location not specified":
            print("   No location to geocode")
            project["latitude"], project["longitude"] = None, None
            skipped_count += 1
            continue

        lat, lng = geocode_address(location)
        if lat and lng:
            project["latitude"] = lat
            project["longitude"] = lng
            geocoded_count += 1
        else:
            project["latitude"], project["longitude"] = None, None
            error_count += 1

        # Respect free API
        time.sleep(1)

    return geocoded_count, skipped_count, error_count


def geocode_file(input_path: Path):
    """
    Geocode projects in the given JSON file.
    Supports two shapes:
      1) List[project]
      2) { "projects": List[project], ... }
    Writes results back to the same file, preserving shape.
    """
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return 1

    with open(input_path, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        projects = data
        geocoded_count, skipped_count, error_count = _geocode_project_list(projects)
        # Write back list
        with open(input_path, "w") as f:
            json.dump(projects, f, indent=2)
    elif isinstance(data, dict) and isinstance(data.get("projects"), list):
        projects = data["projects"]
        geocoded_count, skipped_count, error_count = _geocode_project_list(projects)
        data["projects"] = projects
        with open(input_path, "w") as f:
            json.dump(data, f, indent=2)
    else:
        print("❌ Unsupported JSON format for geocoding")
        return 1

    print("\n📊 GEOCODING SUMMARY")
    print(f"   ✅ Successfully geocoded: {geocoded_count}")
    print(f"   ⏭️  Skipped (already had coords or no address): {skipped_count}")
    print(f"   ❌ Failed to geocode: {error_count}")
    print(f"   📄 Updated file: {input_path}")
    return 0


def geocode_all_projects_default():
    """Fallback to geocoding all projects in all-projects.json (legacy behavior)."""
    default_file = Path("all-projects.json")
    if not default_file.exists():
        print("❌ all-projects.json not found")
        return 1
    return geocode_file(default_file)


if __name__ == "__main__":
    # Optional CLI arg: input JSON path
    if len(sys.argv) > 1:
        sys.exit(geocode_file(Path(sys.argv[1])))
    else:
        sys.exit(geocode_all_projects_default())
