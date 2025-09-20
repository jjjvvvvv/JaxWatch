#!/usr/bin/env python3
"""
Firestore Client for JaxWatch
Handles writing validated municipal data to Firestore
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class FirestoreClient:
    """Client for writing municipal data to Firestore"""

    def __init__(self):
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'jaxwatch-dev')
        self.collection_name = 'municipal_items'
        self._db = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Firestore client with error handling"""
        try:
            # Try to import and initialize Firestore
            from google.cloud import firestore
            self._db = firestore.Client(project=self.project_id)
            logger.info(f"✅ Firestore client initialized for project: {self.project_id}")
        except ImportError:
            logger.warning("⚠️ Google Cloud Firestore not installed - using local fallback")
            self._db = None
        except Exception as e:
            logger.warning(f"⚠️ Firestore initialization failed: {e} - using local fallback")
            self._db = None

    def write_items(self, items: List[Dict[str, Any]], source_id: str) -> bool:
        """
        Write validated items to Firestore or local storage
        Returns True if successful, False otherwise
        """
        if not items:
            logger.info("No items to write")
            return True

        if self._db:
            return self._write_to_firestore(items, source_id)
        else:
            return self._write_to_local_storage(items, source_id)

    def _write_to_firestore(self, items: List[Dict[str, Any]], source_id: str) -> bool:
        """Write items to actual Firestore"""
        try:
            collection_ref = self._db.collection(self.collection_name)
            batch = self._db.batch()

            for item in items:
                # Create document ID from source and item data
                doc_id = self._generate_document_id(item, source_id)
                doc_ref = collection_ref.document(doc_id)

                # Add metadata
                item_with_metadata = {
                    **item,
                    'written_to_firestore_at': datetime.now(),
                    'source_id': source_id,
                    'document_id': doc_id
                }

                batch.set(doc_ref, item_with_metadata)

            # Commit batch write
            batch.commit()
            logger.info(f"✅ Written {len(items)} items to Firestore collection '{self.collection_name}'")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to write to Firestore: {e}")
            # Fallback to local storage
            return self._write_to_local_storage(items, source_id)

    def _write_to_local_storage(self, items: List[Dict[str, Any]], source_id: str) -> bool:
        """Fallback: write items to local JSON files"""
        try:
            # Create output directory
            output_dir = Path("data/outputs")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f"{source_id}_{timestamp}.json"

            # Prepare data with metadata
            output_data = {
                "source_id": source_id,
                "timestamp": datetime.now().isoformat(),
                "total_items": len(items),
                "items": items
            }

            # Write to file
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)

            logger.info(f"💾 Written {len(items)} items to local file: {output_file}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to write to local storage: {e}")
            return False

    def _generate_document_id(self, item: Dict[str, Any], source_id: str) -> str:
        """Generate unique document ID for Firestore"""
        # Use combination of source, date, and item identifier
        date_str = item.get('date', datetime.now().strftime('%Y-%m-%d'))
        item_id = item.get('item_number') or item.get('title', '')[:20]

        # Clean and combine
        clean_item_id = ''.join(c for c in item_id if c.isalnum() or c in '-_')
        doc_id = f"{source_id}_{date_str}_{clean_item_id}"

        return doc_id[:100]  # Firestore document ID limit

    def read_items(self, source_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Read items from Firestore for testing/debugging"""
        if not self._db:
            logger.warning("Firestore not available for reading")
            return []

        try:
            collection_ref = self._db.collection(self.collection_name)

            if source_id:
                query = collection_ref.where('source_id', '==', source_id).limit(limit)
            else:
                query = collection_ref.limit(limit)

            docs = query.stream()
            items = [doc.to_dict() for doc in docs]

            logger.info(f"📖 Read {len(items)} items from Firestore")
            return items

        except Exception as e:
            logger.error(f"❌ Failed to read from Firestore: {e}")
            return []


# Global client instance
_firestore_client = None


def get_firestore_client() -> FirestoreClient:
    """Get global Firestore client instance"""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = FirestoreClient()
    return _firestore_client


def write_municipal_items(items: List[Dict[str, Any]], source_id: str) -> bool:
    """Convenience function for writing municipal items"""
    client = get_firestore_client()
    return client.write_items(items, source_id)


if __name__ == "__main__":
    # Test the Firestore client
    test_items = [
        {
            "board": "Test Board",
            "date": "2025-09-20",
            "title": "Test agenda item",
            "url": "https://test.example.com",
            "flagged": False
        }
    ]

    success = write_municipal_items(test_items, "test_source")
    print(f"Test write successful: {success}")