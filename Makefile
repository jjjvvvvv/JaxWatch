.PHONY: setup install extract update serve clean help observatory test-observatory observatory-update observatory-test

# Default target
help:
	@echo "JaxWatch - Municipal Data Observatory"
	@echo ""
	@echo "🏛️  OBSERVATORY COMMANDS (New Architecture):"
	@echo "  observatory         - Run full municipal data observatory update"
	@echo "  observatory-test    - Test observatory functionality"
	@echo "  test-observatory    - Alias for observatory-test"
	@echo ""
	@echo "🏥 HEALTH MONITORING:"
	@echo "  health-status       - Show system health overview"
	@echo "  health-web          - Start health monitoring dashboard"
	@echo "  health-report       - Export detailed health report"
	@echo ""
	@echo "🔧 ENHANCED PROCESSING:"
	@echo "  upload-web          - Manual PDF upload interface"
	@echo "  admin-web           - Admin correction interface"
	@echo "  upload-status       - Show upload queue status"
	@echo ""
	@echo "🏛️ THREE PILLARS DATA:"
	@echo "  update-all-pillars  - Update private dev & public projects data"
	@echo "  show-project-stats  - Show current project distribution"
	@echo ""
	@echo "📊 LEGACY COMMANDS (Planning Commission Only):"
	@echo "  setup      - Initialize project structure"
	@echo "  install    - Install Python dependencies"
	@echo "  extract    - Extract data from sample PDF"
	@echo "  fetch      - Fetch latest agendas from Jacksonville website"
	@echo "  process    - Process any new PDFs"
	@echo "  update     - Update website data files"
	@echo "  serve      - Start local development server"
	@echo "  clean      - Clean up generated files"
	@echo ""
	@echo "🚀 Quick starts:"
	@echo "  NEW:    make install && make observatory && make serve"
	@echo "  Legacy: make setup && make install && make extract && make serve"

# Initialize project structure
setup:
	@echo "🔧 Setting up project structure..."
	python3 scripts/setup.py

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	pip3 install -r requirements.txt

# Extract data from sample PDF
extract:
	@echo "🔍 Extracting data from sample PDF..."
	python3 experiments/extract_projects_robust.py

# Fetch latest agendas
fetch:
	@echo "🌐 Fetching latest agendas..."
	python3 scripts/fetch_latest_agendas.py

# Process new PDFs
process:
	@echo "🔄 Processing new PDFs..."
	python3 scripts/process_new_pdfs.py

# Update website data
update: process
	@echo "📊 Updating website data..."
	python3 scripts/update_website_data.py

# Start local development server
serve:
	@echo "🚀 Starting local server at http://localhost:8000"
	@echo "Press Ctrl+C to stop"
	cd frontend && python3 -m http.server 8000

# Clean up generated files
clean:
	@echo "🧹 Cleaning up..."
	rm -rf data/extracted/*.json
	rm -rf data/pdfs/*.pdf
	rm -f frontend/all-projects.json
	rm -f summary.json
	rm -f extracted-*.json

# Full update pipeline
pipeline: fetch process update
	@echo "✅ Full update pipeline completed"

# Run everything for a fresh start
fresh: clean setup install extract
	@echo "🎉 Fresh setup completed! Run 'make serve' to view the site."

# =============================================================================
# NEW OBSERVATORY ARCHITECTURE COMMANDS
# =============================================================================

# Run full municipal data observatory update
observatory:
	@echo "🏛️  Running Municipal Data Observatory..."
	python3 -m backend.core.municipal_observatory

# Run observatory tests
observatory-test:
	@echo "🧪 Testing Municipal Observatory..."
	python3 test_observatory.py

# Alias for observatory-test
test-observatory: observatory-test

# Install observatory dependencies
observatory-deps:
	@echo "📦 Installing observatory dependencies..."
	pip3 install pydantic aiohttp beautifulsoup4

# Observatory setup (includes deps)
observatory-setup: install observatory-deps
	@echo "✅ Observatory setup complete!"

# Full observatory development cycle
observatory-dev: observatory-setup observatory-test observatory
	@echo "🚀 Observatory development cycle complete!"

# Clean observatory-specific files
observatory-clean:
	@echo "🧹 Cleaning observatory files..."
	rm -f test_report.json
	rm -f temp_geocoding.json
	rm -f data/observatory_*.json

# Show observatory status
observatory-status:
	@echo "🔍 Observatory Status:"
	@python3 -c "from municipal_observatory import MunicipalObservatory; \
	observatory = MunicipalObservatory(); \
	print('Data sources configured:', len(observatory.config.data_sources)); \
	enabled = [s for s in observatory.config.data_sources if s.enabled]; \
	print('Data sources enabled:', len(enabled)); \
	[print('  -', source.name, '(' + source.update_frequency + ')') for source in enabled]"

# Update only specific data source
observatory-update-planning:
	@echo "📊 Updating Planning Commission only..."
	python3 -c "import asyncio; from planning_commission_adapter import PlanningCommissionAdapter; from municipal_observatory import DataSourceConfig; \
	async def main(): \
		config = DataSourceConfig('planning_commission', 'PlanningCommissionAdapter', True, 'on_demand'); \
		class MockObs: \
			def __init__(self): self.config = type('obj', (object,), {'default_delay_seconds': 1.0})(); \
		adapter = PlanningCommissionAdapter(config, MockObs()); \
		projects = await adapter.fetch_data(); \
		print(f'Fetched {len(projects)} planning commission projects'); \
	asyncio.run(main())"

# Development helper - watch for changes and re-test
observatory-watch:
	@echo "👀 Watching for changes (requires entr)..."
	@echo "Install entr with: brew install entr"
	ls *.py | entr -c make observatory-test

# =============================================================================
# MANUAL UPLOAD AND ENHANCED PROCESSING COMMANDS
# =============================================================================

# Manual upload interface commands
upload-status:
	@echo "📋 Manual upload queue status:"
	python3 experiments/manual_upload.py --status

upload-process:
	@echo "🔄 Processing all pending uploads:"
	python3 experiments/manual_upload.py --process-queue

upload-web:
	@echo "🌐 Starting manual upload web interface:"
	python3 experiments/manual_upload.py --web --port 5001

upload-dedup-stats:
	@echo "🔍 Deduplication system statistics:"
	python3 experiments/manual_upload.py --dedup-stats

upload-version-stats:
	@echo "📋 Version tracking statistics:"
	python3 experiments/manual_upload.py --version-stats

upload-correction-stats:
	@echo "🔧 Correction system statistics:"
	python3 experiments/manual_upload.py --correction-stats

upload-pending-reviews:
	@echo "⏳ Pending review items:"
	python3 experiments/manual_upload.py --pending-reviews

admin-web:
	@echo "🔧 Starting admin correction interface:"
	python3 experiments/admin_correction.py --web --port 5002

# Enhanced PDF processing test
test-enhanced-pdf:
	@echo "🧪 Testing enhanced PDF processing:"
	python3 experiments/enhanced_pdf_processor.py experiments/sample-pc-agenda-10-03-24.pdf --verbose

# Test deduplication system
test-deduplication:
	@echo "🔍 Testing deduplication system:"
	python3 experiments/deduplication_system.py

# Test version tracking system
test-version-tracking:
	@echo "📋 Testing version tracking system:"
	python3 version_tracking.py

# Clean enhanced processing data
clean-enhanced:
	@echo "🧹 Cleaning enhanced processing data..."
	rm -rf data/manual_uploads/
	rm -rf data/processed_uploads/
	rm -rf data/deduplication/

# Full enhanced processing setup
enhanced-setup: install upload-dedup-stats
	@echo "✅ Enhanced processing system ready!"

# =============================================================================
# SOURCE HEALTH MONITORING COMMANDS (advanced; gated)
# =============================================================================

# Set ADVANCED=1 or HEALTH_MODULE=experiments.advanced.source_health_monitor to enable
ADVANCED ?= 0
HEALTH_MODULE ?= $(if $(filter 1 yes true on,$(ADVANCED)),experiments.advanced.source_health_monitor,backend.common.source_health_monitor)

# Show system health status
health-status:
	@echo "🏥 Checking system health status:"
	python3 -m $(HEALTH_MODULE) --status

# Show detailed metrics for specific source
health-source:
	@echo "📊 Source health metrics (specify SOURCE=name):"
	@if [ -z "$(SOURCE)" ]; then echo "Usage: make health-source SOURCE=planning_commission"; exit 1; fi
	python3 -m $(HEALTH_MODULE) --source $(SOURCE)

# Export health report
health-report:
	@echo "📋 Exporting health report:"
	python3 -m $(HEALTH_MODULE) --export data/health_report.json

# Start health monitoring web dashboard
health-web:
	@echo "🌐 Starting health dashboard:"
	python3 -m $(HEALTH_MODULE) --web --port 5003

# Clean up old health data
health-cleanup:
	@echo "🧹 Cleaning up old health data (30+ days):"
	python3 -m $(HEALTH_MODULE) --cleanup 30

# Quick health check (for daily monitoring)
health-check:
	@echo "⚡ Quick health check:"
	@python3 -m $(HEALTH_MODULE) --status | grep -E "(Overall Status|Critical Sources)" || echo "No critical issues detected"

# =============================================================================
# THREE PILLARS DATA COLLECTION
# =============================================================================

# Update all three pillars data and refresh website
update-all-pillars:
	@echo "🏛️ Updating all three pillars data..."
	@python3 -c "import asyncio; import json; from datetime import datetime; from private_development_adapter import PrivateDevelopmentAdapter; from public_projects_adapter import PublicProjectsAdapter; from municipal_observatory import DataSourceConfig; async def main(): dev_config = DataSourceConfig('private_development', 'PrivateDevelopmentAdapter', True, 'daily'); public_config = DataSourceConfig('public_projects', 'PublicProjectsAdapter', True, 'weekly'); class MockObs: def __init__(self): self.config = type('obj', (object,), {'default_delay_seconds': 1.0})(); mock_obs = MockObs(); dev_adapter = PrivateDevelopmentAdapter(dev_config, mock_obs); public_adapter = PublicProjectsAdapter(public_config, mock_obs); dev_projects = await dev_adapter.fetch_data(); public_projects = await public_adapter.fetch_data(); all_projects = dev_projects + public_projects; projects_data = []; for project in all_projects: project_dict = project.model_dump(); for key, value in project_dict.items(): if hasattr(value, 'isoformat'): project_dict[key] = value.isoformat(); layer_val = project_dict.get('layer'); project_dict['category'] = 'private_development' if layer_val == 'private_dev' else 'public_projects' if layer_val == 'public_project' else 'infrastructure' if layer_val == 'infrastructure' else 'zoning'; projects_data.append(project_dict); final_data = {'last_updated': datetime.now().isoformat(), 'total_projects': len(projects_data), 'projects': projects_data, 'schema_version': '2.0', 'sources': ['private_development', 'public_projects']}; json.dump(final_data, open('all-projects.json', 'w'), indent=2); print(f'Updated {len(projects_data)} projects'); asyncio.run(main())"

# Show current project distribution
show-project-stats:
	@echo "📊 Current project distribution:"
	@python3 -c "import json; data = json.load(open('all-projects.json')); cats = {}; [cats.update({p.get('category', 'unknown'): cats.get(p.get('category', 'unknown'), 0) + 1}) for p in data['projects']]; [print(f'  {cat}: {count}') for cat, count in cats.items()]; print(f'Total: {data[\"total_projects\"]}'); print(f'Last updated: {data[\"last_updated\"]}')"
