"""
Project CRM - Merge extracted projects into accumulated database.

Handles:
- Fuzzy matching to find existing projects
- Merging new mentions into existing projects
- Flagging uncertain matches for human review

Usage:
    python3 -m backend.bd.crm [--reset]
"""
import argparse
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bd.crm")

BD_DIR = Path("outputs/bd")
EXTRACTIONS_FILE = BD_DIR / "latest_extractions.json"
PROJECTS_FILE = BD_DIR / "projects.json"
REVIEW_FILE = BD_DIR / "needs_review.json"

# Confidence thresholds
AUTO_MERGE_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60


def slugify(text: str) -> str:
    """Convert text to slug for project ID."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:50]  # Limit length


def similarity(a: str, b: str) -> float:
    """Calculate string similarity (0-1)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_matching_project(
    new_project: Dict,
    existing_projects: Dict[str, Dict]
) -> Tuple[Optional[str], float]:
    """
    Find matching existing project.
    Returns (project_id, confidence) or (None, 0).
    """
    new_name = new_project.get("project_name", "").lower()
    new_developer = new_project.get("developer", "").lower()
    new_location = new_project.get("location", "").lower() if new_project.get("location") else ""
    new_resolution = new_project.get("resolution_number", "")

    best_match = None
    best_confidence = 0.0

    for project_id, project in existing_projects.items():
        existing_name = project.get("name", "").lower()
        existing_developer = project.get("developer", "").lower()
        existing_location = project.get("location", "").lower() if project.get("location") else ""

        # Strategy 1: Exact name match
        if new_name and existing_name and new_name == existing_name:
            return (project_id, 1.0)

        # Strategy 2: Check if resolution numbers share prefix (same meeting batch)
        existing_resolutions = [m.get("resolution") for m in project.get("mentions", []) if m.get("resolution")]
        if new_resolution and existing_resolutions:
            # Same resolution prefix (e.g., 2026-01-XX)
            new_prefix = new_resolution.rsplit("-", 1)[0] if "-" in new_resolution else ""
            for res in existing_resolutions:
                existing_prefix = res.rsplit("-", 1)[0] if "-" in res else ""
                if new_prefix and new_prefix == existing_prefix:
                    # Same meeting, check name similarity
                    name_sim = similarity(new_name, existing_name)
                    if name_sim > 0.7:
                        confidence = 0.9
                        if confidence > best_confidence:
                            best_match = project_id
                            best_confidence = confidence

        # Strategy 3: Developer + location combo
        if new_developer and new_location and existing_developer and existing_location:
            dev_match = similarity(new_developer, existing_developer) > 0.8
            loc_match = similarity(new_location, existing_location) > 0.7
            if dev_match and loc_match:
                confidence = 0.85
                if confidence > best_confidence:
                    best_match = project_id
                    best_confidence = confidence

        # Strategy 4: Fuzzy name similarity
        name_sim = similarity(new_name, existing_name)
        if name_sim > REVIEW_THRESHOLD and name_sim > best_confidence:
            best_match = project_id
            best_confidence = name_sim

    return (best_match, best_confidence)


def create_project_entry(extracted: Dict, source: str = "dia_board") -> Dict:
    """Create a new project entry from extracted data."""
    meeting_date = extracted.get("_meeting_date", "")

    return {
        "name": extracted.get("project_name", "Unknown"),
        "developer": extracted.get("developer", "Unknown"),
        "type": extracted.get("project_type", "other"),
        "location": extracted.get("location"),
        "total_investment": extracted.get("total_investment"),
        "incentives": extracted.get("incentives", []),
        "stage": extracted.get("stage", "other"),
        "first_seen": meeting_date,
        "last_updated": meeting_date,
        "mentions": [
            {
                "date": meeting_date,
                "source": source,
                "resolution": extracted.get("resolution_number"),
                "action": extracted.get("action", ""),
                "url": extracted.get("_extracted_from", ""),
            }
        ],
        "timeline": [
            f"{meeting_date}: {extracted.get('action', 'First seen')}"
        ],
        "concerns": [extracted.get("concerns")] if extracted.get("concerns") else [],
        "bd_signals": [],
        "status": "active",
    }


def merge_into_project(project: Dict, extracted: Dict) -> Dict:
    """Merge new extraction data into existing project."""
    meeting_date = extracted.get("_meeting_date", "")

    # Add new mention
    new_mention = {
        "date": meeting_date,
        "source": "dia_board",
        "resolution": extracted.get("resolution_number"),
        "action": extracted.get("action", ""),
        "url": extracted.get("_extracted_from", ""),
    }

    # Check for duplicate mention (same date + resolution)
    existing_mentions = project.get("mentions", [])
    is_duplicate = any(
        m.get("date") == meeting_date and m.get("resolution") == extracted.get("resolution_number")
        for m in existing_mentions
    )

    if not is_duplicate:
        project["mentions"].append(new_mention)
        project["timeline"].append(f"{meeting_date}: {extracted.get('action', 'Update')}")

    # Update stage if more advanced
    stage_order = ["rfp", "term_sheet", "conceptual", "final_approval", "amendment", "extension", "deferred"]
    current_stage = project.get("stage", "other")
    new_stage = extracted.get("stage", "other")
    if new_stage in stage_order and current_stage in stage_order:
        if stage_order.index(new_stage) > stage_order.index(current_stage):
            project["stage"] = new_stage

    # Update last_updated
    project["last_updated"] = meeting_date

    # Add new incentives if not already present
    existing_incentives = project.get("incentives", [])
    new_incentives = extracted.get("incentives", [])
    for inc in new_incentives:
        # Simple duplicate check by type + amount
        is_dup = any(
            e.get("type") == inc.get("type") and e.get("amount") == inc.get("amount")
            for e in existing_incentives
        )
        if not is_dup:
            existing_incentives.append(inc)
    project["incentives"] = existing_incentives

    # Add concerns
    if extracted.get("concerns"):
        project.setdefault("concerns", []).append(extracted["concerns"])

    # Update investment if larger
    if extracted.get("total_investment"):
        project["total_investment"] = extracted["total_investment"]

    return project


def load_projects() -> Dict[str, Dict]:
    """Load existing projects from CRM."""
    if not PROJECTS_FILE.exists():
        return {}
    try:
        with open(PROJECTS_FILE) as f:
            data = json.load(f)
        return data.get("projects", {})
    except Exception:
        return {}


def save_projects(projects: Dict[str, Dict]):
    """Save projects to CRM file."""
    data = {
        "updated_at": datetime.now().isoformat(),
        "total_projects": len(projects),
        "projects": projects,
    }
    with open(PROJECTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Merge extracted projects into CRM")
    parser.add_argument("--reset", action="store_true", help="Clear existing CRM and start fresh")
    args = parser.parse_args()

    if not EXTRACTIONS_FILE.exists():
        logger.error(f"No extractions found: {EXTRACTIONS_FILE}")
        logger.info("Run 'make bd-extract' first")
        return

    # Load extractions
    with open(EXTRACTIONS_FILE) as f:
        extractions_data = json.load(f)
    extracted_projects = extractions_data.get("projects", [])

    if not extracted_projects:
        logger.info("No projects to merge")
        return

    logger.info(f"Processing {len(extracted_projects)} extracted projects")

    # Load or reset existing projects
    if args.reset:
        logger.info("Resetting CRM")
        projects = {}
    else:
        projects = load_projects()
        logger.info(f"Loaded {len(projects)} existing projects")

    # Track uncertain matches for review
    needs_review = []
    new_count = 0
    merged_count = 0

    for extracted in extracted_projects:
        project_name = extracted.get("project_name", "")
        if not project_name:
            continue

        # Find matching project
        match_id, confidence = find_matching_project(extracted, projects)

        if confidence >= AUTO_MERGE_THRESHOLD:
            # Auto-merge
            logger.info(f"Merging '{project_name}' into '{match_id}' ({confidence:.0%} confidence)")
            projects[match_id] = merge_into_project(projects[match_id], extracted)
            merged_count += 1

        elif confidence >= REVIEW_THRESHOLD:
            # Flag for review
            logger.info(f"Flagging '{project_name}' for review (possible match: '{match_id}' at {confidence:.0%})")
            needs_review.append({
                "new_project": extracted,
                "possible_match": match_id,
                "confidence": confidence,
                "existing_name": projects[match_id]["name"] if match_id else None,
            })
            # Still create as new for now
            project_id = slugify(project_name)
            if project_id in projects:
                project_id = f"{project_id}-{len(projects)}"
            projects[project_id] = create_project_entry(extracted)
            new_count += 1

        else:
            # New project
            project_id = slugify(project_name)
            if project_id in projects:
                project_id = f"{project_id}-{len(projects)}"
            logger.info(f"Creating new project: {project_id}")
            projects[project_id] = create_project_entry(extracted)
            new_count += 1

    # Save results
    save_projects(projects)
    logger.info(f"Saved {len(projects)} projects to {PROJECTS_FILE}")
    logger.info(f"  New: {new_count}, Merged: {merged_count}")

    # Save review items
    if needs_review:
        with open(REVIEW_FILE, "w") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "items": needs_review,
            }, f, indent=2)
        logger.warning(f"{len(needs_review)} items need review → {REVIEW_FILE}")


if __name__ == "__main__":
    main()
