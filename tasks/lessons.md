# Lessons Learned
> Compounding memory for JaxWatch development. Updated after corrections, insights, or mistakes.

## Project-Specific Patterns

### Storage Architecture
- **Raw data is immutable**: `outputs/raw/` should NEVER be modified by AI processes
- **AI outputs go to enrichment layer**: All LLM-generated content → `outputs/projects/projects_enriched.json`
- **Text cache exists**: Extracted PDF text is at `outputs/files/{source}/{year}/{filename}.txt` — don't re-download

### Key Files to Know
- `jaxwatch/api/core.py` — Central API, use `JaxWatchCore` class for all operations
- `jaxwatch/config/manager.py` — Configuration system, use `get_config()` for paths
- `document_verifier/commands/summarize.py` — The "correct" summarization path (uses cached text)
- `process_summaries.py` — DEPRECATED, violates architecture (re-downloads PDFs, writes to raw)

### Data Flow
```
Collection → outputs/raw/ (metadata only)
PDF extraction → outputs/files/ (text cache)
Project identification → outputs/projects/projects_index.json
AI enrichment → outputs/projects/projects_enriched.json
```

## Common Pitfalls to Avoid

1. **Don't write to raw data** — The `outputs/raw/` directory is for source metadata only
2. **Don't re-download PDFs** — Text is cached in `outputs/files/`, use it
3. **Don't hardcode paths** — Use `JaxWatchConfig.paths` from config manager
4. **Don't create new LLM functions** — Three exist already, need consolidation first

## Best Practices Discovered

1. **Use `document_verifier` for all summarization** — It correctly uses cached text and writes to enrichment layer
2. **Follow custodial AI principles** — Document verifier extracts explicit facts only, no speculation
3. **Reference scanner is append-only** — Annotations stored separately with attribution
4. **JaxWatchCore is the API** — Route all operations through it, not direct subprocess calls
