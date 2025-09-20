#!/usr/bin/env python3
"""
JaxWatch Municipal Observatory
Master orchestrator for coordinating municipal data collection from multiple sources
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type, Any
from pathlib import Path
import json
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

from .municipal_schema import MunicipalProject, DataSource, ProjectType, SchemaVersion
from ..common.adaptive_polling import AdaptivePoller, should_poll_source, record_poll_result
from ..common.alerts import alert_validation_failure, alert_pipeline_failure, alert_system_health

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DataSourceConfig:
    """Configuration for a data source"""
    name: str
    adapter_class: str
    enabled: bool = True
    update_frequency: str = "weekly"  # daily, weekly, monthly, on_demand
    last_update: Optional[datetime] = None
    specific_config: Dict[str, Any] = None

    def __post_init__(self):
        if self.specific_config is None:
            self.specific_config = {}

@dataclass
class ObservatoryConfig:
    """Main observatory configuration"""
    data_sources: List[DataSourceConfig]
    output_directory: str = "data"
    max_concurrent_sources: int = 3
    respect_robots_txt: bool = True
    default_delay_seconds: float = 1.0
    enable_cross_referencing: bool = True

class DataSourceAdapter(ABC):
    """Abstract base class for all data source adapters"""

    def __init__(self, config: DataSourceConfig, observatory: 'MunicipalObservatory'):
        self.config = config
        self.observatory = observatory
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def fetch_data(self) -> List[MunicipalProject]:
        """Fetch and return normalized municipal projects"""
        pass

    @abstractmethod
    def get_update_schedule(self) -> Dict[str, Any]:
        """Return when this source should be updated"""
        pass

    @property
    @abstractmethod
    def data_source_type(self) -> DataSource:
        """Return the data source type this adapter handles"""
        pass

    def should_update(self) -> bool:
        """Determine if this source needs updating based on adaptive polling schedule"""
        if not self.config.enabled:
            return False

        # Use adaptive polling system if available
        if hasattr(self.observatory, 'adaptive_poller'):
            return self.observatory.adaptive_poller.should_poll_now(self.config.name)

        # Fallback to legacy scheduling logic
        if self.config.last_update is None:
            return True

        frequency = self.config.update_frequency
        now = datetime.now()

        if frequency == "daily":
            return (now - self.config.last_update).days >= 1
        elif frequency == "weekly":
            return (now - self.config.last_update).days >= 7
        elif frequency == "monthly":
            return (now - self.config.last_update).days >= 30
        else:  # on_demand
            return False

class ProjectNormalizer:
    """Normalizes projects from different sources to unified schema"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def normalize_project(self, raw_project: Dict[str, Any], source: DataSource) -> MunicipalProject:
        """Convert raw project data to unified schema"""

        try:
            # Check if this is legacy format (v1) that needs migration
            if 'project_type' in raw_project and isinstance(raw_project.get('project_type'), str):
                # Looks like legacy format
                migrated = SchemaVersion.migrate_from_v1(raw_project)
                migrated.data_source = source
                return migrated

            # Assume it's already in v2 format, just validate
            return MunicipalProject(**raw_project)

        except Exception as e:
            self.logger.error(f"Failed to normalize project {raw_project.get('project_id', 'unknown')}: {e}")
            raise

class CrossReferenceEngine:
    """Links related projects across different data sources"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def find_related_projects(self, projects: List[MunicipalProject]) -> List[MunicipalProject]:
        """Find and link related projects"""

        # Create lookup indices
        by_location = {}
        by_project_id = {}
        by_address = {}

        for project in projects:
            # Index by project ID patterns
            if project.project_id:
                by_project_id[project.project_id] = project

            # Index by location/address
            if project.location:
                location_key = project.location.lower().strip()
                if location_key not in by_location:
                    by_location[location_key] = []
                by_location[location_key].append(project)

            # Index by geographic coordinates (within small radius)
            if project.latitude and project.longitude:
                coord_key = f"{project.latitude:.4f},{project.longitude:.4f}"
                if coord_key not in by_address:
                    by_address[coord_key] = []
                by_address[coord_key].append(project)

        # Find relationships
        updated_projects = []
        for project in projects:
            updated_project = self._find_project_relationships(
                project, by_location, by_project_id, by_address
            )
            updated_projects.append(updated_project)

        return updated_projects

    def _find_project_relationships(self, project: MunicipalProject,
                                  by_location: Dict, by_project_id: Dict,
                                  by_address: Dict) -> MunicipalProject:
        """Find relationships for a single project"""

        related_projects = []

        # Find projects at same location
        if project.location:
            location_key = project.location.lower().strip()
            location_matches = by_location.get(location_key, [])

            for match in location_matches:
                if match.project_id != project.project_id:
                    related_projects.append({
                        "project_id": match.project_id,
                        "relationship_type": "same_location",
                        "description": f"Same location: {project.location}"
                    })

        # Find projects with geographic proximity
        if project.latitude and project.longitude:
            coord_key = f"{project.latitude:.4f},{project.longitude:.4f}"
            coord_matches = by_address.get(coord_key, [])

            for match in coord_matches:
                if (match.project_id != project.project_id and
                    not any(rp["project_id"] == match.project_id for rp in related_projects)):
                    related_projects.append({
                        "project_id": match.project_id,
                        "relationship_type": "geographic_proximity",
                        "description": "Geographically proximate projects"
                    })

        # Look for sequential project IDs (phases)
        if project.project_id and any(char.isdigit() for char in project.project_id):
            # Simple heuristic for related project sequences
            base_id = ''.join(c for c in project.project_id if not c.isdigit())
            for pid, p in by_project_id.items():
                if (pid != project.project_id and
                    pid.startswith(base_id) and
                    not any(rp["project_id"] == pid for rp in related_projects)):
                    related_projects.append({
                        "project_id": pid,
                        "relationship_type": "sequential",
                        "description": "Related project sequence"
                    })

        # Update the project with found relationships
        project.related_projects = related_projects[:5]  # Limit to 5 most relevant
        return project

class MunicipalObservatory:
    """Main orchestrator for municipal data collection and processing"""

    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.adapters: Dict[str, DataSourceAdapter] = {}
        self.normalizer = ProjectNormalizer()
        self.cross_reference_engine = CrossReferenceEngine()

        # Initialize adaptive polling system
        self.adaptive_poller = AdaptivePoller()

        # Initialize optional components with graceful fallback
        try:
            from financial_correlator import FinancialCorrelator
            self.financial_correlator = FinancialCorrelator()
        except ImportError:
            self.financial_correlator = None

        try:
            from alert_system import AlertSystem
            self.alert_system = AlertSystem()
        except ImportError:
            self.alert_system = None

        # Initialize health monitoring system
        try:
            from source_health_monitor import SourceHealthMonitor
            self.health_monitor = SourceHealthMonitor()
        except ImportError:
            self.health_monitor = None

        self.logger = logging.getLogger(__name__)

        # Ensure output directory exists
        Path(self.config.output_directory).mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_file: Optional[str]) -> ObservatoryConfig:
        """Load configuration from file or create default"""

        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                config_data = json.load(f)

            # Convert dict to dataclass
            data_sources = [DataSourceConfig(**ds) for ds in config_data.get('data_sources', [])]
            config_data['data_sources'] = data_sources
            return ObservatoryConfig(**config_data)

        # Default configuration
        return ObservatoryConfig(
            data_sources=[
                DataSourceConfig(
                    name="planning_commission",
                    adapter_class="PlanningCommissionAdapter",
                    update_frequency="weekly",
                    specific_config={
                        "base_url": "https://www.jacksonville.gov/departments/planning-and-development/planning-commission.aspx",
                        "agenda_patterns": [
                            r'pc.*agenda.*\.pdf',
                            r'planning.*commission.*agenda.*\.pdf'
                        ]
                    }
                ),
                DataSourceConfig(
                    name="infrastructure",
                    adapter_class="InfrastructureAdapter",
                    update_frequency="weekly",
                    enabled=True,
                    specific_config={
                        "base_url": "https://maps.coj.net/capitalprojects/",
                        "focus_period_months": 6
                    }
                ),
                DataSourceConfig(
                    name="private_development",
                    adapter_class="PrivateDevelopmentAdapter",
                    update_frequency="daily",
                    enabled=True,
                    specific_config={
                        "base_url": "https://jaxepics.coj.net/",
                        "focus_period_months": 6
                    }
                ),
                DataSourceConfig(
                    name="public_projects",
                    adapter_class="PublicProjectsAdapter",
                    update_frequency="weekly",
                    enabled=True,
                    specific_config={
                        "departments": ["parks", "public_works", "utilities"],
                        "focus_period_months": 6
                    }
                ),
                DataSourceConfig(
                    name="city_council",
                    adapter_class="CityCouncilAdapter",
                    update_frequency="weekly",
                    enabled=False,  # Optional - skip if not available
                    specific_config={
                        "base_url": "https://jaxcityc.legistar.com",
                        "calendar_url": "https://jaxcityc.legistar.com/Calendar.aspx"
                    }
                )
            ]
        )

    def register_adapter(self, adapter: DataSourceAdapter):
        """Register a data source adapter"""
        self.adapters[adapter.config.name] = adapter
        self.logger.info(f"Registered adapter: {adapter.config.name}")

    async def update_all_sources(self) -> Dict[str, List[MunicipalProject]]:
        """Update all enabled data sources"""

        sources_to_update = [
            adapter for adapter in self.adapters.values()
            if adapter.should_update()
        ]

        if not sources_to_update:
            self.logger.info("No sources need updating")
            return {}

        self.logger.info(f"Updating {len(sources_to_update)} data sources")

        # Run updates concurrently but limit concurrency
        semaphore = asyncio.Semaphore(self.config.max_concurrent_sources)

        async def update_with_semaphore(adapter):
            async with semaphore:
                return await self._update_single_source(adapter)

        tasks = [update_with_semaphore(adapter) for adapter in sources_to_update]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        all_results = {}
        for adapter, result in zip(sources_to_update, results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to update {adapter.config.name}: {result}")
                all_results[adapter.config.name] = []
            else:
                all_results[adapter.config.name] = result
                adapter.config.last_update = datetime.now()

        return all_results

    async def _update_single_source(self, adapter: DataSourceAdapter) -> List[MunicipalProject]:
        """Update a single data source"""

        self.logger.info(f"Updating {adapter.config.name}")
        start_time = datetime.now()

        try:
            # Add delay for respectful scraping
            await asyncio.sleep(self.config.default_delay_seconds)

            # Fetch raw data
            raw_projects = await adapter.fetch_data()

            # Normalize to unified schema
            normalized_projects = []
            for raw_project in raw_projects:
                if isinstance(raw_project, dict):
                    normalized = self.normalizer.normalize_project(
                        raw_project, adapter.data_source_type
                    )
                    normalized_projects.append(normalized)
                else:
                    # Already normalized
                    normalized_projects.append(raw_project)

            # Calculate response time and record successful polling attempt
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            if hasattr(self, 'adaptive_poller'):
                self.adaptive_poller.record_poll_attempt(adapter.config.name, True)

            # Record health metrics
            if self.health_monitor:
                self.health_monitor.record_poll_attempt(
                    adapter.config.name, True, response_time_ms,
                    documents_found=len(raw_projects),
                    new_documents=len(normalized_projects)
                )

                # Record processing events
                for project in normalized_projects:
                    self.health_monitor.record_processing_event(
                        adapter.config.name, 'document_processed', True,
                        document_id=getattr(project, 'project_id', None)
                    )

            self.logger.info(f"Fetched {len(normalized_projects)} projects from {adapter.config.name}")
            return normalized_projects

        except Exception as e:
            # Calculate response time for failed attempts
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Record failed polling attempt
            if hasattr(self, 'adaptive_poller'):
                self.adaptive_poller.record_poll_attempt(adapter.config.name, False, str(e))

            # Record health metrics for failure
            if self.health_monitor:
                self.health_monitor.record_poll_attempt(
                    adapter.config.name, False, response_time_ms, str(e)
                )
                self.health_monitor.record_processing_event(
                    adapter.config.name, 'polling_failed', False,
                    metadata={'error': str(e)}
                )

            self.logger.error(f"Error updating {adapter.config.name}: {e}")
            raise

    def aggregate_all_data(self, source_results: Dict[str, List[MunicipalProject]]) -> List[MunicipalProject]:
        """Aggregate data from all sources and apply cross-referencing"""

        all_projects = []
        for source_name, projects in source_results.items():
            all_projects.extend(projects)

        self.logger.info(f"Aggregating {len(all_projects)} total projects")

        # Apply cross-referencing if enabled
        if self.config.enable_cross_referencing:
            all_projects = self.cross_reference_engine.find_related_projects(all_projects)
            self.logger.info("Applied cross-referencing")

        # Sort by meeting date (newest first) and item number
        all_projects.sort(key=lambda p: (
            p.meeting_date or '',
            int(p.item_number or '0')
        ), reverse=True)

        return all_projects

    def save_aggregated_data(self, projects: List[MunicipalProject]):
        """Save aggregated data to files"""

        # Convert to dictionaries for JSON serialization
        projects_data = []
        for project in projects:
            project_dict = project.dict()
            # Convert datetime objects to ISO strings
            for key, value in project_dict.items():
                if isinstance(value, datetime):
                    project_dict[key] = value.isoformat()

            # Backfill legacy UI 'category' for frontend compatibility
            # Map unified layer -> UI categories used by app.js
            category = project_dict.get('category')
            if not category:
                # Try layer first (new schema), then project_type (legacy)
                layer = project_dict.get('layer') or project_dict.get('project_type')
                # Handle both enum and string
                layer_val = getattr(layer, 'value', layer) if layer else 'zoning'
                mapping = {
                    'zoning': 'zoning',
                    'private_dev': 'private_development',
                    'public_project': 'public_projects',
                    'infrastructure': 'infrastructure'
                }
                project_dict['category'] = mapping.get(layer_val, 'zoning')
            projects_data.append(project_dict)

        # Create aggregated data structure
        aggregated_data = {
            'last_updated': datetime.now().isoformat(),
            'total_projects': len(projects),
            'projects': projects_data,
            'schema_version': SchemaVersion.CURRENT,
            'sources': list(self.adapters.keys())
        }

        # Save main data file
        main_file = Path(self.config.output_directory) / 'all-projects.json'
        with open(main_file, 'w') as f:
            json.dump(aggregated_data, f, indent=2)

        # Save copy for website
        website_file = Path('all-projects.json')
        with open(website_file, 'w') as f:
            json.dump(aggregated_data, f, indent=2)

        self.logger.info(f"Saved {len(projects)} projects to {main_file}")

    async def run_full_update(self) -> List[MunicipalProject]:
        """Run complete update cycle"""

        self.logger.info("Starting full observatory update")

        # Update all sources
        source_results = await self.update_all_sources()

        # Aggregate data
        all_projects = self.aggregate_all_data(source_results)

        # Apply financial correlation if available
        if self.financial_correlator:
            self.logger.info("Applying financial correlation analysis")
            all_projects = self.financial_correlator.correlate_financial_data(all_projects)

        # Generate alerts if available
        if self.alert_system:
            self.logger.info("Processing projects for alerts")
            alerts = self.alert_system.process_projects(all_projects)
            if alerts:
                self.logger.info(f"Generated {len(alerts)} new alerts")

        # Save results
        self.save_aggregated_data(all_projects)

        self.logger.info(f"Observatory update complete: {len(all_projects)} total projects")
        return all_projects

    def get_polling_status(self) -> Dict[str, Any]:
        """Get current status of adaptive polling system"""
        if hasattr(self, 'adaptive_poller'):
            return self.adaptive_poller.get_polling_status()
        else:
            return {"error": "Adaptive polling not initialized"}

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status of all sources"""
        if self.health_monitor:
            return {
                'system_summary': self.health_monitor.get_system_health_summary(),
                'source_details': self.health_monitor.get_all_sources_health()
            }
        else:
            return {"error": "Health monitoring not initialized"}

    def force_poll_source(self, source_name: str):
        """Force immediate polling of a specific source"""
        if hasattr(self, 'adaptive_poller'):
            self.adaptive_poller.force_poll(source_name)
            self.logger.info(f"Forced poll scheduled for {source_name}")
        else:
            self.logger.warning("Adaptive polling not available")

    def update_polling_schedule(self, source_name: str, **kwargs):
        """Update polling schedule for a source"""
        if hasattr(self, 'adaptive_poller'):
            self.adaptive_poller.update_schedule(source_name, **kwargs)
            self.logger.info(f"Updated polling schedule for {source_name}")
        else:
            self.logger.warning("Adaptive polling not available")

# Factory function for creating adapters
def create_adapter(config: DataSourceConfig, observatory: MunicipalObservatory) -> Optional[DataSourceAdapter]:
    """Factory function to create adapters based on configuration"""

    # Import here to avoid circular dependencies
    if config.adapter_class == "PlanningCommissionAdapter":
        from ..adapters.planning_commission_adapter import PlanningCommissionAdapter
        return PlanningCommissionAdapter(config, observatory)
    elif config.adapter_class == "InfrastructureAdapter":
        from ..adapters.infrastructure_adapter import InfrastructureAdapter
        return InfrastructureAdapter(config, observatory)
    elif config.adapter_class == "PrivateDevelopmentAdapter":
        from ..adapters.private_development_adapter import PrivateDevelopmentAdapter
        return PrivateDevelopmentAdapter(config, observatory)
    elif config.adapter_class == "PublicProjectsAdapter":
        from ..adapters.public_projects_adapter import PublicProjectsAdapter
        return PublicProjectsAdapter(config, observatory)
    elif config.adapter_class == "CityCouncilAdapter":
        # Optional adapter - skip if not available
        try:
            from ..adapters.city_council_adapter import CityCouncilAdapter
            return CityCouncilAdapter(config, observatory)
        except ImportError:
            logger.warning(f"CityCouncilAdapter not available, skipping")
            return None
    else:
        logger.error(f"Unknown adapter class: {config.adapter_class}")
        return None

if __name__ == "__main__":
    async def main():
        # Example usage
        observatory = MunicipalObservatory()

        # Register available adapters
        for source_config in observatory.config.data_sources:
            if source_config.enabled:
                adapter = create_adapter(source_config, observatory)
                if adapter:
                    observatory.register_adapter(adapter)

        # Run full update
        projects = await observatory.run_full_update()
        print(f"Updated {len(projects)} projects from {len(observatory.adapters)} sources")

    # Run the example
    asyncio.run(main())
