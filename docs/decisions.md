# JaxWatch Architectural Decisions

This document captures key architectural decisions to prevent drift and maintain consistency throughout development.

## Decision Log

### 1. MVP Scope Definition
**Date**: 2025-09-20
**Decision**: MVP focuses exclusively on agendas and notes data collection
**Rationale**: Clear scope prevents feature creep and ensures delivery of core functionality
**Implications**:
- No OCR, AI summaries, glossary, or blog features in MVP
- All development effort focused on data collection and basic presentation
- Advanced features deferred to post-MVP phases

### 2. Unified Schema Validation
**Date**: 2025-09-20
**Decision**: All pipelines must flow through orchestrator and validate against unified schema
**Rationale**: Ensures data consistency and prevents corruption from different sources
**Implications**:
- No direct scraper output without schema validation
- Failed validation items flagged but not dropped
- Schema changes require version migration support

### 3. Null Handling Policy
**Date**: 2025-09-20
**Decision**: Missing/invalid data written as null/unknown values with flagged=true, never dropped
**Rationale**: Preserves data integrity and enables debugging of extraction issues
**Implications**:
- All schema fields must be nullable or have defaults
- Flagged items need manual review process
- Source URLs always preserved for transparency

### 4. Orchestrator-Only Execution
**Date**: 2025-09-20
**Decision**: All scrapers called only through orchestrator, no direct standalone runs in production
**Rationale**: Ensures consistent error handling, logging, and schema validation
**Implications**:
- Individual adapters can only be run directly for development/testing
- Production deployments use single entrypoint
- Centralized health monitoring and alerting

### 5. Frontend Data Source
**Date**: 2025-09-20
**Decision**: Frontend reads from Firestore buffer, never directly from scrapers
**Rationale**: Clean separation of concerns and better performance
**Implications**:
- Orchestrator writes to Firestore after validation
- Frontend queries live data without backend dependencies
- Data consistency guaranteed through single write path

### 6. Repository Organization
**Date**: 2025-09-20
**Decision**: Clear folder separation: /frontend, /backend, /experiments, /docs
**Rationale**: Prevents confusion between working code and experiments
**Implications**:
- Working code in /backend and /frontend only
- Experimental code in /experiments (not imported by production)
- Documentation in /docs for decisions and roadmap

### 7. Alert Strategy
**Date**: 2025-09-20
**Decision**: Fail fast with immediate Slack alerts for validation failures and critical errors
**Rationale**: Early detection prevents data quality issues from accumulating
**Implications**:
- No silent failures allowed in production
- Structured alert format for easy parsing
- Alert fatigue prevented through intelligent grouping

### 8. Newspaper-First UI Philosophy
**Date**: 2025-09-20
**Decision**: Feed view is primary interface, map is secondary feature
**Rationale**: Users consume municipal data like news - chronologically and by topic
**Implications**:
- Index page optimized for browsing latest items
- Map enhances but doesn't replace feed functionality
- Content organization mirrors news site patterns

## Change Process

New decisions that introduce architectural tradeoffs must:
1. Be documented in this file with date and rationale
2. Include implications for existing and future code
3. Be approved through PR review process
4. Update roadmap.md if they affect planned development phases

## Review Schedule

This document reviewed monthly to ensure decisions remain relevant and identify any architectural drift.