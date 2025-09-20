#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
import json

def fetch_planning_commission_agendas():
    """Fetch latest Planning Commission agenda PDFs from Jacksonville website"""

    base_url = "https://www.jacksonville.gov"
    pc_url = f"{base_url}/departments/planning-and-development/planning-commission.aspx"

    print(f"🌐 Fetching agenda list from: {pc_url}")

    try:
        # Get the main Planning Commission page
        response = requests.get(pc_url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for PDF links (adjust selectors based on actual site structure)
        pdf_links = []

        # Common patterns for Planning Commission agenda PDFs
        agenda_patterns = [
            r'pc.*agenda.*\.pdf',
            r'planning.*commission.*agenda.*\.pdf',
            r'agenda.*\d{2}-\d{2}-\d{2,4}.*\.pdf'
        ]

        # Find all links that might be PDF agendas
        all_links = soup.find_all('a', href=True)

        for link in all_links:
            href = link['href']
            link_text = link.get_text().lower()

            # Check if this looks like a Planning Commission agenda
            for pattern in agenda_patterns:
                if re.search(pattern, href.lower()) or re.search(pattern, link_text):
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = base_url + href
                    elif not href.startswith('http'):
                        href = base_url + '/' + href

                    pdf_info = {
                        'url': href,
                        'text': link.get_text().strip(),
                        'found_date': datetime.now().isoformat()
                    }

                    # Try to extract date from link text or URL
                    date_match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', href + ' ' + link_text)
                    if date_match:
                        pdf_info['date_string'] = date_match.group(1)

                    pdf_links.append(pdf_info)
                    break

        print(f"📄 Found {len(pdf_links)} potential agenda PDFs")

        # Download recent PDFs (last 30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        downloaded = []

        for pdf_info in pdf_links:
            try:
                # Generate filename
                url_parts = pdf_info['url'].split('/')
                filename = url_parts[-1] if url_parts[-1].endswith('.pdf') else f"agenda-{datetime.now().strftime('%Y%m%d')}.pdf"

                # Clean filename
                filename = re.sub(r'[^\w\-.]', '-', filename)
                filepath = Path('data/pdfs') / filename

                # Create directory if it doesn't exist
                filepath.parent.mkdir(parents=True, exist_ok=True)

                # Check if we already have this file
                if filepath.exists():
                    print(f"⏭️  Skipping existing file: {filename}")
                    continue

                # Download PDF
                print(f"⬇️  Downloading: {filename}")
                pdf_response = requests.get(pdf_info['url'], timeout=60)
                pdf_response.raise_for_status()

                # Verify it's actually a PDF
                if not pdf_response.content.startswith(b'%PDF'):
                    print(f"⚠️  Warning: {filename} doesn't appear to be a valid PDF")
                    continue

                # Save PDF
                with open(filepath, 'wb') as f:
                    f.write(pdf_response.content)

                pdf_info['local_file'] = str(filepath)
                pdf_info['file_size'] = len(pdf_response.content)
                downloaded.append(pdf_info)

                print(f"✅ Downloaded: {filename} ({len(pdf_response.content)} bytes)")

            except Exception as e:
                print(f"❌ Error downloading {pdf_info['url']}: {e}")
                continue

        # Save metadata about downloaded files
        metadata = {
            'last_check': datetime.now().isoformat(),
            'total_found': len(pdf_links),
            'downloaded': downloaded,
            'all_links': pdf_links
        }

        metadata_file = Path('data/fetch_metadata.json')
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"📊 Downloaded {len(downloaded)} new agendas")
        print(f"💾 Metadata saved to: {metadata_file}")

        return downloaded

    except Exception as e:
        print(f"❌ Error fetching agendas: {e}")
        return []

if __name__ == "__main__":
    downloaded = fetch_planning_commission_agendas()

    if downloaded:
        print(f"\n🎉 Successfully downloaded {len(downloaded)} new agenda PDFs")
        for pdf_info in downloaded:
            print(f"  • {pdf_info['local_file']}")
    else:
        print("\n📭 No new agendas found or downloaded")