#!/usr/bin/env python3
"""
Test suite for current Municipal Observatory implementation
Tests schema validation, adapters, and data collection
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Import current observatory components
from backend.core.municipal_observatory import load_sources, get_adapter_function
from backend.core.agenda_schema import validate_agenda_item, validate_notice_item
from backend.adapters.city_council_fetch import fetch as city_council_fetch
from backend.adapters.ddrb_fetch import fetch as ddrb_fetch


class CurrentObservatoryTester:
    """Test suite for current Municipal Observatory implementation"""

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

    def test_sources_configuration(self):
        """Test sources.yaml configuration loading"""
        print("\n🧪 Testing Sources Configuration")

        try:
            sources, config = load_sources()

            self.log_test(
                "Sources Configuration Loading",
                len(sources) > 0,
                f"Loaded {len(sources)} sources from sources.yaml"
            )

            # Check required sources are present
            source_ids = [s['id'] for s in sources]
            required_sources = ['city_council', 'ddrb', 'planning_commission', 'infrastructure_committee']

            for required in required_sources:
                self.log_test(
                    f"Required Source: {required}",
                    required in source_ids,
                    f"Found {required} in configuration"
                )

            # Test enabled/disabled status
            enabled_sources = [s for s in sources if s.get('enabled', False)]
            self.log_test(
                "Enabled Sources",
                len(enabled_sources) >= 4,  # Should have at least 4 enabled
                f"{len(enabled_sources)} sources enabled"
            )

        except Exception as e:
            self.log_test("Sources Configuration Loading", False, str(e))
            self.errors.append(f"Config error: {e}")

    def test_schema_validation(self):
        """Test schema validation with various data scenarios"""
        print("\n🧪 Testing Schema Validation")

        # Test 1: Valid agenda item
        valid_item = {
            "board": "Planning Commission",
            "date": "2025-09-20",
            "title": "Test agenda item",
            "url": "https://example.com/agenda.pdf",
            "flagged": False
        }

        try:
            validated = validate_agenda_item(valid_item)
            self.log_test(
                "Schema Validation - Valid Item",
                validated.board == "Planning Commission",
                f"Validated item: {validated.title}"
            )
        except Exception as e:
            self.log_test("Schema Validation - Valid Item", False, str(e))

        # Test 2: Item with missing fields (should be flagged)
        incomplete_item = {
            "board": "",
            "date": "",
            "title": "Incomplete item",
            "flagged": False
        }

        try:
            flagged = validate_agenda_item(incomplete_item)
            self.log_test(
                "Schema Validation - Flagged Item",
                flagged.flagged == True,
                f"Item correctly flagged for missing fields"
            )
        except Exception as e:
            self.log_test("Schema Validation - Flagged Item", False, str(e))

        # Test 3: Notice item validation
        notice_item = {
            "board": "Development Services",
            "date": "2025-09-20",
            "title": "Development notice",
            "flagged": False
        }

        try:
            validated_notice = validate_notice_item(notice_item)
            self.log_test(
                "Schema Validation - Notice Item",
                validated_notice.board == "Development Services",
                f"Validated notice: {validated_notice.title}"
            )
        except Exception as e:
            self.log_test("Schema Validation - Notice Item", False, str(e))

    def test_adapter_functions(self):
        """Test adapter function imports and basic functionality"""
        print("\n🧪 Testing Adapter Functions")

        # Test adapter function loading
        adapters_to_test = [
            "planning_commission_adapter",
            "infrastructure_adapter",
            "private_development_adapter",
            "public_projects_adapter",
            "city_council_adapter",
            "ddrb_adapter"
        ]

        for adapter_name in adapters_to_test:
            try:
                adapter_func = get_adapter_function(adapter_name)
                self.log_test(
                    f"Adapter Import: {adapter_name}",
                    adapter_func is not None,
                    f"Successfully imported {adapter_name}"
                )
            except Exception as e:
                self.log_test(f"Adapter Import: {adapter_name}", False, str(e))

    def test_city_council_adapter(self):
        """Test City Council adapter specifically"""
        print("\n🧪 Testing City Council Adapter")

        try:
            items = city_council_fetch()

            self.log_test(
                "City Council Fetch",
                len(items) > 0,
                f"Fetched {len(items)} items from City Council"
            )

            if items:
                # Test first item structure
                item = items[0]
                required_fields = ['board', 'date', 'title', 'url']

                for field in required_fields:
                    self.log_test(
                        f"City Council Item - {field}",
                        field in item,
                        f"Field '{field}' present in item"
                    )

                # Test schema validation on real item
                try:
                    validated = validate_agenda_item(item)
                    self.log_test(
                        "City Council Schema Validation",
                        True,
                        f"Item validates as: {validated.title[:50]}..."
                    )
                except Exception as e:
                    self.log_test("City Council Schema Validation", False, str(e))

        except Exception as e:
            self.log_test("City Council Adapter", False, str(e))
            self.errors.append(f"City Council error: {e}")

    def test_ddrb_adapter(self):
        """Test DDRB adapter specifically"""
        print("\n🧪 Testing DDRB Adapter")

        try:
            items = ddrb_fetch()

            self.log_test(
                "DDRB Fetch",
                len(items) >= 1,  # Should at least return fallback
                f"Fetched {len(items)} items from DDRB"
            )

            if items:
                # Test item structure
                item = items[0]
                self.log_test(
                    "DDRB Item Structure",
                    'board' in item and 'Downtown Development Review Board' in str(item['board']),
                    f"Board: {item.get('board', 'missing')}"
                )

                # Test schema validation
                try:
                    validated = validate_agenda_item(item)
                    self.log_test(
                        "DDRB Schema Validation",
                        True,
                        f"Item validates: {validated.flagged}"
                    )
                except Exception as e:
                    self.log_test("DDRB Schema Validation", False, str(e))

        except Exception as e:
            self.log_test("DDRB Adapter", False, str(e))
            self.errors.append(f"DDRB error: {e}")

    def test_data_aggregation(self):
        """Test data aggregation functionality"""
        print("\n🧪 Testing Data Aggregation")

        try:
            from backend.tools.aggregate_data import aggregate_municipal_data

            # Test aggregation with current data
            result = aggregate_municipal_data()

            self.log_test(
                "Data Aggregation",
                result['total_items'] > 0,
                f"Aggregated {result['total_items']} total items"
            )

            # Check output file
            output_file = Path("frontend/municipal-data.json")
            self.log_test(
                "Aggregation Output File",
                output_file.exists(),
                f"Created output file: {output_file}"
            )

            # Test JSON structure
            if output_file.exists():
                with open(output_file) as f:
                    data = json.load(f)

                required_fields = ['timestamp', 'total_items', 'sources', 'projects', 'summary']
                for field in required_fields:
                    self.log_test(
                        f"Aggregation Structure - {field}",
                        field in data,
                        f"Field '{field}' present in output"
                    )

        except Exception as e:
            self.log_test("Data Aggregation", False, str(e))
            self.errors.append(f"Aggregation error: {e}")

    def test_flagged_items_handling(self):
        """Test flagged items are properly identified"""
        print("\n🧪 Testing Flagged Items Handling")

        try:
            # Test items that should be flagged
            test_cases = [
                {
                    "board": "",  # Missing board
                    "date": "2025-09-20",
                    "title": "Test item",
                    "expected_flagged": True
                },
                {
                    "board": "Planning Commission",
                    "date": "",  # Missing date
                    "title": "Test item",
                    "expected_flagged": True
                },
                {
                    "board": "Planning Commission",
                    "date": "2025-09-20",
                    "title": "Complete item",
                    "expected_flagged": False
                }
            ]

            for i, case in enumerate(test_cases):
                expected = case.pop('expected_flagged')
                validated = validate_agenda_item(case)

                self.log_test(
                    f"Flagged Item Test {i+1}",
                    validated.flagged == expected,
                    f"Expected flagged={expected}, got flagged={validated.flagged}"
                )

        except Exception as e:
            self.log_test("Flagged Items Handling", False, str(e))

    def generate_test_report(self):
        """Generate test report"""
        print("\n" + "="*60)
        print("🎯 CURRENT MUNICIPAL OBSERVATORY TEST REPORT")
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
        report_file = Path('current_test_report.json')
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


def main():
    """Run all current implementation tests"""
    print("🚀 Starting Current Municipal Observatory Test Suite")
    print("=" * 60)

    tester = CurrentObservatoryTester()

    # Run all test suites
    tester.test_sources_configuration()
    tester.test_schema_validation()
    tester.test_adapter_functions()
    tester.test_city_council_adapter()
    tester.test_ddrb_adapter()
    tester.test_data_aggregation()
    tester.test_flagged_items_handling()

    # Generate final report
    all_passed = tester.generate_test_report()

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Current observatory implementation is working correctly.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Review the report above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)