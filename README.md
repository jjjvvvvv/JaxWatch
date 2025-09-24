# JaxWatch

JaxWatch is a collection-first municipal observatory.

This MVP focuses purely on collecting raw links and metadata from known sources. No parsing or geocoding — just transparent, repeatable collection with JSON outputs and simple verification.

## What gets collected
- Per-source crawl with simple pattern matching and a few special cases
- Year-based storage: `outputs/raw/<source_id>/<year>/<source_id>.json`
  - Each run loads the current year's file, de-duplicates by URL, and appends new items
  - `seen_before` is preserved and set to `true` if an existing URL is re-seen in a later run
- Logs are written to `outputs/logs/<YYYY-MM-DD>.log`

Each JSON contains:
- metadata: `source`, `source_name`, `year`, `updated_at`
- `items`: list of discovered links with fields:
  - `url`, `filename`, `title`, `source`, `source_name`, `date_collected`, `status`, `http_status`, `seen_before`, `doc_type`

## Document classification (doc_type)
- City Council (Legistar): from query param `M=` in URL
  - `M=A` → `agenda`, `M=M` → `minutes`, `M=E2` → `addendum`, `M=E3` → `amendments`, `M=IC` → `calendar_invite`, else `other`
- Planning Commission: substring matching
  - `meeting-agenda` or `PC MEETING AGENDA` → `agenda`
  - `results` or `Results Agenda` → `results`
  - `staff` or `filedrop.coj.net` → `staff_reports`
  - else `other`
- DDRB: substring matching
  - contains `agenda` → `agenda`, `packet` → `packet`, `minutes` → `minutes`, else `other`
- Capital Projects: always `gis_layer`

## Run collection

Use the Makefile commands:

- `make collect-all` — runs all sources defined in `backend/collector/sources.yaml` and then verifies outputs
- `make collect-source name=<id|Name>` — runs a single source

Example:
```
make collect-all
make collect-source name=planning_commission
```

## Verify outputs

Verify required fields (including `doc_type`) and summarize by doc_type:
```
make verify-outputs
# or with args:
python3 -m backend.tools.verify_outputs --source planning_commission --date 2025
```

## Admin view

Lightweight admin for browsing collected files:
```
make admin-view
# open http://localhost:5010
```

## Configuration

- Sources are defined in `backend/collector/sources.yaml`
- Collector module: `backend/collector/engine.py`
- Admin app: `backend/collector/admin_app.py`
- Output verifier: `backend/tools/verify_outputs.py`

## Frontend

Static frontend lives under `frontend/`. It remains unchanged and can be served by any static server. The collector does not write to the frontend.

## Notes

- Legacy observatory pipelines, schemas, and advanced parsing have been removed in this MVP.
- The collector maintains a per-year store and preserves `seen_before` across runs within the same year.
