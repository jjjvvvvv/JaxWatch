#!/usr/bin/env python3

import json
import glob
from pathlib import Path
from datetime import datetime
from extract_projects_robust import ProjectExtractor

def process_all_pdfs():
    """Process all PDF files and create aggregated data"""

    # Find all PDF files
    pdf_files = list(Path('.').glob('*.pdf'))

    if not pdf_files:
        print("📭 No PDF files found")
        return

    print(f"🔄 Processing {len(pdf_files)} PDF files")

    all_projects = []
    all_meetings = []
    processing_results = []

    for pdf_file in pdf_files:
        print(f"\n📄 Processing: {pdf_file}")

        try:
            extractor = ProjectExtractor()
            result = extractor.extract_projects_from_pdf(str(pdf_file))

            if result and result['projects']:
                projects = result['projects']
                meeting_info = result['meeting_info']

                # Update source_pdf to point to actual PDF URL if available
                pdf_name = pdf_file.stem
                if 'pc-agenda-' in pdf_name:
                    date_part = pdf_name.replace('pc-agenda-', '')
                    pdf_url = f"https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/{date_part}-agenda.pdf.aspx?lang=en-US"

                    # Update all projects with the correct source URL
                    for project in projects:
                        project['source_pdf'] = pdf_url

                all_projects.extend(projects)

                # Add meeting summary
                meeting_summary = {
                    'meeting_date': meeting_info.get('meeting_date', ''),
                    'project_count': len(projects),
                    'source_file': str(pdf_file),
                    'source_pdf': projects[0].get('source_pdf', '') if projects else ''
                }
                all_meetings.append(meeting_summary)

                processing_results.append({
                    'file': str(pdf_file),
                    'meeting_date': meeting_info.get('meeting_date', 'Unknown'),
                    'project_count': len(projects),
                    'status': 'success'
                })

                print(f"✅ Extracted {len(projects)} projects from {pdf_file}")

            else:
                print(f"❌ Failed to extract data from {pdf_file}")
                processing_results.append({
                    'file': str(pdf_file),
                    'status': 'failed'
                })

        except Exception as e:
            print(f"❌ Error processing {pdf_file}: {e}")
            processing_results.append({
                'file': str(pdf_file),
                'status': 'error',
                'error': str(e)
            })

    if not all_projects:
        print("❌ No projects extracted from any PDFs")
        return

    # Sort projects by meeting date (newest first) and item number
    all_projects.sort(key=lambda p: (
        p.get('meeting_date', ''),
        int(p.get('item_number', '0'))
    ), reverse=True)

    # Sort meetings by date (newest first)
    all_meetings.sort(key=lambda m: m.get('meeting_date', ''), reverse=True)

    # Generate statistics
    from collections import defaultdict
    project_types = defaultdict(int)
    council_districts = defaultdict(int)
    status_counts = defaultdict(int)

    for project in all_projects:
        project_types[project.get('project_type', 'Unknown')] += 1
        council_districts[project.get('council_district', 'Unknown')] += 1

        rec = project.get('staff_recommendation', '')
        if 'APPROVE' in rec.upper():
            status_counts['Approved'] += 1
        elif 'DEFER' in rec.upper():
            status_counts['Deferred'] += 1
        elif 'DENY' in rec.upper():
            status_counts['Denied'] += 1
        else:
            status_counts['Other'] += 1

    # Create aggregated data
    website_data = {
        'last_updated': datetime.now().isoformat(),
        'summary': {
            'total_projects': len(all_projects),
            'total_meetings': len(all_meetings),
            'date_range': {
                'earliest': all_meetings[-1].get('meeting_date', '') if all_meetings else '',
                'latest': all_meetings[0].get('meeting_date', '') if all_meetings else ''
            },
            'project_types': dict(project_types),
            'council_districts': dict(council_districts),
            'status_counts': dict(status_counts)
        },
        'meetings': all_meetings,
        'projects': all_projects,
        'processing_info': {
            'processed_files': len(pdf_files),
            'successful_extractions': len([r for r in processing_results if r['status'] == 'success']),
            'processing_results': processing_results
        }
    }

    # Save aggregated data for website
    output_file = Path('all-projects.json')
    with open(output_file, 'w') as f:
        json.dump(website_data, f, indent=2)

    print(f"\n💾 Aggregated data saved to: {output_file}")
    print(f"\n📊 PROCESSING SUMMARY:")
    print(f"  Total Projects: {len(all_projects)}")
    print(f"  Total Meetings: {len(all_meetings)}")
    print(f"  Date Range: {website_data['summary']['date_range']['earliest']} to {website_data['summary']['date_range']['latest']}")
    print(f"  Successful Extractions: {len([r for r in processing_results if r['status'] == 'success'])}/{len(pdf_files)}")

    # Show meeting breakdown
    print(f"\n📅 MEETINGS PROCESSED:")
    for meeting in all_meetings:
        print(f"  • {meeting['meeting_date']}: {meeting['project_count']} projects")

    return website_data

if __name__ == "__main__":
    result = process_all_pdfs()