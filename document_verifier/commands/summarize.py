#!/usr/bin/env python3
"""
Document Verifier - Document Verification Command
Verifies JaxWatch civic documents with AI analysis
"""

import json
import requests
import os
import yaml
import argparse
from datetime import datetime
from pathlib import Path


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def call_llm(prompt, config):
    """Simple LLM call using local Ollama service."""
    url = "http://localhost:11434/api/chat"

    response = requests.post(url, json={
        "model": config['llm_model'],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }, headers={
        "Content-Type": "application/json"
    })

    if response.status_code != 200:
        raise Exception(f"Ollama API call failed: {response.status_code} - {response.text}")

    return response.json()["message"]["content"]


def load_prompt_template():
    """Load the summarization prompt template."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "summarize_item.md"
    with open(prompt_path, 'r') as f:
        return f.read()


def load_enhanced_projects(output_path):
    """Load existing enhanced projects state."""
    if not output_path.exists():
        return [], set()

    try:
        with open(output_path, 'r') as f:
            enhanced_projects = json.load(f)

        # Build set of already-annotated project IDs
        annotated_ids = set()
        for project in enhanced_projects:
            if project.get("document_verification"):
                annotated_ids.add(project.get("id"))

        return enhanced_projects, annotated_ids
    except (json.JSONDecodeError, IOError):
        return [], set()


def save_enhanced_projects(enhanced_projects, output_path):
    """Save enhanced projects to file."""
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(enhanced_projects, f, indent=2)


def extract_key_sections(full_text, max_chars=3000):
    """Extract key authorization sections from PDF text, prioritizing RESOLVED clauses."""
    import re

    lines = full_text.split('\n')

    # Priority sections - look for authorization language
    key_patterns = [
        r'(?i)\bNOW\s+THEREFORE\s+BE\s+IT\s+RESOLVED\b',
        r'(?i)\bBE\s+IT\s+RESOLVED\b',
        r'(?i)\bSECTION\s+\d+',
        r'(?i)\bauthorize[sd]?\b',
        r'(?i)\binstruc[ts]?\b',
        r'(?i)\bdirect[s]?\b',
        r'(?i)\bmillion\b|\$\d+',
        r'(?i)\bcontingent\b|\bdependent\b'
    ]

    # Find lines with key authorization language
    priority_lines = []
    for i, line in enumerate(lines):
        if any(re.search(pattern, line) for pattern in key_patterns):
            # Include context: 2 lines before and 3 lines after
            start = max(0, i-2)
            end = min(len(lines), i+4)
            priority_lines.extend(range(start, end))

    # Remove duplicates and sort
    priority_lines = sorted(set(priority_lines))

    if priority_lines:
        # Extract priority sections
        key_content = '\n'.join(lines[i] for i in priority_lines)
        if len(key_content) <= max_chars:
            return key_content
        else:
            # If still too long, truncate key sections
            return key_content[:max_chars] + "\n[...key sections truncated...]"

    # Fallback: head + tail strategy
    if len(full_text) <= max_chars:
        return full_text

    head_size = max_chars // 2
    tail_size = max_chars - head_size - 50  # Leave room for separator
    return full_text[:head_size] + "\n\n[...middle sections omitted...]\n\n" + full_text[-tail_size:]


def get_pdf_text_for_project(project):
    """Extract and return PDF text content for project mentions."""
    import sys
    sys.path.append('../../backend/tools')

    # Import make_filename function
    try:
        from pdf_extractor import make_filename
    except ImportError:
        # Fallback if import fails
        def make_filename(item):
            url = item.get('url', '')
            if 'cms/getattachment' in url:
                # Extract the attachment ID and filename from URL
                parts = url.split('/')
                for i, part in enumerate(parts):
                    if part == 'getattachment' and i + 1 < len(parts):
                        attachment_id = parts[i+1].replace('-', '')
                        if i + 2 < len(parts):
                            # Include the filename part
                            filename_part = parts[i+2]
                            return f"getattachment_{attachment_id}_{filename_part}.pdf"
                        return f"getattachment_{attachment_id}"
            return "unknown_document"

    all_text_content = []

    for mention in project.get('mentions', []):
        if not mention.get('url'):
            continue

        # Map URL to filename using existing PDF extractor logic
        filename = make_filename(mention)

        # Determine source and year from mention
        source = mention.get('source', 'dia_board')
        meeting_date = mention.get('meeting_date', '')
        year = meeting_date[:4] if meeting_date else '2025'

        # Build path to extracted text file
        # Resolve path relative to document_verifier directory
        document_verifier_dir = Path(__file__).parent.parent
        text_file_path = document_verifier_dir / f"../outputs/files/{source}/{year}/{filename}.txt"

        if text_file_path.exists():
            try:
                content = text_file_path.read_text(encoding='utf-8')

                # Smart text truncation - prioritize authorization sections
                processed_content = extract_key_sections(content)
                all_text_content.append(f"Document: {mention.get('title', 'Unknown')}\n{processed_content}")
            except Exception as e:
                print(f"Warning: Could not read text from {text_file_path}: {e}")
        else:
            print(f"Warning: No extracted text found for {mention.get('url', 'unknown URL')}")

    return "\n\n---\n\n".join(all_text_content)


def enhance_project(project, prompt_template, config):
    """Add document_verification to single project with PDF content."""
    # Get PDF text content for this project
    pdf_content = get_pdf_text_for_project(project)

    # Create a simplified version of the project for the prompt
    project_summary = {
        "id": project.get("id"),
        "title": project.get("title"),
        "summary": project.get("summary"),
        "status": project.get("status"),
        "source": project.get("source"),
        "address": project.get("address"),
        "doc_type": project.get("doc_type"),
    }

    # Create enhanced prompt with PDF content
    if pdf_content:
        enhanced_prompt = prompt_template.format(
            project_json=json.dumps(project_summary, indent=2),
            document_content=pdf_content
        )
    else:
        enhanced_prompt = prompt_template.format(
            project_json=json.dumps(project_summary, indent=2),
            document_content="[No document content available for analysis]"
        )

    prompt = enhanced_prompt

    try:
        analysis = call_llm(prompt, config)

        project["document_verification"] = {
            "enhanced_summary": analysis.strip(),
            "processed_at": datetime.now().isoformat(),
            "version": "0.1.0"
        }
        print(f"✓ Enhanced project: {project.get('id')} - {project.get('title', 'N/A')}")

    except Exception as e:
        print(f"✗ Failed to enhance project {project.get('id')}: {e}")
        project["document_verification"] = {
            "enhanced_summary": f"ERROR: {str(e)}",
            "processed_at": datetime.now().isoformat(),
            "version": "0.1.0"
        }

    return project


def select_projects_to_process(projects, annotated_ids, limit=10, target_project_id=None, force=False, active_year=None):
    """Select projects for processing, respecting already-annotated state."""
    if target_project_id:
        # Process only the specified project
        target_project = None
        for project in projects:
            if project.get("id") == target_project_id:
                target_project = project
                break

        if not target_project:
            print(f"Error: Project '{target_project_id}' not found")
            return []

        if target_project_id in annotated_ids and not force:
            print(f"Project '{target_project_id}' is already annotated. Use --force to reprocess.")
            return []

        print(f"Selected 1 project for processing:")
        print(f"  1. {target_project.get('id')} - {target_project.get('title', 'N/A')}")
        return [target_project]

    # Filter out already-annotated projects unless force mode
    available_projects = []
    for project in projects:
        project_id = project.get("id")
        if not force and project_id in annotated_ids:
            continue  # Skip already annotated
        available_projects.append(project)

    if not available_projects:
        print("All projects are already annotated. Use --force to reprocess existing annotations.")
        return []

    # Filter by active year if specified
    if active_year:
        filtered_projects = []
        for project in available_projects:
            latest_activity = project.get("latest_activity_date")
            if latest_activity:
                try:
                    activity_year = datetime.strptime(latest_activity, '%Y-%m-%d').year
                    if activity_year == active_year:
                        filtered_projects.append(project)
                except (ValueError, TypeError):
                    continue

        if not filtered_projects:
            print(f"No projects found with activity in {active_year}")
            return []

        available_projects = filtered_projects
        print(f"Filtered to {len(available_projects)} projects active in {active_year}")

    # Sort by latest_activity_date (newest first)
    def get_activity_date(project):
        latest_activity = project.get("latest_activity_date")
        if latest_activity:
            try:
                return datetime.strptime(latest_activity, '%Y-%m-%d')
            except (ValueError, TypeError):
                pass
        # Fallback to very old date if no valid activity date
        return datetime(1900, 1, 1)

    available_projects.sort(key=get_activity_date, reverse=True)
    selected = available_projects[:limit]

    print(f"Selected {len(selected)} projects for processing:")
    for i, project in enumerate(selected, 1):
        print(f"  {i}. {project.get('id')} - {project.get('title', 'N/A')}")

    return selected


def main(argv=None):
    """Main function to run the summarize command."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Verify civic documents with AI analysis")
    parser.add_argument("--project", help="Process only the specified project ID")
    parser.add_argument("--force", action="store_true", help="Ignore 'already annotated' check and reprocess")
    parser.add_argument("--active-year", type=int, help="Filter projects where latest_activity_date.year == specified year")

    args = parser.parse_args(argv)

    try:
        config = load_config()
        prompt_template = load_prompt_template()

        # Resolve paths relative to document_verifier directory
        document_verifier_dir = Path(__file__).parent.parent
        input_path = document_verifier_dir / config['input_path']
        output_path = document_verifier_dir / config['output_path']

        print(f"Loading projects from: {input_path}")

        # Load existing projects
        with open(input_path, 'r') as f:
            projects = json.load(f)

        print(f"Loaded {len(projects)} total projects")

        # Load existing enhanced projects state (memory)
        enhanced_projects, annotated_ids = load_enhanced_projects(output_path)

        if annotated_ids:
            print(f"Found {len(annotated_ids)} already-annotated projects")

        # Select projects for processing based on state and arguments
        selected_projects = select_projects_to_process(
            projects,
            annotated_ids,
            limit=10,
            target_project_id=args.project,
            force=args.force,
            active_year=getattr(args, 'active_year', None)
        )

        if not selected_projects:
            print("Nothing to do.")
            return 0

        print(f"\nProcessing {len(selected_projects)} projects...")

        # Process selected projects
        newly_enhanced = []
        for i, project in enumerate(selected_projects, 1):
            print(f"\n[{i}/{len(selected_projects)}] Processing: {project.get('id')}")
            enhanced_project = enhance_project(project.copy(), prompt_template, config)
            newly_enhanced.append(enhanced_project)

        # Merge newly enhanced projects with existing ones
        enhanced_lookup = {p.get("id"): p for p in enhanced_projects}

        # Update or add newly enhanced projects
        for project in newly_enhanced:
            project_id = project.get("id")
            enhanced_lookup[project_id] = project

        # Create final enhanced projects list
        final_enhanced = list(enhanced_lookup.values())

        print(f"\nWriting enhanced projects to: {output_path}")
        save_enhanced_projects(final_enhanced, output_path)

        print(f"✓ Successfully enhanced {len(newly_enhanced)} projects")
        print(f"✓ Total enhanced projects: {len(final_enhanced)}")
        print(f"✓ Output written to: {output_path}")

        # Show sample enhancement
        if newly_enhanced and newly_enhanced[0].get("document_verification"):
            sample = newly_enhanced[0]
            print(f"\nSample enhancement for '{sample.get('title', 'N/A')}':")
            print("-" * 60)
            print(sample["document_verification"]["enhanced_summary"])
            print("-" * 60)

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    exit(main(sys.argv[1:]))