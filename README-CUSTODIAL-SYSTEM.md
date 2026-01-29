# JaxWatch Custodial System Architecture

## Overview

JaxWatch implements a strict separation of concerns for civic document processing with immutable raw data and clearly bounded AI roles.

## System Flow

```
Raw Documents → Verifier (Clawdbot) → Custodian (Molt Bot) → Views
```

### 1. Raw Documents (Immutable Source of Truth)
- **Location**: `outputs/raw/`, `outputs/files/`
- **Sources**: City websites, official document repositories
- **Content**: Unmodified PDF text, meeting minutes, resolutions, ordinances
- **Guarantee**: **Never modified by AI or processing**

### 2. Verifier (Clawdbot) - Document Analysis Agent
- **Purpose**: Verify and extract explicit information from civic documents
- **Role**: Document auditor, not summarizer
- **Input**: Raw PDF text + project metadata
- **Output**: Structured verification (Authorization, Actors, Financial details, etc.)
- **Boundaries**:
  - ✅ Quote directly from documents
  - ✅ Extract explicit facts
  - ❌ No speculation or inference
  - ❌ No summaries or narrative
- **Usage**: `python clawdbot.py document_verify --project DIA-RES-2025-12-03`

### 3. Custodian (Molt Bot) - Reference Detection Agent
- **Purpose**: Autonomous background enrichment through reference detection
- **Role**: AI teammate for slow, patient document relationship mapping
- **Input**: Extracted document text across multiple files
- **Output**: Reference annotations linking documents
- **Boundaries**:
  - ✅ Detect citations (ordinances, resolutions, amendments)
  - ✅ Extract relationship evidence
  - ✅ Confidence scoring
  - ❌ No summaries or interpretation
  - ❌ No modification of source data
- **Usage**: `python moltbot/moltbot.py run --source dia_board --year 2025`

### 4. Views (Dashboard) - Read-Only Interface
- **Purpose**: Present all data layers with clear attribution
- **Sources**: Raw projects + Clawdbot verification + Molt references
- **Guarantees**:
  - Source documents always linkable/verifiable
  - AI outputs clearly labeled as derived/non-authoritative
  - No editing of AI interpretations

## Storage Architecture

```
outputs/
├── raw/                    # Immutable scraped data
├── files/                  # Extracted PDF text (immutable)
├── projects/               # Project extraction (deterministic)
└── annotations/
    └── molt/               # Custodian-detected references (append-only)

clawdbot/
└── outputs/                # Document verification outputs (versioned)

dashboard/                  # Read-only views combining all layers
```

## Key Principles

### Data Immutability
- Raw documents are never modified by AI processing
- All AI outputs are append-only with source attribution
- Original document URLs always preserved and accessible

### Clear Boundaries
- **Clawdbot**: Document verification only (explicit facts from text)
- **Molt Bot**: Reference detection only (citations and relationships)
- **No overlap**: Each agent has distinct, non-conflicting responsibilities

### molt.bot Inspiration
Molt Bot follows molt.bot principles:
- **Local control**: Runs on your machine, no cloud dependencies
- **AI as teammate**: Autonomous but bounded custodial role
- **Persistence**: Maintains state across runs (idempotent)
- **Background operation**: Slow, careful enrichment over time

## Usage Examples

### Basic Document Verification
```bash
# Verify a specific civic document
python clawdbot.py document_verify --project DIA-RES-2025-12-03 --force

# Verify all documents from 2025
python clawdbot.py document_verify --active-year 2025
```

### Custodial Reference Detection
```bash
# Run Molt Bot on DIA Board documents from 2025
python moltbot/moltbot.py run --source dia_board --year 2025

# Check what Molt Bot has found
python moltbot/moltbot.py status

# Dry run (see what would be processed)
python moltbot/moltbot.py run --source dia_board --dry-run
```

### Dashboard Access
```bash
# Start read-only dashboard
cd dashboard && python app.py
# Visit http://localhost:5000/projects/DIA-RES-2025-12-03
```

## Output Formats

### Clawdbot Document Verification
```
Authorization
• The DIA authorizes issuance of formal Notice of Disposition on or about January 15, 2026

Actors
• Downtown Investment Authority (DIA)
• Chief Executive Officer of DIA

Financial details
• Not specified in document

[...]
```

### Molt Bot Reference Annotation
```json
{
  "type": "reference",
  "reference_type": "ordinance",
  "source_document_url": "https://dia.jacksonville.gov/cms/getattachment/...",
  "target_identifier": "ORDINANCE 2022-372-E",
  "evidence_excerpt": "pursuant to Ordinance 2022-372-E as amended",
  "confidence": "high",
  "detected_at": "2026-01-28T21:30:00.000Z"
}
```

## Safety Guarantees

1. **Raw data immutability**: No AI process can modify source documents
2. **Attribution**: All AI outputs traceable to specific source documents
3. **Deterministic pipeline**: System works without AI agents (core extraction remains functional)
4. **Idempotent operations**: Safe to re-run Molt Bot without data corruption
5. **Clear labeling**: Dashboard distinguishes between authoritative and derived data

## Agent Coordination

- **No direct communication**: Agents operate independently
- **Shared storage**: All agents read from same immutable source data
- **Append-only**: No agent overwrites another's outputs
- **Version tracking**: All outputs include processing timestamps and versions

This architecture ensures civic transparency with reliable AI assistance while maintaining the integrity and verifiability of official government documents.