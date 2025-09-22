#!/usr/bin/env python3
"""
Infrastructure Projects Adapter for JaxWatch

Collects infrastructure project data from Jacksonville's Capital Improvement Projects
dashboard and other public works sources.
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

class InfrastructureAdapter(DataSourceAdapter):
    """Adapter for Jacksonville infrastructure and capital improvement projects"""

    def __init__(self, config: DataSourceConfig, observatory: 'MunicipalObservatory'):
        super().__init__(config, observatory)
        self.base_urls = {
            'capital_projects_map': 'https://maps.coj.net/capitalprojects/',
            'public_works': 'https://www.jacksonville.gov/departments/public-works',
            'construction_projects': 'https://www.jacksonville.gov/departments/public-works/docs/construction-projects.aspx'
        }

    @property
    def data_source_type(self) -> DataSource:
        return DataSource.PUBLIC_WORKS

    def get_update_schedule(self) -> Dict[str, Any]:
        """Infrastructure projects update weekly"""
        return {
            'frequency': 'weekly',
            'preferred_day': 'monday',
            'preferred_hour': 9,
            'retry_count': 3
        }

    async def fetch_data(self) -> List[CivicProject]:
        """Fetch infrastructure project data from multiple sources"""
        self.logger.info("Fetching infrastructure project data...")

        projects = []

        # Try to get data from multiple sources
        capital_projects = await self._fetch_capital_projects()
        projects.extend(capital_projects)

        construction_updates = await self._fetch_construction_updates()
        projects.extend(construction_updates)

        # Filter to last 6 months
        six_months_ago = datetime.now() - timedelta(days=180)
        recent_projects = []

        for project in projects:
            # Check if project has recent activity
            if (project.date_received and project.date_received >= six_months_ago) or \
               (project.status_date and project.status_date >= six_months_ago):
                recent_projects.append(project)

        self.logger.info(f"Found {len(recent_projects)} infrastructure projects in last 6 months")
        return recent_projects

    async def _fetch_capital_projects(self) -> List[CivicProject]:
        """Fetch data from Capital Improvement Projects dashboard"""
        projects = []

        try:
            # Try to find API endpoints or data sources
            async with aiohttp.ClientSession() as session:
                # First, check if there are any ESRI REST services
                potential_endpoints = [
                    'https://maps.coj.net/arcgis/rest/services/',
                    'https://services.arcgis.com/search?q=jacksonville%20capital%20projects',
                    'https://maps.coj.net/capitalprojects/config.json'
                ]

                for endpoint in potential_endpoints:
                    try:
                        async with session.get(endpoint, timeout=10) as response:
                            if response.status == 200:
                                data = await response.text()
                                # Look for service definitions or data
                                if 'services' in data.lower() or 'layers' in data.lower():
                                    self.logger.info(f"Found potential data service at {endpoint}")
                                    # Parse and extract project data
                                    projects.extend(await self._parse_esri_data(data, session))
                    except Exception as e:
                        self.logger.debug(f"Could not access {endpoint}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error fetching capital projects data: {e}")

        return projects

    async def _parse_esri_data(self, data: str, session: aiohttp.ClientSession) -> List[CivicProject]:
        """Parse ESRI/ArcGIS service data for project information"""
        projects = []

        try:
            # Look for service URLs in the data
            service_pattern = r'https://[^"]+/rest/services/[^"]+/MapServer'
            service_urls = re.findall(service_pattern, data)

            for service_url in service_urls:
                try:
                    # Query the service for layer information
                    layers_url = f"{service_url}?f=json"
                    async with session.get(layers_url, timeout=10) as response:
                        if response.status == 200:
                            service_info = await response.json()

                            # Look for layers that might contain project data
                            if 'layers' in service_info:
                                for layer in service_info['layers']:
                                    if any(keyword in layer.get('name', '').lower()
                                          for keyword in ['project', 'capital', 'infrastructure', 'construction']):
                                        # Fetch data from this layer
                                        layer_projects = await self._fetch_layer_data(
                                            service_url, layer['id'], session
                                        )
                                        projects.extend(layer_projects)

                except Exception as e:
                    self.logger.debug(f"Could not parse service {service_url}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error parsing ESRI data: {e}")

        return projects

    async def _fetch_layer_data(self, service_url: str, layer_id: int,
                               session: aiohttp.ClientSession) -> List[CivicProject]:
        """Fetch data from a specific ESRI map service layer"""
        projects = []

        try:
            # Query the layer for features
            query_url = f"{service_url}/{layer_id}/query"
            params = {
                'where': '1=1',  # Get all features
                'outFields': '*',
                'f': 'json',
                'returnGeometry': 'true'
            }

            async with session.get(query_url, params=params, timeout=15) as response:
                if response.status == 200:
                    layer_data = await response.json()

                    if 'features' in layer_data:
                        for feature in layer_data['features']:
                            project = await self._convert_feature_to_project(feature)
                            if project:
                                projects.append(project)

        except Exception as e:
            self.logger.debug(f"Could not fetch layer {layer_id} data: {e}")

        return projects

    async def _convert_feature_to_project(self, feature: Dict[str, Any]) -> Optional[CivicProject]:
        """Convert ESRI feature to CivicProject"""
        try:
            attributes = feature.get('attributes', {})
            geometry = feature.get('geometry', {})

            # Extract basic project information
            project_id = str(attributes.get('OBJECTID', attributes.get('ID', '')))
            title = attributes.get('PROJECT_NAME', attributes.get('NAME', 'Infrastructure Project'))
            description = attributes.get('DESCRIPTION', attributes.get('PROJECT_DESC', ''))

            # Extract location information
            location = attributes.get('LOCATION', attributes.get('ADDRESS', ''))

            # Extract coordinates if available
            latitude, longitude = None, None
            if geometry:
                if geometry.get('x') and geometry.get('y'):
                    longitude, latitude = geometry['x'], geometry['y']
                elif 'rings' in geometry and geometry['rings']:
                    # For polygon geometry, use centroid
                    coords = geometry['rings'][0]
                    if coords:
                        avg_x = sum(coord[0] for coord in coords) / len(coords)
                        avg_y = sum(coord[1] for coord in coords) / len(coords)
                        longitude, latitude = avg_x, avg_y

            # Extract budget/cost information
            budget = attributes.get('BUDGET', attributes.get('COST', attributes.get('TOTAL_COST')))
            if budget:
                try:
                    budget = float(budget)
                except (ValueError, TypeError):
                    budget = None

            # Extract dates
            start_date = self._parse_esri_date(attributes.get('START_DATE'))
            completion_date = self._parse_esri_date(attributes.get('COMPLETION_DATE',
                                                                  attributes.get('END_DATE')))

            # Determine project stage
            status_text = attributes.get('STATUS', '').lower()
            if 'complete' in status_text:
                stage = ProcessStage.COMPLETED
            elif 'construction' in status_text or 'progress' in status_text:
                stage = ProcessStage.CONSTRUCTION
            elif 'approved' in status_text:
                stage = ProcessStage.APPROVED
            else:
                stage = ProcessStage.FILED

            # Create the project
            project = CivicProject(
                slug=f"infra-{project_id.lower().replace(' ', '-')}",
                project_id=f"INFRA-{project_id}",
                title=title,
                layer=ProjectLayer.INFRASTRUCTURE,
                stage=stage,
                decision_authority=DecisionAuthority.STAFF,  # Most infrastructure is staff-level
                data_source=DataSource.PUBLIC_WORKS,
                description=description,
                location=location,
                latitude=latitude,
                longitude=longitude,
                metadata={
                    'source': 'capital_projects_dashboard',
                    'raw_attributes': attributes,
                    'geometry_type': geometry.get('type') if geometry else None,
                    'estimated_cost': budget,
                    'start_date': start_date.isoformat() if start_date else None,
                    'completion_date': completion_date.isoformat() if completion_date else None
                }
            )

            return project

        except Exception as e:
            self.logger.error(f"Error converting feature to project: {e}")
            return None

    def _parse_esri_date(self, date_value: Any) -> Optional[datetime]:
        """Parse ESRI date format (usually epoch milliseconds)"""
        if not date_value:
            return None

        try:
            # ESRI often uses epoch milliseconds
            if isinstance(date_value, (int, float)) and date_value > 1000000000:
                # If it's a large number, assume milliseconds
                if date_value > 1000000000000:
                    return datetime.fromtimestamp(date_value / 1000)
                else:
                    return datetime.fromtimestamp(date_value)
        except (ValueError, OSError):
            pass

        return None

    async def _fetch_construction_updates(self) -> List[CivicProject]:
        """Fetch current construction project updates from public works"""
        projects = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_urls['construction_projects'], timeout=10) as response:
                    if response.status == 200:
                        html_content = await response.text()

                        # Look for construction project information in the HTML
                        # This would need to be adapted based on the actual page structure
                        projects.extend(await self._parse_construction_html(html_content))

        except Exception as e:
            self.logger.error(f"Error fetching construction updates: {e}")

        return projects

    async def _parse_construction_html(self, html: str) -> List[CivicProject]:
        """Parse HTML content for construction project information"""
        projects = []

        try:
            # Basic HTML parsing - would need to be refined based on actual structure
            # This is a simplified parser - real implementation would use BeautifulSoup
            # or similar for proper HTML parsing
            pass

        except Exception as e:
            self.logger.error(f"Error parsing construction HTML: {e}")

        return projects

# Factory function for the observatory
def create_infrastructure_adapter(config: DataSourceConfig, observatory) -> InfrastructureAdapter:
    """Factory function to create infrastructure adapter"""
    return InfrastructureAdapter(config, observatory)

async def main():
    """Test the infrastructure adapter"""
    from municipal_observatory import DataSourceConfig

    # Create test configuration
    config = DataSourceConfig(
        name='infrastructure',
        adapter_class='InfrastructureAdapter',
        enabled=True,
        update_frequency='weekly'
    )

    # Mock observatory
    class MockObservatory:
        def __init__(self):
            self.config = type('obj', (object,), {'default_delay_seconds': 1.0})()

    adapter = InfrastructureAdapter(config, MockObservatory())

    print("🏗️  Testing Infrastructure Adapter...")
    projects = await adapter.fetch_data()
    print(f"Found {len(projects)} infrastructure projects")

    for project in projects[:3]:  # Show first 3
        print(f"- {project.title} ({project.location})")
        estimated_cost = project.metadata.get('estimated_cost') if project.metadata else None
        if estimated_cost:
            print(f"  Cost: ${estimated_cost:,.2f}")
        print(f"  Stage: {project.stage.value}")
        print()

if __name__ == "__main__":
    asyncio.run(main())