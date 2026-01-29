#!/usr/bin/env python3
"""
JaxWatch Document Verifier Local Admin Dashboard
A read-only-first, CRM-style interface for browsing and managing projects
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for

from data_access import (
    load_projects_index,
    load_enriched_projects,
    load_status,
    get_project_by_id,
    save_status,
    load_reference_scanner_annotations_for_project
)


app = Flask(__name__)


@app.route('/')
def index():
    """Dashboard overview with system status and quick counts."""
    try:
        # Load data
        raw_projects = load_projects_index()
        enriched_projects = load_enriched_projects()
        status = load_status()

        # Create lookup for enriched projects
        enriched_lookup = {p['id']: p for p in enriched_projects}

        # Calculate statistics
        total_projects = len(raw_projects)
        enriched_count = len(enriched_projects)
        pending_count = total_projects - enriched_count

        # Master projects stats
        master_projects = [p for p in raw_projects if p.get('is_master_project', False)]
        master_count = len(master_projects)

        # Recent activity
        recent_enhanced = []
        if enriched_projects:
            # Sort by processed_at and take latest 5
            sorted_projects = sorted(
                enriched_projects,
                key=lambda p: p.get('document_verification', {}).get('processed_at', ''),
                reverse=True
            )[:5]
            recent_enhanced = sorted_projects

        return render_template('index.html',
            status=status,
            total_projects=total_projects,
            enriched_count=enriched_count,
            pending_count=pending_count,
            master_count=master_count,
            recent_enhanced=recent_enhanced
        )

    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/projects')
def projects():
    """Project list with search, filter, and sort capabilities."""
    try:
        # Load data
        raw_projects = load_projects_index()
        enriched_projects = load_enriched_projects()

        # Create lookup for enhanced status
        enriched_lookup = {p['id']: p for p in enriched_projects}

        # Merge data - add enhancement status to raw projects
        projects = []
        for project in raw_projects:
            project_data = project.copy()
            project_data['has_enhancement'] = project['id'] in enriched_lookup
            if project_data['has_enhancement']:
                enhanced = enriched_lookup[project['id']]
                project_data['processed_at'] = enhanced.get('document_verification', {}).get('processed_at')
                project_data['enhancement_version'] = enhanced.get('document_verification', {}).get('version')
            projects.append(project_data)

        # Apply filters
        search = request.args.get('search', '').strip()
        filter_enhanced = request.args.get('enhanced')
        filter_master = request.args.get('master')
        sort_by = request.args.get('sort', 'title')

        if search:
            projects = [p for p in projects if
                       search.lower() in p.get('title', '').lower() or
                       search.lower() in p.get('id', '').lower()]

        if filter_enhanced == 'yes':
            projects = [p for p in projects if p['has_enhancement']]
        elif filter_enhanced == 'no':
            projects = [p for p in projects if not p['has_enhancement']]

        if filter_master == 'yes':
            projects = [p for p in projects if p.get('is_master_project', False)]
        elif filter_master == 'no':
            projects = [p for p in projects if not p.get('is_master_project', False)]

        # Apply sorting
        reverse_sort = False
        if sort_by == 'title':
            projects.sort(key=lambda p: p.get('title', '').lower())
        elif sort_by == 'processed_at':
            projects.sort(key=lambda p: p.get('processed_at', ''), reverse=True)
            reverse_sort = True
        elif sort_by == 'child_count':
            projects.sort(key=lambda p: p.get('child_project_count', 0), reverse=True)
            reverse_sort = True
        elif sort_by == 'mentions':
            projects.sort(key=lambda p: p.get('total_child_mentions', 0), reverse=True)
            reverse_sort = True

        return render_template('projects.html',
            projects=projects,
            search=search,
            filter_enhanced=filter_enhanced,
            filter_master=filter_master,
            sort_by=sort_by,
            total_count=len(projects)
        )

    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/projects/<project_id>')
def project_detail(project_id):
    """Project detail view showing raw data and Document Verifier analysis."""
    try:
        # Get project from both sources
        raw_project = get_project_by_id(project_id, source='raw')
        enriched_project = get_project_by_id(project_id, source='enriched')

        if not raw_project:
            return render_template('error.html', error=f"Project {project_id} not found")

        # Prepare display data
        has_enhancement = enriched_project is not None
        document_verification = None

        if has_enhancement:
            document_verification = enriched_project.get('document_verification', {})

        # Load Reference Scanner derived references
        derived_references = load_reference_scanner_annotations_for_project(raw_project)

        return render_template('project_detail.html',
            project=raw_project,
            has_enhancement=has_enhancement,
            document_verification=document_verification,
            derived_references=derived_references,
            project_id=project_id
        )

    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/actions/run-summarize', methods=['POST'])
def run_summarize():
    """Trigger document_verifier document_verify command."""
    try:
        # Get action type
        action = request.form.get('action', 'demo')

        # Change to document_verifier directory and run command
        document_verifier_dir = Path(__file__).parent.parent / 'document_verifier'

        if action == 'live':
            cmd = ['python3', 'document_verifier.py', 'document_verify']
        else:
            cmd = ['python3', 'document_verifier.py', 'demo']

        # Run command
        result = subprocess.run(
            cmd,
            cwd=document_verifier_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Update status
        status = {
            'last_run': datetime.now().isoformat(),
            'command': ' '.join(cmd),
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr,
            'action_type': action
        }
        save_status(status)

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'Successfully ran {action} command',
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Command failed with code {result.returncode}',
                'error': result.stderr
            })

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': 'Command timed out after 5 minutes'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@app.route('/status')
def status_api():
    """API endpoint to get current system status."""
    try:
        status = load_status()
        raw_projects = load_projects_index()
        enriched_projects = load_enriched_projects()

        return jsonify({
            'status': status,
            'counts': {
                'total': len(raw_projects),
                'enriched': len(enriched_projects),
                'pending': len(raw_projects) - len(enriched_projects)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)})


if __name__ == '__main__':
    print("🌐 Starting JaxWatch Dashboard")
    print("   URL: http://localhost:5000")
    print("   Mode: Local development")
    print("   Press Ctrl+C to stop")

    app.run(host='127.0.0.1', port=5000, debug=True)