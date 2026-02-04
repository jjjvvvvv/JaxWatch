# Local LLM Extraction System (Ollama + Llama 3.1)

This project uses a local LLM (Ollama + Llama 3.1 8B) for semantic extraction, parsing, and document verification. This approach significantly improves data quality over previous regex-based heuristics.

## Key Features
- **Semantic Metadata Extraction**: Intelligently identifies meeting titles and dates from webpage text, avoiding "semantic blindness" (e.g., distinguishing a meeting date from a budget year).
- **Flexible Document Classification**: Classifies documents (Agendas, Minutes, Packets, Resolutions) based on context rather than fixed keyword matches.
- **Document Verification**: AI-powered analysis extracts explicit facts, authorization language, and financial mentions from civic documents.

## Components
- `backend/collector/dia_meeting_scraper.py`: Uses the Ollama API for page parsing and link classification.
- `document_verifier/commands/summarize.py`: Document verification and enrichment (reads cached text from `outputs/files/`, writes to `outputs/projects/projects_enriched.json`).

## Architecture Principles
- **Immutable raw data**: AI never modifies `outputs/raw/` — source metadata stays clean
- **Cached text extraction**: PDFs extracted once to `outputs/files/`, reused by all downstream processes
- **Enrichment layer**: All AI-generated content goes to `outputs/projects/projects_enriched.json`

## Requirements
- **Ollama**: Must be running locally on port 11434.
- **Model**: `llama3.1:8b` must be pulled (`ollama pull llama3.1:8b`).

## Usage

```bash
# Verify documents for a specific project
python -m document_verifier.commands.summarize --project DIA-RES-2025-01-15

# Verify all projects from a specific year
python -m document_verifier.commands.summarize --active-year 2025

# Force re-verification of already processed projects
python -m document_verifier.commands.summarize --force
```

## Performance Note
LLM-based extraction takes approximately 1-2 minutes per document, compared to milliseconds for regex. However, the resulting data is much more accurate and includes structured verification output.
