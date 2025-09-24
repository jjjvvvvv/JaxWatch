# JaxWatch

JaxWatch is a collection-first municipal observatory.

This MVP focuses purely on collecting raw links and metadata from known sources. No parsing or geocoding — just transparent, repeatable collection with JSON outputs and simple verification.

## What gets collected
- Per-source crawl with simple pattern matching and a few special cases
- Outputs are written as JSON to `outputs/raw/<source_id>/<YYYY-MM-DD>.json`
- Logs are written to `outputs/logs/<YYYY-MM-DD>.log`

Each JSON contains:
- metadata: `source`, `source_name`, `timestamp`, `pages_fetched`, `links_discovered`
- `items`: list of discovered links with fields `url`, `filename`, `title`, `source`, `source_name`, `date_collected`, `status`, `http_status`, `seen_before`

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

Verify health and required fields of the JSON files:
```
make verify-outputs
# or with args:
python3 -m backend.tools.verify_outputs --source planning_commission --date 2025-09-24
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
- The collector does not persist cross-day state; `seen_before` is included but not persisted across runs.
