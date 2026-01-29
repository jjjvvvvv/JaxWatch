"""
Data access utilities for JaxWatch Dashboard
Handles reading/writing JSON files on disk
"""

import json
from pathlib import Path
from typing import List, Dict, Optional


# Define data file paths relative to this file
BASE_DIR = Path(__file__).parent.parent
PROJECTS_INDEX_PATH = BASE_DIR / 'outputs' / 'projects' / 'projects_index.json'
PROJECTS_ENRICHED_PATH = BASE_DIR / 'outputs' / 'projects' / 'projects_enriched.json'
DOCUMENT_VERIFIER_DEMO_PATH = BASE_DIR / 'document_verifier' / 'demo_output.json'
STATUS_PATH = BASE_DIR / 'dashboard' / 'status.json'
REFERENCE_SCANNER_ANNOTATIONS_PATH = BASE_DIR / 'outputs' / 'annotations' / 'reference_scanner'


def load_projects_index() -> List[Dict]:
    """Load raw JaxWatch projects from projects_index.json."""
    try:
        with open(PROJECTS_INDEX_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def load_enriched_projects() -> List[Dict]:
    """Load enhanced projects from projects_enriched.json or demo output."""
    # Try projects_enriched.json first, fall back to demo output
    paths_to_try = [PROJECTS_ENRICHED_PATH, DOCUMENT_VERIFIER_DEMO_PATH]

    for path in paths_to_try:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    return []


def load_status() -> Dict:
    """Load system status from status.json."""
    try:
        with open(STATUS_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'last_run': None,
            'command': None,
            'success': None,
            'output': '',
            'error': '',
            'action_type': None
        }


def save_status(status: Dict) -> None:
    """Save system status to status.json."""
    try:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_PATH, 'w') as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save status: {e}")


def get_project_by_id(project_id: str, source: str = 'raw') -> Optional[Dict]:
    """
    Get a specific project by ID from either raw or enriched data.

    Args:
        project_id: The project ID to find
        source: Either 'raw' or 'enriched'

    Returns:
        Project dictionary or None if not found
    """
    if source == 'raw':
        projects = load_projects_index()
    elif source == 'enriched':
        projects = load_enriched_projects()
    else:
        raise ValueError("source must be 'raw' or 'enriched'")

    for project in projects:
        if project.get('id') == project_id:
            return project

    return None


def get_enhancement_stats() -> Dict:
    """Get statistics about enhancements."""
    raw_projects = load_projects_index()
    enriched_projects = load_enriched_projects()

    enriched_ids = {p['id'] for p in enriched_projects}

    stats = {
        'total_projects': len(raw_projects),
        'enriched_projects': len(enriched_projects),
        'enhancement_rate': len(enriched_projects) / len(raw_projects) if raw_projects else 0,
        'master_projects_total': len([p for p in raw_projects if p.get('is_master_project', False)]),
        'master_projects_enriched': len([p for p in enriched_projects if p.get('is_master_project', False)])
    }

    return stats


def search_projects(query: str, source: str = 'raw') -> List[Dict]:
    """
    Search projects by title or ID.

    Args:
        query: Search query string
        source: Either 'raw' or 'enriched'

    Returns:
        List of matching projects
    """
    if source == 'raw':
        projects = load_projects_index()
    elif source == 'enriched':
        projects = load_enriched_projects()
    else:
        raise ValueError("source must be 'raw' or 'enriched'")

    query = query.lower().strip()
    if not query:
        return projects

    matches = []
    for project in projects:
        title = project.get('title', '').lower()
        project_id = project.get('id', '').lower()

        if query in title or query in project_id:
            matches.append(project)

    return matches


def get_recent_activity(limit: int = 10) -> List[Dict]:
    """Get recently processed projects."""
    enriched_projects = load_enriched_projects()

    # Sort by processed_at timestamp
    sorted_projects = sorted(
        enriched_projects,
        key=lambda p: p.get('document_verification', {}).get('processed_at', ''),
        reverse=True
    )

    return sorted_projects[:limit]


def load_reference_scanner_annotations_for_project(project: Dict) -> List[Dict]:
    """
    Load Reference Scanner derived references for a specific project.

    Args:
        project: Project dictionary containing mentions with URLs

    Returns:
        List of reference annotations from Reference Scanner
    """
    if not REFERENCE_SCANNER_ANNOTATIONS_PATH.exists():
        return []

    references = []
    project_urls = set()

    # Collect all URLs associated with this project
    for mention in project.get('mentions', []):
        if mention.get('url'):
            project_urls.add(mention['url'])

    # Load annotations that reference any of this project's documents
    for annotation_file in REFERENCE_SCANNER_ANNOTATIONS_PATH.glob('*.json'):
        try:
            with open(annotation_file, 'r') as f:
                annotation = json.load(f)

            # Check if this annotation is for one of the project's documents
            source_url = annotation.get('source_document_url', '')
            if any(url in source_url for url in project_urls) or any(source_url in url for url in project_urls):
                references.append(annotation)

        except (json.JSONDecodeError, FileNotFoundError):
            continue

    # Sort by confidence and detected date
    references.sort(key=lambda x: (
        {'high': 3, 'medium': 2, 'low': 1}.get(x.get('confidence', 'low'), 1),
        x.get('detected_at', '')
    ), reverse=True)

    return references


def get_reference_scanner_stats() -> Dict:
    """Get statistics about Reference Scanner annotations."""
    if not REFERENCE_SCANNER_ANNOTATIONS_PATH.exists():
        return {
            'total_annotations': 0,
            'by_confidence': {'high': 0, 'medium': 0, 'low': 0},
            'by_type': {}
        }

    annotations = []
    for annotation_file in REFERENCE_SCANNER_ANNOTATIONS_PATH.glob('*.json'):
        try:
            with open(annotation_file, 'r') as f:
                annotation = json.load(f)
                annotations.append(annotation)
        except (json.JSONDecodeError, FileNotFoundError):
            continue

    stats = {
        'total_annotations': len(annotations),
        'by_confidence': {'high': 0, 'medium': 0, 'low': 0},
        'by_type': {}
    }

    for annotation in annotations:
        confidence = annotation.get('confidence', 'low')
        ref_type = annotation.get('reference_type', 'unknown')

        if confidence in stats['by_confidence']:
            stats['by_confidence'][confidence] += 1

        if ref_type not in stats['by_type']:
            stats['by_type'][ref_type] = 0
        stats['by_type'][ref_type] += 1

    return stats