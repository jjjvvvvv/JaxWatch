#!/usr/bin/env python3
"""
Public Projects Adapter for JaxWatch

Collects public project data from Jacksonville's parks, recreation, municipal facilities,
and other city-sponsored projects.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import re

from ..core.municipal_schema import CivicProject, DataSource, ProjectLayer, ProcessStage, DecisionAuthority
from ..core.municipal_observatory import DataSourceAdapter, DataSourceConfig

class PublicProjectsAdapter(DataSourceAdapter):
    """Adapter for Jacksonville public projects, parks, and municipal facilities"""

    def __init__(self, config: DataSourceConfig, observatory: 'MunicipalObservatory'):
        super().__init__(config, observatory)
        self.base_urls = {
            'parks_recreation': 'https://www.jacksonville.gov/departments/parks-recreation-community-services',
            'public_works': 'https://www.jacksonville.gov/departments/public-works',
            'capital_projects': 'https://www.jacksonville.gov/mayor/mayor-s-transparency-dashboards/capital-improvement-projects-dashboard',
            'jea_projects': 'https://www.jea.com/',  # Jacksonville Electric Authority
            'airport_projects': 'https://www.flyjacksonville.com/',
            'port_projects': 'https://www.jaxport.com/'
        }

    @property
    def data_source_type(self) -> DataSource:
        return DataSource.PUBLIC_WORKS

    def get_update_schedule(self) -> Dict[str, Any]:
        """Public projects update weekly"""
        return {
            'frequency': 'weekly',
            'preferred_day': 'tuesday',
            'preferred_hour': 10,
            'retry_count': 3
        }

    async def fetch_data(self) -> List[CivicProject]:
        """Fetch public project data from multiple city departments"""
        self.logger.info("Fetching public project data...")

        projects = []

        # Collect from multiple public sources
        parks_projects = await self._fetch_parks_recreation_projects()
        projects.extend(parks_projects)

        municipal_projects = await self._fetch_municipal_projects()
        projects.extend(municipal_projects)

        utility_projects = await self._fetch_utility_projects()
        projects.extend(utility_projects)

        # Filter to last 6 months
        six_months_ago = datetime.now() - timedelta(days=180)
        recent_projects = []

        for project in projects:
            # Check for recent activity using extracted_at or last_updated
            project_date = project.extracted_at
            if project.last_updated:
                project_date = project.last_updated

            if project_date and project_date >= six_months_ago:
                recent_projects.append(project)

        self.logger.info(f"Found {len(recent_projects)} public projects in last 6 months")
        return recent_projects

    async def _fetch_parks_recreation_projects(self) -> List[CivicProject]:
        """Fetch parks and recreation project data"""
        projects = []

        try:
            # Parks and recreation project data collection would happen here
            # Currently no real data source implemented
            pass

        except Exception as e:
            self.logger.error(f"Error fetching parks projects: {e}")

        return projects

    async def _fetch_municipal_projects(self) -> List[CivicProject]:
        """Fetch municipal facility and city building projects"""
        projects = []

        try:
            # Municipal project data collection would happen here
            # Currently no real data source implemented
            pass

        except Exception as e:
            self.logger.error(f"Error fetching municipal projects: {e}")

        return projects

    async def _fetch_utility_projects(self) -> List[CivicProject]:
        """Fetch utility and infrastructure projects from JEA and other utilities"""
        projects = []

        try:
            # Utility project data collection would happen here
            # Currently no real data source implemented
            pass

        except Exception as e:
            self.logger.error(f"Error fetching utility projects: {e}")

        return projects

    async def _convert_project_to_civic(self, project_data: Dict[str, Any],
                                      source_type: str) -> Optional[CivicProject]:
        """Convert project data to CivicProject"""
        try:
            project_id = project_data.get('project_id', '')
            project_name = project_data.get('project_name', '')
            location = project_data.get('location', '')
            project_type = project_data.get('project_type', '')
            description = project_data.get('description', '')
            budget = project_data.get('budget')
            start_date = project_data.get('start_date')
            completion_date = project_data.get('expected_completion')
            department = project_data.get('department', '')

            # Determine stage based on project status
            stage = ProcessStage.CONSTRUCTION  # Most public projects are in construction when announced

            # Public projects are typically approved by city council or department heads
            decision_authority = DecisionAuthority.CITY_COUNCIL

            # Create descriptive tags
            tags = [project_type, "Public Project"]
            if department:
                tags.append(department)
            if budget and budget > 1000000:
                tags.append(">$1M")
            if budget and budget > 10000000:
                tags.append(">$10M")

            # Create the project
            project = CivicProject(
                slug=f"public-{project_id.lower().replace(' ', '-').replace('/', '-')}",
                project_id=project_id,
                title=project_name,
                layer=ProjectLayer.PUBLIC_PROJECT,
                stage=stage,
                decision_authority=decision_authority,
                data_source=DataSource.PUBLIC_WORKS,
                description=description,
                location=location,
                estimated_value=budget,
                proposed_start=start_date,
                proposed_completion=completion_date,
                funding_source="City of Jacksonville" if source_type != 'utility' else department,
                status=f"Construction ongoing - Expected completion: {completion_date}" if completion_date else "In progress",
                descriptive_tags=tags
            )

            return project

        except Exception as e:
            self.logger.error(f"Error converting project to civic project: {e}")
            return None

# Factory function for the observatory
def create_public_projects_adapter(config: DataSourceConfig, observatory) -> PublicProjectsAdapter:
    """Factory function to create public projects adapter"""
    return PublicProjectsAdapter(config, observatory)

async def main():
    """Test the public projects adapter"""
    from municipal_observatory import DataSourceConfig

    # Create test configuration
    config = DataSourceConfig(
        name='public_projects',
        adapter_class='PublicProjectsAdapter',
        enabled=True,
        update_frequency='weekly'
    )

    # Mock observatory
    class MockObservatory:
        def __init__(self):
            self.config = type('obj', (object,), {'default_delay_seconds': 1.0})()

    adapter = PublicProjectsAdapter(config, MockObservatory())

    print("🏛️  Testing Public Projects Adapter...")
    projects = await adapter.fetch_data()
    print(f"Found {len(projects)} public projects")

    for project in projects:
        print(f"- {project.title}")
        print(f"  ID: {project.project_id}")
        print(f"  Stage: {project.stage.value}")
        print(f"  Location: {project.location}")
        if project.estimated_value:
            print(f"  Budget: ${project.estimated_value:,.2f}")
        if project.funding_source:
            print(f"  Funded by: {project.funding_source}")
        if project.proposed_completion:
            print(f"  Expected completion: {project.proposed_completion}")
        print()

if __name__ == "__main__":
    asyncio.run(main())