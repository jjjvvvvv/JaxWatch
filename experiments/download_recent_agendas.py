#!/usr/bin/env python3

import requests
from pathlib import Path
import re

def download_recent_agendas():
    """Download recent Planning Commission agendas from Jacksonville"""

    # URLs found from search - October 2024 through January 2025
    agenda_urls = [
        "https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/10-17-24-agenda.pdf.aspx?lang=en-US",
        "https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/11-07-24-agenda.pdf.aspx?lang=en-US",
        "https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/11-21-24-agenda.pdf.aspx?lang=en-US",
        "https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/12-05-24-agenda.pdf.aspx?lang=en-US",
        "https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/12-19-24-agenda.pdf.aspx?lang=en-US",
        "https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/01-02-25-agenda.pdf.aspx?lang=en-US",
        "https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/01-16-25-agenda.pdf.aspx?lang=en-US"
    ]

    downloaded = []

    for url in agenda_urls:
        try:
            # Extract date from URL for filename
            date_match = re.search(r'(\d{2}-\d{2}-\d{2,4})-agenda', url)
            if date_match:
                date_str = date_match.group(1)
                filename = f"pc-agenda-{date_str}.pdf"
            else:
                filename = f"pc-agenda-{len(downloaded)}.pdf"

            filepath = Path(filename)

            # Skip if already exists
            if filepath.exists():
                print(f"⏭️  Skipping existing: {filename}")
                continue

            print(f"⬇️  Downloading: {filename}")

            # Download PDF
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            # Verify it's a PDF
            if not response.content.startswith(b'%PDF'):
                print(f"⚠️  Warning: {filename} doesn't appear to be a valid PDF")
                continue

            # Save file
            with open(filepath, 'wb') as f:
                f.write(response.content)

            print(f"✅ Downloaded: {filename} ({len(response.content)} bytes)")
            downloaded.append(filename)

        except Exception as e:
            print(f"❌ Error downloading {url}: {e}")
            continue

    print(f"\n📊 Downloaded {len(downloaded)} new agenda PDFs")
    return downloaded

if __name__ == "__main__":
    downloaded = download_recent_agendas()
    for pdf in downloaded:
        print(f"  • {pdf}")