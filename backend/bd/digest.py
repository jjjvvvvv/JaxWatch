"""
Business Development digest generator.

Reads projects.json and signals.json to produce a project-centric markdown digest.
Also surfaces items needing human review.
"""
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bd.digest")

BD_DIR = Path("outputs/bd")
PROJECTS_FILE = BD_DIR / "projects.json"
SIGNALS_FILE = BD_DIR / "signals.json"
REVIEW_FILE = BD_DIR / "needs_review.json"
DIGEST_FILE = BD_DIR / "digest.md"

SIGNAL_LABELS = {
    "big_money": "Big Money",
    "active_incentives": "Active Incentives",
    "complexity": "Complex Project",
    "trouble": "Trouble Signs",
    "new_opportunity": "New Opportunity",
}


def format_money(value: str) -> str:
    """Format money string for display."""
    if not value:
        return "N/A"
    return value


def generate_digest() -> str:
    """Generate project-centric markdown digest."""
    lines = [
        "# BD Digest",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # Load projects
    if not PROJECTS_FILE.exists():
        lines.append("No projects found. Run `make bd-extract` first.")
        return "\n".join(lines)

    with open(PROJECTS_FILE) as f:
        projects_data = json.load(f)
    projects = projects_data.get("projects", {})

    if not projects:
        lines.append("No projects in CRM yet.")
        return "\n".join(lines)

    lines.append(f"**{len(projects)} projects tracked**")
    lines.append("")

    # Load signals
    signals_by_project = {}
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE) as f:
            signals_data = json.load(f)
        for sig in signals_data.get("signals", []):
            signals_by_project[sig.get("project_id")] = sig.get("signals", [])

    # Section 1: Projects with BD signals (sorted by signal count)
    projects_with_signals = [
        (pid, p) for pid, p in projects.items()
        if p.get("bd_signals")
    ]
    projects_with_signals.sort(key=lambda x: len(x[1].get("bd_signals", [])), reverse=True)

    if projects_with_signals:
        lines.append("## Hot Opportunities")
        lines.append("")

        for project_id, project in projects_with_signals[:10]:
            name = project.get("name", "Unknown")
            developer = project.get("developer", "Unknown")
            investment = format_money(project.get("total_investment"))
            stage = project.get("stage", "unknown").replace("_", " ").title()
            signals = project.get("bd_signals", [])
            first_seen = project.get("first_seen", "")
            mention_count = len(project.get("mentions", []))

            signal_icons = []
            for s in signals:
                if s == "big_money":
                    signal_icons.append("💰")
                elif s == "active_incentives":
                    signal_icons.append("🎯")
                elif s == "complexity":
                    signal_icons.append("🔧")
                elif s == "trouble":
                    signal_icons.append("⚠️")
                elif s == "new_opportunity":
                    signal_icons.append("🆕")

            lines.append(f"### {' '.join(signal_icons)} {name}")
            lines.append("")
            lines.append(f"- **Developer**: {developer}")
            lines.append(f"- **Investment**: {investment}")
            lines.append(f"- **Stage**: {stage}")
            lines.append(f"- **First Seen**: {first_seen}")
            lines.append(f"- **Mentions**: {mention_count}")
            lines.append(f"- **Signals**: {', '.join(SIGNAL_LABELS.get(s, s) for s in signals)}")

            # Show incentives
            incentives = project.get("incentives", [])
            if incentives:
                lines.append(f"- **Incentives**:")
                for inc in incentives[:3]:
                    inc_type = inc.get("type", "unknown").replace("_", " ").title()
                    inc_amount = inc.get("amount", "N/A")
                    inc_status = inc.get("status", "unknown")
                    lines.append(f"  - {inc_type}: {inc_amount} ({inc_status})")

            # Show recent timeline
            timeline = project.get("timeline", [])
            if timeline:
                lines.append(f"- **Timeline**:")
                for event in timeline[-3:]:
                    lines.append(f"  - {event}")

            lines.append("")

        if len(projects_with_signals) > 10:
            lines.append(f"*...and {len(projects_with_signals) - 10} more projects with signals*")
            lines.append("")

    # Section 2: All projects summary
    lines.append("## All Projects")
    lines.append("")
    lines.append("| Project | Developer | Investment | Stage | Signals |")
    lines.append("|---------|-----------|------------|-------|---------|")

    for project_id, project in sorted(projects.items(), key=lambda x: x[1].get("last_updated", ""), reverse=True):
        name = project.get("name", "Unknown")[:30]
        developer = project.get("developer", "Unknown")[:20]
        investment = format_money(project.get("total_investment"))[:15]
        stage = project.get("stage", "?")[:10]
        signals = ", ".join(project.get("bd_signals", []))[:20] or "-"

        lines.append(f"| {name} | {developer} | {investment} | {stage} | {signals} |")

    lines.append("")

    # Section 3: Items needing review
    if REVIEW_FILE.exists():
        with open(REVIEW_FILE) as f:
            review_data = json.load(f)
        review_items = review_data.get("items", [])

        if review_items:
            lines.append("## Needs Review")
            lines.append("")
            lines.append("These items may be duplicates. Please verify:")
            lines.append("")

            for item in review_items:
                new_name = item.get("new_project", {}).get("project_name", "Unknown")
                existing_name = item.get("existing_name", "Unknown")
                confidence = item.get("confidence", 0)

                lines.append(f"- **{new_name}** may be same as **{existing_name}** ({confidence:.0%} match)")

            lines.append("")
            lines.append("*Edit `outputs/bd/projects.json` to merge duplicates manually.*")
            lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point."""
    BD_DIR.mkdir(parents=True, exist_ok=True)

    digest = generate_digest()

    with open(DIGEST_FILE, "w") as f:
        f.write(digest)

    logger.info(f"Wrote digest to {DIGEST_FILE}")
    print(digest)


if __name__ == "__main__":
    main()
