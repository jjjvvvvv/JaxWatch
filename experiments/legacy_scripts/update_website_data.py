#!/usr/bin/env python3

import json
import glob
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def update_website_data():
    """Aggregate all extracted project data into files for the website"""

    # Find all extracted JSON files from both new and legacy locations
    extracted_files = []
    extracted_files += list(Path('data/extracted').glob('*.json'))
    # Legacy/top-level extracted files
    extracted_files += list(Path('.').glob('extracted-*.json'))
    extracted_files += list(Path('.').glob('extracted-pc-*.json'))
    extracted_files += list(Path('.').glob('extracted-projects-*.json'))

    if not extracted_files:
        print("📭 No extracted data files found")
        return

    print(f"📊 Aggregating data from {len(extracted_files)} files")

    all_projects = []
    all_meetings = []
    stats = defaultdict(int)

    for json_file in extracted_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            # Support both dict with 'projects' and raw list formats
            if isinstance(data, dict):
                projects = data.get('projects', [])
                meeting_info = data.get('meeting_info', {})
            elif isinstance(data, list):
                projects = data
                meeting_info = {}
            else:
                projects = []
                meeting_info = {}

            if projects:
                all_projects.extend(projects)
                stats['total_files'] += 1
                stats['total_projects'] += len(projects)

                # Add meeting info
                if meeting_info:
                    # Ensure we minimally annotate the meeting entry
                    meeting_info = dict(meeting_info)
                    meeting_info['project_count'] = len(projects)
                    meeting_info['source_file'] = str(json_file)
                    all_meetings.append(meeting_info)
                else:
                    # Attempt to derive minimal meeting entry from first project
                    first = projects[0]
                    derived = {
                        'meeting_date': first.get('meeting_date', ''),
                        'source_file': str(json_file),
                        'project_count': len(projects)
                    }
                    all_meetings.append(derived)

                print(f"  ✅ {json_file.name}: {len(projects)} projects")

        except Exception as e:
            print(f"  ❌ Error reading {json_file}: {e}")
            continue

    if not all_projects:
        print("❌ No projects found in any files")
        return

    # Sort projects by meeting date (newest first) and then by item number
    all_projects.sort(key=lambda p: (
        p.get('meeting_date', ''),
        int(p.get('item_number', '0'))
    ), reverse=True)

    # Sort meetings by date (newest first)
    all_meetings.sort(key=lambda m: m.get('meeting_date', ''), reverse=True)

    # Generate statistics
    project_types = defaultdict(int)
    council_districts = defaultdict(int)
    status_counts = defaultdict(int)

    for project in all_projects:
        project_types[project.get('project_type', 'Unknown')] += 1
        council_districts[project.get('council_district', 'Unknown')] += 1

        # Categorize status
        rec = project.get('staff_recommendation', '')
        if 'APPROVE' in rec.upper():
            status_counts['Approved'] += 1
        elif 'DEFER' in rec.upper():
            status_counts['Deferred'] += 1
        elif 'DENY' in rec.upper():
            status_counts['Denied'] += 1
        else:
            status_counts['Other'] += 1

    # Create aggregated data structure
    website_data = {
        'last_updated': datetime.now().isoformat(),
        'summary': {
            'total_projects': len(all_projects),
            'total_meetings': len(all_meetings),
            'project_types': dict(project_types),
            'council_districts': dict(council_districts),
            'status_counts': dict(status_counts)
        },
        'meetings': all_meetings,
        'projects': all_projects
    }

    # Save main data file for the website
    main_data_file = Path('data/all-projects.json')
    main_data_file.parent.mkdir(parents=True, exist_ok=True)

    with open(main_data_file, 'w') as f:
        json.dump(website_data, f, indent=2)

    print(f"💾 Main data file saved: {main_data_file}")

    # Also save a copy in the root directory for the website
    website_file = Path('all-projects.json')
    with open(website_file, 'w') as f:
        json.dump(website_data, f, indent=2)

    print(f"💾 Website data file saved: {website_file}")

    # Create a lightweight summary file
    summary_data = {
        'last_updated': website_data['last_updated'],
        'summary': website_data['summary'],
        'recent_meetings': all_meetings[:5],  # Last 5 meetings
        'recent_projects': all_projects[:20]   # Last 20 projects
    }

    summary_file = Path('summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary_data, f, indent=2)

    print(f"💾 Summary file saved: {summary_file}")

    # Update the app.js file to use the new data source
    update_app_js_data_source()

    print(f"\n📊 AGGREGATION SUMMARY:")
    print(f"  Total Projects: {len(all_projects)}")
    print(f"  Total Meetings: {len(all_meetings)}")
    print(f"  Project Types: {len(project_types)}")
    print(f"  Council Districts: {len(council_districts)}")

    return website_data

def update_app_js_data_source():
    """Update app.js to load from the new aggregated data file"""

    app_js_file = Path('app.js')
    if not app_js_file.exists():
        print("⚠️  app.js not found - skipping data source update")
        return

    try:
        with open(app_js_file, 'r') as f:
            content = f.read()

        # Replace the JSON file reference
        old_pattern = "extracted-projects-10-03-24.json"
        new_pattern = "all-projects.json"

        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern)

            with open(app_js_file, 'w') as f:
                f.write(content)

            print(f"✅ Updated app.js data source to use {new_pattern}")
        else:
            print("⚠️  Could not find data source reference in app.js")

    except Exception as e:
        print(f"❌ Error updating app.js: {e}")

if __name__ == "__main__":
    result = update_website_data()

    if result:
        print(f"\n🎉 Website data updated successfully!")
        print(f"📈 {result['summary']['total_projects']} projects across {result['summary']['total_meetings']} meetings")
    else:
        print("\n❌ Failed to update website data")
