#!/usr/bin/env python3

import requests
from pathlib import Path
import re
from bs4 import BeautifulSoup

def fetch_planning_commission_documents():
    """Fetch actual Planning Commission documents from the URLs found in search"""

    # URLs I actually found in my search results
    document_urls = [
        # Results agenda from August 2025 (most recent)
        "https://www.jacksonville.gov/departments/planning-and-development/docs/current-planning-division/planning-commission-docs/pc-results-agenda-08-21-25.aspx",

        # Planning Commission main page with document links
        "https://www.jacksonville.gov/departments/planning-and-development/planning-commission.aspx",

        # Planning Commission meetings online page
        "https://www.jacksonville.gov/departments/planning-and-development/current-planning-division/planning-commission-meetings-online"
    ]

    print("🌐 Fetching actual Planning Commission documents from search results...")

    for url in document_urls:
        try:
            print(f"\n📄 Fetching: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse the page content
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for PDF links or agenda references
            pdf_links = []

            # Find all links that might be PDFs or documents
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().strip()

                # Check if this looks like a document we want
                if any(keyword in text.lower() for keyword in ['agenda', 'results', 'meeting', 'planning commission', 'pc ']):
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = "https://www.jacksonville.gov" + href

                    pdf_links.append({
                        'url': href,
                        'text': text,
                        'source_page': url
                    })

            print(f"  Found {len(pdf_links)} document links:")
            for link in pdf_links[:10]:  # Show first 10
                print(f"    • {link['text']}: {link['url']}")

            if len(pdf_links) > 10:
                print(f"    ... and {len(pdf_links) - 10} more")

        except Exception as e:
            print(f"  ❌ Error fetching {url}: {e}")

    # Also try the specific staff reports link I found
    staff_reports_url = "https://filedrop.coj.net/?ShareToken=6D5E7EF5F2C8F84865FAF215AA85367C2143B061"
    print(f"\n📊 Checking staff reports file drop: {staff_reports_url}")

    try:
        response = requests.get(staff_reports_url, timeout=30)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"  Content-Length: {len(response.content)} bytes")
    except Exception as e:
        print(f"  ❌ Error accessing staff reports: {e}")

def download_results_agenda():
    """Try to download the results agenda I found"""

    # The specific results agenda URL from my search
    url = "https://www.jacksonville.gov/departments/planning-and-development/docs/current-planning-division/planning-commission-docs/pc-results-agenda-08-21-25.aspx"

    print(f"⬇️  Attempting to download results agenda...")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Parse to see if this is a document or a page with links
        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for actual PDF download links
        pdf_links = soup.find_all('a', href=lambda x: x and '.pdf' in x.lower())

        if pdf_links:
            print(f"  Found {len(pdf_links)} PDF links:")
            for link in pdf_links:
                pdf_url = link['href']
                if pdf_url.startswith('/'):
                    pdf_url = "https://www.jacksonville.gov" + pdf_url

                print(f"    📄 {link.get_text().strip()}: {pdf_url}")

                # Try to download the first PDF
                try:
                    pdf_response = requests.get(pdf_url, timeout=60)
                    pdf_response.raise_for_status()

                    if pdf_response.content.startswith(b'%PDF'):
                        filename = f"pc-results-agenda-08-21-25.pdf"
                        with open(filename, 'wb') as f:
                            f.write(pdf_response.content)

                        print(f"    ✅ Downloaded: {filename} ({len(pdf_response.content)} bytes)")
                        return filename
                    else:
                        print(f"    ⚠️  Not a valid PDF")

                except Exception as e:
                    print(f"    ❌ Error downloading PDF: {e}")
        else:
            print("  No direct PDF links found on page")

            # Check if the page itself contains document content
            content_length = len(response.content)
            content_type = response.headers.get('Content-Type', '')

            print(f"  Page info: {content_type}, {content_length} bytes")

            # Look for any downloadable content or attachment links
            attachments = soup.find_all('a', href=lambda x: x and 'attachment' in x.lower())
            if attachments:
                print(f"  Found {len(attachments)} attachment links:")
                for att in attachments[:5]:
                    print(f"    📎 {att.get_text().strip()}: {att['href']}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    return None

if __name__ == "__main__":
    # Fetch document links from the pages I found
    fetch_planning_commission_documents()

    # Try to download the specific results agenda
    downloaded_file = download_results_agenda()

    if downloaded_file:
        print(f"\n🎉 Successfully downloaded: {downloaded_file}")
        print("Now run: python3 extract_projects_robust.py {downloaded_file}")
    else:
        print("\n📋 No documents downloaded, but found URLs for manual investigation")
        print("Check the document links above for manual download opportunities")