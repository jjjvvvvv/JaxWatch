#!/usr/bin/env python3
"""
JaxWatch Document Verifier Local Admin Dashboard
A read-only-first, CRM-style interface for browsing and managing projects
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for

# Add parent directory to path for JaxWatch imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from jaxwatch.api import JaxWatchCore, verify_documents
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
    """Enhanced operations dashboard with system status and operational controls."""
    try:
        # Load data
        raw_projects = load_projects_index()
        enriched_projects = load_enriched_projects()
        status = load_status()

        # Get JaxWatch stats
        core = JaxWatchCore()
        project_stats = core.get_project_stats()

        # Calculate enhanced statistics
        total_projects = len(raw_projects)
        enriched_count = len(enriched_projects)
        pending_count = total_projects - enriched_count

        # Calculate verification percentage
        verification_percentage = (enriched_count / total_projects * 100) if total_projects > 0 else 0

        # Count references
        reference_count = 0
        for project in enriched_projects:
            references = project.get('references', [])
            if isinstance(references, list):
                reference_count += len(references)

        # Calculate reference coverage
        projects_with_refs = sum(1 for p in enriched_projects if p.get('references'))
        reference_coverage = f"{(projects_with_refs / total_projects * 100):.1f}%" if total_projects > 0 else "0%"

        # Recent projects for batch operations (last 20)
        recent_projects = raw_projects[-20:] if len(raw_projects) > 20 else raw_projects

        # Enhanced recent activity
        recent_enhanced = []
        if enriched_projects:
            sorted_projects = sorted(
                enriched_projects,
                key=lambda p: p.get('document_verification', {}).get('processed_at', ''),
                reverse=True
            )[:5]
            recent_enhanced = sorted_projects

        # Active jobs
        active_jobs = [job for job in active_dashboard_jobs.values() if job['status'] == 'running']

        # Mock some additional dashboard data
        collection_last_run = "4 hours ago"
        extraction_last_run = "2 hours ago"
        total_documents = f"{len(raw_projects) * 3:,}"  # Rough estimate
        processing_rate = "~3 per minute"

        return render_template('index_enhanced.html',
            # Core statistics
            status=status,
            total_projects=total_projects,
            enriched_count=enriched_count,
            pending_count=pending_count,

            # Enhanced statistics
            verification_percentage=verification_percentage,
            reference_count=reference_count,
            reference_coverage=reference_coverage,

            # Pipeline status
            collection_last_run=collection_last_run,
            extraction_last_run=extraction_last_run,
            total_documents=total_documents,
            processing_rate=processing_rate,

            # Recent activity and operations
            recent_enhanced=recent_enhanced,
            recent_projects=recent_projects,
            active_jobs=active_jobs,

            # Legacy compatibility
            master_count=project_stats.get('dia_resolutions', 0) + project_stats.get('ddrb_cases', 0)
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
    """Trigger document verification using JaxWatch Core API."""
    try:
        # Get action type
        action = request.form.get('action', 'demo')

        start_time = datetime.now()

        if action == 'live':
            # Use real JaxWatch Core API for document verification
            core = JaxWatchCore()
            result = core.verify_documents()
            cmd_desc = "JaxWatch Core API: verify_documents()"

            if result.success:
                output = f"✅ Processed {result.projects_processed} projects\n"
                output += f"✅ Verified {result.projects_verified} projects\n"
                output += "Document verification completed successfully"
            else:
                output = f"❌ Verification failed\nErrors: {', '.join(result.errors)}"
        else:
            # Demo mode - simulate verification process
            cmd_desc = "JaxWatch Core API: demo mode"
            output = """🎭 DEMO MODE - Mock Document Verification

✅ Loading projects index...
✅ Found 142 projects for verification
✅ Processing DIA-RES-2025-12-03...
✅ Processing DDRB-2025-001...
✅ Processing DIA-RES-2025-11-15...

📊 Mock Results:
- Authorization language detected: 3/3 projects
- Financial mentions found: $2.3M in development incentives
- Actors identified: DIA Board, DDRB, Private developers

✅ Demo verification completed successfully
🛈 No actual API calls made in demo mode"""
            result = type('MockResult', (), {'success': True, 'projects_processed': 3, 'projects_verified': 3})()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Update status
        status = {
            'last_run': start_time.isoformat(),
            'command': cmd_desc,
            'success': result.success,
            'output': output,
            'error': ', '.join(getattr(result, 'errors', [])) if hasattr(result, 'errors') else '',
            'action_type': action,
            'duration_seconds': duration,
            'projects_processed': getattr(result, 'projects_processed', 0),
            'projects_verified': getattr(result, 'projects_verified', 0)
        }
        save_status(status)

        if result.success:
            return jsonify({
                'success': True,
                'message': f'Successfully completed {action} verification',
                'output': output,
                'duration': duration,
                'stats': {
                    'projects_processed': getattr(result, 'projects_processed', 0),
                    'projects_verified': getattr(result, 'projects_verified', 0)
                }
            })
        else:
            error_msg = ', '.join(getattr(result, 'errors', ['Unknown error']))
            return jsonify({
                'success': False,
                'message': f'Verification failed: {error_msg}',
                'error': error_msg
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'error': str(e)
        })


# Job management for enhanced dashboard
active_dashboard_jobs = {}
job_counter = 0


@app.route('/api/jobs/start', methods=['POST'])
def start_job():
    """Start a new job via the enhanced dashboard."""
    global job_counter
    try:
        data = request.get_json()
        task_type = data.get('task')
        params = data.get('params', {})

        job_counter += 1
        job_id = f"dash_job_{job_counter}"

        # Create job record
        job = {
            'id': job_id,
            'task': task_type,
            'params': params,
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'description': _get_job_description(task_type, params),
            'stats': {}
        }

        active_dashboard_jobs[job_id] = job

        # Start background processing
        import threading
        thread = threading.Thread(target=_execute_dashboard_job, args=(job_id,))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': f'Started {task_type} job'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/jobs/status')
def jobs_status():
    """Get status of all active jobs."""
    try:
        jobs = list(active_dashboard_jobs.values())
        return jsonify({
            'success': True,
            'jobs': jobs,
            'active_count': len([j for j in jobs if j['status'] == 'running'])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'jobs': []
        })


@app.route('/api/jobs/<job_id>/status')
def job_status(job_id):
    """Get status of a specific job."""
    try:
        job = active_dashboard_jobs.get(job_id)
        if job:
            return jsonify({
                'success': True,
                'job': job
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/config')
def api_config():
    """Show current configuration."""
    try:
        from jaxwatch.config.manager import get_config
        config = get_config()

        config_data = {
            'llm': {
                'model': config.llm.model,
                'api_url': config.llm.api_url,
                'has_api_key': bool(config.llm.api_key)
            },
            'paths': {
                'projects_index': str(config.paths.projects_index),
                'outputs_dir': str(config.paths.outputs_dir),
                'enhanced_projects': str(config.paths.enhanced_projects)
            },
            'features': {
                'enable_debug_logging': config.get_feature('enable_debug_logging'),
                'max_concurrent_jobs': config.get_feature('max_concurrent_jobs'),
                'auto_backup_interval_hours': config.get_feature('auto_backup_interval_hours')
            }
        }

        return jsonify(config_data)
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/logs')
def api_logs():
    """Show recent system logs."""
    try:
        # This would typically read from log files
        # For now, return mock log data
        logs = [
            {'timestamp': datetime.now().isoformat(), 'level': 'INFO', 'message': 'Dashboard API accessed'},
            {'timestamp': (datetime.now() - timedelta(minutes=5)).isoformat(), 'level': 'INFO', 'message': 'Project verification completed'},
            {'timestamp': (datetime.now() - timedelta(minutes=10)).isoformat(), 'level': 'DEBUG', 'message': 'Core API initialized'}
        ]

        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)})


def _get_job_description(task_type, params):
    """Get human-readable description for a job."""
    descriptions = {
        'verify_demo': 'Running demo verification',
        'verify_live': 'Running live document verification',
        'verify_batch': f"Verifying {params.get('size', 10)} projects",
        'extract': 'Extracting projects from documents',
        'scan_references': f"Scanning references ({params.get('source', 'all')} source)",
        'process_selected': f"Processing {len(params.get('project_ids', []))} selected projects",
        'export_data': f"Exporting data as {params.get('format', 'JSON')}",
        'cleanup': 'Cleaning up old data',
        'reindex': 'Rebuilding project index',
        'validate': 'Validating data integrity',
        'test_llm': 'Testing LLM connection',
        'health_check': 'Running system health check'
    }

    return descriptions.get(task_type, f"Running {task_type}")


def _execute_dashboard_job(job_id):
    """Execute a dashboard job in background."""
    job = active_dashboard_jobs.get(job_id)
    if not job:
        return

    try:
        task_type = job['task']
        params = job['params']

        # Update progress
        job['progress'] = 10

        if task_type in ['verify_demo', 'verify_live']:
            # Use existing verification logic
            action = 'demo' if task_type == 'verify_demo' else 'live'

            if action == 'live':
                core = JaxWatchCore()
                result = core.verify_documents()

                job['progress'] = 80

                if result.success:
                    job['stats'] = {
                        'processed': result.projects_processed,
                        'verified': result.projects_verified
                    }
                    job['status'] = 'completed'
                    job['result'] = f"Verified {result.projects_verified} projects"
                else:
                    job['status'] = 'failed'
                    job['error'] = ', '.join(result.errors)
            else:
                # Demo mode
                import time
                time.sleep(2)  # Simulate processing
                job['progress'] = 80
                job['stats'] = {'processed': 3, 'verified': 3}
                job['status'] = 'completed'
                job['result'] = "Demo verification completed"

        elif task_type == 'verify_batch':
            # Batch verification
            core = JaxWatchCore()
            batch_size = params.get('size', 10)
            force = params.get('force', False)

            job['progress'] = 30
            result = core.verify_documents(force=force)
            job['progress'] = 80

            job['stats'] = {
                'processed': min(result.projects_processed, batch_size),
                'verified': min(result.projects_verified, batch_size)
            }
            job['status'] = 'completed' if result.success else 'failed'

        elif task_type == 'extract':
            # Project extraction
            core = JaxWatchCore()
            year = params.get('year')

            job['progress'] = 30
            result = core.extract_projects(year=year)
            job['progress'] = 80

            job['stats'] = {
                'projects_created': result.projects_created,
                'projects_total': result.projects_total
            }
            job['status'] = 'completed' if result.success else 'failed'

        elif task_type == 'process_selected':
            # Process selected projects
            core = JaxWatchCore()
            project_ids = params.get('project_ids', [])
            force = params.get('force', False)

            job['progress'] = 30
            result = core.enrich_projects(project_ids=project_ids, force_reverify=force)
            job['progress'] = 80

            job['stats'] = {
                'processed': result.projects_processed,
                'verified': result.projects_verified,
                'references': result.references_detected
            }
            job['status'] = 'completed' if result.success else 'failed'

        else:
            # Mock other operations
            import time
            time.sleep(1)
            job['progress'] = 80
            job['status'] = 'completed'
            job['stats'] = {'completed': True}

        job['progress'] = 100
        job['completed_at'] = datetime.now().isoformat()

    except Exception as e:
        job['status'] = 'failed'
        job['error'] = str(e)
        job['progress'] = 100
        job['completed_at'] = datetime.now().isoformat()


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