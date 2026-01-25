import json
import logging
import requests
import pdfplumber
import io
import time
from pathlib import Path
from backend.collector.dia_meeting_scraper import _call_llm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("outputs/summary_process.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("summary_proc")

DATA_FILE = Path("outputs/raw/dia_board/2026/dia_board.json")

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

def summarize_text(text: str) -> str:
    """Ask LLM to summarize the meeting packet content."""
    # Cap at ~60,000 chars (approx 15k tokens) to stay well within 128k but keep speed reasonable
    text_sample = text[:60000]
    
    prompt = f"""
    You are a city hall reporter analyzing a meeting packet.
    Summarize the following text from a Downtown Investment Authority (DIA) meeting.
    
    GUIDELINES:
    1. EXTRACT HARD DATA: List specific project names, dollar amounts (grants/loans), and addresses.
    2. RESOLUTIONS: Briefly explain what each resolution does (e.g. "Approves $500k rev grant for X").
    3. IGNORE: Roll calls, pledge of allegiance, routine approvals of minutes unless contested.
    4. FORMAT: Use Markdown bullet points.
    
    PACKET TEXT:
    {text_sample}
    """
    
    return _call_llm(prompt, json_mode=False)

def main():
    if not DATA_FILE.exists():
        logger.error(f"Data file not found: {DATA_FILE}")
        return

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return

    items = data.get("items", [])
    packets = [it for it in items if it.get("doc_type") == "packet"]
    logger.info(f"Found {len(packets)} packets in 2026 bucket.")
    
    updated_count = 0
    
    for i, item in enumerate(items):
        if item.get("doc_type") != "packet":
            continue
            
        if item.get("summary"):
            logger.info(f"Skipping {item['title']} (already summarized)")
            continue

        logger.info(f"Processing {item['title']} ({i+1}/{len(items)})...")
        
        text = download_and_extract_text(item["url"])
        if not text:
            logger.warning("No text extracted, skipping summary.")
            continue
            
        logger.info("Generating summary...")
        summary = summarize_text(text)
        
        if summary:
            item["summary"] = summary
            updated_count += 1
            
            # Save incrementally
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2)
            logger.info("Saved summary.")
        
        logger.info("Sleeping to cool down...")
        time.sleep(2) 

    logger.info(f"Done. Updated {updated_count} summaries.")

if __name__ == "__main__":
    main()
