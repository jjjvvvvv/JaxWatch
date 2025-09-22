#!/usr/bin/env python3
"""
Planning Commission Data Source Adapter
Integrates existing Planning Commission scraper with new observatory architecture
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.core.municipal_observatory import DataSourceAdapter
from backend.core.municipal_schema import MunicipalProject, DataSource, SchemaVersion
from experiments.legacy_scripts.fetch_latest_agendas import fetch_planning_commission_agendas
from experiments.extract_projects_robust import ProjectExtractor

class PlanningCommissionAdapter(DataSourceAdapter):
    """Adapter for Jacksonville Planning Commission data"""

    @property
    def data_source_type(self) -> DataSource:
        return DataSource.PLANNING_COMMISSION

    def get_update_schedule(self) -> Dict[str, Any]:
        """Planning Commission meets 1st and 3rd Thursday of each month"""
        return {
            "frequency": "bi_weekly",
            "meeting_days": ["first_thursday", "third_thursday"],
            "agenda_availability": "friday_before"  # Agendas available Friday before meeting
        }

    async def fetch_data(self) -> List[MunicipalProject]:
        """Fetch and process Planning Commission data"""

        try:
            # Step 1: Fetch latest agenda PDFs
            self.logger.info("Fetching latest Planning Commission agendas")
            downloaded_agendas = await self._fetch_agendas()

            # Step 2: Extract project data from PDFs
            self.logger.info(f"Processing {len(downloaded_agendas)} agenda PDFs")
            all_projects = []

            for agenda_info in downloaded_agendas:
                projects = await self._extract_projects_from_pdf(agenda_info)
                all_projects.extend(projects)

            # Step 3: Apply geocoding if needed
            geocoded_projects = await self._apply_geocoding(all_projects)

            self.logger.info(f"Successfully processed {len(geocoded_projects)} projects")
            return geocoded_projects

        except Exception as e:
            self.logger.error(f"Error fetching Planning Commission data: {e}")
            # Return existing data if available as fallback
            return await self._load_existing_data()

    async def _fetch_agendas(self) -> List[Dict[str, Any]]:
        """Fetch agenda PDFs using existing scraper"""

        loop = asyncio.get_event_loop()

        # Run the existing agenda fetcher in a thread to avoid blocking
        try:
            downloaded = await loop.run_in_executor(
                None, fetch_planning_commission_agendas
            )
            return downloaded or []
        except Exception as e:
            self.logger.error(f"Error fetching agendas: {e}")
            return []

    async def _extract_projects_from_pdf(self, agenda_info: Dict[str, Any]) -> List[MunicipalProject]:
        """Extract projects from a single PDF using existing extractor"""

        pdf_path = agenda_info.get('local_file')
        if not pdf_path or not Path(pdf_path).exists():
            self.logger.warning(f"PDF file not found: {pdf_path}")
            return []

        try:
            self.logger.info(f"Extracting projects from {Path(pdf_path).name}")

            # Use existing ProjectExtractor
            extractor = ProjectExtractor()
            loop = asyncio.get_event_loop()

            # Run extraction in thread to avoid blocking
            extraction_result = await loop.run_in_executor(
                None, extractor.extract_projects_from_pdf, pdf_path
            )

            if not extraction_result:
                self.logger.warning(f"No data extracted from {pdf_path}")
                return []

            # Convert to unified schema
            projects = extraction_result.get('projects', [])
            meeting_info = extraction_result.get('meeting_info', {})

            unified_projects = []
            for project_data in projects:
                try:
                    # Add meeting info to project data
                    project_data['meeting_info'] = meeting_info
                    project_data['source_pdf'] = Path(pdf_path).name

                    # Convert to unified schema using migration
                    unified_project = SchemaVersion.migrate_from_v1(project_data)
                    unified_project.data_source = DataSource.PLANNING_COMMISSION

                    # Enhance with additional metadata
                    unified_project = self._enhance_project_metadata(unified_project, agenda_info)

                    unified_projects.append(unified_project)

                except Exception as e:
                    self.logger.error(f"Error converting project {project_data.get('project_id', 'unknown')}: {e}")
                    continue

            self.logger.info(f"Converted {len(unified_projects)} projects from {Path(pdf_path).name}")
            return unified_projects

        except Exception as e:
            self.logger.error(f"Error extracting from {pdf_path}: {e}")
            return []

    def _enhance_project_metadata(self, project: MunicipalProject,
                                agenda_info: Dict[str, Any]) -> MunicipalProject:
        """Add additional metadata to projects"""

        # Add source document info
        if agenda_info.get('url'):
            project.source_url = agenda_info['url']

        # Add to source documents list
        if project.source_pdf and project.source_pdf not in project.source_documents:
            project.source_documents.append(project.source_pdf)

        # Set geographic scope based on project layer
        if project.layer.value == "zoning":
            # Geographic scope not in new schema - removing this logic
            pass
        elif "district" in (project.council_district or "").lower():
            pass
        else:
            pass

        # Enhanced tagging
        enhanced_tags = set(project.tags or [])

        # Add tags based on project content
        if project.title:
            title_lower = project.title.lower()
            if "residential" in title_lower:
                enhanced_tags.add("residential")
            if "commercial" in title_lower:
                enhanced_tags.add("commercial")
            if "industrial" in title_lower:
                enhanced_tags.add("industrial")
            if "mixed" in title_lower:
                enhanced_tags.add("mixed_use")

        if project.request:
            request_lower = project.request.lower()
            if "buffer" in request_lower:
                enhanced_tags.add("buffer_reduction")
            if "variance" in request_lower:
                enhanced_tags.add("variance")
            if "conditional" in request_lower:
                enhanced_tags.add("conditional_use")

        project.tags = list(enhanced_tags)

        return project

    async def _apply_geocoding(self, projects: List[MunicipalProject]) -> List[MunicipalProject]:
        """Apply geocoding to projects that need it"""

        projects_needing_geocoding = [
            p for p in projects
            if p.location and not (p.latitude and p.longitude)
        ]

        if not projects_needing_geocoding:
            self.logger.info("All projects already have coordinates")
            return projects

        self.logger.info(f"Geocoding {len(projects_needing_geocoding)} projects")

        # Use existing geocoding infrastructure
        try:
            # Create temporary file with projects needing geocoding
            temp_file = Path("temp_geocoding.json")

            # Convert to legacy format for existing geocoder
            legacy_format = []
            for project in projects_needing_geocoding:
                legacy_project = {
                    "slug": project.slug,
                    "project_id": project.project_id,
                    "location": project.location,
                    "latitude": project.latitude,
                    "longitude": project.longitude
                }
                legacy_format.append(legacy_project)

            with open(temp_file, 'w') as f:
                json.dump(legacy_format, f, indent=2)

            # Run geocoding script
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["python3", "geocode_projects.py", str(temp_file)],
                    check=False,
                    capture_output=True
                )
            )

            # Read back geocoded results
            if temp_file.exists():
                with open(temp_file, 'r') as f:
                    geocoded_data = json.load(f)

                # Update original projects with coordinates
                geocoded_lookup = {item['slug']: item for item in geocoded_data}

                for project in projects:
                    if project.slug in geocoded_lookup:
                        geocoded = geocoded_lookup[project.slug]
                        if geocoded.get('latitude') and geocoded.get('longitude'):
                            project.latitude = geocoded['latitude']
                            project.longitude = geocoded['longitude']

                # Clean up temp file
                temp_file.unlink()

        except Exception as e:
            self.logger.error(f"Error during geocoding: {e}")

        return projects

    async def _load_existing_data(self) -> List[MunicipalProject]:
        """Load existing extracted data as fallback"""

        try:
            extracted_dir = Path("data/extracted")
            if not extracted_dir.exists():
                return []

            projects = []
            json_files = list(extracted_dir.glob("*.json"))

            for json_file in json_files[-5:]:  # Last 5 files as fallback
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)

                    for project_data in data.get('projects', []):
                        unified_project = SchemaVersion.migrate_from_v1(project_data)
                        unified_project.data_source = DataSource.PLANNING_COMMISSION
                        projects.append(unified_project)

                except Exception as e:
                    self.logger.error(f"Error loading {json_file}: {e}")
                    continue

            self.logger.info(f"Loaded {len(projects)} existing projects as fallback")
            return projects

        except Exception as e:
            self.logger.error(f"Error loading existing data: {e}")
            return []

    def get_data_freshness(self) -> Dict[str, Any]:
        """Get information about data freshness"""

        try:
            # Check when we last fetched data
            metadata_file = Path("data/fetch_metadata.json")
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                last_check = metadata.get('last_check')
                if last_check:
                    last_check_dt = datetime.fromisoformat(last_check)
                    hours_since = (datetime.now() - last_check_dt).total_seconds() / 3600

                    return {
                        "last_check": last_check,
                        "hours_since_last_check": round(hours_since, 1),
                        "downloaded_count": len(metadata.get('downloaded', [])),
                        "status": "fresh" if hours_since < 24 else "stale"
                    }

            return {
                "last_check": None,
                "status": "unknown"
            }

        except Exception as e:
            self.logger.error(f"Error checking data freshness: {e}")
            return {"status": "error"}

if __name__ == "__main__":
    # Test the adapter
    import asyncio
    from municipal_observatory import DataSourceConfig

    async def test_adapter():
        config = DataSourceConfig(
            name="planning_commission",
            adapter_class="PlanningCommissionAdapter",
            update_frequency="weekly"
        )

        # Create mock observatory
        class MockObservatory:
            def __init__(self):
                self.config = type('obj', (object,), {
                    'default_delay_seconds': 1.0
                })()

        observatory = MockObservatory()
        adapter = PlanningCommissionAdapter(config, observatory)

        print("Testing Planning Commission Adapter...")

        # Test data freshness
        freshness = adapter.get_data_freshness()
        print(f"Data freshness: {freshness}")

        # Test should_update
        should_update = adapter.should_update()
        print(f"Should update: {should_update}")

        if should_update:
            print("Fetching data...")
            projects = await adapter.fetch_data()
            print(f"Fetched {len(projects)} projects")

            if projects:
                sample = projects[0]
                print(f"Sample project: {sample.project_id} - {sample.title}")
                print(f"Project type: {sample.project_type}")
                print(f"Decision stage: {sample.decision_stage}")

    asyncio.run(test_adapter())