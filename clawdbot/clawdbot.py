#!/usr/bin/env python3
"""
Clawdbot - JaxWatch Enhancement Tool
Entry point for running Clawdbot commands
"""

import sys
import importlib.util
from pathlib import Path


def load_command(command_name):
    """Dynamically load a command module."""
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
Clawdbot - JaxWatch Enhancement Tool

Usage:
    python clawdbot.py <command>

Available Commands:
    summarize    Enhance projects with LLM-generated summaries
    demo         Run demonstration with mock responses (no API key needed)

Examples:
    python clawdbot.py demo
    python clawdbot.py summarize

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
        return command_module.main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error running command '{command_name}': {e}")
        return 1


if __name__ == "__main__":
    exit(main())