#!/usr/bin/env python3

import json
import re
from datetime import datetime

def categorize_project(project):
    """Categorize a project based on its type and characteristics"""
    project_type = project.get('project_type', '').lower()
    request = project.get('request', '').lower()
    title = project.get('title', '').lower()

    # All current projects are zoning-related since they come from Planning Commission
    category = "zoning"

    # Determine project scale based on type and description
    if any(keyword in project_type for keyword in ['pud', 'rezoning']):
        project_scale = "district"
    elif any(keyword in project_type for keyword in ['variance', 'administrative deviation', 'minor modification']):
        project_scale = "neighborhood"
    else:
        project_scale = "neighborhood"

    return {
        'category': category,
        'data_source': 'planning_commission',
        'project_scale': project_scale,
        'estimated_value': None,  # Not available in current data
        'completion_timeline': None  # Not available in current data
    }

def extend_project_data(projects_file):
    """Extend existing project data with new schema fields"""

    print(f"Loading projects from {projects_file}...")

    with open(projects_file, 'r') as f:
        projects = json.load(f)

    print(f"Found {len(projects)} projects to update")

    updated_projects = []

    for project in projects:
        # Add new fields
        new_fields = categorize_project(project)

        # Create updated project with new fields
        updated_project = {**project, **new_fields}

        updated_projects.append(updated_project)

    # Create backup of original file
    backup_file = projects_file.replace('.json', '_backup.json')
    print(f"Creating backup at {backup_file}")

    with open(backup_file, 'w') as f:
        json.dump(projects, f, indent=2)

    # Write updated data
    print(f"Writing updated data to {projects_file}")

    with open(projects_file, 'w') as f:
        json.dump(updated_projects, f, indent=2)

    print("Data schema extension complete!")

    # Print summary statistics
    categories = {}
    scales = {}
    sources = {}

    for project in updated_projects:
        cat = project.get('category', 'unknown')
        scale = project.get('project_scale', 'unknown')
        source = project.get('data_source', 'unknown')

        categories[cat] = categories.get(cat, 0) + 1
        scales[scale] = scales.get(scale, 0) + 1
        sources[source] = sources.get(source, 0) + 1

    print("\nSummary:")
    print(f"Categories: {categories}")
    print(f"Project Scales: {scales}")
    print(f"Data Sources: {sources}")

if __name__ == "__main__":
    extend_project_data('all-projects.json')