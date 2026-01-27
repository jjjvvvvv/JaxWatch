"""
Business Development signal detector.

Scans the project CRM for consulting opportunity signals.
Outputs signals.json with detected opportunities per project.

Usage:
    python3 -m backend.bd.detector [--reset]
"""
import argparse
import json
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bd.detector")

# Paths
BD_DIR = Path("outputs/bd")
PROJECTS_FILE = BD_DIR / "projects.json"
SIGNALS_FILE = BD_DIR / "signals.json"

# Signal detection rules based on project data
SIGNAL_RULES = {
    "big_money": {
        "description": "Project with significant investment (>$500k)",
        "check": lambda p: _has_big_money(p),
    },
    "active_incentives": {
        "description": "Project with pending/recommended incentives",
        "check": lambda p: _has_pending_incentives(p),
    },
    "complexity": {
        "description": "Complex project type or stage",
        "check": lambda p: _is_complex(p),
    },
    "trouble": {
        "description": "Project showing signs of trouble (deferred, concerns, extensions)",
        "check": lambda p: _has_trouble_signs(p),
    },
    "new_opportunity": {
        "description": "Recently appeared project in early stage",
        "check": lambda p: _is_new_opportunity(p),
    },
}


def _parse_money(value: str) -> float:
    """Parse money string to float (in millions)."""
    if not value:
        return 0.0
    value = value.lower().replace(",", "").replace("$", "").strip()

    # Handle "X million"
    if "million" in value or "mil" in value:
        match = re.search(r"([\d.]+)", value)
        if match:
            return float(match.group(1))

    # Handle raw numbers
    match = re.search(r"([\d.]+)", value)
    if match:
        num = float(match.group(1))
        if num > 10000:  # Likely in dollars, convert to millions
            return num / 1_000_000
        return num

    return 0.0


def _has_big_money(project: Dict) -> bool:
    """Check if project has >$500k investment or incentives."""
    # Check total investment
    investment = _parse_money(project.get("total_investment", ""))
    if investment >= 0.5:  # $500k in millions
        return True

    # Check incentives
    for inc in project.get("incentives", []):
        amount = _parse_money(inc.get("amount", ""))
        if amount >= 0.5:
            return True

    return False


def _has_pending_incentives(project: Dict) -> bool:
    """Check if project has pending/recommended incentives."""
    for inc in project.get("incentives", []):
        status = inc.get("status", "").lower()
        if status in ("pending", "recommended"):
            return True
    return False


def _is_complex(project: Dict) -> bool:
    """Check if project is complex (type or stage indicates it)."""
    complex_types = ["mixed-use", "infrastructure", "land_disposition"]
    complex_stages = ["term_sheet", "amendment", "extension"]

    if project.get("type") in complex_types:
        return True
    if project.get("stage") in complex_stages:
        return True

    return False


def _has_trouble_signs(project: Dict) -> bool:
    """Check for trouble indicators."""
    # Check stage
    if project.get("stage") in ("deferred", "extension", "amendment"):
        return True

    # Check concerns
    if project.get("concerns"):
        return True

    # Check timeline for deferrals
    for event in project.get("timeline", []):
        if any(word in event.lower() for word in ["defer", "delay", "concern", "denied"]):
            return True

    return False


def _is_new_opportunity(project: Dict) -> bool:
    """Check if project is a new opportunity (recent, early stage)."""
    early_stages = ["rfp", "term_sheet", "conceptual"]

    if project.get("stage") not in early_stages:
        return False

    # Check if first seen in last 60 days
    first_seen = project.get("first_seen", "")
    if first_seen:
        try:
            dt = datetime.fromisoformat(first_seen)
            days_ago = (datetime.now() - dt).days
            if days_ago <= 60:
                return True
        except ValueError:
            pass

    return False


def detect_signals_for_project(project_id: str, project: Dict) -> List[Dict]:
    """Detect all applicable signals for a project."""
    signals = []

    for signal_type, rule in SIGNAL_RULES.items():
        if rule["check"](project):
            signals.append({
                "type": signal_type,
                "description": rule["description"],
            })

    return signals


def main():
    parser = argparse.ArgumentParser(description="Detect BD signals from project CRM")
    parser.add_argument("--reset", action="store_true", help="Clear existing signals")
    args = parser.parse_args()

    if not PROJECTS_FILE.exists():
        logger.error(f"Projects file not found: {PROJECTS_FILE}")
        logger.info("Run 'make bd-extract' and 'make bd-merge' first")
        return

    # Load projects
    with open(PROJECTS_FILE) as f:
        data = json.load(f)
    projects = data.get("projects", {})

    if not projects:
        logger.info("No projects in CRM")
        return

    logger.info(f"Analyzing {len(projects)} projects for BD signals")

    # Detect signals for each project
    all_signals = []
    for project_id, project in projects.items():
        signals = detect_signals_for_project(project_id, project)

        if signals:
            all_signals.append({
                "project_id": project_id,
                "project_name": project.get("name", ""),
                "developer": project.get("developer", ""),
                "stage": project.get("stage", ""),
                "total_investment": project.get("total_investment", ""),
                "first_seen": project.get("first_seen", ""),
                "last_updated": project.get("last_updated", ""),
                "signals": signals,
                "mention_count": len(project.get("mentions", [])),
            })

            # Update project's bd_signals field
            project["bd_signals"] = [s["type"] for s in signals]

    # Sort by signal count (most interesting first)
    all_signals.sort(key=lambda x: len(x["signals"]), reverse=True)

    # Save signals
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_projects_with_signals": len(all_signals),
        "signals": all_signals,
    }

    with open(SIGNALS_FILE, "w") as f:
        json.dump(output, f, indent=2)

    # Update projects with bd_signals
    with open(PROJECTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Found {len(all_signals)} projects with BD signals → {SIGNALS_FILE}")

    # Summary
    signal_counts = {}
    for sig in all_signals:
        for s in sig["signals"]:
            signal_counts[s["type"]] = signal_counts.get(s["type"], 0) + 1

    for sig_type, count in sorted(signal_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {sig_type}: {count} projects")


if __name__ == "__main__":
    main()
