#!/usr/bin/env python3

import pdfplumber
import re
import json
import sys
import os
from datetime import datetime
from pathlib import Path

class ProjectExtractor:
    def __init__(self):
        self.projects = []
        self.meeting_info = {}
        self.errors = []
        self.warnings = []

    def extract_projects_from_pdf(self, pdf_path):
        """Extract structured project data from Jacksonville Planning Commission agenda PDF"""

        # Validate input
        if not self._validate_pdf_file(pdf_path):
            return None

        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_text = self._extract_all_text(pdf)
                if not all_text:
                    self.errors.append("No text could be extracted from PDF")
                    return None

                return self._extract_projects_from_text(all_text, pdf_path)

        except Exception as e:
            self.errors.append(f"Failed to process PDF: {str(e)}")
            print(f"❌ Error processing PDF: {e}")
            return None

    def extract_projects_from_text(self, text_content: str, source_identifier: str = "text_input"):
        """Extract projects from pre-extracted text content"""
        return self._extract_projects_from_text(text_content, source_identifier)

    def _extract_projects_from_text(self, all_text: str, source_identifier):
        """Internal method to extract projects from text content"""

        try:
            # Extract meeting information
            self._extract_meeting_info(all_text, source_identifier)

            # Extract projects
            self._extract_projects(all_text, source_identifier)

            # Validate extracted data
            self._validate_extracted_data()

            print(f"✅ Extraction completed successfully")
            print(f"📊 Extracted {len(self.projects)} projects")
            if self.warnings:
                print(f"⚠️  {len(self.warnings)} warnings")
            if self.errors:
                print(f"❌ {len(self.errors)} errors")

            return {
                "meeting_info": self.meeting_info,
                "projects": self.projects,
                "extraction_metadata": {
                    "extracted_at": datetime.now().isoformat(),
                    "source": str(source_identifier),
                    "total_projects": len(self.projects),
                    "warnings": self.warnings,
                    "errors": self.errors
                }
            }

        except Exception as e:
            self.errors.append(f"Failed to process text: {str(e)}")
            print(f"❌ Error processing text: {e}")
            return None

    def _validate_pdf_file(self, pdf_path):
        """Validate that the PDF file exists and is readable"""
        pdf_file = Path(pdf_path)

        if not pdf_file.exists():
            self.errors.append(f"PDF file not found: {pdf_path}")
            print(f"❌ PDF file not found: {pdf_path}")
            return False

        if pdf_file.stat().st_size == 0:
            self.errors.append(f"PDF file is empty: {pdf_path}")
            print(f"❌ PDF file is empty: {pdf_path}")
            return False

        if not str(pdf_path).lower().endswith('.pdf'):
            self.warnings.append(f"File doesn't have .pdf extension: {pdf_path}")
            print(f"⚠️  File doesn't have .pdf extension: {pdf_path}")

        return True

    def _extract_all_text(self, pdf):
        """Extract text from all pages with error handling"""
        all_text = ""

        try:
            if len(pdf.pages) == 0:
                self.errors.append("PDF has no pages")
                return None

            print(f"📄 Processing PDF with {len(pdf.pages)} pages")

            for i, page in enumerate(pdf.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        all_text += page_text + "\n"
                    else:
                        self.warnings.append(f"Page {i+1} has no extractable text")
                except Exception as e:
                    self.warnings.append(f"Failed to extract text from page {i+1}: {str(e)}")

            if not all_text.strip():
                self.errors.append("No text extracted from any page")
                return None

            return all_text

        except Exception as e:
            self.errors.append(f"Failed to extract text: {str(e)}")
            return None

    def _extract_meeting_info(self, text, pdf_path):
        """Extract meeting date and basic info"""
        try:
            # Look for meeting date
            date_match = re.search(r'(\w+,\s+\w+\s+\d+,\s+\d{4})', text)
            if date_match:
                self.meeting_info['meeting_date'] = date_match.group(1)
            else:
                self.warnings.append("Could not extract meeting date from PDF")

            self.meeting_info['source_pdf'] = str(pdf_path)

            # Look for commission info
            if 'Planning Commission' in text:
                self.meeting_info['commission_type'] = 'Planning Commission'
            else:
                self.warnings.append("Could not identify commission type")

        except Exception as e:
            self.warnings.append(f"Error extracting meeting info: {str(e)}")

    def _extract_projects(self, text, pdf_path):
        """Extract individual projects with enhanced error handling"""
        # Multiple regex patterns to catch different formats
        patterns = [
            # Standard format with Ex-Parte - location is on the district line
            r'(?:Ex-Parte\s+)?(\d+)\.\s*([A-Z0-9-]+(?:\s*\([^)]+\))?)\s*\n\s*Council District-(\d+)[^–]*–[^P]*Planning District-(\d+)\.?\s*([^S]*?)\s*Signs Posted:\s*(Yes|No)\s*\n\s*Request:\s*([^\n]+)\s*\n\s*Owner\(s\):\s*([^\n]+?)\s*Agent:\s*([^\n]+)\s*\n\s*Staff Recommendation:\s*([^\n]+)',

            # Alternative format without Ex-Parte - location is on the district line
            r'(\d+)\.\s*([A-Z0-9-]+(?:\s*\([^)]+\))?)\s*\n\s*Council District-(\d+)[^–]*–[^P]*Planning District-(\d+)\.?\s*([^S]*?)\s*Signs Posted:\s*(Yes|No)\s*\n\s*Request:\s*([^\n]+)\s*\n\s*Owner\(s\):\s*([^\n]+?)\s*Agent:\s*([^\n]+)\s*\n\s*Staff Recommendation:\s*([^\n]+)'
        ]

        total_matches = 0

        for pattern_idx, pattern in enumerate(patterns):
            matches = list(re.finditer(pattern, text, re.MULTILINE | re.DOTALL))
            print(f"🔍 Pattern {pattern_idx + 1} found {len(matches)} matches")

            for match in matches:
                try:
                    project = self._parse_project_match(match, pdf_path)
                    if project:
                        # Check for duplicates
                        if not any(p['project_id'] == project['project_id'] for p in self.projects):
                            self.projects.append(project)
                            total_matches += 1
                        else:
                            self.warnings.append(f"Duplicate project found: {project['project_id']}")
                except Exception as e:
                    self.warnings.append(f"Error parsing project match: {str(e)}")

        if total_matches == 0:
            self.warnings.append("No projects found using standard patterns")
            # Try a more lenient search
            self._try_lenient_extraction(text, pdf_path)

    def _parse_project_match(self, match, pdf_path):
        """Parse a regex match into a project object"""
        try:
            item_num = match.group(1)
            project_id = match.group(2).strip()
            council_district = match.group(3)
            planning_district = match.group(4)
            location = match.group(5).strip()
            signs_posted = match.group(6)
            request = match.group(7).strip()
            owners = match.group(8).strip()
            agent = match.group(9).strip()
            staff_recommendation = match.group(10).strip()

            # Validate required fields
            if not project_id or not request:
                self.warnings.append(f"Project missing required fields: {project_id}")
                return None

            # Clean and validate data
            location = self._clean_location(location)
            project_type = self._determine_project_type(project_id, request)

            if project_type == "Unknown":
                self.warnings.append(f"Could not determine project type for: {project_id}")

            # Generate slug
            slug = self._generate_slug(project_id, location)

            project = {
                "slug": slug,
                "project_id": project_id,
                "item_number": item_num,
                "meeting_date": self.meeting_info.get('meeting_date', ''),
                "title": request[:100] + "..." if len(request) > 100 else request,
                "location": location,
                "project_type": project_type,
                "request": request,
                "status": f"Planning Commission - {staff_recommendation}",
                "council_district": council_district,
                "planning_district": planning_district,
                "owners": owners,
                "agent": agent,
                "staff_recommendation": staff_recommendation,
                "signs_posted": signs_posted == "Yes",
                "source_pdf": str(pdf_path),
                "extracted_at": datetime.now().isoformat(),
                "tags": self._generate_tags(project_type, request, location)
            }

            return project

        except Exception as e:
            self.warnings.append(f"Error parsing project: {str(e)}")
            return None

    def _clean_location(self, location):
        """Clean and validate location string"""
        if not location:
            return ""

        # Remove extra whitespace and unwanted text
        location = re.sub(r'\s+', ' ', location)
        location = re.sub(r'Signs Posted:.*$', '', location).strip()

        # Extract actual addresses from location field
        # Look for common address patterns
        address_patterns = [
            r'(\d+[\w\s,]*(?:Boulevard|Blvd|Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Lane|Ln|Circle|Cir|Court|Ct|Way|Plaza|Pkwy|Parkway)[\w\s]*)',
            r'(\d+\s+[A-Za-z][^,]*)',  # General pattern for addresses starting with numbers
        ]

        for pattern in address_patterns:
            match = re.search(pattern, location, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # If no address pattern found, return cleaned location
        return location

    def _determine_project_type(self, project_id, request):
        """Determine project type from ID and request"""
        project_id_upper = project_id.upper()
        request_upper = request.upper()

        if project_id_upper.startswith('E-'):
            return "Exception"
        elif project_id_upper.startswith('V-'):
            return "Variance"
        elif project_id_upper.startswith('WLD-'):
            return "Waiver Liquor Distance"
        elif project_id_upper.startswith('MM-'):
            return "Minor Modification"
        elif project_id_upper.startswith('AD-'):
            return "Administrative Deviation"
        elif 'PUD' in project_id_upper or 'PUD' in request_upper:
            return "Planned Unit Development"
        elif re.match(r'\d{4}-\d+', project_id):
            if 'PUD' in request_upper:
                return "Planned Unit Development"
            else:
                return "Land Use/Zoning"

        return "Unknown"

    def _generate_slug(self, project_id, location):
        """Generate URL-friendly slug"""
        slug_base = project_id.lower().replace(' ', '-').replace('(', '').replace(')', '')
        slug_base = re.sub(r'[^\w\s-]', '', slug_base)

        if location:
            location_slug = re.sub(r'[^\w\s-]', '', location.lower())
            location_slug = re.sub(r'\s+', '-', location_slug)[:30]
            slug = f"{slug_base}-{location_slug}"
        else:
            slug = slug_base

        return re.sub(r'-+', '-', slug).strip('-')

    def _generate_tags(self, project_type, request, location):
        """Generate descriptive, factual tags without ranking or judgment"""
        tags = []

        # Add project type in plain English
        if project_type != "Unknown":
            tags.append(project_type.lower().replace(" ", "_"))

        # Descriptive content tags (factual, no judgment)
        request_lower = request.lower()
        location_lower = location.lower() if location else ""

        # Use type descriptions (what it actually is)
        descriptive_keywords = {
            'residential': ['residential', 'housing', 'townhome', 'townhouse', 'apartment', 'condo'],
            'commercial': ['commercial', 'retail', 'store', 'shop'],
            'mixed_use': ['mixed'],
            'restaurant': ['restaurant', 'dining', 'food service'],
            'office': ['office'],
            'medical': ['medical', 'clinic', 'hospital', 'healthcare'],
            'automotive': ['auto', 'car wash', 'vehicle'],
            'alcohol_sales': ['alcohol', 'liquor', 'beer', 'wine'],
            'drive_through': ['drive through', 'drive-through', 'drive thru'],
            'parking': ['parking'],
            'storage': ['storage', 'warehouse'],
            'gas_station': ['gas station', 'fuel', 'convenience store'],
            'setbacks': ['setback'],
            'density': ['density']
        }

        # Geographic descriptive tags (factual areas)
        geographic_keywords = {
            'downtown': ['downtown', 'core', 'central business'],
            'riverside': ['riverside'],
            'avondale': ['avondale'],
            'beaches': ['beach', 'neptune', 'atlantic beach', 'jacksonville beach'],
            'westside': ['westside', 'west jacksonville'],
            'northside': ['northside', 'north jacksonville'],
            'southside': ['southside', 'south jacksonville'],
            'mandarin': ['mandarin'],
            'orange_park': ['orange park'],
            'fleming_island': ['fleming island']
        }

        # Apply descriptive content tags
        for tag, keywords in descriptive_keywords.items():
            if any(keyword in request_lower for keyword in keywords):
                tags.append(tag)

        # Apply geographic tags
        for tag, keywords in geographic_keywords.items():
            if any(keyword in location_lower for keyword in keywords):
                tags.append(tag)

        # Size/scale descriptors (factual only)
        if 'pud' in project_type.lower() or 'planned unit development' in request_lower:
            tags.append('large_development')

        if any(unit_word in request_lower for unit_word in ['units', 'acres', 'square feet']):
            # Try to extract actual numbers for factual scale tags
            import re
            numbers = re.findall(r'\d+', request)
            if numbers:
                largest_num = max(int(n) for n in numbers)
                if largest_num >= 100:
                    tags.append('100plus_units')
                elif largest_num >= 50:
                    tags.append('50plus_units')

        return tags

    def _try_lenient_extraction(self, text, pdf_path):
        """Try more lenient extraction for edge cases"""
        # Look for any numbered items that might be projects
        lenient_pattern = r'(\d+)\.\s*([A-Z0-9-]+)[^\n]*([^\n]*Request:[^\n]+)'
        matches = re.finditer(lenient_pattern, text, re.MULTILINE)

        lenient_count = 0
        for match in matches:
            lenient_count += 1
            self.warnings.append(f"Found potential project with lenient matching: {match.group(2)}")

        if lenient_count > 0:
            self.warnings.append(f"Found {lenient_count} potential projects with lenient matching")

    def _validate_extracted_data(self):
        """Validate the quality of extracted data"""
        if not self.projects:
            self.errors.append("No projects were extracted")
            return

        # Check for data quality issues
        missing_location = sum(1 for p in self.projects if not p['location'])
        if missing_location > 0:
            self.warnings.append(f"{missing_location} projects missing location information")

        # Check for reasonable project counts
        if len(self.projects) > 50:
            self.warnings.append(f"Unusually high number of projects ({len(self.projects)}) - possible parsing error")
        elif len(self.projects) < 5:
            self.warnings.append(f"Unusually low number of projects ({len(self.projects)}) - possible parsing error")

        # Validate project IDs
        unique_ids = set(p['project_id'] for p in self.projects)
        if len(unique_ids) != len(self.projects):
            self.warnings.append("Duplicate project IDs found")

def main():
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    else:
        pdf_file = "sample-pc-agenda-10-03-24.pdf"

    print(f"🚀 Starting extraction from: {pdf_file}")

    extractor = ProjectExtractor()
    result = extractor.extract_projects_from_pdf(pdf_file)

    if result:
        # Generate output filename
        base_name = Path(pdf_file).stem
        output_file = f"extracted-{base_name}.json"

        # Save results
        try:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"💾 Data saved to: {output_file}")
        except Exception as e:
            print(f"❌ Failed to save data: {e}")
            return 1

        # Print summary
        print(f"\n📋 EXTRACTION SUMMARY")
        print(f"Meeting: {result['meeting_info'].get('meeting_date', 'Unknown')}")
        print(f"Projects: {len(result['projects'])}")
        print(f"Warnings: {len(result['extraction_metadata']['warnings'])}")
        print(f"Errors: {len(result['extraction_metadata']['errors'])}")

        return 0
    else:
        print("❌ Extraction failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())