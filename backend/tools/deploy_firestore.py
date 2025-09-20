#!/usr/bin/env python3
"""
Deploy Firestore configuration and test connectivity
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def test_firestore_connection():
    """Test Firestore connection and permissions"""
    try:
        from google.cloud import firestore

        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            print("❌ GOOGLE_CLOUD_PROJECT environment variable not set")
            return False

        print(f"🔗 Testing connection to Firestore project: {project_id}")

        # Initialize client
        db = firestore.Client(project=project_id)

        # Test write permissions with a test document
        test_collection = db.collection('_test_connection')
        test_doc = test_collection.document('test')

        test_data = {
            'test': True,
            'timestamp': firestore.SERVER_TIMESTAMP
        }

        # Try to write
        test_doc.set(test_data)
        print("✅ Write test successful")

        # Try to read
        doc = test_doc.get()
        if doc.exists:
            print("✅ Read test successful")
        else:
            print("⚠️ Document not found after write")

        # Clean up test document
        test_doc.delete()
        print("✅ Delete test successful")

        # Test the actual collection we'll use
        municipal_collection = db.collection('municipal_items')
        print(f"✅ Municipal items collection accessible: {municipal_collection.id}")

        return True

    except ImportError:
        print("❌ google-cloud-firestore not installed")
        print("   Install with: pip install google-cloud-firestore")
        return False

    except Exception as e:
        print(f"❌ Firestore connection failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check GOOGLE_CLOUD_PROJECT environment variable")
        print("   2. Verify GOOGLE_APPLICATION_CREDENTIALS points to valid service account")
        print("   3. Ensure service account has Firestore permissions")
        print("   4. Check that Firestore is enabled in the project")
        return False


def check_environment():
    """Check required environment variables and credentials"""
    print("🔍 Checking environment configuration...")

    # Check project ID
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    if project_id:
        print(f"✅ GOOGLE_CLOUD_PROJECT: {project_id}")
    else:
        print("❌ GOOGLE_CLOUD_PROJECT not set")

    # Check credentials
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_path:
        if os.path.exists(creds_path):
            print(f"✅ GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")

            # Validate JSON
            try:
                with open(creds_path) as f:
                    creds = json.load(f)
                    print(f"   Service account: {creds.get('client_email', 'unknown')}")
                    print(f"   Project ID: {creds.get('project_id', 'unknown')}")
            except Exception as e:
                print(f"   ⚠️ Invalid credentials file: {e}")
        else:
            print(f"❌ Credentials file not found: {creds_path}")
    else:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not set")

    # Check Firebase configuration files
    config_files = [
        'firebase.json',
        'firestore.rules',
        'firestore.indexes.json'
    ]

    print("\n📄 Checking Firebase configuration files...")
    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✅ {config_file}")
        else:
            print(f"❌ {config_file} not found")


def main():
    """Main deployment check function"""
    print("🔥 JaxWatch Firestore Deployment Check")
    print("=" * 50)

    check_environment()
    print()

    if test_firestore_connection():
        print("\n🎉 Firestore deployment is ready!")
        print("\nNext steps:")
        print("1. Run the municipal observatory: python -m backend.core.municipal_observatory")
        print("2. Check Firestore console for data: https://console.firebase.google.com")
        print("3. Deploy Firebase rules: firebase deploy --only firestore")
    else:
        print("\n❌ Firestore deployment needs configuration")
        print("\nSee docs/firestore-deployment.md for setup instructions")


if __name__ == "__main__":
    main()