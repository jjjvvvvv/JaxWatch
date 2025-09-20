#!/usr/bin/env python3

import json
from geocode_nominatim import geocode_address_nominatim

def main():
    # Load projects
    print('Loading projects...')
    with open('all-projects.json', 'r') as f:
        projects = json.load(f)

    print(f'Processing {len(projects)} projects...')
    geocoded_count = 0
    already_done = 0
    no_address = 0
    failed_count = 0

    for i, project in enumerate(projects):
        project_id = project.get('project_id', 'Unknown')

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

        print(f'[{i+1}/{len(projects)}] {project_id}: {location}')
        lat, lng = geocode_address_nominatim(location)

        if lat and lng:
            project['latitude'] = lat
            project['longitude'] = lng
            geocoded_count += 1
            print(f'  ✅ ({lat:.6f}, {lng:.6f})')
        else:
            project['latitude'] = None
            project['longitude'] = None
            failed_count += 1
            print(f'  ❌ Failed')

        # Save progress every 20 projects to avoid losing work
        if (geocoded_count + failed_count) % 20 == 0:
            print(f'💾 Saving progress... (Total: {geocoded_count} geocoded)')
            with open('all-projects.json', 'w') as f:
                json.dump(projects, f, indent=2)

    # Final save
    with open('all-projects.json', 'w') as f:
        json.dump(projects, f, indent=2)

    print(f'\n🎉 GEOCODING COMPLETE!')
    print(f'  ✅ Successfully geocoded: {geocoded_count}')
    print(f'  ⏭️  Already had coordinates: {already_done}')
    print(f'  ⚠️  No valid address: {no_address}')
    print(f'  ❌ Failed to geocode: {failed_count}')
    print(f'  📊 Total with coordinates: {already_done + geocoded_count}')

if __name__ == "__main__":
    main()