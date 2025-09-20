#!/usr/bin/env python3

import pdfplumber
import re
import json
from datetime import datetime

def extract_projects_from_pdf(pdf_path):
    """Extract structured project data from Jacksonville Planning Commission agenda PDF"""

    projects = []
    meeting_info = {}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = ""

            # Extract text from all pages
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text += page_text + "\n"

            # Extract meeting date from header
            date_match = re.search(r'(\w+,\s+\w+\s+\d+,\s+\d{4})', all_text)
            if date_match:
                meeting_info['meeting_date'] = date_match.group(1)
                meeting_info['source_pdf'] = pdf_path

            # Split text into sections and find project entries
            # Look for patterns like "Ex-Parte 1." or just "1." followed by project details

            # Pattern for project entries - matches various formats
            project_pattern = r'(?:Ex-Parte\s+)?(\d+)\.\s*([A-Z0-9-]+(?:\s*\([^)]+\))?)\s*\n\s*Council District-(\d+)[^\n]*Planning District-(\d+)[^\n]*([^\n]+?)Signs Posted:\s*(Yes|No)\s*\n\s*Request:\s*([^\n]+)\s*\n\s*Owner\(s\):\s*([^\n]+)\s*Agent:\s*([^\n]+)\s*\n\s*Staff Recommendation:\s*([^\n]+)'

            matches = re.finditer(project_pattern, all_text, re.MULTILINE | re.DOTALL)

            for match in matches:
                item_num = match.group(1)
                project_id = match.group(2).strip()
                council_district = match.group(3)
                planning_district = match.group(4)
                location = match.group(5).strip()
                signs_posted = match.group(6)
                request = match.group(7).strip()
                owners = match.group(8).strip()
                agent = match.group(9).strip()
                staff_recommendation = match.group(10).strip()

                # Clean up location (remove extra whitespace and signs posted info)
                location = re.sub(r'\s+', ' ', location)
                location = re.sub(r'Signs Posted:.*$', '', location).strip()

                # Determine project type from project_id
                project_type = "Unknown"
                if project_id.startswith('E-'):
                    project_type = "Exception"
                elif project_id.startswith('V-'):
                    project_type = "Variance"
                elif project_id.startswith('WLD-'):
                    project_type = "Waiver Liquor Distance"
                elif project_id.startswith('MM-'):
                    project_type = "Minor Modification"
                elif project_id.startswith('AD-'):
                    project_type = "Administrative Deviation"
                elif project_id.startswith('PUD') or 'PUD' in project_id:
                    project_type = "Planned Unit Development"
                elif project_id.startswith('2024-') or re.match(r'\d{4}-\d+', project_id):
                    if 'PUD' in request.upper():
                        project_type = "Planned Unit Development"
                    else:
                        project_type = "Land Use/Zoning"

                # Create slug from project_id and location
                slug_base = f"{project_id.lower().replace(' ', '-')}"
                if location:
                    location_slug = re.sub(r'[^\w\s-]', '', location.lower())
                    location_slug = re.sub(r'\s+', '-', location_slug)[:30]
                    slug = f"{slug_base}-{location_slug}"
                else:
                    slug = slug_base

                slug = re.sub(r'-+', '-', slug).strip('-')

                project = {
                    "slug": slug,
                    "project_id": project_id,
                    "item_number": item_num,
                    "meeting_date": meeting_info.get('meeting_date', ''),
                    "title": request[:100] + "..." if len(request) > 100 else request,
                    "location": location,
                    "project_type": project_type,
                    "request": request,
                    "status": f"Planning Commission - {staff_recommendation}",
                    "council_district": council_district,
                    "planning_district": planning_district,
                    "owners": owners,
                    "agent": agent,
                    "staff_recommendation": staff_recommendation,
                    "signs_posted": signs_posted == "Yes",
                    "source_pdf": pdf_path,
                    "extracted_at": datetime.now().isoformat(),
                    "tags": _generate_tags(project_type, request, location)
                }

                projects.append(project)

            print(f"Extracted {len(projects)} projects from PDF")
            return {
                "meeting_info": meeting_info,
                "projects": projects
            }

    except Exception as e:
        print(f"Error extracting projects: {e}")
        return None

def _generate_tags(project_type, request, location):
    """Generate relevant tags for a project"""
    tags = []

    # Add project type tag
    if project_type != "Unknown":
        tags.append(project_type.lower().replace(" ", "_"))

    # Add tags based on request content
    request_lower = request.lower()
    if 'townhome' in request_lower or 'townhouse' in request_lower:
        tags.append('townhomes')
    if 'residential' in request_lower or 'housing' in request_lower:
        tags.append('residential')
    if 'commercial' in request_lower:
        tags.append('commercial')
    if 'retail' in request_lower:
        tags.append('retail')
    if 'mixed' in request_lower:
        tags.append('mixed_use')
    if 'density' in request_lower:
        tags.append('density')
    if 'setback' in request_lower:
        tags.append('setbacks')
    if 'parking' in request_lower:
        tags.append('parking')
    if 'alcohol' in request_lower or 'liquor' in request_lower:
        tags.append('alcohol')

    # Add location-based tags
    if location:
        location_lower = location.lower()
        if 'boulevard' in location_lower or 'blvd' in location_lower:
            tags.append('boulevard')
        if 'downtown' in location_lower or 'urban' in location_lower:
            tags.append('urban')

    return tags

if __name__ == "__main__":
    # Test with our sample PDF
    pdf_file = "sample-pc-agenda-10-03-24.pdf"
    result = extract_projects_from_pdf(pdf_file)

    if result:
        # Save to JSON file
        output_file = "extracted-projects-10-03-24.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"\nExtracted data saved to {output_file}")
        print(f"\nMeeting Date: {result['meeting_info'].get('meeting_date', 'Not found')}")
        print(f"Total Projects: {len(result['projects'])}")

        # Show first few projects as examples
        print("\nFirst few projects:")
        for i, project in enumerate(result['projects'][:3]):
            print(f"\n{i+1}. {project['project_id']} - {project['title']}")
            print(f"   Location: {project['location']}")
            print(f"   Type: {project['project_type']}")
            print(f"   Staff Rec: {project['staff_recommendation']}")
            print(f"   Tags: {', '.join(project['tags'])}")