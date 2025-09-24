.PHONY: help collect-all collect-source admin-view verify-outputs show-logs

# Default target
help:
	@echo "JaxWatch — collection-first municipal observatory"
	@echo ""
	@echo "Commands:"
	@echo "  collect-all      Run all sources and verify outputs"
	@echo "  collect-source   Run a single source: make collect-source name=<id|Name>"
	@echo "  admin-view       Start minimal admin (http://localhost:5010)"
	@echo "  verify-outputs   Validate outputs/raw JSON (doc_type, required fields)"
	@echo "  show-logs        Print logs: make show-logs date=YYYY-MM-DD"

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
	@echo "🗂️  Starting admin view at http://localhost:5010"
	python3 -m backend.collector.admin_app --port 5010

verify-outputs:
	@echo "🔎 Verifying outputs/raw health..."
	python3 -m backend.tools.verify_outputs $(ARGS)

show-logs:
	@if [ -z "$(date)" ]; then \
		echo "Usage: make show-logs date=YYYY-MM-DD"; \
		exit 2; \
	fi
	@echo "📜 Logs for $(date):"
	@if [ -f outputs/logs/$(date).log ]; then cat outputs/logs/$(date).log; else echo "No log file for $(date)"; fi
