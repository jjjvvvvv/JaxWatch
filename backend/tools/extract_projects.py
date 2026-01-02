#!/usr/bin/env python3
"""
Extract resolution-centered "project" stubs from collected artifacts, optimized for
reference_only mode. Focus: DIA Board and DDRB resolutions, with associations to
meeting agendas/packets/minutes.

What this does now:
- Scans outputs/files/<source>/<YYYY>/meta/*.json (and PDFs if present) for DIA/DDRB
- Detects resolution IDs like RESOLUTION-YYYY-NN..., RES YYYY-NN, or RESOLUTION YYYY-NN
- Also detects Ordinance IDs and PUD references for context (added to mention snippet)
- When a resolution is found, associates agenda/minutes/packet from the same meeting
  (by meeting_date or meeting_title) from outputs/raw/dia_board/<YYYY>/dia_board.json
- Stores compact project objects at outputs/projects/projects_index.json with fields:
  id, title, doc_type, source, meeting_date, meeting_title, mentions, pending_review

CLI:
  python3 -m backend.tools.extract_projects [--source ID] [--year YYYY]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .project_schema_ext import enhance_project_schema

FILES_DIR = Path("outputs/files")
RAW_DIR = Path("outputs/raw")
PROJECTS_DIR = Path("outputs/projects")
PROJECTS_INDEX = PROJECTS_DIR / "projects_index.json"
DEBUG_DIR = Path("outputs/debug")
DDRB_DEBUG_LOG = DEBUG_DIR / "ddrb_cases.txt"


ORD_RE = re.compile(r"\b(?:ORD|ORDINANCE)[\s-]*(\d{4}-\d{2,})\b", re.I)
# Strong ID rules (only these become projects)
# DIA Resolutions: Match RESOLUTION / RESO / R identifiers with flexible separators
DIA_RESOLUTION_RE = re.compile(
    r"""
    \b
    (?:DIA[\s_-]*)?
    (?:RES(?:OLUTION)?|RESO|R)
    [\s_-]*
    (?P<date>20\d{2}[\s_./-]?\d{2}[\s_./-]?\d{2})
    """,
    re.I | re.VERBOSE,
)
# DDRB Cases: DDRB-YYYY-### (zero-padded)
DDRB_PATTERN = r"""
    \bDDRB                        # Literal prefix
    [\s_\-]*                     # Optional separators before the year
    (?P<year>\d{4})               # Year
    (?:
        [\s]*[\-\u2010\u2011\u2012\u2013\u2014_][\s]*  # Dash/underscore separators
        |
        \s+                                           # Or just whitespace
    )
    (?P<num>\d{1,3})              # Case number (1-3 digits)
    \b
"""
DDRB_CASE_RE = re.compile(DDRB_PATTERN, re.I | re.VERBOSE)
DDRB_INLINE_RE = re.compile(DDRB_PATTERN, re.I | re.VERBOSE)
PUD_RE = re.compile(r"\bPUD\b|PLANNED\s+UNIT\s+DEVELOPMENT", re.I)


LIST_PREFIX_PATTERNS = [
    re.compile(r"^[\s]*[\-\+\*•▪◦\u2010\u2011\u2012\u2013\u2014]+\s+"),
    re.compile(r"^[\s]*\(?\d{1,2}[A-Za-z]?\)?[\).:-]?\s+"),
    re.compile(r"^[\s]*\(?[A-Za-z]{1,2}\)?[\).:-]?\s+"),
    re.compile(r"^[\s]*\(?[IVXLCDM]{1,4}\)?[\).:-]?\s+", re.I),
]



ANCHOR_PROJECTS = {
    "PROJ-RIVERFRONT": {
        "title": "Riverfront Plaza",
        "patterns": [
            r"Riverfront\s+Plaza",
            r"Landing\s+site",
            r"former\s+Landing",
            r"Riverfront\s+Park",
        ]
    },
    "PROJ-GATEWAY": {
        "title": "Pearl Square / Gateway Jax",
        "patterns": [
            r"Pearl\s+Square",
            r"Gateway\s+Jax",
            r"North\s+Pearl",
            r"Porter\s+House.*mansion",
            r"Pearl\s+Street",
        ]
    },
    "PROJ-SHIPYARDS": {
        "title": "The Shipyards & Four Seasons",
        "patterns": [
            r"Shipyards",
            r"Four\s+Seasons",
            r"Metropolitan\s+Park",
            r"Jaguars.*development",
        ]
    },
    "PROJ-LAVILLA": {
        "title": "LaVilla Redevelopment",
        "patterns": [
            r"LaVilla",
            r"UF\s+Graduate",
            r"Lift\s+Evhry\s+Voice",
            r"Broad\s+Street",
        ]
    },
    "PROJ-FORD": {
        "title": "Ford on Bay",
        "patterns": [
            r"Ford\s+on\s+Bay",
            r"former\s+courthouse.*site",
            r"330\s+E.*Bay",
        ]
    }
}

MENTION_DOC_TYPES = {
    "agenda",
    "packet",
    "agenda_packet",
    "minutes",
    "staff_report",
    "presentation",
}
DDRB_SOURCE_IDS = {"dia_ddrb"}
RELATED_DOC_TYPES = MENTION_DOC_TYPES | {"exhibit", "addendum"}


def normalize_doc_type(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[\s-]+", "_", value.strip().lower())


def guess_doc_type_from_name(name: str) -> str:
    lowered = name.lower()
    if "agenda" in lowered and "packet" in lowered:
        return "agenda_packet"
    if "agenda" in lowered:
        return "agenda"
    if "minutes" in lowered:
        return "minutes"
    if "packet" in lowered:
        return "packet"
    if "transcript" in lowered:
        return "transcript"
    if "presentation" in lowered:
        return "presentation"
    if "staff" in lowered and "report" in lowered:
        return "staff_report"
    if "resolution" in lowered:
        return "resolution"
    return "other"


def guess_source_from_context(path: Path, text: str) -> Tuple[str, str]:
    name_lower = path.stem.lower()
    text_upper = text.upper()
    if "DDRB" in text_upper or "ddrb" in name_lower:
        return "dia_ddrb", "DDRB"
    if "DIA" in text_upper or "resolution" in name_lower:
        return "dia_board", "DIA Board"
    return "single_file", "Single File"


def is_remote_url(url: Optional[str]) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def is_html_content(text: str) -> bool:
    """Check if text is primarily HTML/JavaScript content rather than document text."""
    if not text:
        return False

    # Count HTML/JS patterns vs actual content
    html_indicators = [
        r'<!DOCTYPE html',
        r'<html\b',
        r'<script\b',
        r'<div\b',
        r'<meta\b',
        r'window\.',
        r'document\.',
        r'function\s*\(',
        r'var\s+\w+\s*=',
        r'SharePoint',
        r'OneDrive',
    ]

    html_matches = sum(len(re.findall(pattern, text, re.I)) for pattern in html_indicators)

    # If more than 10 HTML indicators in first 2000 chars, consider it HTML
    sample = text[:2000]
    sample_html_matches = sum(len(re.findall(pattern, sample, re.I)) for pattern in html_indicators)

    return sample_html_matches > 10 or html_matches > 20


def is_short_text(text: str, threshold: int = 200) -> bool:
    if not text:
        return True
    normalized = clean_text_fragment(text)
    if not normalized:
        return True
    return len(normalized) < threshold


def process_single_project_file(file_path: Path, index: List[dict]) -> Tuple[List[dict], int, int]:
    target = file_path.expanduser()
    if not target.exists() or not target.is_file():
        print(f"⚠️  Single-file mode: '{target}' not found or not a file")
        return index, 0, 1

    suffix = target.suffix.lower()
    try:
        if suffix == ".txt":
            text = target.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf":
            from .pdf_extractor import extract_text

            text = extract_text(target)
        else:
            print(f"⚠️  Unsupported file type for project extraction: '{target.name}'")
            return index, 0, 1
    except Exception as exc:
        print(f"⚠️  Failed reading '{target}': {exc}")
        return index, 0, 1

    doc_type_guess = guess_doc_type_from_name(target.stem)
    source_value, source_name = guess_source_from_context(target, text)
    meta: Dict[str, Optional[str]] = {
        "url": "",
        "title": target.stem,
        "doc_type": doc_type_guess,
        "source": source_value,
        "source_name": source_name,
        "meeting_date": None,
        "meeting_title": None,
        "local_text_path": str(target) if suffix == ".txt" else "",
    }

    matches = extract_matches_from_text(text, meta.get("doc_type"), meta.get("source"))
    if not matches:
        print(f"🛈 No project identifiers found in {target}")
        return index, 0, 0

    dia_snippet = build_dia_snippet(text, meta.get('url'))
    fallback_snippet = clean_text_fragment(text[:200])

    created = 0
    for hit in matches:
        snippet = dia_snippet if hit.project_type == "DIA-RES" else hit.context
        if not snippet:
            snippet = fallback_snippet
        mention = make_mention(meta, hit.project_id, snippet=snippet)
        if not mention:
            continue
        project_title = hit.candidate_title or meta.get("title") or hit.project_id
        payload = {
            "id": hit.project_id,
            "title": project_title,
            "doc_type": hit.project_type,
            "source": meta.get("source"),
            "meeting_date": meta.get("meeting_date"),
            "meeting_title": meta.get("meeting_title"),
            "mentions": [mention],
        }
        index, is_new = upsert_project(index, payload)
        if is_new:
            created += 1
            print(f"➕ New project: {payload['id']} ({payload.get('title','')})")

    if created == 0:
        print(f"🛈 All matches already existed for {target}")

    return index, created, 0


def clean_text_fragment(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    # More aggressive punctuation cleanup for better title extraction
    cleaned = cleaned.strip("-• ,;:()[]{}'\"+=")
    return cleaned


def strip_list_prefix(value: str) -> str:
    if not value:
        return ""
    working = value
    changed = True
    while changed:
        changed = False
        for pattern in LIST_PREFIX_PATTERNS:
            match = pattern.match(working)
            if match:
                working = working[match.end() :]
                changed = True
                break
    return working.strip()


def clean_ddrb_line(value: str) -> str:
    return strip_list_prefix(clean_text_fragment(value))


def normalize_title_case(text: str) -> str:
    """Convert ALL CAPS or inconsistent case to proper title case."""
    if not text:
        return ""

    # If mostly uppercase, convert to title case
    upper_chars = sum(1 for c in text if c.isupper())
    total_alpha = sum(1 for c in text if c.isalpha())

    if total_alpha > 0 and upper_chars / total_alpha > 0.7:
        # Convert to title case, but preserve certain all-caps words
        words = text.split()
        normalized_words = []

        # Words that should stay uppercase
        keep_upper = {'DIA', 'DDRB', 'LLC', 'INC', 'CORP', 'PUD', 'USA', 'US', 'FL', 'NE', 'SW', 'NW', 'SE'}

        for word in words:
            # Clean word of punctuation for checking
            clean_word = re.sub(r'[^\w]', '', word.upper())
            if clean_word in keep_upper:
                normalized_words.append(word.upper())
            else:
                # Convert to title case
                normalized_words.append(word.capitalize())

        return ' '.join(normalized_words)

    return text


def extract_project_name_from_snippet(snippet: str, project_id: str) -> Optional[str]:
    """Extract the actual project name from DDRB case snippet text."""
    if not snippet or not project_id:
        return None

    # Clean up the snippet
    snippet = snippet.replace('\n', ' ').replace('\r', '')
    snippet = re.sub(r'\s+', ' ', snippet).strip()

    # Extract case ID components for matching
    case_match = re.search(r'DDRB[_\s-]*(\d{4})[_\s-]*(\d+)', project_id, re.I)
    if not case_match:
        return None

    year, num = case_match.groups()
    case_patterns = [
        f"DDRB {year}-{num.zfill(3)}",
        f"DDRB-{year}-{num.zfill(3)}",
        f"DDRB {year}-{num}",
        f"DDRB-{year}-{num}",
    ]

    # Patterns to extract project names from DDRB snippets
    extraction_patterns = [
        # Pattern 1: "DDRB YYYY-NNN, PROJECT NAME"
        r'(?i)DDRB[\s_-]*{year}[\s_-]*{num}(?:,\s*|\s+)([^,;.–-]+?)(?:\s*[,;.–-]|\s*REQUEST|\s*FINAL|\s*CONCEPTUAL|\s*$)',

        # Pattern 2: "project report for DDRB YYYY-NNN, PROJECT NAME"
        r'(?i)project\s+report\s+for\s+DDRB[\s_-]*{year}[\s_-]*{num}(?:,\s*|\s+)([^,;.–-]+?)(?:\s*dated|\s*[,;.]|\s*$)',

        # Pattern 3: "reviewed the project report for DDRB YYYY-NNN, PROJECT NAME"
        r'(?i)reviewed\s+the\s+project\s+report\s+for\s+DDRB[\s_-]*{year}[\s_-]*{num}(?:,\s*|\s+)([^,;.–-]+?)(?:\s*dated|\s*[,;.]|\s*$)',

        # Pattern 4: "DDRB YYYY-NNN REQUEST FOR [ACTION] – PROJECT NAME"
        r'(?i)DDRB[\s_-]*{year}[\s_-]*{num}[\s,]*REQUEST\s+FOR\s+(?:CONCEPTUAL|FINAL|DEVIATION|SPECIAL|EXCEPTION)(?:\s+(?:APPROVAL|REVIEW))?\s*[–-]\s*([^,;.]+?)(?:\s*[,;.]|\s*$)',

        # Pattern 5: Direct project name after case number and comma
        r'(?i)DDRB[\s_-]*{year}[\s_-]*{num}[\s,]*([A-Z][^,;.–-]*?)(?:\s*REQUEST|\s*[,;.–-]|\s*$)',
    ]

    for pattern_template in extraction_patterns:
        pattern = pattern_template.format(year=year, num=num.zfill(3))
        match = re.search(pattern, snippet)
        if match:
            project_name = match.group(1).strip()
            project_name = clean_text_fragment(project_name)
            project_name = normalize_title_case(project_name)
            project_name = clean_ddrb_candidate_text(project_name)

            # Validate it's not procedural text
            if project_name and len(project_name) > 5 and not is_procedural_text(project_name):
                # Remove common suffixes
                project_name = re.sub(r'\s*[–-]\s*(?:REQUEST|FINAL|CONCEPTUAL|APPROVAL|REVIEW)\s*$', '', project_name, flags=re.I)
            project_name = project_name.strip()

            if project_name and len(project_name) > 3:
                return project_name

    # Fallback: try to find capitalized project names near the case ID
    fallback_pattern = rf'(?i)(?:DDRB[\s_-]*{year}[\s_-]*{num}[\s,]*)?([A-Z][A-Z\s&-]+[A-Z])'
    for match in re.finditer(fallback_pattern, snippet):
        candidate = match.group(1).strip()
        candidate = clean_text_fragment(candidate)
        candidate = normalize_title_case(candidate)
        candidate = clean_ddrb_candidate_text(candidate)

        if (candidate and len(candidate) > 8 and
            not is_procedural_text(candidate) and
            not candidate.upper().startswith(('THE MOTION', 'BOARD MEMBER', 'UNANIMOUSLY'))):
            return candidate

    return None


def is_meeting_document(title: str, doc_type: str = None) -> bool:
    """Check if a document is a meeting document rather than a project."""
    if not title:
        return False

    title_upper = title.upper()

    # Direct meeting document indicators
    meeting_indicators = [
        'AGENDA', 'MINUTES', 'PACKET', 'TRANSCRIPT',
        'MEETING-AGENDA', 'MEETING-PACKET', 'MEETING-MINUTES',
        'BOARD-MEETING', 'COMMITTEE-MEETING', 'BOARD-MEETING-AGENDA',
        'SIC-AGENDA', 'FINANCE-BUDGET', 'STRATEGIC-IMPLEMENTATION',
        'MEETING', 'RESOLUTIONS'  # Added broader patterns
    ]

    for indicator in meeting_indicators:
        if indicator in title_upper:
            return True

    # Date-based meeting document patterns (YYYYMMDD format at start)
    if re.search(r'^\d{8}[_\s-].*?(DIA|DDRB)', title_upper):
        return True

    # Meeting agenda packet patterns (broader)
    if re.search(r'\d{8}.*?(AGENDA|MINUTES|PACKET|MEETING)', title_upper):
        return True

    # Pattern like "20150527_DIA-Board-Meeting-Agenda,-Minutes-Resolutions"
    if re.search(r'^\d{8}_.*?-?(MEETING|AGENDA|MINUTES|RESOLUTIONS)', title_upper):
        return True

    return False


def clean_dia_resolution_title(title: str) -> str:
    """Clean up DIA resolution titles by removing prefixes and normalizing format."""
    if not title:
        return ""

    original = title
    cleaned = title

    # Check if this is actually a meeting document title, not a resolution title
    if is_meeting_document(title):
        # This is a meeting document name, not a resolution title
        # Return a placeholder that will be replaced with generated name
        return ""

    # Remove resolution prefixes
    patterns_to_remove = [
        r'^RESOLUTION[-_\s]*\d{4}[-_]\d{2}[-_]\d{2}[-_]',  # RESOLUTION-2024-09-01_
        r'^RESOLUTION[-_\s]*\d{4}[-_]\d{2}[-_]\d{2}\s+',   # RESOLUTION 2024-09-01
        r'^RESOLUTION[-_\s]*',                              # RESOLUTION- or RESOLUTION_
    ]

    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.I)

    # Remove common suffixes
    suffixes_to_remove = [
        r'[-_]EXECUTED$',
        r'[-_]AMENDED$',
        r'[-_]FINAL$',
        r'[-_]DRAFT$',
        r'[-_]SIGNED$',
    ]

    for suffix in suffixes_to_remove:
        cleaned = re.sub(suffix, '', cleaned, flags=re.I)

    # Convert underscores and dashes to spaces, but preserve important dashes
    cleaned = cleaned.replace('_', ' ')

    # Replace multiple dashes with single spaces, but keep single dashes in addresses/names
    cleaned = re.sub(r'-{2,}', ' ', cleaned)  # Multiple dashes become spaces
    cleaned = re.sub(r'(\w)-(\w)', r'\1 \2', cleaned)  # Single dashes between words become spaces

    # Clean up extra whitespace and punctuation
    cleaned = clean_text_fragment(cleaned)

    # Apply title case normalization
    cleaned = normalize_title_case(cleaned)

    # If we stripped too much, return original
    if len(cleaned) < 3:
        return original

    return cleaned


def is_procedural_text(text: str) -> bool:
    """Check if text appears to be procedural/administrative rather than a project name."""
    if not text:
        return True

    text_upper = text.upper()

    # Common procedural indicators
    procedural_patterns = [
        r'\bBOARD\s+MEMBER\b',
        r'\bMODIFIED\s+THEIR\b',
        r'\bGRANTING\s+FINAL\b',
        r'\bAPPROVAL\s+OF\b',
        r'\bREQUEST\s+FOR\s+FINAL\b',
        r'\bMINUTES\s+OF\b',
        r'\bAGENDA\s+FOR\b',
        r'\bDISCUSSION\s+OF\b',
        r'\bREPORT\s+ON\b',
        r'\bWITH\s+THE\s+FOLLOWING\s+RECOMMENDATIONS\b',
        r'^(THE|A|AN)\s+\w+\s+(DISCUSSION|REPORT|REVIEW)$',
    ]

    for pattern in procedural_patterns:
        if re.search(pattern, text_upper):
            return True

    # Check for sentence fragments (incomplete thoughts)
    if text.lower().startswith(('modified their', 'board member', 'granting final', 'the motion')):
        return True

    # Check if it starts with common procedural words
    first_words = text.split()[:3] if text.split() else []
    first_text = ' '.join(first_words).upper()
    if first_text in ['BOARD MEMBER', 'MODIFIED THEIR', 'GRANTING FINAL', 'REQUEST FOR', 'THE MOTION']:
        return True

    return False


def strip_ddrb_identifier(value: str) -> str:
    without_id = DDRB_INLINE_RE.sub("", value)
    cleaned = strip_list_prefix(clean_text_fragment(without_id))
    # Enhanced punctuation cleanup including commas and other separators
    cleaned = cleaned.strip(":-–—•,;()[] ")
    return cleaned


def clean_ddrb_candidate_text(value: str) -> str:
    if not value:
        return ""
    cleaned = value
    cleaned = re.sub(r"[-–—,:\s]*Applicant(?:[:\s].*)?$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[-–—,:\s]*Board\s+Member.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[-–—,:\s]*With\s+The\s+Following\s+Recommendations.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[-–—,:\s]*Motion\s+Was\s+Made.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^The\s+motion[^,]*,\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[-–—,:\s]*Public\s+Comments.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[-–—,:\s]*Staff\s+Report.*$", "", cleaned, flags=re.I)
    cleaned = cleaned.rstrip("-–—,: •")
    return cleaned.strip()


def is_descriptive_candidate(value: str) -> bool:
    if not value:
        return False
    if DDRB_INLINE_RE.search(value):
        return False
    alpha_chars = sum(1 for ch in value if ch.isalpha())
    if alpha_chars < 4:
        return False
    words = [token for token in value.split() if any(c.isalpha() for c in token)]
    if len(words) < 2 and alpha_chars < 10:
        return False
    return True


def score_ddrb_title(value: Optional[str]) -> int:
    if not value:
        return 0
    text = value.strip()
    score = 0

    # Major penalty for procedural text
    if is_procedural_text(text):
        return -50

    # Major penalty for leading punctuation (comma issues)
    if text.startswith((',', ';', ':', '-', '•')):
        score -= 20

    # Base scoring for descriptive candidates
    if is_descriptive_candidate(text):
        score += 10

    length = len(text)
    if 15 <= length <= 80:  # Adjusted ideal length for project names
        score += 5
    elif length < 10:  # Too short
        score -= 5
    elif length > 100:  # Too long, likely fragment
        score -= 3
    else:
        score += 1

    # Penalties for sentence endings (fragments)
    if text.endswith((".", "?", "!")):
        score -= 3

    # Enhanced penalties for administrative language
    admin_patterns = [
        r"\b(discussion|minutes|review|report|agenda|meeting)\b",
        r"\b(board\s+member|granting|approval\s+of)\b",
        r"\b(request\s+for\s+final|modified\s+their)\b"
    ]
    for pattern in admin_patterns:
        if re.search(pattern, text, re.I):
            score -= 5

    # Bonus for project-like terms
    project_patterns = [
        r"\b(hotel|residential|mixed\s+use|development|building|renovation)\b",
        r"\b(conversion|expansion|construction|parking|garage)\b",
        r"\b(restaurant|retail|office|townhomes|apartments)\b",
        r"\b(\d+\s+\w+\s+street|street|avenue|road|boulevard)\b"  # addresses
    ]
    for pattern in project_patterns:
        if re.search(pattern, text, re.I):
            score += 3

    # Character composition scoring
    alpha_chars = sum(1 for ch in text if ch.isalpha())
    if length:
        alpha_ratio = alpha_chars / length
        if alpha_ratio > 0.65:
            score += 2

    # Word count bonus (reasonable project names have multiple words)
    word_count = len([token for token in text.split() if token])
    if 2 <= word_count <= 8:
        score += min(word_count, 6)
    elif word_count > 10:  # Too many words, likely a sentence fragment
        score -= 2

    return score


def select_ddrb_title(context_lines: List[str], id_index: Optional[int]) -> Tuple[Optional[str], int]:
    if not context_lines:
        return None, 0

    candidate_sources: List[Tuple[str, str]] = []
    seen_positions: set[int] = set()

    if id_index is not None:
        seen_positions.add(id_index)
        candidate_sources.append((context_lines[id_index], "id_line"))
        for offset in (1, 2):
            idx = id_index + offset
            if 0 <= idx < len(context_lines):
                seen_positions.add(idx)
                candidate_sources.append((context_lines[idx], "after"))
        for offset in (1, 2):
            idx = id_index - offset
            if 0 <= idx < len(context_lines) and idx not in seen_positions:
                seen_positions.add(idx)
                candidate_sources.append((context_lines[idx], "before"))

    for idx, line in enumerate(context_lines):
        if idx not in seen_positions:
            candidate_sources.append((line, "other"))

    origin_weights = {"id_line": 6, "after": 3, "before": 3, "other": 1}
    seen_text: set[str] = set()
    normalized_candidates: List[Tuple[str, str]] = []
    for source, origin in candidate_sources:
        candidate = strip_ddrb_identifier(source)
        if not candidate:
            candidate = strip_list_prefix(source).strip(":-–—• ")
        candidate = clean_ddrb_candidate_text(candidate)
        candidate = clean_text_fragment(candidate)
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen_text:
            continue
        seen_text.add(key)
        normalized_candidates.append((candidate, origin))

    # Score all candidates and pick the best one
    scored_candidates = []
    for candidate, origin in normalized_candidates:
        if not candidate:
            continue

        # Apply case normalization
        normalized = normalize_title_case(candidate)
        normalized = clean_ddrb_candidate_text(normalized)
        
        # Score the candidate
        title_score = score_ddrb_title(normalized)
        origin_bonus = origin_weights.get(origin, 0)
        total_score = title_score + origin_bonus

        if total_score > 0:  # Only consider positive-scoring candidates
            scored_candidates.append((normalized, total_score, origin))

    # Return the highest-scoring candidate
    if scored_candidates:
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        best_candidate, best_score, best_origin = scored_candidates[0]
        return best_candidate, origin_weights.get(best_origin, 0)

    return None, 0


def extract_context_line(text: str, match: re.Match[str], window: int = 160) -> str:
    if not text:
        return ""
    start = text.rfind("\n", 0, match.start())
    end = text.find("\n", match.end())
    if start == -1:
        start = 0
    else:
        start += 1
    if end == -1:
        end = len(text)
    context = clean_text_fragment(text[start:end])
    if context:
        return context
    fallback_start = max(0, match.start() - window)
    fallback_end = min(len(text), match.end() + window)
    return clean_text_fragment(text[fallback_start:fallback_end])


def extract_ddrb_context(
    text: str,
    match: re.Match[str],
    *,
    lines_before: int = 3,
    lines_after: int = 2,
) -> Tuple[str, Optional[str], int]:
    if not text:
        return "", None, 0
    lines = text.splitlines()
    line_index = text.count("\n", 0, match.start())
    start_idx = max(0, line_index - lines_before)
    end_idx = min(len(lines), line_index + lines_after + 1)
    raw_window = lines[start_idx:end_idx]

    context_lines: List[str] = []
    id_index: Optional[int] = None
    for raw_line in raw_window:
        cleaned = clean_ddrb_line(raw_line)
        if not cleaned:
            continue
        if id_index is None and DDRB_INLINE_RE.search(cleaned):
            id_index = len(context_lines)
        context_lines.append(cleaned)

    context = "; ".join(context_lines)
    if not context:
        fallback_start = max(0, match.start() - 160)
        fallback_end = min(len(text), match.end() + 160)
        context = clean_text_fragment(text[fallback_start:fallback_end])

    title, origin_bonus = select_ddrb_title(context_lines, id_index)
    if title:
        return context, title, origin_bonus
    if context:
        return context, context, 0
    return context, None, 0


def make_mention(data: dict, pid: str, snippet: str = "", doc_type_override: Optional[str] = None, page: int = 1, anchor_id: str = None, financials: List[str] = None) -> dict:
    url = data.get("url") or ""
    if not is_remote_url(url):
        url = ""
    title = data.get("title") or pid
    doc_type = doc_type_override or data.get("doc_type") or "other"
    return {
        "id": pid,
        "url": url,
        "title": title,
        "doc_type": doc_type,
        "source": data.get("source"),
        "source_name": data.get("source_name"),
        "meeting_date": data.get("meeting_date"),
        "meeting_title": data.get("meeting_title"),
        "snippet": snippet,
        "page": page,
        "anchor_id": anchor_id,
        "financials": financials or [],
    }


def build_dia_snippet(text: str, url: str = None) -> str:
    """Enhanced DIA snippet builder that extracts financial and development context."""
    ords = ", ".join(sorted({mm.group(1) for mm in ORD_RE.finditer(text)}))
    has_pud = bool(PUD_RE.search(text))
    parts: List[str] = []
    if ords:
        parts.append(f"Ordinances: {ords}")
    if has_pud:
        parts.append("Mentions PUD")

    # Try to extract financial and development content
    enhanced_snippet = extract_enhanced_snippet(text, url)
    if enhanced_snippet:
        parts.append(enhanced_snippet)

    # Extract metadata information from URL and document names when text is limited
    metadata_snippet = extract_metadata_snippet(url)
    if metadata_snippet:
        parts.append(metadata_snippet)

    if parts:
        return "; ".join(parts)

    # Enhanced fallback - try to load PDF text content if available
    pdf_snippet = try_load_pdf_snippet(url) if url else None
    if pdf_snippet:
        return pdf_snippet

    return clean_text_fragment(text[:200])


def extract_metadata_snippet(url: str) -> str:
    """Extract meaningful information from URLs and document names when text is limited."""
    if not url:
        return ""

    snippet_parts = []
    url_lower = url.lower()

    # Look for financial indicators in URL
    if "term-sheet" in url_lower or "termsheet" in url_lower:
        snippet_parts.append("Contains term sheet with financial arrangements")

    # Look for major development project indicators
    development_indicators = {
        "gateway": "Gateway Jax mixed-use development project",
        "pearl": "Pearl Street development district",
        "lavilla": "LaVilla historic district redevelopment",
        "shipyards": "Shipyards riverfront development",
        "ford": "Ford on Bay development project",
        "lot-j": "Lot J mixed-use stadium district",
        "brooklyn": "Brooklyn district development"
    }

    for key, description in development_indicators.items():
        if key in url_lower:
            snippet_parts.append(description)
            break

    # Look for project scale indicators from URL components
    scale_indicators = []
    if "modification" in url_lower:
        scale_indicators.append("project modification")
    if "allocation" in url_lower:
        scale_indicators.append("funding allocation")
    if "disposition" in url_lower:
        scale_indicators.append("property disposition")
    if "incentive" in url_lower:
        scale_indicators.append("development incentives")

    if scale_indicators:
        snippet_parts.append(f"Project involves: {', '.join(scale_indicators)}")

    # Extract resolution numbers for tracking
    res_match = re.search(r'R-(\d{4}-\d{2}-\d{2})', url)
    if res_match:
        snippet_parts.append(f"Resolution {res_match.group(1)}")

    return "; ".join(snippet_parts) if snippet_parts else ""


def extract_enhanced_snippet(text: str, url: str = None) -> str:
    """Extract financial amounts, development terms, and project context from text."""
    if not text:
        return ""

    snippet_parts = []

    # Extract money mentions
    financials = extract_financials(text)
    if financials:
        snippet_parts.append(f"Financial: {', '.join(financials[:3])}")  # Top 3 amounts

    # Extract development scale indicators
    scale_terms = []
    scale_patterns = [
        r'\b(?:mixed[\s-]?use|mixed[\s-]?development)\b',
        r'\b(?:redevelopment|development)\b',
        r'\b(?:riverfront|waterfront)\b',
        r'\b(?:plaza|tower|district|complex)\b',
        r'\b(?:residential\s+units?|commercial\s+space)\b',
        r'\b(?:parking\s+garage|parking\s+spaces?)\b',
    ]

    for pattern in scale_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        scale_terms.extend([m.lower() for m in matches])

    if scale_terms:
        unique_terms = list(dict.fromkeys(scale_terms))[:3]  # Keep order, limit to 3
        snippet_parts.append(f"Development: {', '.join(unique_terms)}")

    # Extract public/incentive mentions
    public_terms = []
    public_patterns = [
        r'\b(?:incentive\s+package|incentive\s+agreement|public\s+incentive)\b',
        r'\b(?:tax\s+increment|TIF|CRA)\b',
        r'\b(?:public[\s-]?private\s+partnership|PPP)\b',
        r'\b(?:term\s+sheet|funding\s+agreement)\b',
    ]

    for pattern in public_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        public_terms.extend([m.lower() for m in matches])

    if public_terms:
        unique_terms = list(dict.fromkeys(public_terms))[:2]
        snippet_parts.append(f"Public: {', '.join(unique_terms)}")

    return "; ".join(snippet_parts) if snippet_parts else ""


def try_load_pdf_snippet(url: str) -> str:
    """Try to load actual PDF text content for better snippet extraction."""
    if not url:
        return ""

    # Try to find corresponding text file in outputs/files/
    try:
        from urllib.parse import urlparse
        from pathlib import Path
        import hashlib

        # Generate the same filename the PDF extractor would use
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name
        if not filename.endswith('.pdf'):
            return ""

        # Look for text file in various locations
        possible_paths = [
            f"outputs/files/dia_board/2025/{filename}.txt",
            f"outputs/files/dia_board/2024/{filename}.txt",
            f"outputs/files/dia_board/2023/{filename}.txt",
            f"outputs/files/dia_resolutions/2025/{filename}.txt",
            f"outputs/files/dia_resolutions/2024/{filename}.txt",
            f"outputs/files/dia_resolutions/2023/{filename}.txt",
        ]

        for path_str in possible_paths:
            path = Path(path_str)
            if path.exists():
                try:
                    content = path.read_text(encoding='utf-8')
                    # Extract meaningful snippet from PDF content
                    return extract_enhanced_snippet(content[:2000])  # First 2000 chars
                except Exception:
                    continue

    except Exception:
        pass

    return ""


def extract_financials(text: str) -> List[str]:
    """Extract currency amounts from text."""
    if not text:
        return []
    # Match $1.5M, $500,000, $10 million, etc.
    money_pattern = r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?(?:million|billion|M|B|k|K)?"
    matches = re.findall(money_pattern, text)
    return list(set(matches))


def extract_matches_from_text(text: str, doc_type: Optional[str], source: Optional[str]) -> List[MatchHit]:
    if not text:
        return []
    
    hits: Dict[str, MatchHit] = {}
    
    # Check if text is paginated
    pages = []
    if "[[PAGE " in text[:100]:
        # Split by page delimiter
        raw_pages = text.split("[[PAGE ")
        # Skip the first empty chunk if file starts with delimiter
        for chunk in raw_pages:
            if not chunk.strip():
                continue
            # Chunk format: "N]]\nContent..."
            try:
                page_num_str, content = chunk.split("]]", 1)
                page_num = int(page_num_str)
                pages.append((page_num, content))
            except ValueError:
                # Fallback if malformed
                pages.append((1, chunk))
    else:
        pages = [(1, text)]

    doc_type_norm = normalize_doc_type(doc_type)
    allow_ddrb = doc_type_norm in MENTION_DOC_TYPES or (source or "").lower() in DDRB_SOURCE_IDS

    for page_num, page_text in pages:
        # 1. Standard DIA Resolutions
        for match in DIA_RESOLUTION_RE.finditer(page_text):
            pid = normalize_dia_resolution(match)
            if pid in hits:
                continue
            hits[pid] = MatchHit(
                project_id=pid,
                project_type="DIA-RES",
                context=extract_context_line(page_text, match),
                position=match.start(),
                page_number=page_num,
                financials=extract_financials(extract_context_line(page_text, match))
            )

        # 2. DDRB Cases
        if allow_ddrb:
            for match in DDRB_CASE_RE.finditer(page_text):
                pid = normalize_ddrb_case(match)
                context, candidate_title, origin_bonus = extract_ddrb_context(page_text, match)
                title_score = score_ddrb_title(candidate_title) + origin_bonus
                hits[pid] = MatchHit(
                    project_id=pid,
                    project_type="DDRB",
                    context=context,
                    candidate_title=candidate_title,
                    title_score=title_score,
                    position=match.start(),
                    page_number=page_num,
                    financials=extract_financials(context)
                )

        # 3. Anchor Matches
        for anchor_id, data in ANCHOR_PROJECTS.items():
            for pattern in data["patterns"]:
                match = re.search(pattern, page_text, re.I)
                if match:
                    # Use anchor ID as key if not already found (or override?)
                    # For now, we add it as a separate hit. Clusterer will merge.
                    # Actually, if we find a specific ID near the anchor text, that's better.
                    # But for now, let's treat the Anchor ID as a "Project ID" for hit purposes.
                    
                    context = extract_context_line(page_text, match)
                    
                    # Don't overwrite specific resolution/DDRB hits, but allow this to coexist
                    hits[f"{anchor_id}_{page_num}"] = MatchHit(
                        project_id=anchor_id,
                        project_type="ANCHOR",
                        context=context,
                        candidate_title=data["title"],
                        title_score=100, # High score for explicit anchor
                        position=match.start(),
                        page_number=page_num,
                        anchor_id=anchor_id,
                        financials=extract_financials(context)
                    )
                    break # One hit per anchor per page is sufficient

    return list(hits.values())


@dataclass
class TextArtifact:
    source: str
    year: str
    txt_path: Path
    meta_path: Path


@dataclass
class MatchHit:
    project_id: str
    project_type: str
    context: str
    candidate_title: Optional[str] = None
    title_score: int = 0
    position: int = 0
    page_number: int = 1
    anchor_id: Optional[str] = None
    financials: Optional[List[str]] = None


def iter_text_artifacts(source: Optional[str], year: Optional[str]) -> Iterable[TextArtifact]:
    if not FILES_DIR.exists():
        return []
    seen_meta: set[Path] = set()
    for src_dir in sorted([p for p in FILES_DIR.iterdir() if p.is_dir()]):
        sid = src_dir.name
        if source and sid != source:
            continue
        for ydir in sorted([p for p in src_dir.iterdir() if p.is_dir()]):
            yy = ydir.name
            if year and yy != year:
                continue
            meta_candidates: List[Path] = []
            mdir = ydir / "meta"
            if mdir.exists():
                meta_candidates.extend(sorted(mdir.glob("*.json")))
            meta_candidates.extend(sorted(ydir.glob("*.meta.json")))
            for meta_path in meta_candidates:
                if meta_path in seen_meta:
                    continue
                stem = meta_path.stem.lower()
                if "sample" in stem:
                    continue
                try:
                    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                text_field = meta_data.get("local_text_path") or meta_data.get("text_path")
                if not text_field:
                    continue
                txt_path = Path(text_field)
                if not txt_path.is_absolute() and not txt_path.exists():
                    candidate = Path.cwd() / txt_path
                    if candidate.exists():
                        txt_path = candidate
                if not txt_path.exists():
                    continue
                seen_meta.add(meta_path)
                yield TextArtifact(source=sid, year=yy, txt_path=txt_path, meta_path=meta_path)


def load_index() -> List[dict]:
    if PROJECTS_INDEX.exists():
        try:
            return json.loads(PROJECTS_INDEX.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_index(items: List[dict]) -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_INDEX.write_text(json.dumps(items, indent=2), encoding="utf-8")


def normalize_dia_resolution(m: re.Match[str]) -> str:
    raw = m.group("date") if "date" in m.groupdict() else m.group(1)
    digits = re.sub(r"[^0-9]", "", raw)
    if len(digits) < 8:
        return f"DIA-RES-{digits}"
    yyyy, mm, dd = digits[:4], digits[4:6], digits[6:8]
    return f"DIA-RES-{yyyy}-{mm}-{dd}"

def normalize_ddrb_case(m: re.Match[str]) -> str:
    yyyy = m.group("year") if "year" in m.groupdict() else m.group(1)
    num = m.group("num") if "num" in m.groupdict() else m.group(2)
    return f"DDRB-{yyyy}-{int(num):03d}"

def detect_primary_id_from_meta(meta: dict) -> Optional[Tuple[str, str]]:
    """Detect primary (project_id, type) from meta fields (filename/title/url)."""
    hay = " ".join(
        [
            str(meta.get("filename") or ""),
            str(meta.get("title") or ""),
            str(meta.get("url") or ""),
        ]
    )
    m = DIA_RESOLUTION_RE.search(hay)
    if m:
        return normalize_dia_resolution(m), "DIA-RES"
    m = DDRB_CASE_RE.search(hay)
    if m:
        return normalize_ddrb_case(m), "DDRB"
    return None


def iter_meta_items(source: Optional[str], year: Optional[str]) -> Iterable[Tuple[str, str, Path]]:
    """Yield (source, year, meta_path) for all meta JSON files."""
    if not FILES_DIR.exists():
        return []
    for src_dir in sorted([p for p in FILES_DIR.iterdir() if p.is_dir()]):
        sid = src_dir.name
        if source and sid != source:
            continue
        for ydir in sorted([p for p in src_dir.iterdir() if p.is_dir()]):
            yy = ydir.name
            if year and yy != year:
                continue
            meta_candidates: List[Path] = []
            mdir = ydir / "meta"
            if mdir.exists():
                meta_candidates.extend(sorted(mdir.glob("*.json")))
            meta_candidates.extend(sorted(ydir.glob("*.meta.json")))
            for mp in meta_candidates:
                stem = mp.stem.lower()
                if "sample" in stem:
                    continue
                yield sid, yy, mp


def load_raw_year(source: str, year: str) -> List[dict]:
    fp = RAW_DIR / source / year / f"{source}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        return data.get("items", [])
    except Exception:
        return []


def _dedupe_mentions(mentions: List[dict]) -> List[dict]:
    seen: set[Tuple[str, str]] = set()
    out: List[dict] = []
    for m in mentions or []:
        url = (m.get("url") or "").strip()
        if url:
            m["url"] = url
        url_key = url.lower()
        mid = (m.get("id") or "").strip().lower()
        key = (url_key, mid)
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


def upsert_project(index: List[dict], proj: dict) -> Tuple[List[dict], bool]:
    """Insert or merge based on id. Merge mentions and fill missing fields."""
    pid = (proj.get("id") or "").strip()
    if not pid:
        return index, False
    for p in index:
        if (p.get("id") or "").lower() == pid.lower():
            # Merge mentions
            if proj.get("mentions"):
                p.setdefault("mentions", []).extend(proj["mentions"])
                p["mentions"] = _dedupe_mentions(p["mentions"])  # Deduplicate by URL
            # Prefer filling missing metadata
            for k in ["title", "doc_type", "source", "meeting_date", "meeting_title"]:
                if not p.get(k) and proj.get(k):
                    p[k] = proj[k]
            # Preserve existing pending_review unless explicitly provided
            if "pending_review" in proj:
                p["pending_review"] = bool(proj["pending_review"])
            return index, False
    # New entry
    proj.setdefault("mentions", [])
    proj["mentions"] = _dedupe_mentions(proj["mentions"])  # Ensure unique URLs
    proj.setdefault("pending_review", True)
    index.append(proj)
    return index, True


def cleanup_project_titles(index: List[dict]) -> Tuple[List[dict], int]:
    """Post-process existing project titles to clean up problematic entries."""
    cleaned_count = 0

    for project in index:
        doc_type = project.get("doc_type", "")
        if doc_type not in ["DDRB", "DIA-RES"]:
            continue

        original_title = project.get("title", "")
        if not original_title:
            continue

        # Handle DIA resolution titles separately
        if doc_type == "DIA-RES":
            cleaned_title = clean_dia_resolution_title(original_title)
            # If cleaning resulted in empty title (was meeting doc), generate from ID
            if not cleaned_title.strip():
                project_id = project.get("id", "")
                if project_id.startswith("DIA-RES-"):
                    # Extract date from DIA-RES-YYYY-MM-DD format
                    parts = project_id.split('-')
                    if len(parts) >= 5:
                        year, month, day = parts[2], parts[3], parts[4]
                        cleaned_title = f"Resolution {year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        cleaned_title = f"Resolution {project_id}"
                else:
                    cleaned_title = original_title  # Fallback to original
        else:
            # Apply standard DDRB cleaning functions
            cleaned_title = clean_text_fragment(original_title)
            cleaned_title = normalize_title_case(cleaned_title)
            cleaned_title = clean_ddrb_candidate_text(cleaned_title)

            # Remove leading punctuation
            cleaned_title = cleaned_title.lstrip(',;:-• ')

        # For DDRB projects, try to extract project name from snippets
        if project.get("doc_type") == "DDRB":
            # First try to extract from snippets if current title is a document name or procedural
            if (cleaned_title.endswith(('Agenda-Minutes', 'AGENDA-MINUTES', 'Agenda', 'Minutes')) or
                is_procedural_text(cleaned_title)):

                mentions = project.get("mentions", [])
                snippet_extracted = None
                best_snippet_score = -100

                # Look for project names in snippets
                for mention in mentions:
                    snippet = mention.get("snippet", "")
                    if snippet:
                        extracted_name = extract_project_name_from_snippet(snippet, project.get("id", ""))
                        if extracted_name:
                            score = score_ddrb_title(extracted_name) + 20  # Bonus for snippet extraction
                            if score > best_snippet_score:
                                best_snippet_score = score
                                snippet_extracted = extracted_name

                if snippet_extracted:
                    cleaned_title = clean_ddrb_candidate_text(snippet_extracted)
                else:
                    # Try to find a better title from mention titles
                    better_title = None
                    best_score = -100

                    for mention in mentions:
                        mention_title = mention.get("title", "")
                        if mention_title and mention_title != original_title:
                            candidate = clean_text_fragment(mention_title)
                            candidate = normalize_title_case(candidate)
                            candidate = candidate.lstrip(',;:-• ')
                            candidate = clean_ddrb_candidate_text(candidate)

                            if not is_procedural_text(candidate):
                                score = score_ddrb_title(candidate)
                                if score > best_score:
                                    best_score = score
                                    better_title = candidate

                    if better_title:
                        cleaned_title = better_title
                    else:
                        # Keep original but mark for review
                        project["pending_review"] = True
                        continue

            elif is_procedural_text(cleaned_title):
                # Even if it's not a document name, if it's procedural text, try snippet extraction
                mentions = project.get("mentions", [])
                for mention in mentions:
                    snippet = mention.get("snippet", "")
                    if snippet:
                        extracted_name = extract_project_name_from_snippet(snippet, project.get("id", ""))
                        if extracted_name:
                            cleaned_title = clean_ddrb_candidate_text(extracted_name)
                            break
                else:
                    # Mark for review if no snippet extraction succeeded
                    project["pending_review"] = True
                    continue

        # Update title if it changed
        if cleaned_title != original_title and cleaned_title:
            project["title"] = cleaned_title
            cleaned_count += 1
            print(f"📝 Cleaned title: '{original_title}' → '{cleaned_title}'")

    return index, cleaned_count


def validate_project_titles(index: List[dict]) -> None:
    """Fail fast if titles regress to procedural text or leading punctuation."""
    issues: List[str] = []

    for project in index:
        pid = project.get("id") or "(missing id)"
        title = (project.get("title") or "").strip()

        if not title:
            issues.append(f"{pid}: missing title")
            continue

        if title[0] in {',', ';', ':', '-', '•', '–', '—'}:
            issues.append(f"{pid}: title starts with punctuation → '{title}'")
            continue

        lowered = title.lower()
        if lowered.startswith("agenda ") or lowered.startswith("minutes ") or lowered.startswith("meeting "):
            issues.append(f"{pid}: title looks procedural → '{title}'")
            continue

        if is_procedural_text(title):
            issues.append(f"{pid}: procedural text detected → '{title}'")

    if issues:
        preview = "\n".join(issues[:10])
        if len(issues) > 10:
            preview += f"\n… {len(issues) - 10} additional title issue(s)"
        raise SystemExit(
            "Title sanity check failed. Review the following projects and fix extraction heuristics:\n"
            + preview
        )


def is_administrative_title(title: str) -> bool:
    """Check if a title indicates an administrative/financial resolution rather than a development project."""
    if not title:
        return False
    
    title_lower = title.lower()
    
    # Financial and administrative keywords
    admin_terms = [
        "debt reduction", "debt red", "ss fr ", "ss from ",
        "budget", "amending the budget", # "budget" covers many
        "unallocated", "appropriat", "allocating", "allocate", # "appropriat" covers appropriation/ing/ed/typos
        "fund balance", "tid fund", "trust fund", "investment pool earnings",
        "revenue", "earnings", "interest income",
        "election of", "identifying the chair", "appointing",
        "meeting minutes", "meeting agenda", "meeting packet",
        "approving the minutes", "approving minutes",
        "consent agenda", "ratification",
        "financial report", "finance report",
        "schedule of meetings",
        "recognition", "appreciation", "sponsorship", "advertising",
        "approving the 20", "adopting the 20", # Annual adoption things
        "signature authorization", "professional services", "maintenance",


        "cra annual report",
        "declaring the official intent", # Bond issuances often
        "authorizing the issuance", # Bonds
        "pension fund",
    ]
    
    return any(term in title_lower for term in admin_terms)


def remove_meeting_document_projects(index: List[dict]) -> Tuple[List[dict], int]:
    """Remove projects that are actually meeting documents or administrative resolutions."""
    removed_count = 0
    filtered_index = []

    for project in index:
        project_id = project.get("id", "")
        title = project.get("title", "")
        doc_type = project.get("doc_type", "")

        # Check if this is a meeting document masquerading as a project
        if is_meeting_document(title, doc_type):
            removed_count += 1
            # print(f"🗑️ Removed meeting document: {project_id} - '{title}'")
            continue
            
        # Check if this is an administrative resolution
        if is_administrative_title(title):
            removed_count += 1
            # print(f"🗑️ Removed administrative item: {project_id} - '{title}'")
            continue

        # Keep the project
        filtered_index.append(project)

    return filtered_index, removed_count


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Extract candidate projects from collected artifacts")
    ap.add_argument("--source", help="Limit to a single source id", default=None)
    ap.add_argument("--year", help="Limit to a single year (YYYY)", default=None)
    ap.add_argument("--file", help="Process a single extracted text file (or PDF)", default=None)
    ap.add_argument("--reset", help="Recreate projects index file before writing", action="store_true")
    ap.add_argument("--cleanup-titles", help="(deprecated) Title cleanup now runs automatically", action="store_true")
    ap.add_argument("--remove-meeting-docs", help="(deprecated) Cleanup now runs automatically", action="store_true")
    args = ap.parse_args(argv)

    if args.file and args.source:
        ap.error("--file cannot be used with --source")
    if args.file and args.reset:
        ap.error("--file cannot be used with --reset")
    if args.file and args.year:
        ap.error("--file cannot be used with --year")

    if args.reset:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        PROJECTS_INDEX.write_text("[]", encoding="utf-8")
        index: List[dict] = []
    else:
        index = load_index()
        cleaned_index: List[dict] = []
        for proj in index:
            title = (proj.get("title") or "").lower()
            if title.startswith("sample ddrb"):
                continue
            mentions = proj.get("mentions") or []
            sample_url = any("example.com/sample_ddrb" in (m.get("url") or "") for m in mentions)
            if sample_url:
                continue
            cleaned_index.append(proj)
        if len(cleaned_index) != len(index):
            index = cleaned_index

    # Always clean up non-projects
    index, removed_count = remove_meeting_document_projects(index)
    if removed_count > 0:
        print(f"✅ Removed {removed_count} non-project items (meetings/administrative)")

    if args.cleanup_titles:
        print("ℹ️  --cleanup-titles is now automatic; flag retained for compatibility.")
        
    created = 0
    ddrb_debug_entries: List[str] = []
    timestamp = datetime.now().isoformat()
    ddrb_debug_entries.append(f"[EXTRACTION RUN] {timestamp}\n")

    if args.file:
        index, added, exit_code = process_single_project_file(Path(args.file), index)
        if exit_code == 0:
            if added:
                created += added
            save_index(index)
        return exit_code

    # Prefer meta-only scan first (reference_only mode)
    for sid, yy, mp in iter_meta_items(args.source, args.year):
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            continue
        det = detect_primary_id_from_meta(meta)
        if not det:
            continue
        pid, ptype = det
        meta_source = meta.get("source") or sid
        mentions: List[dict] = []
        primary_mention = make_mention(meta, pid)
        if primary_mention:
            mentions.append(primary_mention)

        # Try to enrich with related meeting documents via dia_board raw store
        mdate = (meta.get("meeting_date") or "").strip()
        mtitle = (meta.get("meeting_title") or "").strip()
        related_mentions: List[dict] = []
        for item in load_raw_year("dia_board", yy):
            if not item:
                continue
            md = (item.get("meeting_date") or "").strip()
            mt = (item.get("meeting_title") or "").strip()
            match_meeting = False
            if mdate and md == mdate:
                match_meeting = True
            elif mtitle and mt == mtitle:
                match_meeting = True
            if not match_meeting:
                continue
            doc_type_norm = normalize_doc_type(item.get("doc_type"))
            if doc_type_norm and doc_type_norm in RELATED_DOC_TYPES:
                related_mentions.append(make_mention(item, pid))

        if related_mentions:
            seen_urls: set[str] = {m.get("url") for m in mentions if m.get("url")}
            for mention in related_mentions:
                url = (mention.get("url") or "").strip()
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                mentions.append(mention)

        proj = {
            "id": pid,
            "title": meta.get("title") or pid,
            "doc_type": ptype,
            "source": meta_source,
            "meeting_date": meta.get("meeting_date"),
            "meeting_title": meta.get("meeting_title"),
            "mentions": mentions,
            "pending_review": True,
        }
        
        # Immediate check for admin title
        if is_administrative_title(proj["title"]) or is_meeting_document(proj["title"]):
            continue

        index, is_new = upsert_project(index, proj)
        if is_new:
            created += 1
            print(f"➕ New project: {proj['id']} ({proj.get('title','')}) with {len(proj['mentions'])} mention(s)")

    # Process raw data sources directly for additional project extraction
    raw_sources = ["dia_ddrb", "dia_board"] if not args.source else [args.source] if args.source in ["dia_ddrb", "dia_board"] else []
    for raw_source in raw_sources:
        source_years = [args.year] if args.year else []
        if not source_years:
            # Find all years for this source
            source_dir = RAW_DIR / raw_source
            if source_dir.exists():
                source_years = [d.name for d in source_dir.iterdir() if d.is_dir() and d.name.isdigit()]

        for year in source_years:
            raw_items = load_raw_year(raw_source, year)
            print(f"🔍 Processing {len(raw_items)} raw items from {raw_source}/{year}")

            for item in raw_items:
                # Extract project IDs from raw items
                title = item.get("title", "")
                doc_type = item.get("doc_type", "")
                
                # Check admin/meeting doc early
                if is_administrative_title(title) or is_meeting_document(title, doc_type):
                    continue

                # Look for DDRB case IDs (only actual development cases become projects)
                if "DDRB" in title.upper() or "DDRB" in doc_type.upper():
                    # Only create projects for explicit DDRB case numbers (real development projects)
                    ddrb_match = re.search(DDRB_CASE_RE, title)
                    if ddrb_match:
                        case_year = ddrb_match.group("year")
                        case_num = ddrb_match.group("num")
                        pid = f"DDRB-{case_year}-{case_num.zfill(3)}"
                        project_title = title or f"DDRB Case {case_year}-{case_num}"

                        # Create DDRB project for actual development cases
                        mention = {
                            "id": pid,
                            "url": item.get("url", ""),
                            "title": title,
                            "doc_type": doc_type or "case",
                            "source": raw_source,
                            "source_name": "DDRB" if raw_source == "dia_ddrb" else "DIA Board",
                            "meeting_date": item.get("meeting_date"),
                            "meeting_title": item.get("meeting_title"),
                            "snippet": title[:200] if title else ""
                        }

                        proj = {
                            "id": pid,
                            "title": project_title,
                            "doc_type": "DDRB",
                            "source": raw_source,
                            "meeting_date": item.get("meeting_date"),
                            "meeting_title": item.get("meeting_title"),
                            "mentions": [mention],
                            "pending_review": True,
                        }

                        index, is_new = upsert_project(index, proj)
                        if is_new:
                            created += 1
                            print(f"➕ New DDRB project: {proj['id']} ({proj.get('title','')})")
                    # Skip meeting documents (agendas, packets, minutes) - they are sources only, not projects

                # Look for DIA resolution IDs
                dia_match = DIA_RESOLUTION_RE.search(title)
                if dia_match:
                    pid = normalize_dia_resolution(dia_match)
                    parts = pid.split('-')
                    if len(parts) >= 5:
                        year_str, month_str, day_str = parts[2], parts[3], parts[4]
                    else:
                        year_str, month_str, day_str = pid, "", ""

                    mention = {
                        "id": pid,
                        "url": item.get("url", ""),
                        "title": title,
                        "doc_type": doc_type or "resolution",
                        "source": raw_source,
                        "source_name": "DIA Board",
                        "meeting_date": item.get("meeting_date"),
                        "meeting_title": item.get("meeting_title"),
                        "snippet": title[:200] if title else ""
                    }

                    proj = {
                        "id": pid,
                        "title": title or f"DIA Resolution {year_str}-{month_str}-{day_str}",
                        "doc_type": "DIA-RES",
                        "source": raw_source,
                        "meeting_date": item.get("meeting_date"),
                        "meeting_title": item.get("meeting_title"),
                        "mentions": [mention],
                        "pending_review": True,
                    }

                    index, is_new = upsert_project(index, proj)
                    if is_new:
                        created += 1
                        print(f"➕ New DIA project: {proj['id']} ({proj.get('title','')})")

    # Also scan PDFs (if any downloaded) for primary-ID reinforcement and add snippet context
    for art in iter_text_artifacts(args.source, args.year):
        try:
            meta = json.loads(art.meta_path.read_text(encoding="utf-8"))
            text = art.txt_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            if art.source == "dia_ddrb":
                ddrb_debug_entries.append(f"[ERROR] Failed to read {art.txt_path}: {e}")
            continue

        # Skip HTML-heavy content for DDRB processing
        source_value = (meta.get("source") or art.source or "").strip()
        if source_value.lower() == "dia_ddrb":
            if is_html_content(text):
                debug_lines = [
                    "[SKIPPED HTML]",
                    f"File: {art.txt_path.name}",
                    f"Reason: HTML/JavaScript content detected",
                ]
                title_val = meta.get("title")
                if title_val:
                    debug_lines.append(f"Title: {clean_text_fragment(str(title_val))}")
                url_val = meta.get("url")
                if url_val:
                    debug_lines.append(f"URL: {url_val}")
                ddrb_debug_entries.append("\n".join(debug_lines))
                continue
            if is_short_text(text):
                debug_lines = [
                    "[SHORT TEXT]",
                    f"File: {art.txt_path.name}",
                    f"Length: {len(clean_text_fragment(text))} characters",
                ]
                title_val = meta.get("title")
                if title_val:
                    debug_lines.append(f"Title: {clean_text_fragment(str(title_val))}")
                url_val = meta.get("url")
                if url_val:
                    debug_lines.append(f"URL: {url_val}")
                ddrb_debug_entries.append("\n".join(debug_lines))

        doc_type_value = meta.get("doc_type")
        matches = extract_matches_from_text(text, doc_type_value, meta.get("source") or art.source)
        ddrb_ids_for_file: List[str] = []

        doc_type_norm = normalize_doc_type(doc_type_value)
        allow_ddrb = doc_type_norm in MENTION_DOC_TYPES or source_value.lower() in DDRB_SOURCE_IDS
        text_has_ddrb = bool(re.search(r"\bDDRB\b", text, re.I))
        has_ddrb_hit = any(hit.project_type == "DDRB" for hit in matches)

        if allow_ddrb and text_has_ddrb and not has_ddrb_hit:
            snippet_idx = text.upper().find("DDRB")
            snippet_window = ""
            if snippet_idx != -1:
                snippet_window = clean_text_fragment(
                    text[max(0, snippet_idx - 160) : min(len(text), snippet_idx + 200)]
                )
            if not snippet_window:
                snippet_window = clean_text_fragment(text[:200])
            debug_lines = [
                "[MISSING DDRB ID]",
                f"File: {art.txt_path.name}",
                f"Source: {source_value or art.source}",
                f"Doc type: {doc_type_value or ''}",
            ]
            title_val = meta.get("title")
            if title_val:
                debug_lines.append(f"Title: {clean_text_fragment(str(title_val))}")
            url_val = meta.get("url")
            if url_val:
                debug_lines.append(f"URL: {url_val}")
            if snippet_window:
                debug_lines.append(f"Snippet: {snippet_window}")
            ddrb_debug_entries.append("\n".join(debug_lines))

        if not matches:
            if source_value.lower() == "dia_ddrb":
                ddrb_debug_entries.append(f"[NO DDRB] {art.txt_path}")
            continue

        dia_snippet = build_dia_snippet(text, meta.get("url"))
        fallback_snippet = clean_text_fragment(text[:200])

        for hit in matches:
            if hit.candidate_title and (is_administrative_title(hit.candidate_title) or is_meeting_document(hit.candidate_title)):
                continue
            
            snippet = dia_snippet if hit.project_type == "DIA-RES" else hit.context
            if not snippet:
                snippet = fallback_snippet
            mention = make_mention(meta, hit.project_id, snippet=snippet, page=hit.page_number, anchor_id=hit.anchor_id, financials=hit.financials)
            if not mention:
                continue
            project_title = hit.candidate_title or meta.get("title") or hit.project_id
            
            if is_administrative_title(project_title) or is_meeting_document(project_title):
                continue
                
            payload = {
                "id": hit.project_id,
                "title": project_title,
                "doc_type": hit.project_type,
                "source": source_value or art.source,
                "meeting_date": meta.get("meeting_date"),
                "meeting_title": meta.get("meeting_title"),
                "mentions": [mention],
            }
            if hit.project_type == "DDRB":
                ddrb_ids_for_file.append(hit.project_id)
            index, is_new = upsert_project(index, payload)
            if is_new:
                created += 1
                print(
                    f"➕ New project: {payload['id']} ({payload.get('title','')}) "
                    f"from text in {meta.get('source') or art.source}"
                )
        if source_value.lower() == "dia_ddrb":
            if ddrb_ids_for_file:
                for pid in sorted(set(ddrb_ids_for_file)):
                    ddrb_debug_entries.append(f"[MATCH DDRB] {pid} from {art.txt_path}")
            else:
                ddrb_debug_entries.append(f"[NO DDRB] {art.txt_path}")
    # Always write debug log for DDRB processing
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    # Append to existing log if it exists, otherwise create new
    debug_content = "\n\n".join(ddrb_debug_entries) + "\n\n"

    if DDRB_DEBUG_LOG.exists():
        # Append to existing log
        with open(DDRB_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(debug_content)
    else:
        # Create new log
        DDRB_DEBUG_LOG.write_text(debug_content, encoding="utf-8")

    ddrb_project_count = sum(1 for p in index if (p.get("id") or "").upper().startswith("DDRB-"))
    ddrb_summary = f"\n[SUMMARY] Found {ddrb_project_count} DDRB project(s) in index"
    with open(DDRB_DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(ddrb_summary)

    index, cleaned_count = cleanup_project_titles(index)
    if cleaned_count:
        print(f"🧹 Cleaned {cleaned_count} project titles (automatic)")
        
    # Final pass to remove any that might have slipped through or been renamed to admin titles
    index, removed_count_final = remove_meeting_document_projects(index)
    if removed_count_final > 0:
        print(f"✅ Removed {removed_count_final} items in final pass")

    validate_project_titles(index)

    normalized_index: List[dict] = []
    for project in index:
        normalized_index.append(enhance_project_schema(project))

    save_index(normalized_index)
    print(f"\n🏁 Project extraction complete. Projects indexed: {len(normalized_index)} (new: {created})")
    return 0



if __name__ == "__main__":
    sys.exit(main())
