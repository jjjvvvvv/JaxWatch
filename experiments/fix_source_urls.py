#!/usr/bin/env python3

import json
from pathlib import Path

def fix_source_urls():
    """Fix the source PDF URLs to point to the correct Jacksonville URLs"""

    data_file = Path('all-projects.json')

    with open(data_file, 'r') as f:
        data = json.load(f)

    # URL mappings for the files we downloaded
    url_mappings = {
        'pc-results-05-22-25.pdf': 'https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/05-22-25-Results-Agenda.pdf.aspx?lang=en-US',
        'pc-results-06-05-25.pdf': 'https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/06-05-25-Results-Agenda.pdf.aspx?lang=en-US',
        'sample-pc-agenda-10-03-24.pdf': 'https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/10-03-24-agenda.pdf.aspx?lang=en-US'
    }

    # Update project source PDFs
    updated_count = 0
    for project in data['projects']:
        source_pdf = project.get('source_pdf', '')

        # Check if this is one of our local files that needs URL fixing
        for local_file, proper_url in url_mappings.items():
            if local_file in source_pdf:
                project['source_pdf'] = proper_url
                updated_count += 1
                break

    # Update meeting source PDFs
    for meeting in data['meetings']:
        source_pdf = meeting.get('source_pdf', '')

        for local_file, proper_url in url_mappings.items():
            if local_file in source_pdf:
                meeting['source_pdf'] = proper_url
                break

    # Save updated data
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ Updated {updated_count} project source URLs")
    print(f"📊 Data now contains:")
    print(f"   • {data['summary']['total_projects']} total projects")
    print(f"   • {data['summary']['total_meetings']} meetings")
    print(f"   • Date range: {data['summary']['date_range']['earliest']} to {data['summary']['date_range']['latest']}")

    # Show meeting breakdown
    print(f"\n📅 MEETINGS:")
    for meeting in data['meetings']:
        print(f"   • {meeting['meeting_date']}: {meeting['project_count']} projects")

if __name__ == "__main__":
    fix_source_urls()