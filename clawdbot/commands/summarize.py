#!/usr/bin/env python3
"""
Clawdbot Summarize Command
Enhances JaxWatch project data with LLM-generated analysis
"""

import json
import requests
import os
import yaml
from datetime import datetime
from pathlib import Path


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def call_llm(prompt, config):
    """Simple LLM call using Groq API."""
    api_key = os.environ.get(config['llm_api_key_env'])
    if not api_key:
        raise ValueError(f"Environment variable {config['llm_api_key_env']} not set")

    url = "https://api.groq.com/openai/v1/chat/completions"

    response = requests.post(url, json={
        "model": config['llm_model'],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 500
    }, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })

    if response.status_code != 200:
        raise Exception(f"LLM API call failed: {response.status_code} - {response.text}")

    return response.json()["choices"][0]["message"]["content"]


def load_prompt_template():
    """Load the summarization prompt template."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "summarize_item.md"
    with open(prompt_path, 'r') as f:
        return f.read()


def enhance_project(project, prompt_template, config):
    """Add clawdbot_analysis to single project."""
    # Create a simplified version of the project for the prompt
    project_summary = {
        "id": project.get("id"),
        "title": project.get("title"),
        "summary": project.get("summary"),
        "status": project.get("status"),
        "source": project.get("source"),
        "child_project_count": project.get("child_project_count", 0),
        "total_child_mentions": project.get("total_child_mentions", 0),
        "address": project.get("address"),
        "doc_type": project.get("doc_type"),
        "is_master_project": project.get("is_master_project", False)
    }

    prompt = prompt_template.format(project_json=json.dumps(project_summary, indent=2))

    try:
        analysis = call_llm(prompt, config)

        project["clawdbot_analysis"] = {
            "enhanced_summary": analysis.strip(),
            "processed_at": datetime.now().isoformat(),
            "version": "0.1.0"
        }
        print(f"✓ Enhanced project: {project.get('id')} - {project.get('title', 'N/A')}")

    except Exception as e:
        print(f"✗ Failed to enhance project {project.get('id')}: {e}")
        project["clawdbot_analysis"] = {
            "enhanced_summary": f"ERROR: {str(e)}",
            "processed_at": datetime.now().isoformat(),
            "version": "0.1.0"
        }

    return project


def select_projects_to_process(projects, limit=10):
    """Select interesting projects for processing."""
    # Prioritize master projects with good data
    candidates = []

    for project in projects:
        # Score projects based on how much data they have
        score = 0

        # Prefer master projects
        if project.get("is_master_project", False):
            score += 10

        # Prefer projects with child documents
        child_count = project.get("child_project_count", 0)
        if child_count > 0:
            score += min(child_count, 20)  # Cap at 20 points

        # Prefer projects with addresses
        if project.get("address"):
            score += 5

        # Prefer projects with summaries
        if project.get("summary") and len(project.get("summary", "")) > 20:
            score += 5

        # Avoid projects that are clearly system-generated or minimal
        title = project.get("title", "")
        if len(title) > 10 and "RESOLUTION" not in title.upper():
            score += 3

        candidates.append((score, project))

    # Sort by score and take top N
    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = [project for score, project in candidates[:limit]]

    print(f"Selected {len(selected)} projects for processing:")
    for i, project in enumerate(selected, 1):
        print(f"  {i}. {project.get('id')} - {project.get('title', 'N/A')}")

    return selected


def main():
    """Main function to run the summarize command."""
    try:
        config = load_config()
        prompt_template = load_prompt_template()

        # Resolve paths relative to clawdbot directory
        clawdbot_dir = Path(__file__).parent.parent
        input_path = clawdbot_dir / config['input_path']
        output_path = clawdbot_dir / config['output_path']

        print(f"Loading projects from: {input_path}")

        # Load existing projects
        with open(input_path, 'r') as f:
            projects = json.load(f)

        print(f"Loaded {len(projects)} total projects")

        # Select subset for processing
        selected_projects = select_projects_to_process(projects, limit=10)

        if not selected_projects:
            print("No suitable projects found for processing")
            return

        # Create a copy for output with only enhanced projects
        enhanced_projects = []

        print(f"\nProcessing {len(selected_projects)} projects...")

        for i, project in enumerate(selected_projects, 1):
            print(f"\n[{i}/{len(selected_projects)}] Processing: {project.get('id')}")
            enhanced_project = enhance_project(project.copy(), prompt_template, config)
            enhanced_projects.append(enhanced_project)

        print(f"\nWriting enhanced projects to: {output_path}")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write enhanced projects
        with open(output_path, 'w') as f:
            json.dump(enhanced_projects, f, indent=2)

        print(f"✓ Successfully enhanced {len(enhanced_projects)} projects")
        print(f"✓ Output written to: {output_path}")

        # Show sample enhancement
        if enhanced_projects and enhanced_projects[0].get("clawdbot_analysis"):
            sample = enhanced_projects[0]
            print(f"\nSample enhancement for '{sample.get('title', 'N/A')}':")
            print("-" * 60)
            print(sample["clawdbot_analysis"]["enhanced_summary"])
            print("-" * 60)

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())