#!/usr/bin/env python3
"""
JaxWatch Admin Correction Interface
Human-in-the-loop system for correcting PDF extraction errors
Principles: Simple, efficient, audit-friendly
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re

logger = logging.getLogger(__name__)

# Web framework imports
try:
    from flask import Flask, request, render_template_string, jsonify, redirect, url_for, flash, session
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

class CorrectionType(str, Enum):
    """Types of corrections that can be made"""
    PROJECT_MISSING = "project_missing"  # Human found a project that was missed
    PROJECT_DUPLICATE = "project_duplicate"  # Remove duplicate project
    PROJECT_INCORRECT = "project_incorrect"  # Fix incorrect project details
    FIELD_CORRECTION = "field_correction"  # Fix specific field value
    MEETING_INFO = "meeting_info"  # Correct meeting metadata

@dataclass
class Correction:
    """A specific correction to extracted data"""
    correction_id: str
    correction_type: CorrectionType
    target_document: str  # Document/version ID
    target_project_id: Optional[str] = None  # Specific project if applicable
    target_field: Optional[str] = None  # Specific field if applicable
    original_value: Optional[str] = None
    corrected_value: Optional[str] = None
    reason: str = ""
    corrected_by: str = "admin"
    corrected_at: datetime = None
    verified: bool = False
    verification_notes: str = ""

    def __post_init__(self):
        if self.corrected_at is None:
            self.corrected_at = datetime.now()

class CorrectionManager:
    """Manages correction workflows and audit trails"""

    def __init__(self, storage_dir: str = "data/corrections"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.corrections_file = self.storage_dir / "corrections.json"
        self.corrections: Dict[str, Dict[str, Any]] = self._load_corrections()

        self.pending_file = self.storage_dir / "pending_reviews.json"
        self.pending_reviews: List[Dict[str, Any]] = self._load_pending_reviews()

        self.logger = logging.getLogger(__name__)

    def _load_corrections(self) -> Dict[str, Dict[str, Any]]:
        """Load correction history from storage"""
        if self.corrections_file.exists():
            try:
                with open(self.corrections_file, 'r') as f:
                    data = json.load(f)
                    # Convert ISO strings back to datetime objects
                    for correction_data in data.values():
                        if 'corrected_at' in correction_data:
                            correction_data['corrected_at'] = datetime.fromisoformat(
                                correction_data['corrected_at']
                            )
                    return data
            except Exception as e:
                self.logger.error(f"Error loading corrections: {e}")
                return {}
        return {}

    def _save_corrections(self):
        """Save corrections to storage"""
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            serializable_data = {}
            for correction_id, correction_data in self.corrections.items():
                serializable_data[correction_id] = dict(correction_data)
                if 'corrected_at' in serializable_data[correction_id]:
                    serializable_data[correction_id]['corrected_at'] = (
                        serializable_data[correction_id]['corrected_at'].isoformat()
                    )

            with open(self.corrections_file, 'w') as f:
                json.dump(serializable_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving corrections: {e}")

    def _load_pending_reviews(self) -> List[Dict[str, Any]]:
        """Load pending review items"""
        if self.pending_file.exists():
            try:
                with open(self.pending_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading pending reviews: {e}")
                return []
        return []

    def _save_pending_reviews(self):
        """Save pending review items"""
        try:
            with open(self.pending_file, 'w') as f:
                json.dump(self.pending_reviews, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving pending reviews: {e}")

    def create_correction(self, correction_type: CorrectionType, target_document: str,
                         reason: str, corrected_by: str = "admin",
                         target_project_id: str = None, target_field: str = None,
                         original_value: str = None, corrected_value: str = None) -> str:
        """Create a new correction record"""

        # Generate correction ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        correction_id = f"{correction_type.value}_{timestamp}"

        correction = Correction(
            correction_id=correction_id,
            correction_type=correction_type,
            target_document=target_document,
            target_project_id=target_project_id,
            target_field=target_field,
            original_value=original_value,
            corrected_value=corrected_value,
            reason=reason,
            corrected_by=corrected_by
        )

        self.corrections[correction_id] = asdict(correction)
        self._save_corrections()

        self.logger.info(f"Created correction {correction_id} for {target_document}")
        return correction_id

    def get_document_corrections(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all corrections for a specific document"""
        corrections = []
        for correction_data in self.corrections.values():
            if correction_data['target_document'] == document_id:
                corrections.append(correction_data)

        return sorted(corrections, key=lambda x: x['corrected_at'], reverse=True)

    def apply_corrections_to_data(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all verified corrections to document data"""

        document_id = document_data.get('extraction_metadata', {}).get('source', '')
        if not document_id:
            return document_data

        corrections = self.get_document_corrections(document_id)
        verified_corrections = [c for c in corrections if c.get('verified', False)]

        if not verified_corrections:
            return document_data

        # Make a copy to avoid modifying original
        corrected_data = dict(document_data)

        for correction in verified_corrections:
            correction_type = correction['correction_type']

            if correction_type == CorrectionType.PROJECT_MISSING.value:
                # Add missing project (corrected_value should be JSON of project)
                if correction['corrected_value']:
                    try:
                        new_project = json.loads(correction['corrected_value'])
                        corrected_data.setdefault('projects', []).append(new_project)
                    except json.JSONDecodeError:
                        self.logger.error(f"Invalid project JSON in correction {correction['correction_id']}")

            elif correction_type == CorrectionType.PROJECT_DUPLICATE.value:
                # Remove duplicate project
                if correction['target_project_id']:
                    corrected_data['projects'] = [
                        p for p in corrected_data.get('projects', [])
                        if p.get('project_id') != correction['target_project_id']
                    ]

            elif correction_type == CorrectionType.FIELD_CORRECTION.value:
                # Fix specific field in specific project
                if correction['target_project_id'] and correction['target_field']:
                    for project in corrected_data.get('projects', []):
                        if project.get('project_id') == correction['target_project_id']:
                            project[correction['target_field']] = correction['corrected_value']
                            break

            elif correction_type == CorrectionType.MEETING_INFO.value:
                # Fix meeting metadata
                if correction['target_field']:
                    corrected_data.setdefault('meeting_info', {})[correction['target_field']] = correction['corrected_value']

        # Add correction metadata
        corrected_data['corrections_applied'] = len(verified_corrections)
        corrected_data['last_corrected'] = datetime.now().isoformat()

        return corrected_data

    def flag_for_review(self, document_id: str, extraction_data: Dict[str, Any],
                       reason: str, flagged_by: str = "system") -> str:
        """Flag a document for human review"""

        review_item = {
            "review_id": f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "document_id": document_id,
            "flagged_at": datetime.now().isoformat(),
            "flagged_by": flagged_by,
            "reason": reason,
            "status": "pending",
            "extraction_data": extraction_data,
            "reviewer_notes": ""
        }

        self.pending_reviews.append(review_item)
        self._save_pending_reviews()

        self.logger.info(f"Flagged document {document_id} for review: {reason}")
        return review_item["review_id"]

    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get all pending review items"""
        return [r for r in self.pending_reviews if r.get('status') == 'pending']

    def complete_review(self, review_id: str, reviewer: str, notes: str = "",
                       corrections: List[Dict[str, Any]] = None) -> bool:
        """Mark a review as completed with optional corrections"""

        for review in self.pending_reviews:
            if review['review_id'] == review_id:
                review['status'] = 'completed'
                review['completed_at'] = datetime.now().isoformat()
                review['completed_by'] = reviewer
                review['reviewer_notes'] = notes

                # Apply any corrections made during review
                if corrections:
                    for correction_data in corrections:
                        self.create_correction(**correction_data)

                self._save_pending_reviews()
                self.logger.info(f"Completed review {review_id}")
                return True

        return False

    def get_correction_stats(self) -> Dict[str, Any]:
        """Get statistics about corrections"""

        stats = {
            "total_corrections": len(self.corrections),
            "pending_reviews": len(self.get_pending_reviews()),
            "correction_types": {},
            "verified_corrections": 0,
            "last_updated": datetime.now().isoformat()
        }

        for correction_data in self.corrections.values():
            correction_type = correction_data['correction_type']
            stats["correction_types"][correction_type] = stats["correction_types"].get(correction_type, 0) + 1

            if correction_data.get('verified', False):
                stats["verified_corrections"] += 1

        return stats

def create_admin_app(correction_manager: CorrectionManager):
    """Create Flask app for admin correction interface"""

    if not FLASK_AVAILABLE:
        logger.warning("Flask not available, skipping admin interface")
        return None

    app = Flask(__name__)
    app.secret_key = 'jaxwatch-admin-corrections-dev-key'

    # Main admin interface template
    ADMIN_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>JaxWatch Admin Corrections</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { background: #f8f9fa; padding: 20px; margin-bottom: 20px; border-radius: 5px; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
            .pending { background: #fff3cd; }
            .correction { background: #e7f3ff; margin: 10px 0; padding: 15px; border-radius: 5px; }
            .btn { padding: 8px 16px; margin: 5px; text-decoration: none; border-radius: 3px; border: none; cursor: pointer; }
            .btn-primary { background: #007bff; color: white; }
            .btn-success { background: #28a745; color: white; }
            .btn-warning { background: #ffc107; color: black; }
            .btn-danger { background: #dc3545; color: white; }
            table { width: 100%; border-collapse: collapse; margin: 10px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background: #f2f2f2; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, textarea, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 3px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            .warning { background: #fff3cd; color: #856404; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔧 JaxWatch Admin Corrections</h1>
            <p>Review and correct PDF extraction errors</p>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="status {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="section">
            <h2>📊 System Statistics</h2>
            <table>
                <tr><td><strong>Total Corrections</strong></td><td>{{ stats.total_corrections }}</td></tr>
                <tr><td><strong>Pending Reviews</strong></td><td>{{ stats.pending_reviews }}</td></tr>
                <tr><td><strong>Verified Corrections</strong></td><td>{{ stats.verified_corrections }}</td></tr>
                <tr><td><strong>Last Updated</strong></td><td>{{ stats.last_updated[:19] }}</td></tr>
            </table>
        </div>

        {% if pending_reviews %}
        <div class="section pending">
            <h2>⏳ Pending Reviews ({{ pending_reviews|length }})</h2>
            {% for review in pending_reviews %}
            <div class="correction">
                <h3>Review #{{ review.review_id }}</h3>
                <p><strong>Document:</strong> {{ review.document_id }}</p>
                <p><strong>Reason:</strong> {{ review.reason }}</p>
                <p><strong>Flagged by:</strong> {{ review.flagged_by }} at {{ review.flagged_at[:19] }}</p>

                {% if review.extraction_data.projects %}
                <h4>Extracted Projects ({{ review.extraction_data.projects|length }}):</h4>
                <table style="font-size: 14px;">
                    <tr>
                        <th>Project ID</th>
                        <th>Title</th>
                        <th>Location</th>
                        <th>Type</th>
                        <th>Actions</th>
                    </tr>
                    {% for project in review.extraction_data.projects %}
                    <tr>
                        <td>{{ project.project_id or 'N/A' }}</td>
                        <td>{{ project.title or project.request or 'N/A' }}</td>
                        <td>{{ project.location or 'N/A' }}</td>
                        <td>{{ project.project_type or 'N/A' }}</td>
                        <td>
                            <a href="/correct/{{ review.review_id }}/{{ project.project_id or 'unknown' }}" class="btn btn-primary">Correct</a>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
                {% endif %}

                <div style="margin-top: 15px;">
                    <a href="/review/{{ review.review_id }}" class="btn btn-success">Complete Review</a>
                    <a href="/add_project/{{ review.review_id }}" class="btn btn-warning">Add Missing Project</a>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="section">
            <h2>🔍 Recent Corrections</h2>
            {% if corrections %}
            {% for correction in corrections[:10] %}
            <div class="correction">
                <h4>{{ correction.correction_type }} - {{ correction.corrected_at[:19] }}</h4>
                <p><strong>Document:</strong> {{ correction.target_document }}</p>
                {% if correction.target_project_id %}<p><strong>Project:</strong> {{ correction.target_project_id }}</p>{% endif %}
                {% if correction.target_field %}<p><strong>Field:</strong> {{ correction.target_field }}</p>{% endif %}
                {% if correction.original_value %}<p><strong>Original:</strong> {{ correction.original_value }}</p>{% endif %}
                {% if correction.corrected_value %}<p><strong>Corrected:</strong> {{ correction.corrected_value }}</p>{% endif %}
                <p><strong>Reason:</strong> {{ correction.reason }}</p>
                <p><strong>Status:</strong> {% if correction.verified %}✅ Verified{% else %}⏳ Pending Verification{% endif %}</p>
                {% if not correction.verified %}
                <a href="/verify/{{ correction.correction_id }}" class="btn btn-success">Verify</a>
                {% endif %}
            </div>
            {% endfor %}
            {% else %}
            <p>No corrections recorded yet.</p>
            {% endif %}
        </div>

        <div class="section">
            <h2>➕ Manual Actions</h2>
            <a href="/flag_document" class="btn btn-warning">Flag Document for Review</a>
            <a href="/create_correction" class="btn btn-primary">Create Manual Correction</a>
            <a href="/export_corrections" class="btn btn-secondary">Export Correction Log</a>
        </div>

    </body>
    </html>
    """

    @app.route('/')
    def admin_dashboard():
        stats = correction_manager.get_correction_stats()
        pending_reviews = correction_manager.get_pending_reviews()

        # Get recent corrections
        corrections = list(correction_manager.corrections.values())
        corrections.sort(key=lambda x: x['corrected_at'], reverse=True)

        return render_template_string(ADMIN_TEMPLATE,
                                    stats=stats,
                                    pending_reviews=pending_reviews,
                                    corrections=corrections)

    @app.route('/verify/<correction_id>')
    def verify_correction(correction_id):
        if correction_id in correction_manager.corrections:
            correction_manager.corrections[correction_id]['verified'] = True
            correction_manager.corrections[correction_id]['verified_at'] = datetime.now().isoformat()
            correction_manager._save_corrections()
            flash(f'Correction {correction_id} verified successfully', 'success')
        else:
            flash(f'Correction {correction_id} not found', 'error')

        return redirect(url_for('admin_dashboard'))

    @app.route('/api/stats')
    def api_stats():
        return jsonify(correction_manager.get_correction_stats())

    @app.route('/api/pending')
    def api_pending():
        return jsonify(correction_manager.get_pending_reviews())

    return app

# Command line interface
def main():
    import argparse

    parser = argparse.ArgumentParser(description='JaxWatch Admin Correction System')
    parser.add_argument('--web', action='store_true', help='Start admin web interface')
    parser.add_argument('--port', type=int, default=5002, help='Web interface port')
    parser.add_argument('--stats', action='store_true', help='Show correction statistics')
    parser.add_argument('--pending', action='store_true', help='Show pending reviews')

    args = parser.parse_args()

    # Initialize manager
    manager = CorrectionManager()

    if args.stats:
        stats = manager.get_correction_stats()
        print("🔧 Admin Correction System Statistics")
        print(f"Total Corrections: {stats['total_corrections']}")
        print(f"Pending Reviews: {stats['pending_reviews']}")
        print(f"Verified Corrections: {stats['verified_corrections']}")
        print(f"Correction Types: {stats['correction_types']}")

    elif args.pending:
        pending = manager.get_pending_reviews()
        print(f"⏳ Pending Reviews: {len(pending)}")
        for review in pending:
            print(f"  • {review['review_id']}: {review['reason']} (flagged by {review['flagged_by']})")

    elif args.web:
        if not FLASK_AVAILABLE:
            print("❌ Flask not available. Install with: pip install flask")
            return

        app = create_admin_app(manager)
        if app:
            print(f"🔧 Starting admin interface on http://localhost:{args.port}")
            print("👨‍💼 Admin correction and review interface")
            app.run(debug=True, host='0.0.0.0', port=args.port)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()