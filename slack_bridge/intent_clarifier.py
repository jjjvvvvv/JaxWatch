#!/usr/bin/env python3
"""
Intent Clarifier for Slack Bridge
Conservative fuzzy matching with explicit confirmation requirements
"""

import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher


class IntentClarifier:
    """
    Conservative fuzzy command matching with explicit user confirmation.

    Design Principles:
    - Never auto-execute fuzzy matches without confirmation
    - Fail-closed on ambiguity - ask again rather than guess
    - Maximum 3 suggestions to avoid overwhelming user
    - Clear "I can't run that yet" messaging
    """

    def __init__(self):
        self.similarity_threshold = 0.25  # More sensitive to catch common typos
        self.max_suggestions = 3

    def find_similar_commands(self, message_text: str, command_mappings: List[Dict]) -> List[Dict]:
        """
        Find similar commands using conservative fuzzy matching.

        Args:
            message_text: User's message
            command_mappings: Available command mappings

        Returns:
            List of potential matches with scores
        """
        clean_text = self._clean_message_text(message_text)
        candidates = []

        for mapping in command_mappings:
            score = self._calculate_similarity_score(clean_text, mapping)

            # Only include candidates above threshold
            if score >= self.similarity_threshold:
                candidates.append({
                    'mapping': mapping,
                    'score': score,
                    'explanation': self._generate_match_explanation(clean_text, mapping)
                })

        # Sort by score (highest first) and limit to max suggestions
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:self.max_suggestions]

    def _clean_message_text(self, text: str) -> str:
        """Clean and normalize message text for comparison."""
        # Remove @mentions
        text = re.sub(r'<@[UW]\w+>', '', text)
        # Convert to lowercase, strip whitespace
        text = text.lower().strip()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text

    def _calculate_similarity_score(self, clean_text: str, mapping: Dict) -> float:
        """
        Calculate similarity score between message and command mapping.

        Combines multiple scoring methods:
        - Keyword overlap
        - Edit distance similarity
        - Pattern similarity
        """
        description = mapping.get('description', '').lower()
        pattern = mapping.get('pattern', '')

        # Extract keywords from pattern and description
        mapping_keywords = self._extract_keywords_from_pattern(pattern)
        mapping_keywords.extend(self._extract_keywords_from_description(description))

        message_keywords = clean_text.split()

        # 1. Keyword overlap scoring (40% weight)
        overlap_score = self._calculate_keyword_overlap(message_keywords, mapping_keywords)

        # 2. Edit distance similarity (30% weight)
        edit_score = self._calculate_edit_similarity(clean_text, description)

        # 3. Partial pattern matching (30% weight)
        pattern_score = self._calculate_pattern_similarity(clean_text, pattern)

        # Weighted average
        final_score = (overlap_score * 0.4) + (edit_score * 0.3) + (pattern_score * 0.3)

        return final_score

    def _extract_keywords_from_pattern(self, pattern: str) -> List[str]:
        """Extract meaningful keywords from regex pattern."""
        # Remove regex syntax and extract words
        clean_pattern = re.sub(r'[()\\?+*|^$\[\]{}]', ' ', pattern)
        clean_pattern = re.sub(r'(?i)', '', clean_pattern)  # Remove case-insensitive flag

        # Split and filter meaningful words
        words = clean_pattern.lower().split()
        keywords = []

        for word in words:
            # Skip very short words and regex artifacts
            if len(word) > 2 and not word.startswith('\\') and word not in ['s', 'd']:
                keywords.append(word)

        return keywords

    def _extract_keywords_from_description(self, description: str) -> List[str]:
        """Extract meaningful keywords from command description."""
        # Split description into words, filter common words
        words = re.findall(r'\w+', description.lower())
        stopwords = {'the', 'and', 'or', 'of', 'for', 'on', 'in', 'to', 'from', 'all', 'run'}

        return [word for word in words if word not in stopwords and len(word) > 2]

    def _calculate_keyword_overlap(self, message_keywords: List[str], mapping_keywords: List[str]) -> float:
        """Calculate overlap ratio between message and mapping keywords."""
        if not message_keywords or not mapping_keywords:
            return 0.0

        message_set = set(message_keywords)
        mapping_set = set(mapping_keywords)

        intersection = message_set & mapping_set
        union = message_set | mapping_set

        # Jaccard similarity
        return len(intersection) / len(union) if union else 0.0

    def _calculate_edit_similarity(self, text1: str, text2: str) -> float:
        """Calculate edit distance similarity (0-1)."""
        return SequenceMatcher(None, text1, text2).ratio()

    def _calculate_pattern_similarity(self, message: str, pattern: str) -> float:
        """Calculate how well message might match pattern structure."""
        # Try to match pattern with some flexibility
        try:
            # Remove case-insensitive flag for matching attempt
            clean_pattern = pattern.replace('(?i)', '')

            # Check if there's any structural similarity
            # This is very conservative - looking for word boundaries and basic structure
            if re.search(r'\w+', clean_pattern) and re.search(r'\w+', message):
                # Basic structural similarity
                pattern_words = len(re.findall(r'\w+', clean_pattern))
                message_words = len(re.findall(r'\w+', message))

                # Prefer similar word counts
                if abs(pattern_words - message_words) <= 1:
                    return 0.3
                elif abs(pattern_words - message_words) <= 2:
                    return 0.1

        except re.error:
            pass

        return 0.0

    def _generate_match_explanation(self, message: str, mapping: Dict) -> str:
        """Generate human-readable explanation of why this command matched."""
        description = mapping.get('description', 'Unknown command')

        # Find shared keywords
        message_keywords = set(message.split())
        mapping_keywords = set(self._extract_keywords_from_description(description))
        shared_keywords = message_keywords & mapping_keywords

        if shared_keywords:
            return f"{description} (matched: {', '.join(list(shared_keywords)[:2])})"
        else:
            return description

    def create_clarification_response(self, original_message: str, suggestions: List[Dict]) -> Dict:
        """
        Create clarification response based on suggestion count.

        Returns:
            Dictionary with clarification response and metadata
        """
        if len(suggestions) == 0:
            return {
                'type': 'no_matches',
                'response': self._create_no_matches_response(),
                'needs_confirmation': False
            }

        elif len(suggestions) == 1:
            return {
                'type': 'single_suggestion',
                'response': self._create_single_suggestion_response(suggestions[0]),
                'needs_confirmation': True,
                'suggested_command': suggestions[0]['mapping'],
                'original_message': original_message
            }

        else:  # Multiple suggestions
            return {
                'type': 'multiple_suggestions',
                'response': self._create_multiple_suggestions_response(suggestions),
                'needs_confirmation': True,
                'suggestions': [s['mapping'] for s in suggestions],
                'original_message': original_message
            }

    def _create_no_matches_response(self) -> str:
        """Create response when no similar commands are found."""
        return (
            "🤔 I couldn't match that to any command. "
            "Available commands:\n"
            "• verify documents\n"
            "• verify 2026 projects\n"
            "• scan references\n"
            "• status\n"
            "• dashboard\n\n"
            "Type 'help' for more details."
        )

    def _create_single_suggestion_response(self, suggestion: Dict) -> str:
        """Create response for single fuzzy match."""
        explanation = suggestion['explanation']

        return (
            f"🤔 I can't run that yet. This is the closest match I found:\n\n"
            f"• {explanation}\n\n"
            f"Reply 'yes' to run this, or 'no' to cancel."
        )

    def _create_multiple_suggestions_response(self, suggestions: List[Dict]) -> str:
        """Create response for multiple fuzzy matches."""
        response = "🤔 I can't run that yet. These are the closest matches I found:\n\n"

        for i, suggestion in enumerate(suggestions, 1):
            explanation = suggestion['explanation']
            response += f"{i}. {explanation}\n"

        response += "\nReply with the number you want (1, 2, etc.), or 'none' to cancel."

        return response

    def parse_clarification_response(self, response_text: str, clarification_context: Dict) -> Optional[Dict]:
        """
        Parse user's response to clarification request.

        Args:
            response_text: User's response
            clarification_context: Context from original clarification

        Returns:
            Command to execute or None if cancelled
        """
        clean_response = response_text.strip().lower()

        if clarification_context['type'] == 'single_suggestion':
            if clean_response in ['yes', 'y', 'ok', 'sure']:
                return clarification_context['suggested_command']
            elif clean_response in ['no', 'n', 'cancel', 'stop']:
                return None
            else:
                # Invalid response - ask again
                return {'type': 'invalid_response', 'message': "Please reply 'yes' or 'no'."}

        elif clarification_context['type'] == 'multiple_suggestions':
            if clean_response in ['none', 'no', 'cancel', 'stop']:
                return None

            # Try to parse numeric selection
            try:
                selection = int(clean_response)
                if 1 <= selection <= len(clarification_context['suggestions']):
                    return clarification_context['suggestions'][selection - 1]
                else:
                    return {
                        'type': 'invalid_response',
                        'message': f"Please choose a number between 1 and {len(clarification_context['suggestions'])}, or 'none' to cancel."
                    }
            except ValueError:
                return {
                    'type': 'invalid_response',
                    'message': "Please reply with a number (1, 2, etc.) or 'none' to cancel."
                }

        return None