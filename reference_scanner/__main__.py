#!/usr/bin/env python3
"""
Entry point for running reference_scanner as a module.

Usage:
    python -m reference_scanner run --source dia_board --year 2025
    python -m reference_scanner status
"""

from .reference_scanner import main

if __name__ == "__main__":
    exit(main())
