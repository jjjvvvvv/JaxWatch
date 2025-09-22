#!/usr/bin/env python3
"""
JaxWatch Admin API
Simple Flask API for admin project management
"""

import json
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from .simple_auth import SimpleAuth, require_admin_auth


class AdminAPI:
    """Admin API for JaxWatch project management"""

    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for frontend requests

        # Initialize authentication
        self.auth = SimpleAuth(self.app)

        # Data paths
        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.frontend_dir = self.project_root / "frontend"

        # Setup routes
        self.setup_routes()

    def setup_routes(self):
        """Setup all API routes"""

        @self.app.route('/api/admin/projects', methods=['GET'])
        @require_admin_auth
        def get_projects():
            """Get all projects with admin metadata"""
            try:
                projects = self.load_all_projects()
                return jsonify({
                    "projects": projects,
                    "total": len(projects),
                    "last_updated": datetime.now().isoformat()
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/admin/projects', methods=['POST'])
        @require_admin_auth
        def add_project():
            """Add a new project"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No data provided"}), 400

                # Add the new project to existing projects
                projects = self.load_all_projects()
                projects.append(data)
                self.save_projects(projects)

                return jsonify({"status": "created", "project_id": data.get('project_id')})

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/admin/projects/<project_id>', methods=['PUT'])
        @require_admin_auth
        def update_project(project_id):
            """Update a specific project"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No data provided"}), 400

                result = self.update_project_data(project_id, data)
                if result:
                    return jsonify({"status": "updated", "project_id": project_id})
                else:
                    return jsonify({"error": "Project not found"}), 404

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/admin/projects/<project_id>/flag', methods=['POST'])
        @require_admin_auth
        def toggle_project_flag(project_id):
            """Manually flag/unflag a project"""
            try:
                data = request.get_json() or {}
                flagged = data.get('flagged', True)
                reason = data.get('reason', 'Manual admin review')

                result = self.flag_project(project_id, flagged, reason)
                if result:
                    return jsonify({
                        "status": "updated",
                        "project_id": project_id,
                        "flagged": flagged,
                        "reason": reason
                    })
                else:
                    return jsonify({"error": "Project not found"}), 404

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/admin/health', methods=['GET'])
        @require_admin_auth
        def get_system_health():
            """Get system health report"""
            try:
                health_file = self.data_dir / "runtime" / "health_report.json"
                if health_file.exists():
                    with open(health_file, 'r') as f:
                        health_data = json.load(f)
                    return jsonify(health_data)
                else:
                    return jsonify({"error": "Health report not found"}), 404
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        # Serve admin static files
        @self.app.route('/admin.html')
        def serve_admin():
            """Serve admin interface"""
            return send_from_directory(self.frontend_dir, 'admin.html')

        @self.app.route('/admin.js')
        def serve_admin_js():
            """Serve admin JavaScript"""
            return send_from_directory(self.frontend_dir, 'admin.js')

        @self.app.route('/')
        def serve_index():
            """Serve main index"""
            return send_from_directory(self.frontend_dir, 'index.html')

    def load_all_projects(self):
        """Load all projects from data files"""
        projects = []

        # Load from all-projects.json
        all_projects_file = self.data_dir / "all-projects.json"
        if all_projects_file.exists():
            with open(all_projects_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    projects.extend(data)
                elif isinstance(data, dict) and 'projects' in data:
                    projects.extend(data['projects'])

        # Add admin metadata
        for project in projects:
            self.add_admin_metadata(project)

        return projects

    def add_admin_metadata(self, project):
        """Add admin-specific metadata to project"""
        project['admin_metadata'] = {
            'manually_flagged': project.get('manually_flagged', False),
            'manual_flag_reason': project.get('manual_flag_reason', ''),
            'last_edited_by': project.get('last_edited_by', ''),
            'last_edited_date': project.get('last_edited_date', ''),
            'source_verified': project.get('source_verified', False)
        }

    def update_project_data(self, project_id, updates):
        """Update project data with admin changes"""
        projects = self.load_all_projects()

        for project in projects:
            if project.get('project_id') == project_id or project.get('item_number') == project_id:
                # Update fields
                for key, value in updates.items():
                    if key not in ['project_id', 'item_number']:  # Protect ID fields
                        project[key] = value

                # Add audit trail
                project['last_edited_by'] = 'admin'
                project['last_edited_date'] = datetime.now().isoformat()

                # Save back to file
                self.save_projects(projects)
                return True

        return False

    def flag_project(self, project_id, flagged, reason):
        """Flag or unflag a project manually"""
        projects = self.load_all_projects()

        for project in projects:
            if project.get('project_id') == project_id or project.get('item_number') == project_id:
                project['manually_flagged'] = flagged
                project['manual_flag_reason'] = reason if flagged else ''
                project['last_edited_by'] = 'admin'
                project['last_edited_date'] = datetime.now().isoformat()

                # Also update the main flagged field
                if flagged:
                    project['flagged'] = True

                self.save_projects(projects)
                return True

        return False

    def save_projects(self, projects):
        """Save projects back to data file"""
        all_projects_file = self.data_dir / "all-projects.json"
        frontend_file = self.frontend_dir / "all-projects.json"

        # Save to both locations
        for file_path in [all_projects_file, frontend_file]:
            with open(file_path, 'w') as f:
                json.dump(projects, f, indent=2, default=str)

    def run(self, host='localhost', port=5000, debug=True):
        """Run the admin API server"""
        print(f"Starting JaxWatch Admin API on http://{host}:{port}")
        print(f"Admin Password: {self.auth.admin_password}")
        self.app.run(host=host, port=port, debug=debug)


def create_app():
    """Factory function to create Flask app"""
    admin_api = AdminAPI()
    return admin_api.app


if __name__ == "__main__":
    admin_api = AdminAPI()
    admin_api.run()