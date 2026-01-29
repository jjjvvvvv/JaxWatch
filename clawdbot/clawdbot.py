#!/usr/bin/env python3
"""
Clawdbot - JaxWatch Document Verification Tool
Entry point for running document verification commands
"""

import sys
import importlib.util
from pathlib import Path


def load_command(command_name):
    """Dynamically load a command module."""
    # Handle command aliases
    if command_name == "document_verify":
        command_name = "summarize"

    command_path = Path(__file__).parent / "commands" / f"{command_name}.py"

    if not command_path.exists():
        print(f"Error: Command '{command_name}' not found")
        return None

    spec = importlib.util.spec_from_file_location(f"commands.{command_name}", command_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def print_help():
    """Print help information."""
    print("""
Clawdbot - JaxWatch Document Verification Tool

Usage:
    python clawdbot.py <command> [options]

Available Commands:
    document_verify  Verify civic documents with AI analysis (alias: summarize)
    demo            Run demonstration with mock responses (no API key needed)

Document Verification Options:
    --project <ID>       Process only the specified project ID
    --force              Ignore "already annotated" check and reprocess
    --active-year <YEAR> Filter projects where latest_activity_date.year == YEAR

Examples:
    python clawdbot.py demo
    python clawdbot.py document_verify
    python clawdbot.py document_verify --active-year 2026
    python clawdbot.py document_verify --project DIA-RES-2025-12-03 --force

For more information about JaxWatch, visit:
https://github.com/your-repo/jaxwatch
""")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_help()
        return 1

    command_name = sys.argv[1]

    if command_name in ["-h", "--help", "help"]:
        print_help()
        return 0

    # Load and run the command
    command_module = load_command(command_name)
    if command_module is None:
        return 1

    if not hasattr(command_module, 'main'):
        print(f"Error: Command '{command_name}' does not have a main() function")
        return 1

    try:
        # Pass remaining command-line arguments to the command module
        return command_module.main(sys.argv[2:])
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error running command '{command_name}': {e}")
        return 1


if __name__ == "__main__":
    exit(main())