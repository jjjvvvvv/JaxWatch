.PHONY: help collect-all collect-source admin-view verify-outputs show-logs fetch-pdfs extract-projects reset-projects inspect-project test-pdf test-project slack-digest copy-projects-json deploy-admin pipeline schedule manifest-stats

# Default target
help:
	@echo "JaxWatch — collection-first municipal observatory"
	@echo ""
	@echo "Commands:"
	@echo "  pipeline         Run full data cycle (collect → extract → enrich)"
	@echo "  schedule         Run scheduled pipeline (cron-compatible)"
	@echo "  collect-all      Run all sources and verify outputs"
	@echo "  collect-source   Run a single source: make collect-source name=<id|Name>"
	@echo "  admin-view       Preview static admin UI (http://localhost:8005/admin.html)"
	@echo "  verify-outputs   Validate outputs/raw JSON (doc_type, required fields)"
	@echo "  fetch-pdfs       Download and extract text from PDFs"
	@echo "  extract-projects Scan text files and update projects index"
	@echo "  inspect-project  Print all mentions for a project id=<ID>"
	@echo "  manifest-stats   Show collection manifest statistics"
	@echo "  show-logs        Print logs: make show-logs date=YYYY-MM-DD"

pipeline:
	@echo "🚀 Running full JaxWatch pipeline"
	python3 -m jaxwatch.pipeline.orchestrator $(ARGS)

schedule:
	@echo "⏰ Running scheduled pipeline"
	python3 -m jaxwatch.scheduler $(ARGS)

manifest-stats:
	@echo "📊 Collection manifest statistics"
	@python3 -c "from jaxwatch.state import get_manifest; import json; print(json.dumps(get_manifest().get_stats(), indent=2))"

collect-all:
	@echo "📥 Collecting all sources (collection-first)"
	python3 -m backend.collector.engine --config backend/collector/sources.yaml
	$(MAKE) verify-outputs

collect-source:
	@if [ -z "$(name)" ]; then \
		echo "Usage: make collect-source name=<id|Name>"; \
		exit 2; \
	fi
	@echo "📥 Collecting source: $(name)"
	python3 -m backend.collector.engine --config backend/collector/sources.yaml --source "$(name)"

admin-view:
	@if [ ! -f outputs/projects/projects_index.json ]; then \
		echo "ERROR: outputs/projects/projects_index.json not found. Run extraction first."; \
		exit 1; \
	fi
	@mkdir -p admin_ui/data
	cp outputs/projects/projects_index.json admin_ui/data/projects_index.json
	@if [ -f outputs/projects/extracted_accountability.json ]; then \
		cp outputs/projects/extracted_accountability.json admin_ui/data/extracted_accountability.json; \
		echo "📁 Copied outputs/projects/extracted_accountability.json -> admin_ui/data/extracted_accountability.json"; \
	fi
	@echo "📁 Copied outputs/projects/projects_index.json -> admin_ui/data/projects_index.json"
	@echo "🛠️  Serving static admin UI at http://localhost:8005/admin.html"
	@echo "    (Ctrl+C to stop when finished)"
	python3 -m http.server 8005 --directory admin_ui

verify-outputs:
	@echo "🔎 Verifying outputs/raw health..."
	python3 -m backend.tools.verify_outputs $(ARGS)

fetch-pdfs:
	@echo "📄 Processing artifacts per source policy (reference_only/download/parse_then_discard)..."
	python3 -m backend.tools.pdf_extractor $(ARGS)

extract-projects:
	@echo "🏗️  Extracting candidate projects from text..."
	python3 -m backend.tools.extract_projects $(ARGS)

reset-projects:
	@echo "♻️  Resetting projects index and re-extracting..."
	rm -f outputs/projects/projects_index.json
	python3 -m backend.tools.extract_projects --reset

inspect-project:
	@if [ -z "$(id)" ]; then \
		echo "Usage: make inspect-project id=<project_id_or_substring>"; \
		exit 2; \
	fi
	@echo "🔎 Inspecting project: $(id)"
	python3 -m backend.tools.inspect_project --id "$(id)"

test-pdf:
	@if [ -z "$(file)" ]; then \
		echo "Usage: make test-pdf file=path/to/example.pdf"; \
		exit 2; \
	fi
	@echo "🧪 Extracting single PDF: $(file)"
	python3 -m backend.tools.pdf_extractor --file "$(file)"

test-project:
	@if [ -z "$(file)" ]; then \
		echo "Usage: make test-project file=path/to/example.pdf.txt"; \
		exit 2; \
	fi
	@echo "🧪 Extracting projects from single text: $(file)"
	python3 -m backend.tools.extract_projects --file "$(file)"

show-logs:
	@if [ -z "$(date)" ]; then \
		echo "Usage: make show-logs date=YYYY-MM-DD"; \
		exit 2; \
	fi
	@echo "📜 Logs for $(date):"
	@if [ -f outputs/logs/$(date).log ]; then cat outputs/logs/$(date).log; else echo "No log file for $(date)"; fi

slack-digest:
	@echo "🧵 Posting Slack digest (set SLACK_WEBHOOK_URL and ADMIN_URL, or pass ARGS=--dry-run)"
	python3 -m backend.tools.slack_digest $(ARGS)

copy-projects-json:
	@if [ ! -f outputs/projects/projects_index.json ]; then \
		echo "ERROR: outputs/projects/projects_index.json not found. Run extraction first."; \
		exit 1; \
	fi
	@mkdir -p admin_ui/data
	cp outputs/projects/projects_index.json admin_ui/data/projects_index.json
	@if [ -f outputs/projects/extracted_accountability.json ]; then \
		cp outputs/projects/extracted_accountability.json admin_ui/data/extracted_accountability.json; \
		echo "📁 Copied outputs/projects/extracted_accountability.json -> admin_ui/data/extracted_accountability.json"; \
	fi
	@echo "📁 Copied outputs/projects/projects_index.json -> admin_ui/data/projects_index.json"

deploy-admin:
	@if [ ! -f outputs/projects/projects_index.json ]; then \
		echo "ERROR: outputs/projects/projects_index.json not found. Run extraction first."; \
		exit 1; \
	fi
	@mkdir -p admin_ui/data
	cp outputs/projects/projects_index.json admin_ui/data/projects_index.json
	@if [ -f outputs/projects/extracted_accountability.json ]; then \
		cp outputs/projects/extracted_accountability.json admin_ui/data/extracted_accountability.json; \
		echo "📁 Copied outputs/projects/extracted_accountability.json -> admin_ui/data/extracted_accountability.json"; \
	fi
	@echo "📁 Copied outputs/projects/projects_index.json -> admin_ui/data/projects_index.json"
	@echo "🚀 Deploying admin_ui/ with Vercel"
	vercel --prod --cwd admin_ui
