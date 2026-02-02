# Task Tracking
> Current work items for JaxWatch. Mark complete with verification notes.

## Current Sprint

_No active tasks._

---

## Architectural Review: 2026-02-02

### Executive Summary

JaxWatch is a well-structured civic data observatory with clear separation of concerns. However, the current architecture has **duplicate code paths for summarization**, **redundant PDF processing**, and **fragmented storage patterns** that undermine the stated "immutable raw data" principle.

**Biggest wins available:**
1. Consolidate the two summarization paths into one
2. Eliminate redundant PDF downloads
3. Create unified pipeline orchestration

---

### Critical Inefficiencies Found

#### 1. Duplicate Summarization Systems (HIGH IMPACT)

| Component | Location | Storage | Purpose |
|-----------|----------|---------|---------|
| `process_summaries.py` | `/process_summaries.py:46-65` | `outputs/raw/.../dia_board.json` | DIA packet summaries |
| `document_verifier` | `/document_verifier/commands/summarize.py:184-232` | `outputs/projects/projects_enriched.json` | Document verification |

**Problem:** Two systems doing similar work with different code, storage, and interfaces.

**Impact:**
- Summaries stored in raw data (violates immutability principle)
- Duplicate maintenance burden
- Inconsistent output formats

**Recommendation:** Consolidate into `document_verifier` as single summarization path. Store all AI outputs in enrichment layer only.

---

#### 2. Redundant PDF Processing (MEDIUM IMPACT)

**Current flow in `process_summaries.py:22-44`:**
```
URL → download PDF → pdfplumber extract → summarize → discard
```

**Already available in `outputs/files/`:**
```
PDF text cached at: outputs/files/{source}/{year}/{filename}.txt
```

**Problem:** `process_summaries.py` re-downloads and re-extracts PDFs that `pdf_extractor.py` already processed.

**Impact:** Unnecessary network calls, slower processing, wasted compute.

**Recommendation:** Use cached text files from `outputs/files/` like `document_verifier` does at line 167-171.

---

#### 3. Hardcoded Configuration (MEDIUM IMPACT)

**Location:** `process_summaries.py:20`
```python
DATA_FILE = Path("outputs/raw/dia_board/2026/dia_board.json")
```

**Problem:** Year and source hardcoded. Config system exists at `jaxwatch/config/manager.py` but isn't used.

**Recommendation:** Use `JaxWatchConfig` for all path resolution.

---

#### 4. Inconsistent LLM Integration (LOW-MEDIUM IMPACT)

| Module | LLM Function | Model |
|--------|--------------|-------|
| `process_summaries.py` | imports `_call_llm` from `dia_meeting_scraper` | llama3.1:8b |
| `document_verifier/summarize.py` | own `call_llm()` at line 23-38 | config-driven |
| `dia_meeting_scraper.py` | `_call_llm()` private function | llama3.1:8b |

**Problem:** Three separate LLM call implementations with no shared abstraction.

**Recommendation:** Create `jaxwatch/llm/client.py` as unified interface.

---

#### 5. Storage Principle Violation

**Stated principle (README-CUSTODIAL-SYSTEM.md):**
> "Raw documents never modified by AI"
> "All AI outputs append with source attribution"

**Current violation:** `process_summaries.py:104` writes `summary` field directly into raw data file.

**Impact:** Conflates source data with AI-generated content. Makes auditing difficult.

**Recommendation:** All AI outputs → `outputs/projects/` or `outputs/annotations/` only.

---

#### 6. No Pipeline Orchestration

**Current state:** Manual execution of each step:
```bash
make collect-all      # Step 1
make fetch-pdfs       # Step 2
make extract-projects # Step 3
# Then manually run document_verifier
# Then manually run reference_scanner
```

**Recommendation:** Create `jaxwatch/pipeline/orchestrator.py`:
```python
class CivicPipeline:
    def run_full_cycle(self, source=None, year=None):
        self.collect(source, year)
        self.extract_pdfs()
        self.extract_projects()
        self.verify_documents()
        self.scan_references()
```

---

#### 7. Stateless Collection

**Location:** `backend/collector/engine.py`

**Problem:** No persistent tracking of processed URLs across runs. Each run re-evaluates all links.

**Impact:** Inefficient for incremental updates; can't distinguish "new" vs "seen" documents.

**Recommendation:** Add `outputs/state/collection_manifest.json` tracking:
```json
{
  "last_full_run": "2026-02-01T...",
  "urls_processed": {"url": "timestamp", ...},
  "urls_failed": [...]
}
```

---

### Architecture Diagram (Current)

```
                     ┌─────────────────────────────────────┐
                     │     Government Websites             │
                     │  (DIA, DDRB, Council, Planning)     │
                     └──────────────┬──────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │  backend/collector/engine.py        │
                     │  (BeautifulSoup scraping)           │
                     └──────────────┬──────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ outputs/raw/    │  │ outputs/files/  │  │ outputs/projects│
    │ (metadata JSON) │  │ (extracted txt) │  │ (project index) │
    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
             │                    │                    │
             │    ┌───────────────┘                    │
             │    │ (IGNORED!)                         │
             ▼    │                                    ▼
    ┌─────────────────┐                     ┌─────────────────┐
    │process_summaries│ ──DUPLICATES──────► │document_verifier│
    │ (re-downloads!) │                     │ (uses cache)    │
    └─────────────────┘                     └─────────────────┘
             │                                        │
             ▼                                        ▼
    ┌─────────────────┐                     ┌─────────────────┐
    │ Writes to RAW!  │                     │projects_enriched│
    │ (violates arch) │                     │ (correct layer) │
    └─────────────────┘                     └─────────────────┘
```

---

### Recommended Architecture (Target)

```
                     ┌─────────────────────────────────────┐
                     │     Government Websites             │
                     └──────────────┬──────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │  CivicPipeline.orchestrator         │
                     │  (unified control plane)            │
                     └──────────────┬──────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ 1. Collect      │ ───► │ 2. Extract      │ ───► │ 3. Identify     │
│ (scrape + fetch)│      │ (PDF → text)    │      │ (projects)      │
└─────────────────┘      └─────────────────┘      └─────────────────┘
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ outputs/raw/    │      │ outputs/files/  │      │projects_index   │
│ (IMMUTABLE)     │      │ (cached text)   │      │ (base data)     │
└─────────────────┘      └─────────────────┘      └────────┬────────┘
                                    │                      │
                         ┌──────────┴──────────┐           │
                         ▼                     ▼           ▼
              ┌─────────────────┐   ┌─────────────────────────────┐
              │ jaxwatch/llm/   │   │ 4. Enrich (unified)         │
              │ (shared client) │◄──│ - verify_documents()        │
              └─────────────────┘   │ - scan_references()         │
                                    │ - generate_summaries()      │
                                    └──────────────┬──────────────┘
                                                   │
                                                   ▼
                                    ┌─────────────────────────────┐
                                    │ outputs/projects/           │
                                    │ projects_enriched.json      │
                                    │ (ALL AI outputs here)       │
                                    └─────────────────────────────┘
```

---

## Backlog

### P0 - Critical (Architecture Violations)

- [ ] **Remove summaries from raw data** - Migrate `summary` field from `outputs/raw/` to enrichment layer
- [ ] **Delete `process_summaries.py`** - Consolidate into document_verifier with cached text support

### P1 - High (Efficiency)

- [ ] **Create unified LLM client** - `jaxwatch/llm/client.py` with provider abstraction
- [ ] **Add pipeline orchestrator** - Single `make pipeline` command runs full cycle
- [ ] **Use config system everywhere** - Remove hardcoded paths

### P2 - Medium (Maintainability)

- [ ] **Add collection manifest** - Track processed URLs for incremental updates
- [ ] **Unify storage paths** - All project data through `JaxWatchConfig.paths`
- [ ] **Add scheduling support** - Cron-compatible entry point for automated runs

### P3 - Nice to Have

- [ ] **Add pipeline dry-run mode** - Preview what would be processed
- [ ] **Add telemetry/metrics** - Track processing times, success rates
- [ ] **Consider SQLite for state** - If JSON files become unwieldy

---

## Completed

- [x] **Architectural review** (2026-02-02) - Comprehensive analysis of data collection, ingestion, and summarization pipelines. Identified 7 key inefficiencies with prioritized recommendations.
