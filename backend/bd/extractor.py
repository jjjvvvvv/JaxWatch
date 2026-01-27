"""
Project extractor using LLM.

Extracts structured project data from DIA meeting packets as JSON.
Uses resolution-anchored chunked extraction for better accuracy with Llama 3.1 8B.

Usage:
    python3 -m backend.bd.extractor [--period 2026] [--force]
"""
import argparse
import json
import logging
import re
import requests
import pdfplumber
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bd.extractor")

# Paths
RAW_DIR = Path("outputs/raw")
BD_DIR = Path("outputs/bd")
EXTRACTIONS_DIR = BD_DIR / "extractions"

# Ollama config
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"

# DIA sources to process
DIA_SOURCES = ["dia_board"]

# Resolution patterns
RESOLUTION_PATTERN = re.compile(
    r'RESOLUTION\s+(\d{4}[-_]\d{2}[-_]\d{2})',
    re.IGNORECASE
)

# Recognition resolution detection
RECOGNITION_PATTERNS = [
    r'\brecognition\b',
    r'\bappreciation\b',
    r'\bhonoring\b',
    r'\bcommending\b',
    r'\bservice\s+to\s+the\s+(board|city|community)\b',
    r'\bretiring\b',
    r'\bdeparting\b',
    r'\bthank(s|ing)\s+(him|her|them)\b',
]

# Prompt for single project extraction
SINGLE_PROJECT_PROMPT = '''Extract project data for RESOLUTION {resolution_id} from the text below.

Return a JSON object with these exact fields:
- project_name: The name of the development project
- resolution_number: "{resolution_id}"
- developer: The company/entity developing the project
- project_type: One of: hotel, office, retail, residential, mixed-use, infrastructure, demolition, land_disposition, other
- total_investment: Dollar amount (e.g., "$108.8 million") or null
- incentives: Array of objects with type, amount, status (or empty array)
- location: Street address or area description or null
- stage: One of: rfp, term_sheet, conceptual, final_approval, amendment, extension, deferred, other
- action: Brief description of what the resolution does
- concerns: Any noted issues or null

Incentive types: completion_grant, rev_grant, loan, tax_rebate, land_sale, other
Status values: pending, approved, recommended

EXAMPLE OUTPUT:
{{
  "project_name": "Baptist Health Mixed-Use Hotel",
  "resolution_number": "2026-01-01",
  "developer": "Baptist Health System, Inc.",
  "project_type": "hotel",
  "total_investment": "$108.8 million",
  "incentives": [
    {{"type": "rev_grant", "amount": "$3,200,000", "status": "recommended"}}
  ],
  "location": "Southside CRA",
  "stage": "term_sheet",
  "action": "Recommends City Council approval of REV Grant for hotel development",
  "concerns": null
}}

TEXT FOR RESOLUTION {resolution_id}:
---
{text_chunk}
---

Return ONLY the JSON object. Start with {{ and end with }}:'''


# Valid enum values
VALID_PROJECT_TYPES = {'hotel', 'office', 'retail', 'residential', 'mixed-use',
                       'infrastructure', 'demolition', 'land_disposition', 'other'}
VALID_STAGES = {'rfp', 'term_sheet', 'conceptual', 'final_approval',
                'amendment', 'extension', 'deferred', 'other'}
VALID_INCENTIVE_TYPES = {'completion_grant', 'rev_grant', 'loan', 'tax_rebate',
                         'land_sale', 'other'}


def call_llm(prompt: str, timeout: int = 300) -> Optional[str]:
    """Call Ollama API."""
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "num_ctx": 8192},
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


def download_and_extract_text(url: str, max_pages: int = 50) -> str:
    """Download PDF and extract text."""
    try:
        logger.info(f"Downloading {url}...")
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        resp.raise_for_status()

        text = ""
        with io.BytesIO(resp.content) as f:
            with pdfplumber.open(f) as pdf:
                total_pages = len(pdf.pages)
                process_pages = min(total_pages, max_pages)
                logger.info(f"PDF has {total_pages} pages. Extracting first {process_pages}...")

                for i in range(process_pages):
                    page = pdf.pages[i]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        return text
    except Exception as e:
        logger.error(f"Failed to process PDF {url}: {e}")
        return ""


def discover_resolutions(text: str) -> List[str]:
    """Find all resolution numbers in document using regex."""
    matches = RESOLUTION_PATTERN.findall(text)
    # Normalize to YYYY-MM-DD format
    normalized = []
    for m in matches:
        clean = m.replace('_', '-')
        if clean not in normalized:
            normalized.append(clean)
    return sorted(set(normalized))


def extract_resolution_chunk(text: str, resolution_id: str,
                              context_before: int = 500,
                              context_after: int = 5000) -> str:
    """Extract text chunk focused on a specific resolution.

    Prioritizes finding the actual resolution body (with 'A RESOLUTION OF' or 'TAB' marker)
    over agenda mentions.
    """
    res_id_escaped = re.escape(resolution_id)
    res_id_underscore = re.escape(resolution_id.replace("-", "_"))

    # Priority 1: Look for actual resolution body (has "A RESOLUTION OF" nearby)
    body_patterns = [
        re.compile(rf'TAB\s+[IVX]+\.[A-Z]\s*\n*\s*RESOLUTION\s+{res_id_escaped}', re.IGNORECASE),
        re.compile(rf'RESOLUTION\s+{res_id_escaped}\s*\n+\s*A\s+RESOLUTION\s+OF', re.IGNORECASE),
        re.compile(rf'RESOLUTION\s+{res_id_underscore}\s*\n+\s*A\s+RESOLUTION\s+OF', re.IGNORECASE),
    ]

    for pattern in body_patterns:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - context_before)
            end = min(len(text), match.end() + context_after)
            return text[start:end]

    # Priority 2: Find the LAST mention (usually the actual resolution, not agenda)
    simple_patterns = [
        re.compile(rf'RESOLUTION\s+{res_id_escaped}', re.IGNORECASE),
        re.compile(rf'RESOLUTION\s+{res_id_underscore}', re.IGNORECASE),
    ]

    last_match = None
    for pattern in simple_patterns:
        for match in pattern.finditer(text):
            last_match = match

    if last_match:
        start = max(0, last_match.start() - context_before)
        end = min(len(text), last_match.end() + context_after)
        return text[start:end]

    return ""


def is_recognition_resolution(chunk: str) -> bool:
    """Detect if a resolution is for recognition/appreciation rather than a project."""
    chunk_lower = chunk.lower()
    for pattern in RECOGNITION_PATTERNS:
        if re.search(pattern, chunk_lower):
            return True
    return False


def repair_json(raw_response: str) -> Optional[str]:
    """Attempt to repair common JSON issues from LLM output."""
    if not raw_response:
        return None

    text = raw_response.strip()

    # 1. Remove markdown code fences
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0].strip()
    elif '```' in text:
        parts = text.split('```')
        if len(parts) >= 2:
            text = parts[1].strip()

    # 2. Find JSON object boundaries
    first_brace = text.find('{')
    last_brace = text.rfind('}')

    if first_brace == -1:
        return None

    if last_brace == -1 or last_brace < first_brace:
        # Missing closing brace - try to add it
        text = text[first_brace:] + '}'
    else:
        text = text[first_brace:last_brace + 1]

    # 3. Fix common issues
    # Fix trailing commas before } or ]
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # 4. Fix Python literals
    text = re.sub(r':\s*None\b', ': null', text)
    text = re.sub(r':\s*True\b', ': true', text)
    text = re.sub(r':\s*False\b', ': false', text)

    return text


def validate_project_schema(obj: dict, resolution_id: str) -> Tuple[bool, List[str]]:
    """Validate extracted project against expected schema. Fill in defaults for missing fields."""
    errors = []

    # Fill in defaults for missing fields
    if not obj.get('project_name'):
        # Try to derive from other fields
        if obj.get('developer'):
            obj['project_name'] = f"{obj['developer']} Project"
        else:
            obj['project_name'] = f"Resolution {resolution_id}"

    if not obj.get('developer'):
        obj['developer'] = "Unknown"

    if not obj.get('project_type'):
        obj['project_type'] = "other"

    if not obj.get('stage'):
        obj['stage'] = "other"

    if not obj.get('action'):
        obj['action'] = f"Resolution {resolution_id} action"

    # No required field check - we filled in defaults

    # Validate project_type enum
    if obj.get('project_type'):
        ptype = obj['project_type'].lower().replace(' ', '-')
        if ptype not in VALID_PROJECT_TYPES:
            # Try to fix common variants
            if ptype in ['mixed_use', 'mixeduse']:
                obj['project_type'] = 'mixed-use'
            else:
                errors.append(f"Invalid project_type: {obj['project_type']}")

    # Validate stage enum
    if obj.get('stage'):
        stage = obj['stage'].lower().replace(' ', '_')
        if stage not in VALID_STAGES:
            errors.append(f"Invalid stage: {obj['stage']}")

    # Validate incentives structure
    if 'incentives' in obj and obj['incentives']:
        if not isinstance(obj['incentives'], list):
            errors.append("incentives must be an array")
        else:
            for i, inc in enumerate(obj['incentives']):
                if not isinstance(inc, dict):
                    errors.append(f"incentives[{i}] must be an object")

    return len(errors) == 0, errors


def extract_single_project(text: str, resolution_id: str,
                           meeting_date: str, source_url: str,
                           max_retries: int = 2) -> Optional[Dict]:
    """Extract a single project with validation and retry."""

    # Get focused chunk
    chunk = extract_resolution_chunk(text, resolution_id)
    if not chunk:
        logger.warning(f"Could not find resolution {resolution_id} in text")
        return None

    # Check if it's a recognition resolution
    if is_recognition_resolution(chunk):
        logger.info(f"Skipping recognition resolution: {resolution_id}")
        return None

    # Limit chunk size to fit in context window (8192 tokens ~ 32k chars)
    max_chunk = 20000
    if len(chunk) > max_chunk:
        chunk = chunk[:max_chunk]

    prompt = SINGLE_PROJECT_PROMPT.format(
        resolution_id=resolution_id,
        text_chunk=chunk
    )

    for attempt in range(max_retries + 1):
        result = call_llm(prompt)

        if not result:
            logger.warning(f"LLM returned empty for {resolution_id}, attempt {attempt + 1}")
            continue

        # Repair JSON
        repaired = repair_json(result)
        if not repaired:
            logger.warning(f"Could not extract JSON from response for {resolution_id}")
            logger.debug(f"Raw response: {result[:500]}")
            continue

        try:
            project = json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error for {resolution_id}: {e}")
            logger.debug(f"Repaired JSON: {repaired[:500]}")
            continue

        # Ensure resolution_number is set
        if not project.get('resolution_number'):
            project['resolution_number'] = resolution_id

        # Validate
        is_valid, errors = validate_project_schema(project, resolution_id)

        if is_valid:
            # Add metadata
            project['_extracted_from'] = source_url
            project['_meeting_date'] = meeting_date
            project['_extracted_at'] = datetime.now().isoformat()
            logger.info(f"Extracted: {project.get('project_name', 'Unknown')} ({resolution_id})")
            return project
        else:
            logger.warning(f"Validation errors for {resolution_id} (attempt {attempt + 1}): {errors}")

    logger.error(f"Failed to extract valid project for {resolution_id} after {max_retries + 1} attempts")
    return None


def extract_projects_from_text(text: str, meeting_date: str, source_url: str) -> List[Dict]:
    """Main extraction pipeline - resolution-anchored chunked extraction."""
    if not text:
        return []

    # Phase 1: Discover resolutions
    resolutions = discover_resolutions(text)
    logger.info(f"Discovered {len(resolutions)} resolutions: {resolutions}")

    if not resolutions:
        logger.warning("No resolutions found in document")
        return []

    # Filter to only current meeting's resolutions (by year)
    meeting_year = meeting_date[:4] if meeting_date else None
    if meeting_year:
        current_resolutions = [r for r in resolutions if r.startswith(meeting_year)]
        if current_resolutions:
            logger.info(f"Filtering to {meeting_year} resolutions: {current_resolutions}")
            resolutions = current_resolutions

    # Phase 2: Extract each resolution
    projects = []
    for res_id in resolutions:
        project = extract_single_project(text, res_id, meeting_date, source_url)
        if project:
            projects.append(project)

    logger.info(f"Successfully extracted {len(projects)} projects from {len(resolutions)} resolutions")
    return projects


def parse_period(period: str) -> tuple:
    """Parse period string into (year, quarter)."""
    if not period:
        return (None, None)

    period = period.upper().strip()

    q_match = re.match(r"Q(\d)-(\d{4})", period)
    if q_match:
        return (int(q_match.group(2)), int(q_match.group(1)))

    if re.match(r"^\d{4}$", period):
        return (int(period), None)

    return (None, None)


def is_packet(item: Dict) -> bool:
    """Check if item is a meeting packet."""
    doc_type = item.get("doc_type", "")
    title = item.get("title", "").lower()
    return doc_type == "packet" or "agenda packet" in title


def main():
    parser = argparse.ArgumentParser(description="Extract projects from DIA meeting packets")
    parser.add_argument("--period", help="Filter by period: 2026, Q1-2025, etc.")
    parser.add_argument("--force", action="store_true", help="Re-extract even if already done")
    args = parser.parse_args()

    year, quarter = parse_period(args.period)
    if year:
        period_str = f"Q{quarter}-{year}" if quarter else str(year)
        logger.info(f"Filtering to period: {period_str}")

    # Ensure output directories exist
    BD_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)

    if not RAW_DIR.exists():
        logger.error(f"Raw data directory not found: {RAW_DIR}")
        return

    all_extractions = []

    for source_name in DIA_SOURCES:
        source_dir = RAW_DIR / source_name
        if not source_dir.exists():
            logger.info(f"Skipping {source_name} (not found)")
            continue

        # Find JSON files (optionally filtered by year)
        if year:
            search_dir = source_dir / str(year)
            if not search_dir.exists():
                continue
        else:
            search_dir = source_dir

        for json_file in search_dir.rglob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read {json_file}: {e}")
                continue

            items = data.get("items", [])
            packets = [it for it in items if is_packet(it)]

            for item in packets:
                title = item.get("title", "")
                url = item.get("url", "")
                meeting_date = item.get("meeting_date", "")

                # Check if already extracted
                extraction_id = f"{source_name}_{meeting_date}_{hash(url)}"
                extraction_file = EXTRACTIONS_DIR / f"{extraction_id}.json"

                if extraction_file.exists() and not args.force:
                    logger.info(f"Skipping {title} (already extracted)")
                    with open(extraction_file) as f:
                        existing = json.load(f)
                    all_extractions.extend(existing.get("projects", []))
                    continue

                logger.info(f"Processing: {title}")

                # Download and extract text
                text = download_and_extract_text(url)
                if not text:
                    continue

                # Extract projects using resolution-anchored chunking
                projects = extract_projects_from_text(text, meeting_date, url)

                # Save extraction
                extraction_data = {
                    "source": source_name,
                    "meeting_date": meeting_date,
                    "packet_title": title,
                    "packet_url": url,
                    "extracted_at": datetime.now().isoformat(),
                    "projects": projects,
                }

                with open(extraction_file, "w") as f:
                    json.dump(extraction_data, f, indent=2)

                all_extractions.extend(projects)
                logger.info(f"Saved extraction to {extraction_file}")

    # Write combined extractions for CRM processing
    combined_file = BD_DIR / "latest_extractions.json"
    with open(combined_file, "w") as f:
        json.dump({
            "extracted_at": datetime.now().isoformat(),
            "period": args.period,
            "total_projects": len(all_extractions),
            "projects": all_extractions,
        }, f, indent=2)

    logger.info(f"Extracted {len(all_extractions)} total projects → {combined_file}")
    logger.info("Run 'make bd-merge' to merge into CRM")


if __name__ == "__main__":
    main()
