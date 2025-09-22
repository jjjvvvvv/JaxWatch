#!/usr/bin/env python3
"""
Private Development Adapter for JaxWatch

Collects private development project data from Jacksonville's building permits,
development applications, and related sources.
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.municipal_observatory import MunicipalObservatory
import re

from ..core.municipal_schema import CivicProject, DataSource, ProjectLayer, ProcessStage, DecisionAuthority
from ..core.municipal_observatory import DataSourceAdapter, DataSourceConfig

class PrivateDevelopmentAdapter(DataSourceAdapter):
    """Adapter for Jacksonville private development permits and applications"""

    def __init__(self, config: DataSourceConfig, observatory: 'MunicipalObservatory'):
        super().__init__(config, observatory)
        self.base_urls = {
            'jaxepics': 'https://jaxepics.coj.net/',
            'permits_daily': 'https://www.jacksonville.gov/departments/planning-and-development/building-inspection-division/statistical-reports-and-daily-permits-issued',
            'building_permits': 'https://www.jacksonville.gov/departments/planning-and-development/building-inspection-division',
            'development_services': 'https://www.jacksonville.gov/departments/planning-and-development/development-services-division'
        }

    @property
    def data_source_type(self) -> DataSource:
        return DataSource.DEVELOPMENT_SERVICES

    def get_update_schedule(self) -> Dict[str, Any]:
        """Private development updates daily (permits issued daily)"""
        return {
            'frequency': 'daily',
            'preferred_day': 'monday-friday',
            'preferred_hour': 10,
            'retry_count': 3
        }

    async def fetch_data(self) -> List[CivicProject]:
        """Fetch private development project data"""
        self.logger.info("Fetching private development project data...")

        projects = []

        # Try multiple data sources for comprehensive coverage
        permit_projects = await self._fetch_building_permits()
        projects.extend(permit_projects)

        development_applications = await self._fetch_development_applications()
        projects.extend(development_applications)

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

        self.logger.info(f"Found {len(recent_projects)} private development projects in last 6 months")
        return recent_projects

    async def _fetch_building_permits(self) -> List[CivicProject]:
        """Fetch building permit data from Jacksonville sources"""
        projects = []

        try:
            # Try to access the daily permits page for recent data
            async with aiohttp.ClientSession() as session:
                # First, try to get recent permit data
                projects.extend(await self._fetch_recent_permits(session))

                # Then try JAXEPICS if accessible
                projects.extend(await self._fetch_jaxepics_data(session))

        except Exception as e:
            self.logger.error(f"Error fetching building permits: {e}")

        return projects

    async def _fetch_recent_permits(self, session: aiohttp.ClientSession) -> List[CivicProject]:
        """Fetch recent permit data from statistical reports page"""
        projects = []

        try:
            async with session.get(self.base_urls['permits_daily'], timeout=10) as response:
                if response.status == 200:
                    html_content = await response.text()

                    # Look for recent permit links or data
                    # This would need to be customized based on actual page structure
                    permit_links = self._extract_permit_links(html_content)

                    for link in permit_links:
                        permit_projects = await self._process_permit_document(session, link)
                        projects.extend(permit_projects)

        except Exception as e:
            self.logger.debug(f"Could not fetch recent permits: {e}")

        return projects

    def _extract_permit_links(self, html: str) -> List[str]:
        """Extract permit document links from HTML"""
        links = []

        # Look for PDF or Excel files with permit data
        patterns = [
            r'href="([^"]*(?:permit|daily|report)[^"]*\.(?:pdf|xlsx?|csv))"',
            r'href="([^"]*\d{4}[^"]*\.(?:pdf|xlsx?|csv))"'  # Files with years
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if not match.startswith('http'):
                    match = f"https://www.jacksonville.gov{match}"
                links.append(match)

        return links[:5]  # Limit to 5 most recent

    async def _process_permit_document(self, session: aiohttp.ClientSession,
                                     doc_url: str) -> List[CivicProject]:
        """Process a permit document to extract project data"""
        projects = []

        try:
            # Document parsing would happen here
            # Currently no real permit data parsing implemented
            pass

        except Exception as e:
            self.logger.debug(f"Could not process permit document {doc_url}: {e}")

        return projects

    async def _convert_permit_to_project(self, permit_data: Dict[str, Any]) -> Optional[CivicProject]:
        """Convert permit data to CivicProject"""
        try:
            permit_number = permit_data.get('permit_number', '')
            address = permit_data.get('address', '')
            project_type = permit_data.get('project_type', '')
            description = permit_data.get('description', '')
            permit_date = permit_data.get('permit_date')
            estimated_cost = permit_data.get('estimated_cost')

            # Parse permit date
            project_date = None
            if permit_date:
                try:
                except ValueError:
                    pass

            # Determine stage based on permit type and status
            stage = ProcessStage.APPROVED  # Most building permits are approved to be issued

            # Determine decision authority (building permits are typically staff-level)
            decision_authority = DecisionAuthority.STAFF

            # Create project
            project = CivicProject(
                slug=f"dev-{permit_number.lower().replace(' ', '-').replace('/', '-')}",
                project_id=permit_number,
                title=f"{project_type} - {address}",
                layer=ProjectLayer.PRIVATE_DEV,
                stage=stage,
                decision_authority=decision_authority,
                data_source=DataSource.DEVELOPMENT_SERVICES,
                description=description,
                location=address,
                address=address,
                estimated_value=estimated_cost,
                status=f"Permit issued: {permit_date}" if permit_date else None,
                descriptive_tags=[project_type, "Building Permit"] if project_type else ["Building Permit"]
            )

            return project

        except Exception as e:
            self.logger.error(f"Error converting permit to project: {e}")
            return None

    async def _fetch_jaxepics_data(self, session: aiohttp.ClientSession) -> List[CivicProject]:
        """Attempt to fetch data from JAXEPICS system"""
        projects = []

        try:
            # JAXEPICS appears to be a JavaScript application
            # For now, we'll return empty list but this could be expanded
            # to handle the API calls that the JS app makes

            async with session.get(self.base_urls['jaxepics'], timeout=10) as response:
                if response.status == 200:
                    html_content = await response.text()

                    # Look for API endpoints in the JavaScript
                    api_patterns = [
                        r'api[/\\][^"\']*',
                        r'service[s]?[/\\][^"\']*',
                        r'data[/\\][^"\']*'
                    ]

                    for pattern in api_patterns:
                        matches = re.findall(pattern, html_content, re.IGNORECASE)
                        for match in matches[:3]:  # Limit attempts
                            api_projects = await self._try_jaxepics_api(session, match)
                            projects.extend(api_projects)

        except Exception as e:
            self.logger.debug(f"Could not access JAXEPICS: {e}")

        return projects

    async def _try_jaxepics_api(self, session: aiohttp.ClientSession,
                               api_path: str) -> List[CivicProject]:
        """Try to fetch data from a discovered API endpoint"""
        projects = []

        try:
            # Construct full URL
            if not api_path.startswith('http'):
                api_url = f"https://jaxepics.coj.net/{api_path.lstrip('/')}"
            else:
                api_url = api_path

            async with session.get(api_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    # Process API response
                    if isinstance(data, list):
                        for item in data[:10]:  # Limit to 10 items
                            project = await self._convert_api_item_to_project(item)
                            if project:
                                projects.append(project)

        except Exception as e:
            self.logger.debug(f"Could not fetch from API {api_path}: {e}")

        return projects

    async def _convert_api_item_to_project(self, item: Dict[str, Any]) -> Optional[CivicProject]:
        """Convert API response item to CivicProject"""
        try:
            # This would need to be customized based on actual API structure
            project_id = str(item.get('id', item.get('permit_number', '')))
            title = item.get('title', item.get('description', 'Development Project'))

            return CivicProject(
                slug=f"api-dev-{project_id.lower().replace(' ', '-')}",
                project_id=project_id,
                title=title,
                layer=ProjectLayer.PRIVATE_DEV,
                stage=ProcessStage.FILED,
                decision_authority=DecisionAuthority.STAFF,
                data_source=DataSource.DEVELOPMENT_SERVICES,
                description=item.get('description', ''),
                descriptive_tags=["API Data", "JAXEPICS"]
            )

        except Exception as e:
            self.logger.error(f"Error converting API item to project: {e}")
            return None

    async def _fetch_development_applications(self) -> List[CivicProject]:
        """Fetch development application data"""
        projects = []

        try:
            # This would connect to development services for larger projects
            # Currently no real development application data source implemented
            pass

        except Exception as e:
            self.logger.error(f"Error fetching development applications: {e}")

        return projects

    async def _convert_application_to_project(self, app_data: Dict[str, Any]) -> Optional[CivicProject]:
        """Convert development application to CivicProject"""
        try:
            app_id = app_data.get('application_id', '')
            project_name = app_data.get('project_name', '')
            address = app_data.get('address', '')
            app_type = app_data.get('application_type', '')
            description = app_data.get('description', '')
            submitted_date = app_data.get('submitted_date')

            # Development applications typically go through planning review
            stage = ProcessStage.REVIEW
            decision_authority = DecisionAuthority.PLANNING_COMMISSION

            project = CivicProject(
                slug=f"dev-app-{app_id.lower().replace(' ', '-').replace('/', '-')}",
                project_id=app_id,
                title=f"{project_name}",
                layer=ProjectLayer.PRIVATE_DEV,
                stage=stage,
                decision_authority=decision_authority,
                data_source=DataSource.DEVELOPMENT_SERVICES,
                description=description,
                location=address,
                address=address,
                status=f"Application submitted: {submitted_date}" if submitted_date else None,
                descriptive_tags=[app_type, "Development Application"] if app_type else ["Development Application"]
            )

            return project

        except Exception as e:
            self.logger.error(f"Error converting application to project: {e}")
            return None

# Factory function for the observatory
def create_private_development_adapter(config: DataSourceConfig, observatory) -> PrivateDevelopmentAdapter:
    """Factory function to create private development adapter"""
    return PrivateDevelopmentAdapter(config, observatory)

async def main():
    """Test the private development adapter"""
    from municipal_observatory import DataSourceConfig

    # Create test configuration
    config = DataSourceConfig(
        name='private_development',
        adapter_class='PrivateDevelopmentAdapter',
        enabled=True,
        update_frequency='daily'
    )

    # Mock observatory
    class MockObservatory:
        def __init__(self):
            self.config = type('obj', (object,), {'default_delay_seconds': 1.0})()

    adapter = PrivateDevelopmentAdapter(config, MockObservatory())

    print("🏗️  Testing Private Development Adapter...")
    projects = await adapter.fetch_data()
    print(f"Found {len(projects)} private development projects")

    for project in projects:
        print(f"- {project.title}")
        print(f"  ID: {project.project_id}")
        print(f"  Stage: {project.stage.value}")
        print(f"  Location: {project.location}")
        if project.estimated_value:
            print(f"  Cost: ${project.estimated_value:,.2f}")
        if project.status:
            print(f"  Status: {project.status}")
        print()

if __name__ == "__main__":
    asyncio.run(main())