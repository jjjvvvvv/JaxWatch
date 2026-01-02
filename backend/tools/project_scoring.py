#!/usr/bin/env python3
"""
Project Scoring System for JaxWatch

Implements confidence and importance scoring for civic projects based on:
- Confidence: How likely a project is "real" vs administrative noise
- Importance: Impact, scale, and public relevance

Key insight: Projects are hypotheses that accrete evidence over time.
"""

import json
import re
import logging
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class ProjectScorer:
    """Computes confidence and importance scores for civic projects."""

    def __init__(self):
        # Money extraction patterns
        self.money_patterns = [
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:million|M)\b',  # $5.2 million, $5.2M
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:thousand|K)\b',  # $500 thousand, $500K
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b',                    # $1,500,000
        ]

        # Language scoring patterns
        self.penalty_words = {
            'approval of minutes', 'officer elections', 'procedural',
            'discussion only', 'presentation only', 'informational only'
        }

        self.bonus_words = {
            'development', 'redevelopment', 'incentive', 'agreement',
            'master plan', 'site plan', 'final approval', 'construction',
            'mixed-use', 'public-private', 'investment', 'funding'
        }

        # Scale indicators
        self.high_impact_terms = {
            'redevelopment', 'mixed-use', 'district', 'block', 'riverfront',
            'downtown', 'plaza', 'complex', 'tower', 'garage', 'park'
        }

        self.low_impact_terms = {
            'sign', 'awning', 'variance only', 'exception only', 'minor variance'
        }

        # Publicness indicators
        self.publicness_terms = {
            'public land', 'riverwalk', 'street', 'park', 'public fund',
            'public-private', 'city property', 'municipal', 'tax increment',
            'TIF', 'CRA', 'incentive package'
        }

    def extract_money_mentions(self, project: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract money mentions from project text with context."""
        money_mentions = []

        for mention in project.get('mentions', []):
            snippet = mention.get('snippet', '')
            title = mention.get('title', '')
            text = f"{title} {snippet}"

            # Find money patterns
            for pattern in self.money_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    amount_str = match.group(1)
                    full_match = match.group(0)

                    # Convert to numeric value
                    amount_numeric = self._parse_amount(amount_str, full_match)
                    if amount_numeric > 0:
                        # Extract context around the match
                        start = max(0, match.start() - 50)
                        end = min(len(text), match.end() + 50)
                        context = text[start:end].strip()

                        money_mentions.append({
                            'amount': full_match,
                            'amount_numeric': amount_numeric,
                            'context': context,
                            'source_url': mention.get('url'),
                            'doc_type': mention.get('doc_type'),
                            'page': mention.get('page'),
                            'confidence': 'high' if 'M' in full_match or 'million' in full_match else 'medium'
                        })

        # Sort by amount (highest first) and deduplicate
        money_mentions.sort(key=lambda x: x['amount_numeric'], reverse=True)
        seen_amounts = set()
        unique_mentions = []
        for mention in money_mentions:
            amount = mention['amount_numeric']
            if amount not in seen_amounts:
                seen_amounts.add(amount)
                unique_mentions.append(mention)

        return unique_mentions[:5]  # Top 5 mentions

    def _parse_amount(self, amount_str: str, full_match: str) -> int:
        """Parse monetary amount to numeric value."""
        try:
            # Remove commas and convert to float
            base_amount = float(amount_str.replace(',', ''))

            # Apply multipliers
            if 'million' in full_match.lower() or 'M' in full_match:
                return int(base_amount * 1_000_000)
            elif 'thousand' in full_match.lower() or 'K' in full_match:
                return int(base_amount * 1_000)
            else:
                return int(base_amount)
        except (ValueError, TypeError):
            return 0

    def calculate_confidence_score(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence score (0-100) based on 5 signals."""
        signals = {}

        # 1. Mentions Score (0-25 points)
        mention_count = len(project.get('mentions', []))
        if mention_count == 1:
            signals['mentions_score'] = 5
        elif 2 <= mention_count <= 3:
            signals['mentions_score'] = 15
        elif 4 <= mention_count <= 6:
            signals['mentions_score'] = 20
        else:  # 7+
            signals['mentions_score'] = 25

        # 2. Temporal Score (0-20 points)
        signals['temporal_score'] = self._calculate_temporal_score(project)

        # 3. Board Diversity Score (0-15 points)
        signals['board_diversity_score'] = self._calculate_board_diversity_score(project)

        # 4. Language Score (0-25 points)
        signals['language_score'] = self._calculate_language_score(project)

        # 5. Identity Score (0-15 points)
        signals['identity_score'] = self._calculate_identity_score(project)

        # Calculate total score
        total_score = sum(signals.values())

        # Determine confidence level
        if total_score <= 30:
            confidence_level = 'low'
        elif total_score <= 60:
            confidence_level = 'medium'
        elif total_score <= 80:
            confidence_level = 'high'
        else:
            confidence_level = 'very_high'

        return {
            'confidence_score': min(100, total_score),
            'confidence_signals': signals,
            'confidence_level': confidence_level
        }

    def _calculate_temporal_score(self, project: Dict[str, Any]) -> int:
        """Calculate temporal persistence score."""
        mentions = project.get('mentions', [])
        if not mentions:
            return 5

        # Extract all dates
        dates = []
        for mention in mentions:
            meeting_date = mention.get('meeting_date')
            if meeting_date:
                try:
                    dates.append(datetime.strptime(meeting_date, '%Y-%m-%d').date())
                except ValueError:
                    continue

        if len(dates) <= 1:
            return 5

        # Calculate time span
        min_date = min(dates)
        max_date = max(dates)
        span_days = (max_date - min_date).days

        if span_days < 30:  # Same month
            return 8
        elif span_days < 365:  # Multiple months
            return 15
        else:  # Multiple years
            return 20

    def _calculate_board_diversity_score(self, project: Dict[str, Any]) -> int:
        """Calculate board diversity score."""
        sources = set()
        for mention in project.get('mentions', []):
            source = mention.get('source')
            if source:
                sources.add(source)

        if len(sources) == 1:
            return 5
        elif 'dia_ddrb' in sources and ('dia_board' in sources or 'dia_resolutions' in sources):
            return 15
        elif len(sources) >= 2:
            return 10
        else:
            return 5

    def _calculate_language_score(self, project: Dict[str, Any]) -> int:
        """Calculate language quality score."""
        # Collect all text
        all_text = []
        title = project.get('title', '').lower()
        all_text.append(title)

        for mention in project.get('mentions', []):
            snippet = mention.get('snippet', '').lower()
            mention_title = mention.get('title', '').lower()
            all_text.extend([snippet, mention_title])

        combined_text = ' '.join(all_text)

        score = 10  # Base score

        # Apply penalties
        for penalty_word in self.penalty_words:
            if penalty_word.lower() in combined_text:
                score -= 5

        # Apply bonuses
        for bonus_word in self.bonus_words:
            if bonus_word.lower() in combined_text:
                score += 3

        return max(0, min(25, score))

    def _calculate_identity_score(self, project: Dict[str, Any]) -> int:
        """Calculate identity consistency score."""
        score = 0

        # Check for consistent naming
        titles = [project.get('title', '')]
        names = [project.get('name', '')]
        for mention in project.get('mentions', []):
            titles.append(mention.get('title', ''))

        # Simple consistency check - if most titles share common words
        if len(titles) > 1:
            # Count word frequency across titles
            word_counts = {}
            for title in titles:
                if title:
                    words = re.findall(r'\w+', title.lower())
                    for word in words:
                        if len(word) > 3:  # Ignore short words
                            word_counts[word] = word_counts.get(word, 0) + 1

            # If any word appears in multiple titles
            if any(count > 1 for count in word_counts.values()):
                score += 5

        # Check for address mentions
        combined_text = ' '.join(str(x) for x in [project.get('title', ''), project.get('name', '')])
        if re.search(r'\d+\s+\w+\s+(street|st|avenue|ave|road|rd|drive|dr|way|blvd|boulevard)', combined_text, re.IGNORECASE):
            score += 5

        # Check for developer/entity names (capitalized words suggesting proper nouns)
        if re.search(r'\b[A-Z][a-z]+\s+(LLC|Inc|Corp|Company|Development|Group|Partners)\b', combined_text):
            score += 3

        # Check for branded names (title case with common development words)
        if re.search(r'\b[A-Z][a-z]+\s+(Plaza|Tower|Square|Center|District|Commons|Pointe|Landing)\b', combined_text):
            score += 2

        return min(15, score)

    def calculate_importance_score(self, project: Dict[str, Any], money_mentions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate importance score (0-100) with weighted signals."""
        signals = {}

        # 1. Money Score (0-50 points) - HIGHEST WEIGHT
        signals['money_score'] = self._calculate_money_score(money_mentions)

        # 2. Scale Score (0-25 points)
        signals['scale_score'] = self._calculate_scale_score(project)

        # 3. Duration Score (0-15 points)
        signals['duration_score'] = self._calculate_duration_score(project)

        # 4. Board Escalation Score (0-15 points)
        signals['board_escalation_score'] = self._calculate_board_escalation_score(project)

        # 5. Publicness Score (0-20 points)
        signals['publicness_score'] = self._calculate_publicness_score(project, money_mentions)

        # Calculate total score
        total_score = sum(signals.values())

        # Determine importance level
        if total_score <= 30:
            importance_level = 'low'
        elif total_score <= 60:
            importance_level = 'medium'
        elif total_score <= 80:
            importance_level = 'high'
        else:
            importance_level = 'very_high'

        return {
            'importance_score': min(100, total_score),
            'importance_signals': signals,
            'importance_level': importance_level
        }

    def _calculate_money_score(self, money_mentions: List[Dict[str, Any]]) -> int:
        """Calculate money score based on largest amount mentioned."""
        if not money_mentions:
            return 0

        max_amount = max(money_mentions, key=lambda x: x['amount_numeric'])['amount_numeric']

        if max_amount == 0:
            return 0
        elif max_amount < 100_000:
            base_score = 10
        elif max_amount < 1_000_000:
            base_score = 20
        elif max_amount < 10_000_000:
            base_score = 35
        else:
            base_score = 50

        # Public incentive bonus - check if any mention includes incentive language
        for mention in money_mentions:
            context = mention.get('context', '').lower()
            if any(word in context for word in ['incentive', 'public', 'city', 'tif', 'cra', 'tax increment']):
                base_score = min(50, base_score + 10)
                break

        return base_score

    def _calculate_scale_score(self, project: Dict[str, Any]) -> int:
        """Calculate physical/project scale score."""
        # Collect all text
        all_text = []
        title = project.get('title', '').lower()
        name = project.get('name', '').lower()
        all_text.extend([title, name])

        for mention in project.get('mentions', []):
            snippet = mention.get('snippet', '').lower()
            mention_title = mention.get('title', '').lower()
            all_text.extend([snippet, mention_title])

        combined_text = ' '.join(all_text)

        score = 0

        # High-impact terms bonus
        for term in self.high_impact_terms:
            if term in combined_text:
                score += 5

        # Low-impact terms penalty
        for term in self.low_impact_terms:
            if term in combined_text:
                score -= 3

        return max(0, min(25, score))

    def _calculate_duration_score(self, project: Dict[str, Any]) -> int:
        """Calculate project duration score."""
        mentions = project.get('mentions', [])
        if len(mentions) <= 1:
            return 3

        # Count unique meeting dates
        unique_dates = set()
        for mention in mentions:
            meeting_date = mention.get('meeting_date')
            if meeting_date:
                unique_dates.add(meeting_date)

        if len(unique_dates) <= 1:
            return 3
        elif len(unique_dates) <= 3:
            return 8
        else:
            return 15

    def _calculate_board_escalation_score(self, project: Dict[str, Any]) -> int:
        """Calculate board hierarchy score."""
        sources = set()
        for mention in project.get('mentions', []):
            source = mention.get('source')
            if source:
                sources.add(source)

        # Future: add city_council = 15 points
        if any(source in ['dia_board', 'dia_resolutions'] for source in sources):
            return 10
        elif 'dia_ddrb' in sources:
            return 5
        else:
            return 5

    def _calculate_publicness_score(self, project: Dict[str, Any], money_mentions: List[Dict[str, Any]]) -> int:
        """Calculate public relevance score."""
        # Collect all text including money contexts
        all_text = []
        title = project.get('title', '').lower()
        name = project.get('name', '').lower()
        all_text.extend([title, name])

        for mention in project.get('mentions', []):
            snippet = mention.get('snippet', '').lower()
            mention_title = mention.get('title', '').lower()
            all_text.extend([snippet, mention_title])

        for money_mention in money_mentions:
            context = money_mention.get('context', '').lower()
            all_text.append(context)

        combined_text = ' '.join(all_text)

        score = 0
        for term in self.publicness_terms:
            if term in combined_text:
                score += 4

        return min(20, score)

    def extract_supporting_data(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Extract supporting data for scoring transparency."""
        # Scale indicators
        all_text = ' '.join([
            project.get('title', ''),
            project.get('name', ''),
            ' '.join(m.get('snippet', '') for m in project.get('mentions', []))
        ]).lower()

        scale_indicators = [term for term in self.high_impact_terms if term in all_text]

        # Board progression
        board_progression = []
        board_mentions = {}
        for mention in project.get('mentions', []):
            source = mention.get('source')
            meeting_date = mention.get('meeting_date')
            if source and meeting_date:
                if source not in board_mentions:
                    board_mentions[source] = {'first_mention': meeting_date, 'mention_count': 0}
                board_mentions[source]['mention_count'] += 1
                if meeting_date < board_mentions[source]['first_mention']:
                    board_mentions[source]['first_mention'] = meeting_date

        for board, data in board_mentions.items():
            board_progression.append({
                'board': board,
                'first_mention': data['first_mention'],
                'mention_count': data['mention_count']
            })

        # Identity signals
        identity_signals = {
            'consistent_names': list(set([project.get('title'), project.get('name')])),
            'address_mentions': [],
            'developer_name': None,
            'branded_name': None
        }

        # Extract addresses (simple pattern)
        address_pattern = r'\d+\s+\w+\s+(?:street|st|avenue|ave|road|rd|drive|dr|way|blvd|boulevard)'
        addresses = re.findall(address_pattern, all_text, re.IGNORECASE)
        identity_signals['address_mentions'] = list(set(addresses))

        return {
            'scale_indicators': scale_indicators,
            'board_progression': board_progression,
            'identity_signals': identity_signals
        }

    def create_display_explanations(self, confidence_data: Dict[str, Any],
                                    importance_data: Dict[str, Any],
                                    money_mentions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create user-friendly explanations for scores."""

        # Confidence explanation
        conf_parts = []
        if confidence_data['confidence_signals']['mentions_score'] >= 20:
            conf_parts.append("multiple mentions")
        if confidence_data['confidence_signals']['temporal_score'] >= 15:
            conf_parts.append("extended timeline")
        if confidence_data['confidence_signals']['board_diversity_score'] >= 10:
            conf_parts.append("cross-board visibility")

        confidence_explanation = f"{confidence_data['confidence_level'].title()} confidence based on " + ', '.join(conf_parts)

        # Importance explanation
        imp_parts = []
        if money_mentions:
            max_amount = max(money_mentions, key=lambda x: x['amount_numeric'])['amount_numeric']
            if max_amount >= 1_000_000:
                imp_parts.append(f"${max_amount/1_000_000:.1f}M mentioned")
            else:
                imp_parts.append(f"${max_amount:,.0f} mentioned")

        if importance_data['importance_signals']['scale_score'] >= 15:
            imp_parts.append("large-scale development")
        if importance_data['importance_signals']['publicness_score'] >= 12:
            imp_parts.append("public involvement")

        rank_explanation = f"{importance_data['importance_level'].title()} importance due to " + ', '.join(imp_parts) if imp_parts else "Standard project review"

        # Determine highlighting and review priority
        should_highlight = (
            importance_data['importance_score'] >= 60 or
            confidence_data['confidence_score'] >= 70
        )

        review_priority = 'high' if confidence_data['confidence_score'] < 40 else 'low'

        return {
            'rank_explanation': rank_explanation,
            'confidence_explanation': confidence_explanation,
            'should_highlight': should_highlight,
            'review_priority': review_priority
        }

    def score_project(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Score a single project with all enhancements."""
        logger.debug(f"Scoring project: {project.get('id', 'unknown')}")

        # Extract money mentions
        money_mentions = self.extract_money_mentions(project)

        # Calculate scores
        confidence_data = self.calculate_confidence_score(project)
        importance_data = self.calculate_importance_score(project, money_mentions)

        # Extract supporting data
        supporting_data = self.extract_supporting_data(project)

        # Create display explanations
        display_data = self.create_display_explanations(confidence_data, importance_data, money_mentions)

        # Create enhanced project
        enhanced_project = project.copy()
        enhanced_project.update({
            # Scoring results
            'confidence_score': confidence_data['confidence_score'],
            'confidence_signals': confidence_data['confidence_signals'],
            'confidence_level': confidence_data['confidence_level'],

            'importance_score': importance_data['importance_score'],
            'importance_signals': importance_data['importance_signals'],
            'importance_level': importance_data['importance_level'],

            # Supporting data
            'money_mentions': money_mentions,
            'scale_indicators': supporting_data['scale_indicators'],
            'board_progression': supporting_data['board_progression'],
            'identity_signals': supporting_data['identity_signals'],

            # Admin features
            'scoring_metadata': {
                'last_scored': datetime.now().isoformat(),
                'scoring_version': '1.0',
                'manual_overrides': {
                    'importance_score': None,
                    'confidence_score': None,
                    'override_reason': None
                }
            },

            # UI display helpers
            'display_ranking': display_data
        })

        return enhanced_project

    def score_all_projects(self, projects_file: str, output_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """Score all projects in the index."""
        logger.info(f"Loading projects from {projects_file}")

        with open(projects_file, 'r') as f:
            projects = json.load(f)

        logger.info(f"Scoring {len(projects)} projects...")

        scored_projects = []
        for i, project in enumerate(projects):
            if i % 10 == 0:
                logger.info(f"Processed {i}/{len(projects)} projects")
            scored_project = self.score_project(project)
            scored_projects.append(scored_project)

        # Sort by importance score (descending)
        scored_projects.sort(key=lambda p: p['importance_score'], reverse=True)

        if output_file:
            logger.info(f"Writing scored projects to {output_file}")
            with open(output_file, 'w') as f:
                json.dump(scored_projects, f, indent=2, ensure_ascii=False)

        logger.info(f"Scoring complete. {len(scored_projects)} projects scored.")
        return scored_projects


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Score JaxWatch projects for confidence and importance')
    parser.add_argument('--input', '-i',
                       default='outputs/projects/projects_index.json',
                       help='Input projects file')
    parser.add_argument('--output', '-o',
                       help='Output file (defaults to overwriting input)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_file = args.output or args.input

    scorer = ProjectScorer()
    scorer.score_all_projects(args.input, output_file)

    logger.info("Project scoring completed successfully!")


if __name__ == '__main__':
    main()