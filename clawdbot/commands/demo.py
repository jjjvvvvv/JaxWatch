#!/usr/bin/env python3
"""
Clawdbot Demo Command
Demonstrates the enhancement without requiring API keys by using mock responses
"""

import json
from datetime import datetime
from pathlib import Path

# Import the main functions from summarize
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from summarize import load_config, load_prompt_template, select_projects_to_process


def mock_llm_call(project):
    """Generate mock LLM responses for demonstration."""
    project_id = project.get("id", "UNKNOWN")
    title = project.get("title", "Unknown Project")
    child_count = project.get("child_project_count", 0)

    # Generate contextual mock responses based on project data
    if "SHIPYARDS" in project_id.upper():
        return "The Shipyards development is a major mixed-use waterfront project featuring residential, commercial, and entertainment facilities. With 118 related documents spanning multiple years, this represents one of Jacksonville's most significant ongoing developments with substantial public investment and regulatory oversight."

    elif "RIVERFRONT" in project_id.upper():
        return "Riverfront Plaza represents a key downtown revitalization effort focused on waterfront accessibility and public space enhancement. The project involves coordination between multiple city departments and private developers, with emphasis on creating pedestrian-friendly riverside amenities."

    elif "LAVILLA" in project_id.upper():
        return "LaVilla Redevelopment is a historic district revitalization project aimed at preserving cultural heritage while promoting economic development. The initiative includes mixed-use development, historic preservation, and community engagement components with significant Community Redevelopment Agency involvement."

    elif "GATEWAY" in project_id.upper():
        return "Pearl Square/Gateway Jax represents a transit-oriented development project designed to enhance connectivity and create mixed-use urban density. The project focuses on integrating transportation infrastructure with commercial and residential development in a key downtown gateway location."

    elif "FORD" in project_id.upper():
        return "Ford on Bay is a commercial development project involving adaptive reuse or redevelopment of automotive-related facilities. The project involves zoning considerations, environmental assessments, and coordination with economic development initiatives to transform underutilized urban space."

    else:
        # Generic response for other projects
        doc_count = child_count if child_count > 0 else "limited"
        return f"{title} is a Jacksonville civic project with {doc_count} related documents. The project involves municipal planning processes, regulatory review, and coordination between city departments to address community development needs while ensuring compliance with zoning and environmental requirements."


def enhance_project_demo(project, prompt_template):
    """Add clawdbot_analysis to project using mock LLM response."""
    analysis = mock_llm_call(project)

    project["clawdbot_analysis"] = {
        "enhanced_summary": analysis,
        "processed_at": datetime.now().isoformat(),
        "version": "0.1.0-demo"
    }
    print(f"✓ Enhanced project: {project.get('id')} - {project.get('title', 'N/A')}")

    return project


def main():
    """Main function to run the demo command."""
    try:
        config = load_config()
        prompt_template = load_prompt_template()

        # Resolve paths relative to clawdbot directory
        clawdbot_dir = Path(__file__).parent.parent
        input_path = clawdbot_dir / config['input_path']

        # Use a demo output path
        output_path = clawdbot_dir / "demo_output.json"

        print("🎭 DEMO MODE - Using mock LLM responses")
        print(f"Loading projects from: {input_path}")

        # Load existing projects
        with open(input_path, 'r') as f:
            projects = json.load(f)

        print(f"Loaded {len(projects)} total projects")

        # Select subset for processing
        selected_projects = select_projects_to_process(projects, limit=5)

        if not selected_projects:
            print("No suitable projects found for processing")
            return

        # Create a copy for output with only enhanced projects
        enhanced_projects = []

        print(f"\nProcessing {len(selected_projects)} projects with mock responses...")

        for i, project in enumerate(selected_projects, 1):
            print(f"\n[{i}/{len(selected_projects)}] Processing: {project.get('id')}")
            enhanced_project = enhance_project_demo(project.copy(), prompt_template)
            enhanced_projects.append(enhanced_project)

        print(f"\nWriting demo results to: {output_path}")

        # Write enhanced projects
        with open(output_path, 'w') as f:
            json.dump(enhanced_projects, f, indent=2)

        print(f"✓ Successfully enhanced {len(enhanced_projects)} projects")
        print(f"✓ Demo output written to: {output_path}")

        # Show all enhancements
        print(f"\n🎯 Demo Results Summary:")
        print("=" * 80)
        for i, project in enumerate(enhanced_projects, 1):
            print(f"\n{i}. {project.get('title', 'N/A')} ({project.get('id')})")
            print("-" * 60)
            print(project["clawdbot_analysis"]["enhanced_summary"])

        print("\n" + "=" * 80)
        print("🎭 This was a demonstration using mock responses.")
        print("To use real LLM analysis, set GROQ_API_KEY and run: python clawdbot.py summarize")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())