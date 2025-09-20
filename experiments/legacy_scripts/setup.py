#!/usr/bin/env python3

import os
from pathlib import Path
import json
from datetime import datetime

def setup_project_structure():
    """Initialize the project directory structure"""

    print("🔧 Setting up JaxWatch project structure...")

    # Create necessary directories
    directories = [
        'data',
        'data/pdfs',
        'data/extracted',
        'scripts'
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {directory}")

    # Create initial processed files tracking
    processed_file = Path('data/processed_pdfs.json')
    if not processed_file.exists():
        initial_data = {
            'last_updated': datetime.now().isoformat(),
            'processed_files': []
        }

        with open(processed_file, 'w') as f:
            json.dump(initial_data, f, indent=2)
        print(f"📄 Created: {processed_file}")

    # Create .gitignore if it doesn't exist
    gitignore_file = Path('.gitignore')
    if not gitignore_file.exists():
        gitignore_content = """# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# Data files (comment out if you want to track them)
data/pdfs/*.pdf
*.pdf

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
"""
        with open(gitignore_file, 'w') as f:
            f.write(gitignore_content)
        print(f"📄 Created: {gitignore_file}")

    # Create requirements.txt
    requirements_file = Path('requirements.txt')
    if not requirements_file.exists():
        requirements_content = """pdfplumber>=0.11.0
requests>=2.25.0
beautifulsoup4>=4.9.0
"""
        with open(requirements_file, 'w') as f:
            f.write(requirements_content)
        print(f"📄 Created: {requirements_file}")

    print("\n✅ Project structure setup complete!")
    print("\nNext steps:")
    print("1. Initialize git repository: git init")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run extraction: python extract_projects_robust.py")
    print("4. Open index.html in browser to view results")

if __name__ == "__main__":
    setup_project_structure()