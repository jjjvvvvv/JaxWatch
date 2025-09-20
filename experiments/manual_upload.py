#!/usr/bin/env python3
"""
JaxWatch Manual Upload Interface
Simple web interface for uploading irregular PDFs and managing document processing
Principles: Simple, secure, auditable
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib
import shutil
import tempfile

# Web framework imports
try:
    from flask import Flask, request, render_template_string, jsonify, redirect, url_for, flash
    from werkzeug.utils import secure_filename
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from extract_projects_robust import ProjectExtractor
from enhanced_pdf_processor import EnhancedPDFProcessor, process_pdf_with_fallback
from deduplication_system import DeduplicationManager, register_processed_document
from version_tracking import VersionTracker, register_document_version
from admin_correction import CorrectionManager
from municipal_schema import CivicProject, migrate_from_legacy

logger = logging.getLogger(__name__)

class ManualUploadManager:
    """Manages manual PDF uploads and processing queue"""

    def __init__(self, upload_dir: str = "data/manual_uploads",
                 processed_dir: str = "data/processed_uploads"):
        self.upload_dir = Path(upload_dir)
        self.processed_dir = Path(processed_dir)
        self.queue_file = self.upload_dir / "processing_queue.json"
        self.logger = logging.getLogger(__name__)

        # Initialize deduplication manager
        self.deduplication_manager = DeduplicationManager()

        # Initialize version tracker
        self.version_tracker = VersionTracker()

        # Initialize correction manager
        self.correction_manager = CorrectionManager()

        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # Initialize processing queue
        self.processing_queue = self._load_queue()

    def _load_queue(self) -> List[Dict[str, Any]]:
        """Load processing queue from file"""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading queue: {e}")
                return []
        return []

    def _save_queue(self):
        """Save processing queue to file"""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(self.processing_queue, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving queue: {e}")

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file for deduplication"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def is_duplicate(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if file has already been processed"""
        for item in self.processing_queue:
            if item.get('file_hash') == file_hash:
                return item
        return None

    def validate_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Validate uploaded PDF file"""
        validation = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "file_size": 0,
            "page_count": 0
        }

        try:
            # Check file exists
            if not file_path.exists():
                validation["errors"].append("File does not exist")
                return validation

            # Check file size
            file_size = file_path.stat().st_size
            validation["file_size"] = file_size

            if file_size == 0:
                validation["errors"].append("File is empty")
                return validation

            if file_size > 50 * 1024 * 1024:  # 50MB limit
                validation["errors"].append("File too large (>50MB)")
                return validation

            # Check if it's actually a PDF
            with open(file_path, 'rb') as f:
                header = f.read(5)
                if not header.startswith(b'%PDF-'):
                    validation["errors"].append("Not a valid PDF file")
                    return validation

            # Use enhanced PDF processor for validation
            try:
                processor = EnhancedPDFProcessor()
                validation_result = processor._validate_pdf_file(file_path)

                if not validation_result["valid"]:
                    validation["errors"].extend(validation_result["errors"])
                    validation["warnings"].extend(validation_result["warnings"])
                    return validation

                validation["page_count"] = validation_result["page_count"]

                # Quick text extraction test
                text_result = processor._extract_text_based(file_path)
                if text_result["success"]:
                    validation["warnings"].append(f"Text extraction quality: {text_result['quality_score']:.2f}")
                else:
                    validation["warnings"].append("Text extraction challenging - OCR may be needed")

            except Exception as e:
                validation["errors"].append(f"Error validating PDF: {str(e)}")
                return validation

            validation["valid"] = True

        except Exception as e:
            validation["errors"].append(f"Validation error: {str(e)}")

        return validation

    def add_to_queue(self, file_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add file to processing queue"""

        try:
            # Validate the PDF
            validation = self.validate_pdf(file_path)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": "PDF validation failed",
                    "validation": validation
                }

            # Calculate file hash for basic deduplication
            file_hash = self.calculate_file_hash(file_path)

            # Check for basic file duplicates first
            basic_duplicate = self.is_duplicate(file_hash)
            if basic_duplicate:
                return {
                    "success": False,
                    "error": "Duplicate file already processed",
                    "duplicate": basic_duplicate
                }

            # Advanced deduplication check using enhanced PDF processing
            try:
                # Quick PDF processing for deduplication
                pdf_result = process_pdf_with_fallback(file_path)
                if pdf_result.success:
                    # Check for document-level duplication
                    duplicate_check = self.deduplication_manager.check_document(
                        file_path, pdf_result.text_content, metadata
                    )

                    if duplicate_check.is_duplicate and duplicate_check.confidence >= 0.8:
                        return {
                            "success": False,
                            "error": f"Duplicate document detected ({duplicate_check.duplicate_type})",
                            "duplicate_type": duplicate_check.duplicate_type,
                            "confidence": duplicate_check.confidence,
                            "reasons": duplicate_check.reasons,
                            "existing_entry": duplicate_check.existing_entry
                        }
                    elif duplicate_check.duplicate_type == 'potential_amendment':
                        # Log potential amendment but allow upload
                        validation["warnings"].append(
                            f"Potential amendment of existing document (confidence: {duplicate_check.confidence:.2f})"
                        )
                        validation["warnings"].extend(duplicate_check.reasons)
                else:
                    validation["warnings"].append("Could not perform advanced deduplication check")

            except Exception as e:
                validation["warnings"].append(f"Advanced deduplication check failed: {str(e)}")
                self.logger.warning(f"Deduplication check failed: {e}")

            # Generate secure filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if FLASK_AVAILABLE:
                secure_name = secure_filename(file_path.name)
            else:
                # Simple filename sanitization without Flask
                secure_name = "".join(c for c in file_path.name if c.isalnum() or c in ".-_")
            final_filename = f"{timestamp}_{secure_name}"
            final_path = self.upload_dir / final_filename

            # Move file to upload directory
            shutil.move(str(file_path), str(final_path))

            # Create queue entry
            queue_entry = {
                "id": len(self.processing_queue) + 1,
                "filename": final_filename,
                "original_name": file_path.name,
                "file_path": str(final_path),
                "file_hash": file_hash,
                "file_size": validation["file_size"],
                "page_count": validation["page_count"],
                "uploaded_at": datetime.now().isoformat(),
                "status": "pending",
                "metadata": metadata,
                "validation": validation,
                "processing_attempts": 0,
                "last_error": None
            }

            self.processing_queue.append(queue_entry)
            self._save_queue()

            self.logger.info(f"Added file to processing queue: {final_filename}")

            return {
                "success": True,
                "queue_entry": queue_entry
            }

        except Exception as e:
            self.logger.error(f"Error adding file to queue: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def process_queue_item(self, item_id: int) -> Dict[str, Any]:
        """Process a single item from the queue"""

        # Find the item
        item = None
        for queue_item in self.processing_queue:
            if queue_item["id"] == item_id:
                item = queue_item
                break

        if not item:
            return {"success": False, "error": "Item not found in queue"}

        if item["status"] != "pending":
            return {"success": False, "error": f"Item already {item['status']}"}

        try:
            # Update status
            item["status"] = "processing"
            item["processing_attempts"] += 1
            item["processing_started"] = datetime.now().isoformat()
            self._save_queue()

            # Extract projects from PDF using enhanced processor
            file_path = Path(item["file_path"])

            # First, use enhanced PDF processor to get robust text extraction
            pdf_result = process_pdf_with_fallback(file_path)

            if not pdf_result.success:
                item["status"] = "failed"
                item["last_error"] = "Enhanced PDF processing failed"
                item["processing_completed"] = datetime.now().isoformat()
                item["pdf_processing_errors"] = pdf_result.errors
                item["pdf_processing_warnings"] = pdf_result.warnings
                self._save_queue()

                return {
                    "success": False,
                    "error": "Enhanced PDF processing failed",
                    "pdf_errors": pdf_result.errors,
                    "pdf_warnings": pdf_result.warnings
                }

            # Now use the project extractor with the enhanced text
            extractor = ProjectExtractor()

            # Use the enhanced text extraction directly
            result = extractor.extract_projects_from_text(
                pdf_result.text_content,
                f"enhanced_pdf:{file_path.name}"
            )

            # Add enhanced processing metadata
            if result:
                result["enhanced_processing"] = {
                    "method_used": pdf_result.method_used,
                    "quality_score": pdf_result.quality_score,
                    "text_length": len(pdf_result.text_content),
                    "processing_time": pdf_result.processing_time,
                    "warnings": pdf_result.warnings
                }

            if result is None:
                item["status"] = "failed"
                item["last_error"] = "PDF extraction failed"
                item["processing_completed"] = datetime.now().isoformat()
                self._save_queue()

                return {
                    "success": False,
                    "error": "PDF extraction failed",
                    "extraction_errors": extractor.errors
                }

            # Save extracted data
            output_file = self.processed_dir / f"extracted_{item['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

            # Register document version for tracking
            try:
                # Determine document title and description
                title = item["metadata"].get("title", item["original_name"])
                description = item["metadata"].get("notes", "")
                if not description:
                    description = f"{item['metadata'].get('document_type', 'Document')} from {item['metadata'].get('department', 'Unknown Department')}"

                # Register version
                version_id = self.version_tracker.register_version(
                    title=title,
                    description=description,
                    content_hash=pdf_result.text_content[:32] if pdf_result.text_content else "",  # Simple content hash
                    projects=result.get("projects", []),
                    processing_metadata=item["metadata"],
                    filename=item["original_name"]
                )

                item["version_id"] = version_id

            except Exception as e:
                result["warnings"].append(f"Version tracking registration failed: {str(e)}")
                self.logger.warning(f"Failed to register version: {e}")

            # Register document and projects for deduplication
            try:
                doc_id, project_ids = register_processed_document(
                    file_path,
                    pdf_result.text_content,
                    item["metadata"],
                    result.get("projects", [])
                )

                item["deduplication_doc_id"] = doc_id
                item["deduplication_project_ids"] = project_ids

            except Exception as e:
                result["warnings"].append(f"Deduplication registration failed: {str(e)}")
                self.logger.warning(f"Failed to register for deduplication: {e}")

            # Check if document should be flagged for review
            should_flag = False
            flag_reasons = []

            # Flag if PDF quality is low
            if pdf_result.quality_score < 0.5:
                should_flag = True
                flag_reasons.append(f"Low PDF quality score: {pdf_result.quality_score:.2f}")

            # Flag if OCR was used (higher chance of errors)
            if pdf_result.method_used == "ocr":
                should_flag = True
                flag_reasons.append("Document processed using OCR - may contain recognition errors")

            # Flag if many extraction errors
            if len(extractor.errors) > 0:
                should_flag = True
                flag_reasons.append(f"Extraction errors: {len(extractor.errors)}")

            # Flag if no projects found when expected
            if len(result.get("projects", [])) == 0 and item["metadata"].get("document_type") == "agenda":
                should_flag = True
                flag_reasons.append("No projects found in agenda document")

            # Flag if too many warnings
            if len(extractor.warnings) > 10:
                should_flag = True
                flag_reasons.append(f"High number of extraction warnings: {len(extractor.warnings)}")

            if should_flag:
                try:
                    review_id = self.correction_manager.flag_for_review(
                        document_id=item["version_id"] if "version_id" in item else item["filename"],
                        extraction_data=result,
                        reason="; ".join(flag_reasons),
                        flagged_by="quality_check_system"
                    )
                    item["flagged_for_review"] = review_id
                    result["flagged_for_review"] = review_id
                    result["warnings"].append(f"Document flagged for review: {'; '.join(flag_reasons)}")
                except Exception as e:
                    result["warnings"].append(f"Failed to flag for review: {str(e)}")
                    self.logger.warning(f"Failed to flag document for review: {e}")

            # Update queue item
            item["status"] = "completed"
            item["processing_completed"] = datetime.now().isoformat()
            item["output_file"] = str(output_file)
            item["projects_extracted"] = len(result.get("projects", []))
            item["extraction_warnings"] = extractor.warnings
            item["extraction_errors"] = extractor.errors
            self._save_queue()

            # Move processed file
            processed_file = self.processed_dir / item["filename"]
            shutil.move(str(file_path), str(processed_file))
            item["file_path"] = str(processed_file)
            self._save_queue()

            self.logger.info(f"Successfully processed {item['filename']}: {item['projects_extracted']} projects")

            return {
                "success": True,
                "projects_extracted": item["projects_extracted"],
                "output_file": str(output_file),
                "warnings": extractor.warnings,
                "errors": extractor.errors
            }

        except Exception as e:
            # Update status on error
            item["status"] = "failed"
            item["last_error"] = str(e)
            item["processing_completed"] = datetime.now().isoformat()
            self._save_queue()

            self.logger.error(f"Error processing {item['filename']}: {e}")

            return {
                "success": False,
                "error": str(e)
            }

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current status of processing queue"""

        status_counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}

        for item in self.processing_queue:
            status_counts[item.get("status", "unknown")] += 1

        return {
            "total_items": len(self.processing_queue),
            "status_counts": status_counts,
            "queue": self.processing_queue
        }

    def retry_failed_item(self, item_id: int) -> Dict[str, Any]:
        """Retry processing a failed item"""

        for item in self.processing_queue:
            if item["id"] == item_id and item["status"] == "failed":
                item["status"] = "pending"
                item["last_error"] = None
                self._save_queue()

                return {"success": True, "message": "Item queued for retry"}

        return {"success": False, "error": "Item not found or not failed"}

    def delete_queue_item(self, item_id: int) -> Dict[str, Any]:
        """Delete an item from the queue"""

        for i, item in enumerate(self.processing_queue):
            if item["id"] == item_id:
                # Clean up files
                file_path = Path(item["file_path"])
                if file_path.exists():
                    file_path.unlink()

                if "output_file" in item:
                    output_path = Path(item["output_file"])
                    if output_path.exists():
                        output_path.unlink()

                # Remove from queue
                self.processing_queue.pop(i)
                self._save_queue()

                return {"success": True, "message": "Item deleted"}

        return {"success": False, "error": "Item not found"}

    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get deduplication system statistics"""
        return self.deduplication_manager.get_deduplication_stats()

    def get_version_stats(self) -> Dict[str, Any]:
        """Get version tracking statistics"""
        return self.version_tracker.get_version_stats()

    def get_document_history(self, version_id: str) -> List[Dict[str, Any]]:
        """Get version history for a document"""
        return self.version_tracker.get_version_history(version_id)

    def get_correction_stats(self) -> Dict[str, Any]:
        """Get admin correction statistics"""
        return self.correction_manager.get_correction_stats()

    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get pending review items"""
        return self.correction_manager.get_pending_reviews()

# Flask web interface (optional)
def create_upload_app(upload_manager: ManualUploadManager):
    """Create Flask app for manual upload interface"""

    if not FLASK_AVAILABLE:
        logger.warning("Flask not available, skipping web interface")
        return None

    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'jaxwatch-dev-key-change-in-production')

    # Template for upload interface
    UPLOAD_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>JaxWatch Manual Upload</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .warning { background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .btn { padding: 5px 10px; margin: 2px; text-decoration: none; border-radius: 3px; }
            .btn-primary { background-color: #007bff; color: white; }
            .btn-danger { background-color: #dc3545; color: white; }
            .btn-secondary { background-color: #6c757d; color: white; }
            form { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>🏛️ JaxWatch Manual Upload</h1>
        <p>Upload irregular PDFs for processing (agendas, meeting minutes, special reports)</p>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="status {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <form method="post" enctype="multipart/form-data">
            <h3>Upload New PDF</h3>

            <p><label>PDF File:</label><br>
            <input type="file" name="pdf_file" accept=".pdf" required></p>

            <p><label>Source Department:</label><br>
            <select name="department" required>
                <option value="">Select Department</option>
                <option value="planning_commission">Planning Commission</option>
                <option value="city_council">City Council</option>
                <option value="development_services">Development Services</option>
                <option value="public_works">Public Works</option>
                <option value="parks_recreation">Parks & Recreation</option>
                <option value="other">Other</option>
            </select></p>

            <p><label>Document Type:</label><br>
            <select name="document_type" required>
                <option value="">Select Type</option>
                <option value="agenda">Meeting Agenda</option>
                <option value="minutes">Meeting Minutes</option>
                <option value="special_report">Special Report</option>
                <option value="amendment">Amendment/Correction</option>
                <option value="other">Other</option>
            </select></p>

            <p><label>Meeting Date (if applicable):</label><br>
            <input type="date" name="meeting_date"></p>

            <p><label>Notes:</label><br>
            <textarea name="notes" rows="3" cols="50" placeholder="Any additional context or special instructions"></textarea></p>

            <p><input type="submit" value="Upload & Queue for Processing" class="btn btn-primary"></p>
        </form>

        <h3>Processing Queue</h3>
        {% if queue_status %}
            <p><strong>Total Items:</strong> {{ queue_status.total_items }} |
               <strong>Pending:</strong> {{ queue_status.status_counts.pending }} |
               <strong>Processing:</strong> {{ queue_status.status_counts.processing }} |
               <strong>Completed:</strong> {{ queue_status.status_counts.completed }} |
               <strong>Failed:</strong> {{ queue_status.status_counts.failed }}</p>

            {% if queue_status.queue %}
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Filename</th>
                        <th>Department</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Uploaded</th>
                        <th>Projects</th>
                        <th>Actions</th>
                    </tr>
                    {% for item in queue_status.queue %}
                    <tr>
                        <td>{{ item.id }}</td>
                        <td>{{ item.original_name }}</td>
                        <td>{{ item.metadata.department if item.metadata else 'N/A' }}</td>
                        <td>{{ item.metadata.document_type if item.metadata else 'N/A' }}</td>
                        <td>{{ item.status }}</td>
                        <td>{{ item.uploaded_at[:16] }}</td>
                        <td>{{ item.projects_extracted if item.projects_extracted else 'N/A' }}</td>
                        <td>
                            {% if item.status == 'pending' %}
                                <a href="/process/{{ item.id }}" class="btn btn-primary">Process</a>
                            {% elif item.status == 'failed' %}
                                <a href="/retry/{{ item.id }}" class="btn btn-secondary">Retry</a>
                            {% endif %}
                            <a href="/delete/{{ item.id }}" class="btn btn-danger" onclick="return confirm('Delete this item?')">Delete</a>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            {% endif %}
        {% endif %}

        <p><a href="/queue" class="btn btn-secondary">Refresh Queue Status</a></p>
    </body>
    </html>
    """

    @app.route('/', methods=['GET', 'POST'])
    def upload_form():
        if request.method == 'POST':
            try:
                # Check if file was uploaded
                if 'pdf_file' not in request.files:
                    flash('No file uploaded', 'error')
                    return redirect(request.url)

                file = request.files['pdf_file']
                if file.filename == '':
                    flash('No file selected', 'error')
                    return redirect(request.url)

                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    file.save(temp_file.name)
                    temp_path = Path(temp_file.name)

                # Collect metadata
                metadata = {
                    "department": request.form.get('department'),
                    "document_type": request.form.get('document_type'),
                    "meeting_date": request.form.get('meeting_date'),
                    "notes": request.form.get('notes'),
                    "uploaded_by": "manual_interface",
                    "upload_timestamp": datetime.now().isoformat()
                }

                # Add to processing queue
                result = upload_manager.add_to_queue(temp_path, metadata)

                if result["success"]:
                    flash(f'File uploaded successfully! Queue ID: {result["queue_entry"]["id"]}', 'success')
                else:
                    flash(f'Upload failed: {result["error"]}', 'error')

            except Exception as e:
                flash(f'Error processing upload: {str(e)}', 'error')

            return redirect(url_for('upload_form'))

        # GET request - show form and queue status
        queue_status = upload_manager.get_queue_status()
        return render_template_string(UPLOAD_TEMPLATE, queue_status=queue_status)

    @app.route('/process/<int:item_id>')
    def process_item(item_id):
        result = upload_manager.process_queue_item(item_id)

        if result["success"]:
            flash(f'Processing completed! {result["projects_extracted"]} projects extracted.', 'success')
            if result.get("warnings"):
                flash(f'Warnings: {"; ".join(result["warnings"])}', 'warning')
        else:
            flash(f'Processing failed: {result["error"]}', 'error')

        return redirect(url_for('upload_form'))

    @app.route('/retry/<int:item_id>')
    def retry_item(item_id):
        result = upload_manager.retry_failed_item(item_id)

        if result["success"]:
            flash('Item queued for retry', 'success')
        else:
            flash(f'Retry failed: {result["error"]}', 'error')

        return redirect(url_for('upload_form'))

    @app.route('/delete/<int:item_id>')
    def delete_item(item_id):
        result = upload_manager.delete_queue_item(item_id)

        if result["success"]:
            flash('Item deleted', 'success')
        else:
            flash(f'Delete failed: {result["error"]}', 'error')

        return redirect(url_for('upload_form'))

    @app.route('/queue')
    def queue_status():
        return redirect(url_for('upload_form'))

    @app.route('/api/queue')
    def api_queue_status():
        return jsonify(upload_manager.get_queue_status())

    return app

# Command line interface
def main():
    import argparse

    parser = argparse.ArgumentParser(description='JaxWatch Manual Upload Manager')
    parser.add_argument('--web', action='store_true', help='Start web interface')
    parser.add_argument('--port', type=int, default=5000, help='Web interface port')
    parser.add_argument('--process-queue', action='store_true', help='Process all pending items')
    parser.add_argument('--status', action='store_true', help='Show queue status')
    parser.add_argument('--dedup-stats', action='store_true', help='Show deduplication statistics')
    parser.add_argument('--version-stats', action='store_true', help='Show version tracking statistics')
    parser.add_argument('--correction-stats', action='store_true', help='Show correction system statistics')
    parser.add_argument('--pending-reviews', action='store_true', help='Show pending review items')

    args = parser.parse_args()

    # Initialize manager
    manager = ManualUploadManager()

    if args.status:
        status = manager.get_queue_status()
        print("📋 Manual Upload Queue Status")
        print(f"Total Items: {status['total_items']}")
        for status_type, count in status['status_counts'].items():
            print(f"  {status_type.title()}: {count}")

        if status['queue']:
            print("\n📄 Queue Items:")
            for item in status['queue']:
                print(f"  #{item['id']}: {item['original_name']} ({item['status']})")

    elif args.process_queue:
        print("🔄 Processing all pending items...")
        for item in manager.processing_queue:
            if item['status'] == 'pending':
                print(f"Processing #{item['id']}: {item['original_name']}")
                result = manager.process_queue_item(item['id'])
                if result['success']:
                    print(f"  ✅ Success: {result['projects_extracted']} projects")
                else:
                    print(f"  ❌ Failed: {result['error']}")

    elif args.dedup_stats:
        stats = manager.get_deduplication_stats()
        print("🔍 Deduplication System Statistics")
        print(f"📄 Documents tracked: {stats['document_fingerprints']}")
        print(f"🏗️  Projects tracked: {stats['project_signatures']}")
        print(f"📁 Storage directory: {stats['storage_dir']}")
        print(f"🕐 Last updated: {stats['last_updated']}")

    elif args.version_stats:
        stats = manager.get_version_stats()
        print("📋 Version Tracking Statistics")
        print(f"📄 Total versions: {stats['total_versions']}")
        print(f"🔗 Document lineages: {stats['total_lineages']}")
        print(f"📊 Version types: {stats['version_types']}")
        print(f"📈 Version statuses: {stats['version_statuses']}")
        print(f"🕐 Last updated: {stats['last_updated']}")

    elif args.correction_stats:
        stats = manager.get_correction_stats()
        print("🔧 Correction System Statistics")
        print(f"📝 Total corrections: {stats['total_corrections']}")
        print(f"⏳ Pending reviews: {stats['pending_reviews']}")
        print(f"✅ Verified corrections: {stats['verified_corrections']}")
        print(f"📊 Correction types: {stats['correction_types']}")
        print(f"🕐 Last updated: {stats['last_updated']}")

    elif args.pending_reviews:
        pending = manager.get_pending_reviews()
        print(f"⏳ Pending Reviews: {len(pending)}")
        if pending:
            for review in pending:
                print(f"  • {review['review_id']}: {review['reason']}")
                print(f"    Document: {review['document_id']}")
                print(f"    Flagged by: {review['flagged_by']} at {review['flagged_at'][:19]}")
                if review.get('extraction_data', {}).get('projects'):
                    print(f"    Projects: {len(review['extraction_data']['projects'])}")
                print()
        else:
            print("No pending reviews.")

    elif args.web:
        if not FLASK_AVAILABLE:
            print("❌ Flask not available. Install with: pip install flask")
            return

        app = create_upload_app(manager)
        if app:
            print(f"🌐 Starting web interface on http://localhost:{args.port}")
            print("📁 Upload irregular PDFs for processing")
            app.run(debug=True, host='0.0.0.0', port=args.port)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()