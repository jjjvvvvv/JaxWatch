#!/usr/bin/env python3
"""
JaxWatch Image Prompt Generator
===============================

Generates descriptive prompts for image generation tools (including streetview-focused
tools like "nano banana" or general AI image generators) based on Jacksonville civic
project data.

This tool operates independently of core JaxWatch functionality and can be evolved
over time as a creative visualization feature.

Usage:
    python3 tools/image_prompt_generator.py --preview
    python3 tools/image_prompt_generator.py --type streetview --output prompts.txt
    python3 tools/image_prompt_generator.py --filter "Laura Street" --type both
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class JaxWatchImagePromptGenerator:
    """
    Generates creative image prompts from Jacksonville civic project data.

    Designed to work with:
    - Streetview-focused image generation tools
    - General AI image generators (DALL-E, Midjourney, Stable Diffusion)
    - Urban planning visualization tools
    """

    def __init__(self, projects_file: str = None):
        base_dir = Path(__file__).parent.parent
        default_file = base_dir / "admin_ui" / "data" / "projects_index.json"
        self.projects_file = projects_file or str(default_file)
        self.projects = self._load_projects()

    def _load_projects(self) -> List[Dict]:
        """Load projects from the JaxWatch data file."""
        try:
            with open(self.projects_file) as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Projects file not found: {self.projects_file}")
            return []

    def _analyze_project_context(self, project: Dict) -> Dict:
        """Deep analysis of project context for better prompt generation."""
        # Combine all text content
        all_text = []
        financial_mentions = []
        document_types = set()

        for mention in project.get('mentions', []):
            snippet = mention.get('snippet', '').strip()
            doc_type = mention.get('doc_type', '').strip()

            if snippet:
                all_text.append(snippet)
            if doc_type:
                document_types.add(doc_type)

            # Extract financial amounts
            financial_matches = re.findall(r'\$[\d,]+', snippet)
            financial_mentions.extend(financial_matches)

        full_text = ' '.join(all_text).lower()

        # Enhanced keyword analysis
        project_characteristics = {
            'scale': self._determine_project_scale(financial_mentions, full_text),
            'type': self._classify_development_type(full_text, project['title']),
            'location_context': self._analyze_location_context(project.get('address', ''), full_text),
            'civic_process': self._analyze_civic_process(document_types, full_text),
            'architectural_style': self._infer_architectural_style(full_text, project['title']),
            'timeline': self._estimate_timeline(project.get('meeting_date', ''), full_text)
        }

        return {
            'full_text': full_text,
            'financial_amounts': financial_mentions,
            'characteristics': project_characteristics,
            'doc_types': list(document_types)
        }

    def _determine_project_scale(self, financials: List[str], text: str) -> str:
        """Determine project scale from financial and textual clues."""
        if financials:
            amounts = []
            for amt in financials:
                try:
                    clean_amt = int(re.sub(r'[,$]', '', amt))
                    amounts.append(clean_amt)
                except ValueError:
                    continue

            if amounts:
                max_amount = max(amounts)
                if max_amount > 5000000:
                    return "major_development"
                elif max_amount > 1000000:
                    return "significant_development"
                elif max_amount > 100000:
                    return "moderate_development"

        # Scale indicators in text
        if any(word in text for word in ['major', 'large-scale', 'master plan', 'phases']):
            return "major_development"
        elif any(word in text for word in ['renovation', 'improvement', 'enhancement']):
            return "improvement_project"

        return "standard_development"

    def _classify_development_type(self, text: str, title: str) -> str:
        """Classify the type of development."""
        title_lower = title.lower()
        combined = (text + ' ' + title_lower).lower()

        if 'mixed' in combined and 'use' in combined:
            return "mixed_use"
        elif any(word in combined for word in ['residential', 'apartment', 'housing', 'units']):
            return "residential"
        elif any(word in combined for word in ['office', 'commercial', 'retail', 'store']):
            return "commercial"
        elif any(word in combined for word in ['hotel', 'hospitality']):
            return "hospitality"
        elif any(word in combined for word in ['parking', 'garage']):
            return "parking_infrastructure"
        elif any(word in combined for word in ['streetscape', 'street', 'sidewalk', 'public']):
            return "public_infrastructure"
        elif any(word in combined for word in ['park', 'green', 'plaza']):
            return "public_space"

        return "general_development"

    def _analyze_location_context(self, address: str, text: str) -> Dict:
        """Analyze location-specific context."""
        context = {
            'downtown': False,
            'waterfront': False,
            'historic': False,
            'specific_area': None
        }

        combined = (address + ' ' + text).lower()

        # Downtown indicators
        if any(word in combined for word in ['downtown', 'laura', 'monroe', 'forsyth', 'adams', 'duval']):
            context['downtown'] = True

        # Waterfront indicators
        if any(word in combined for word in ['river', 'waterfront', 'st johns', 'southbank']):
            context['waterfront'] = True

        # Historic indicators
        if any(word in combined for word in ['historic', 'heritage', 'preservation']):
            context['historic'] = True

        # Specific areas
        if 'shipyard' in combined:
            context['specific_area'] = 'shipyards'
        elif 'southbank' in combined:
            context['specific_area'] = 'southbank'

        return context

    def _analyze_civic_process(self, doc_types: set, text: str) -> str:
        """Analyze what stage of civic process the project is in."""
        if 'resolution' in doc_types:
            return "approved_project"
        elif any(word in text for word in ['proposal', 'proposed', 'plan']):
            return "proposed_project"
        elif any(word in text for word in ['construction', 'building', 'under way']):
            return "active_construction"
        else:
            return "planning_stage"

    def _infer_architectural_style(self, text: str, title: str) -> str:
        """Infer likely architectural style from project context."""
        combined = (text + ' ' + title).lower()

        if any(word in combined for word in ['modern', 'contemporary', 'glass', 'steel']):
            return "modern"
        elif any(word in combined for word in ['historic', 'preservation', 'restoration']):
            return "historic_preservation"
        elif 'mixed' in combined:
            return "mixed_contemporary"
        else:
            return "contemporary_urban"

    def _estimate_timeline(self, meeting_date: str, text: str) -> str:
        """Estimate project timeline."""
        if any(word in text for word in ['completed', 'finished', 'open']):
            return "completed"
        elif any(word in text for word in ['construction', 'building']):
            return "under_construction"
        elif meeting_date:
            try:
                # If recent meeting, likely active
                from datetime import datetime
                meeting_year = int(meeting_date[:4]) if meeting_date else 2024
                current_year = datetime.now().year
                if current_year - meeting_year <= 1:
                    return "recently_active"
            except:
                pass

        return "planned"

    def generate_streetview_prompt(self, project: Dict, context: Dict) -> str:
        """Generate a detailed streetview prompt optimized for visual generation."""
        chars = context['characteristics']
        location = context['characteristics']['location_context']

        address = project.get('address', 'downtown Jacksonville')
        title = project['title']

        # Base scene setting
        if chars['type'] == 'mixed_use':
            base_scene = f"Modern mixed-use development streetview at {address}, Jacksonville, Florida"
        elif chars['type'] == 'residential':
            base_scene = f"Contemporary residential development at {address}, Jacksonville, Florida"
        elif chars['type'] == 'commercial':
            base_scene = f"Commercial building development at {address}, Jacksonville, Florida"
        elif chars['type'] == 'public_infrastructure':
            base_scene = f"Enhanced streetscape and public infrastructure at {address}, Jacksonville, Florida"
        else:
            base_scene = f"Urban development project at {address}, Jacksonville, Florida"

        # Architectural and scale details
        architectural_details = []

        if chars['scale'] == 'major_development':
            architectural_details.append("large-scale modern architecture")
        elif chars['scale'] == 'significant_development':
            architectural_details.append("mid-rise contemporary building design")
        else:
            architectural_details.append("thoughtfully designed urban architecture")

        if chars['architectural_style'] == 'modern':
            architectural_details.append("glass and steel construction, clean lines")
        elif chars['architectural_style'] == 'historic_preservation':
            architectural_details.append("preserved historic facade with modern integration")
        else:
            architectural_details.append("contemporary Florida architectural style")

        # Environmental and location context
        environment_details = []

        if location['downtown']:
            environment_details.extend([
                "urban downtown setting",
                "mixed pedestrian and vehicle traffic",
                "city skyline visible in background"
            ])

        if location['waterfront']:
            environment_details.append("St. Johns River waterfront visible")

        if location['historic']:
            environment_details.append("historic district character")

        # Standard Jacksonville elements
        environment_details.extend([
            "subtropical landscaping with palm trees",
            "Florida sunshine lighting",
            "wide sidewalks with modern streetscape elements"
        ])

        # Construction/completion state
        completion_details = []
        if chars['timeline'] == 'completed':
            completion_details.append("completed and occupied building")
        elif chars['timeline'] == 'under_construction':
            completion_details.append("active construction with safety barriers and equipment")
        else:
            completion_details.append("finished development ready for use")

        # Combine all elements
        prompt_parts = [
            base_scene,
            ', '.join(architectural_details),
            ', '.join(environment_details),
            ', '.join(completion_details),
            "professional architectural photography, high resolution, realistic lighting, urban planning visualization"
        ]

        return '. '.join(prompt_parts) + '.'

    def generate_aerial_prompt(self, project: Dict, context: Dict) -> str:
        """Generate an aerial/drone view prompt."""
        chars = context['characteristics']
        location = context['characteristics']['location_context']

        address = project.get('address', 'downtown Jacksonville')

        prompt = f"Aerial drone view of development at {address}, Jacksonville, Florida. "

        # Add scale context
        if chars['scale'] == 'major_development':
            prompt += "Large development footprint visible from above, multiple buildings or phases. "

        # Location context
        if location['downtown']:
            prompt += "Downtown Jacksonville urban grid pattern, "
        if location['waterfront']:
            prompt += "St. Johns River and waterfront context visible, "

        # Standard aerial elements
        prompt += "bird's-eye perspective showing urban planning integration, "
        prompt += "surrounding street network and neighboring buildings, "
        prompt += "green spaces and landscaping incorporated, "
        prompt += "professional urban planning visualization, "
        prompt += "high resolution aerial photography, clear weather, optimal lighting"

        return prompt

    def generate_conceptual_prompt(self, project: Dict, context: Dict) -> str:
        """Generate a conceptual/artistic interpretation prompt."""
        chars = context['characteristics']
        title = project['title']

        prompt = f"Artistic conceptual visualization of '{title}' development project, Jacksonville. "

        # Add conceptual elements based on project type
        if chars['type'] == 'mixed_use':
            prompt += "Dynamic mixed-use community space, vibrant street life, "
        elif chars['type'] == 'public_infrastructure':
            prompt += "Enhanced public realm, people-friendly streetscape, community gathering, "
        elif chars['civic_process'] == 'approved_project':
            prompt += "Vision of approved development bringing positive urban change, "

        prompt += "architectural rendering style, optimistic future vision, "
        prompt += "warm Florida lighting, people enjoying the space, "
        prompt += "urban planning concept art, inspirational presentation style"

        return prompt

    def generate_prompts_for_project(self, project: Dict,
                                   prompt_types: List[str] = None) -> Dict:
        """Generate all requested prompt types for a single project."""
        if prompt_types is None:
            prompt_types = ['streetview']

        context = self._analyze_project_context(project)
        prompts = {}

        if 'streetview' in prompt_types:
            prompts['streetview'] = self.generate_streetview_prompt(project, context)

        if 'aerial' in prompt_types:
            prompts['aerial'] = self.generate_aerial_prompt(project, context)

        if 'conceptual' in prompt_types:
            prompts['conceptual'] = self.generate_conceptual_prompt(project, context)

        return {
            'project_info': {
                'id': project.get('id'),
                'title': project['title'],
                'address': project.get('address'),
                'coordinates': (project.get('latitude'), project.get('longitude'))
            },
            'analysis': context['characteristics'],
            'prompts': prompts
        }

    def generate_all_prompts(self, project_filter: Optional[str] = None,
                           prompt_types: List[str] = None) -> List[Dict]:
        """Generate prompts for all eligible projects."""
        if prompt_types is None:
            prompt_types = ['streetview']

        results = []

        # Filter to projects with location data
        located_projects = [p for p in self.projects
                          if p.get('address') and p.get('latitude') and p.get('longitude')]

        if project_filter:
            located_projects = [p for p in located_projects
                              if project_filter.lower() in p['title'].lower()
                              or project_filter.lower() in p.get('address', '').lower()]

        for project in located_projects:
            result = self.generate_prompts_for_project(project, prompt_types)
            results.append(result)

        return results

    def export_for_image_generation(self, output_file: str = None,
                                   prompt_types: List[str] = None,
                                   project_filter: Optional[str] = None) -> str:
        """Export prompts in a format ready for image generation tools."""
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"jaxwatch_image_prompts_{timestamp}.txt"

        prompts_data = self.generate_all_prompts(project_filter, prompt_types)

        with open(output_file, 'w') as f:
            f.write("JaxWatch Jacksonville Development Image Prompts\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Projects: {len(prompts_data)}\n")
            f.write(f"Prompt types: {', '.join(prompt_types or ['streetview'])}\n")
            f.write("\nOptimized for: streetview generators, DALL-E, Midjourney, Stable Diffusion\n")
            f.write("\n" + "=" * 60 + "\n\n")

            for i, data in enumerate(prompts_data):
                info = data['project_info']
                analysis = data['analysis']

                f.write(f"PROJECT {i+1}: {info['title']}\n")
                f.write(f"Location: {info['address']}\n")
                f.write(f"Coordinates: {info['coordinates']}\n")
                f.write(f"Scale: {analysis['scale'].replace('_', ' ').title()}\n")
                f.write(f"Type: {analysis['type'].replace('_', ' ').title()}\n")
                f.write(f"Status: {analysis['civic_process'].replace('_', ' ').title()}\n")

                for prompt_type, prompt in data['prompts'].items():
                    f.write(f"\n{prompt_type.upper()} PROMPT:\n")
                    f.write(f"{prompt}\n")

                f.write("\n" + "-" * 80 + "\n\n")

        return output_file


def main():
    """Command-line interface for the image prompt generator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate image prompts from JaxWatch Jacksonville project data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --preview                          # Preview all streetview prompts
  %(prog)s --type aerial --output prompts.txt # Export aerial prompts
  %(prog)s --filter "Laura" --type both       # Both types for Laura Street projects
  %(prog)s --type conceptual --preview        # Conceptual art prompts
        """
    )

    parser.add_argument('--filter', type=str,
                       help='Filter projects by title/address substring')
    parser.add_argument('--type',
                       choices=['streetview', 'aerial', 'conceptual', 'both', 'all'],
                       default='streetview',
                       help='Type of prompts to generate')
    parser.add_argument('--output', type=str,
                       help='Output file for prompts (default: timestamped file)')
    parser.add_argument('--preview', action='store_true',
                       help='Preview prompts in terminal instead of saving')

    args = parser.parse_args()

    # Map type options to actual types
    type_mapping = {
        'streetview': ['streetview'],
        'aerial': ['aerial'],
        'conceptual': ['conceptual'],
        'both': ['streetview', 'aerial'],
        'all': ['streetview', 'aerial', 'conceptual']
    }

    prompt_types = type_mapping[args.type]

    generator = JaxWatchImagePromptGenerator()

    if args.preview:
        print(f"JaxWatch Image Prompt Generator - Preview Mode")
        print(f"Prompt types: {', '.join(prompt_types)}")
        if args.filter:
            print(f"Filter: {args.filter}")
        print("=" * 60)

        results = generator.generate_all_prompts(
            project_filter=args.filter,
            prompt_types=prompt_types
        )

        if not results:
            print("No projects found matching criteria.")
            return

        for i, result in enumerate(results):
            info = result['project_info']
            analysis = result['analysis']

            print(f"\n🏗️  PROJECT {i+1}: {info['title']}")
            print(f"   📍 {info['address']}")
            print(f"   📊 {analysis['scale'].replace('_', ' ').title()} | {analysis['type'].replace('_', ' ').title()}")

            for prompt_type, prompt in result['prompts'].items():
                print(f"\n   🎨 {prompt_type.upper()}:")
                print(f"   {prompt}")

        print(f"\n📈 Generated {len(results)} project prompt sets")

    else:
        output_file = generator.export_for_image_generation(
            output_file=args.output,
            prompt_types=prompt_types,
            project_filter=args.filter
        )
        print(f"✅ Image prompts exported to: {output_file}")
        print(f"🎨 Ready for use with image generation tools!")


if __name__ == '__main__':
    main()