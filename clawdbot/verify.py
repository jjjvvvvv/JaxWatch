#!/usr/bin/env python3
"""
Clawdbot Verification Script
Validates that the implementation meets the plan requirements
"""

import json
import os
from pathlib import Path


def verify_file_structure():
    """Verify all required files exist."""
    clawdbot_dir = Path(__file__).parent
    required_files = [
        "config.yaml",
        "clawdbot.py",
        "requirements.txt",
        "README.md",
        "commands/summarize.py",
        "commands/demo.py",
        "prompts/summarize_item.md"
    ]

    missing_files = []
    for file_path in required_files:
        full_path = clawdbot_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)

    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    else:
        print("✅ All required files present")
        return True


def verify_data_paths():
    """Verify input data exists."""
    clawdbot_dir = Path(__file__).parent
    input_path = clawdbot_dir / "../admin_ui/data/projects_index.json"

    if not input_path.exists():
        print(f"❌ Input data file not found: {input_path}")
        return False

    try:
        with open(input_path, 'r') as f:
            projects = json.load(f)

        print(f"✅ Input data loaded: {len(projects)} projects")

        # Check for master projects
        master_projects = [p for p in projects if p.get("is_master_project", False)]
        print(f"✅ Found {len(master_projects)} master projects")

        return True
    except Exception as e:
        print(f"❌ Error reading input data: {e}")
        return False


def verify_demo_output():
    """Verify demo produces expected output."""
    clawdbot_dir = Path(__file__).parent
    demo_output = clawdbot_dir / "demo_output.json"

    if not demo_output.exists():
        print("❌ Demo output not found - run 'python3 clawdbot.py demo' first")
        return False

    try:
        with open(demo_output, 'r') as f:
            enhanced_projects = json.load(f)

        if len(enhanced_projects) == 0:
            print("❌ Demo output is empty")
            return False

        # Verify structure
        for project in enhanced_projects:
            if "clawdbot_analysis" not in project:
                print(f"❌ Project {project.get('id')} missing clawdbot_analysis")
                return False

            analysis = project["clawdbot_analysis"]
            required_fields = ["enhanced_summary", "processed_at", "version"]
            for field in required_fields:
                if field not in analysis:
                    print(f"❌ Missing field '{field}' in clawdbot_analysis")
                    return False

        print(f"✅ Demo output verified: {len(enhanced_projects)} enhanced projects")
        print(f"   Sample enhancement: {enhanced_projects[0]['clawdbot_analysis']['enhanced_summary'][:80]}...")
        return True

    except Exception as e:
        print(f"❌ Error reading demo output: {e}")
        return False


def verify_configuration():
    """Verify configuration is valid."""
    try:
        import yaml
        clawdbot_dir = Path(__file__).parent
        config_path = clawdbot_dir / "config.yaml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        required_keys = ["llm_provider", "llm_model", "llm_api_key_env", "input_path", "output_path"]
        for key in required_keys:
            if key not in config:
                print(f"❌ Missing config key: {key}")
                return False

        print("✅ Configuration valid")
        return True

    except Exception as e:
        print(f"❌ Error reading configuration: {e}")
        return False


def main():
    """Run all verification checks."""
    print("🔍 Clawdbot Verification")
    print("=" * 50)

    checks = [
        ("File Structure", verify_file_structure),
        ("Configuration", verify_configuration),
        ("Data Paths", verify_data_paths),
        ("Demo Output", verify_demo_output)
    ]

    all_passed = True
    for check_name, check_func in checks:
        print(f"\n{check_name}:")
        if not check_func():
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All verification checks passed!")
        print("\nTo use clawdbot:")
        print("1. Demo mode:  python3 clawdbot.py demo")
        print("2. Live mode:  export GROQ_API_KEY=your-key && python3 clawdbot.py summarize")
        return 0
    else:
        print("❌ Some verification checks failed")
        return 1


if __name__ == "__main__":
    exit(main())