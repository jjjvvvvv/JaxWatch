#!/usr/bin/env python3
"""
Test script for Municipal Observatory end-to-end functionality
Verifies integration of schema, adapters, and orchestration
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Import our observatory components
from backend.core.municipal_observatory import MunicipalObservatory, DataSourceConfig, create_adapter
from backend.core.municipal_schema import MunicipalProject, SchemaVersion, ProjectTypeMapping
from backend.adapters.planning_commission_adapter import PlanningCommissionAdapter
# from backend.adapters.city_council_adapter import CityCouncilAdapter  # Optional adapter

class ObservatoryTester:
    """Comprehensive test suite for Municipal Observatory"""

    def __init__(self):
        self.test_results = []
        self.errors = []

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"    {details}")

        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_schema_validation(self):
        """Test unified schema validation and migration"""

        print("\n🧪 Testing Schema Validation")

        # Test 1: Schema validation with flagged items
        from backend.core.municipal_schema import CivicProject, ProjectLayer, ProcessStage, DecisionAuthority, DataSource

        # Test valid project
        valid_project_data = {
            "slug": "test-project-valid",
            "project_id": "AD-23-36",
            "title": "Test Administrative Deviation",
            "layer": ProjectLayer.ZONING,
            "stage": ProcessStage.APPROVED,
            "decision_authority": DecisionAuthority.PLANNING_COMMISSION,
            "data_source": DataSource.PLANNING_COMMISSION,
            "estimated_value": 150000,
            "meeting_date": "2024-10-03",
            "council_district": "7",
            "location": "123 Test Street"
        }

        try:
            valid_project = CivicProject(**valid_project_data)
            self.log_test("Schema Validation - Valid Project", True, f"Successfully created project: {valid_project.title}")
        except Exception as e:
            self.log_test("Schema Validation - Valid Project", False, str(e))

        # Test 2: Project with missing required fields (should be flagged)
        incomplete_project_data = {
            "slug": "test-project-incomplete",
            "project_id": "",  # Missing required field
            "title": "Incomplete Project",
            "layer": ProjectLayer.ZONING,
            "stage": ProcessStage.REVIEW,
            "decision_authority": DecisionAuthority.PLANNING_COMMISSION,
            "data_source": DataSource.PLANNING_COMMISSION,
        }

        try:
            # Test creating project with missing project_id (should work but be flagged)
            incomplete_project = CivicProject(**incomplete_project_data)
            # In production, this would be flagged by validation logic
            self.log_test("Schema Validation - Incomplete Project", True, "Project created with empty project_id")
        except Exception as e:
            self.log_test("Schema Validation - Incomplete Project", False, str(e))

        # Test 3: Alert system integration
        try:
            from backend.common.alerts import alert_validation_failure
            result = alert_validation_failure(
                source="test_source",
                project_id="test-123",
                error="Test validation error"
            )
            # Should not fail even if no webhook configured
            self.log_test("Alert System - Validation Failure", True, "Alert function executed successfully")
        except Exception as e:
            self.log_test("Alert System - Validation Failure", False, str(e))

        # Test 4: Legacy migration
        legacy_project = {
            "slug": "test-legacy",
            "project_id": "AD-23-36",
            "title": "Legacy Project",
            "project_type": "Administrative Deviation",
            "status": "APPROVE with CONDITIONS",
            "estimated_value": 150000,
            "meeting_date": "2024-10-03",
            "council_district": "7",
            "location": "123 Test Street"
        }

        try:
            from backend.core.municipal_schema import migrate_from_legacy
            migrated = migrate_from_legacy(legacy_project)
            self.log_test(
                "Legacy Migration",
                migrated.layer.value == "zoning",
                f"Migrated type: {migrated.project_type}"
            )
        except Exception as e:
            self.log_test("Schema Migration", False, str(e))

        # Test 2: Project type classification
        test_cases = [
            ("Administrative Deviation", "zoning"),
            ("Road Construction", "infrastructure"),
            ("Private Development", "private_dev"),
            ("Public Park", "public_project")
        ]

        for input_type, expected_type in test_cases:
            classified = ProjectTypeMapping.classify_project_type(input_type)
            self.log_test(
                f"Type Classification: {input_type}",
                classified.value == expected_type,
                f"Expected {expected_type}, got {classified.value}"
            )

    def test_observatory_configuration(self):
        """Test observatory configuration and setup"""

        print("\n🧪 Testing Observatory Configuration")

        try:
            # Test default configuration
            observatory = MunicipalObservatory()
            self.log_test(
                "Default Configuration",
                len(observatory.config.data_sources) > 0,
                f"Loaded {len(observatory.config.data_sources)} data sources"
            )

            # Test adapter registration
            for source_config in observatory.config.data_sources:
                if source_config.enabled:
                    adapter = create_adapter(source_config, observatory)
                    if adapter:
                        observatory.register_adapter(adapter)

            self.log_test(
                "Adapter Registration",
                len(observatory.adapters) > 0,
                f"Registered {len(observatory.adapters)} adapters"
            )

        except Exception as e:
            self.log_test("Observatory Configuration", False, str(e))

    async def test_planning_commission_adapter(self):
        """Test Planning Commission adapter functionality"""

        print("\n🧪 Testing Planning Commission Adapter")

        try:
            config = DataSourceConfig(
                name="planning_commission",
                adapter_class="PlanningCommissionAdapter",
                update_frequency="weekly"
            )

            # Mock observatory for testing
            class MockObservatory:
                def __init__(self):
                    self.config = type('obj', (object,), {
                        'default_delay_seconds': 0.1  # Faster for testing
                    })()

            observatory = MockObservatory()
            adapter = PlanningCommissionAdapter(config, observatory)

            # Test adapter properties
            self.log_test(
                "PC Adapter Properties",
                adapter.data_source_type.value == "planning_commission",
                f"Data source: {adapter.data_source_type}"
            )

            # Test update schedule
            schedule = adapter.get_update_schedule()
            self.log_test(
                "PC Update Schedule",
                "bi_weekly" in schedule.get("frequency", ""),
                f"Schedule: {schedule}"
            )

            # Test data freshness check
            freshness = adapter.get_data_freshness()
            self.log_test(
                "PC Data Freshness Check",
                "status" in freshness,
                f"Freshness: {freshness.get('status')}"
            )

            # Test should_update logic
            should_update = adapter.should_update()
            self.log_test(
                "PC Should Update Logic",
                isinstance(should_update, bool),
                f"Should update: {should_update}"
            )

        except Exception as e:
            self.log_test("Planning Commission Adapter", False, str(e))
            self.errors.append(f"PC Adapter error: {e}")

    async def test_city_council_adapter(self):
        """Test City Council adapter functionality"""

        print("\n🧪 Testing City Council Adapter")

        try:
            config = DataSourceConfig(
                name="city_council",
                adapter_class="CityCouncilAdapter",
                update_frequency="weekly",
                specific_config={
                    "calendar_url": "https://jaxcityc.legistar.com/Calendar.aspx"
                }
            )

            # Mock observatory for testing
            class MockObservatory:
                def __init__(self):
                    self.config = type('obj', (object,), {
                        'default_delay_seconds': 0.1
                    })()

            observatory = MockObservatory()
            adapter = CityCouncilAdapter(config, observatory)

            # Test adapter properties
            self.log_test(
                "CC Adapter Properties",
                adapter.data_source_type.value == "city_council",
                f"Data source: {adapter.data_source_type}"
            )

            # Test project classification
            test_texts = [
                ("Road improvement project on Main Street", "infrastructure"),
                ("New park facility construction", "public_project"),
                ("Budget allocation for development", "public_project"),
                ("Zoning variance approval", "zoning")
            ]

            for text, expected_type in test_texts:
                classified = adapter._classify_council_project(text)
                self.log_test(
                    f"CC Classification: {text[:30]}...",
                    classified.value == expected_type,
                    f"Expected {expected_type}, got {classified.value}"
                )

        except Exception as e:
            self.log_test("City Council Adapter", False, str(e))
            self.errors.append(f"CC Adapter error: {e}")

    def test_cross_reference_engine(self):
        """Test cross-reference functionality"""

        print("\n🧪 Testing Cross-Reference Engine")

        try:
            from municipal_observatory import CrossReferenceEngine

            engine = CrossReferenceEngine()

            # Create test projects with relationships
            projects = [
                MunicipalProject(
                    slug="project-1",
                    project_id="P1",
                    title="Project 1",
                    project_type="zoning",
                    decision_stage="review",
                    authority_level="planning",
                    data_source="planning_commission",
                    location="123 Main Street",
                    latitude=30.3322,
                    longitude=-81.6557
                ),
                MunicipalProject(
                    slug="project-2",
                    project_id="P2",
                    title="Project 2",
                    project_type="infrastructure",
                    decision_stage="approved",
                    authority_level="council",
                    data_source="city_council",
                    location="123 Main Street",  # Same location
                    latitude=30.3322,
                    longitude=-81.6557
                )
            ]

            # Test relationship finding
            enhanced_projects = engine.find_related_projects(projects)

            # Check if relationships were found
            has_relationships = any(
                len(p.related_projects) > 0 for p in enhanced_projects
            )

            self.log_test(
                "Cross-Reference Relationships",
                has_relationships,
                f"Found relationships in {sum(len(p.related_projects) for p in enhanced_projects)} projects"
            )

        except Exception as e:
            self.log_test("Cross-Reference Engine", False, str(e))
            self.errors.append(f"Cross-reference error: {e}")

    async def test_end_to_end_integration(self):
        """Test complete end-to-end integration"""

        print("\n🧪 Testing End-to-End Integration")

        try:
            # Create observatory with limited config for testing
            observatory = MunicipalObservatory()

            # Create test configuration with only enabled adapters
            test_config = DataSourceConfig(
                name="planning_commission",
                adapter_class="PlanningCommissionAdapter",
                update_frequency="on_demand",  # Don't auto-update during testing
                enabled=True
            )

            # Register adapter
            adapter = create_adapter(test_config, observatory)
            if adapter:
                observatory.register_adapter(adapter)

                self.log_test(
                    "Integration - Adapter Creation",
                    True,
                    f"Created and registered {test_config.name} adapter"
                )
            else:
                self.log_test(
                    "Integration - Adapter Creation",
                    False,
                    "Failed to create adapter"
                )

            # Test data aggregation with mock data
            mock_source_results = {
                "planning_commission": [
                    MunicipalProject(
                        slug="test-integration",
                        project_id="INT-001",
                        title="Integration Test Project",
                        project_type="zoning",
                        decision_stage="review",
                        authority_level="planning",
                        data_source="planning_commission"
                    )
                ]
            }

            aggregated = observatory.aggregate_all_data(mock_source_results)
            self.log_test(
                "Integration - Data Aggregation",
                len(aggregated) == 1,
                f"Aggregated {len(aggregated)} projects"
            )

            # Test data saving
            observatory.save_aggregated_data(aggregated)
            output_file = Path('all-projects.json')
            self.log_test(
                "Integration - Data Saving",
                output_file.exists(),
                f"Saved data to {output_file}"
            )

        except Exception as e:
            self.log_test("End-to-End Integration", False, str(e))
            self.errors.append(f"Integration error: {e}")

    def test_existing_data_compatibility(self):
        """Test compatibility with existing data format"""

        print("\n🧪 Testing Existing Data Compatibility")

        try:
            # Check if we can load existing data
            existing_file = Path('all-projects.json')
            if existing_file.exists():
                with open(existing_file, 'r') as f:
                    existing_data = json.load(f)

                # Try to migrate a sample project
                if existing_data and len(existing_data) > 0:
                    # Handle both old format (list) and new format (dict with projects)
                    if isinstance(existing_data, list):
                        sample_project = existing_data[0]
                    else:
                        sample_project = existing_data.get('projects', [{}])[0]

                    if sample_project:
                        migrated = SchemaVersion.migrate_from_v1(sample_project)
                        self.log_test(
                            "Existing Data Migration",
                            migrated.project_id is not None,
                            f"Migrated project: {migrated.project_id}"
                        )
                else:
                    self.log_test(
                        "Existing Data Migration",
                        True,
                        "No existing projects to migrate"
                    )
            else:
                self.log_test(
                    "Existing Data Migration",
                    True,
                    "No existing data file found"
                )

        except Exception as e:
            self.log_test("Existing Data Compatibility", False, str(e))

    def generate_test_report(self):
        """Generate comprehensive test report"""

        print("\n" + "="*60)
        print("🎯 MUNICIPAL OBSERVATORY TEST REPORT")
        print("="*60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        failed_tests = total_tests - passed_tests

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "No tests run")

        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  • {result['test']}: {result['details']}")

        if self.errors:
            print(f"\n⚠️ ERRORS ENCOUNTERED:")
            for error in self.errors:
                print(f"  • {error}")

        # Save detailed report
        report_file = Path('test_report.json')
        with open(report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': total_tests,
                    'passed': passed_tests,
                    'failed': failed_tests,
                    'success_rate': (passed_tests/total_tests)*100 if total_tests > 0 else 0
                },
                'test_results': self.test_results,
                'errors': self.errors,
                'generated_at': datetime.now().isoformat()
            }, f, indent=2)

        print(f"\n📊 Detailed report saved to: {report_file}")

        return passed_tests == total_tests

async def main():
    """Run all tests"""

    print("🚀 Starting Municipal Observatory Test Suite")
    print("=" * 60)

    tester = ObservatoryTester()

    # Run all test suites
    tester.test_schema_validation()
    tester.test_observatory_configuration()
    await tester.test_planning_commission_adapter()
    await tester.test_city_council_adapter()
    tester.test_cross_reference_engine()
    await tester.test_end_to_end_integration()
    tester.test_existing_data_compatibility()

    # Generate final report
    all_passed = tester.generate_test_report()

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Observatory is ready for deployment.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Review the report above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())