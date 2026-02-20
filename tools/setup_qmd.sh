#!/usr/bin/env bash
# Setup QMD collection for JaxWatch meeting documents.
# Run this once after installing QMD: bun install -g github:tobi/qmd
set -euo pipefail

DOCS_DIR="/Users/jjjvvvvv/Desktop/JaxWatch/outputs/files"

if ! command -v qmd &>/dev/null; then
    echo "Error: qmd not found. Install with: bun install -g github:tobi/qmd"
    exit 1
fi

echo "Adding JaxWatch documents collection..."
qmd collection add "$DOCS_DIR" --name jaxwatch-docs

echo "Building embeddings (this may take a few minutes)..."
qmd embed

echo "Done. Test with: qmd query 'Starbucks'"
