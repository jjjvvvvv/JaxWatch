# Local LLM Extraction System (Ollama + Llama 3.1)

This project has been updated to use a local LLM (Ollama + Llama 3.1 8B) for semantic extraction and parsing of meeting data. This approach significantly improves data quality over previous regex-based heuristics.

## Key Features
- **Semantic Metadata Extraction**: Intelligently identifies meeting titles and dates from webpage text, avoiding "semantic blindness" (e.g., distinguishing a meeting date from a budget year).
- **Flexible Document Classification**: Classifies documents (Agendas, Minutes, Packets, Resolutions) based on context rather than fixed keyword matches.
- **Automated PDF Summarization**: Includes tools to download and summarize the first 50 pages of meeting packets, extracting key project names, dollar amounts, and resolutions.

## Components
- `backend/collector/dia_meeting_scraper.py`: Refactored to use the Ollama API for page parsing and link classification.
- `backend/collector/admin_app.py`: Updated to display LLM-generated summaries in the admin dashboard.
- `process_summaries.py`: A standalone script to bulk-process existing items and generate content summaries.

## Requirements
- **Ollama**: Must be running locally on port 11434.
- **Model**: `llama3.1:8b` must be pulled (`ollama pull llama3.1:8b`).

## Performance Note
LLM-based extraction takes approximately 1-2 minutes per meeting page, compared to milliseconds for the previous system. However, the resulting data is much more accurate and enriched with content summaries.
