#!/usr/bin/env python3
"""
Start the JaxWatch Admin API Server
Simple script to run the admin interface
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables if not already set
if not os.getenv('ADMIN_PASSWORD'):
    os.environ['ADMIN_PASSWORD'] = 'admin123'  # Default for development

if not os.getenv('SECRET_KEY'):
    os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

# Import and run the admin API
try:
    from backend.admin.api import AdminAPI

    print("Starting JaxWatch Admin Interface...")
    print(f"Admin Password: {os.getenv('ADMIN_PASSWORD')}")
    print("Navigate to: http://localhost:5000/admin.html")
    print("Press Ctrl+C to stop the server")

    admin_api = AdminAPI()
    admin_api.run(host='localhost', port=5000, debug=True)

except ImportError as e:
    print(f"Error importing admin API: {e}")
    print("Make sure Flask and Flask-CORS are installed:")
    print("pip install flask flask-cors")
    sys.exit(1)
except KeyboardInterrupt:
    print("\nShutting down admin server...")
    sys.exit(0)
except Exception as e:
    print(f"Error starting admin server: {e}")
    sys.exit(1)