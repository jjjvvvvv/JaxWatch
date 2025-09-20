#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import our extraction module
sys.path.append(str(Path(__file__).parent.parent))
from extract_projects_robust import ProjectExtractor

def process_new_pdfs():
    """Process any new PDF files that haven't been extracted yet"""

    # Check for fetch metadata to find new PDFs
    metadata_file = Path('data/fetch_metadata.json')
    processed_file = Path('data/processed_pdfs.json')

    # Load metadata about downloaded PDFs
    if not metadata_file.exists():
        print("📭 No fetch metadata found - no new PDFs to process")
        return []

    with open(metadata_file, 'r') as f:
        fetch_data = json.load(f)

    # Load list of already processed PDFs
    processed_pdfs = set()
    if processed_file.exists():
        with open(processed_file, 'r') as f:
            processed_data = json.load(f)
            processed_pdfs = set(processed_data.get('processed_files', []))

    # Find PDFs that need processing
    downloaded_pdfs = fetch_data.get('downloaded', [])
    new_pdfs = [pdf for pdf in downloaded_pdfs if pdf.get('local_file') not in processed_pdfs]

    if not new_pdfs:
        print("📭 No new PDFs to process")
        return []

    print(f"🔄 Processing {len(new_pdfs)} new PDFs")

    all_results = []
    successfully_processed = []

    for pdf_info in new_pdfs:
        pdf_path = pdf_info['local_file']
        print(f"\n📄 Processing: {pdf_path}")

        try:
            # Extract projects using our robust extractor
            extractor = ProjectExtractor()
            result = extractor.extract_projects_from_pdf(pdf_path)

            if result:
                # Generate output filename based on the PDF name
                pdf_name = Path(pdf_path).stem
                output_file = Path('data/extracted') / f"{pdf_name}.json"
                output_file.parent.mkdir(parents=True, exist_ok=True)

                # Save extraction results
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)

                print(f"✅ Extracted {len(result['projects'])} projects to {output_file}")

                # Add file info for aggregation
                result['source_info'] = pdf_info
                result['output_file'] = str(output_file)
                all_results.append(result)

                successfully_processed.append(pdf_path)

            else:
                print(f"❌ Failed to extract data from {pdf_path}")

        except Exception as e:
            print(f"❌ Error processing {pdf_path}: {e}")

    # Update processed files list
    if successfully_processed:
        processed_data = {
            'last_updated': datetime.now().isoformat(),
            'processed_files': list(processed_pdfs.union(successfully_processed))
        }

        with open(processed_file, 'w') as f:
            json.dump(processed_data, f, indent=2)

        print(f"💾 Updated processed files list: {processed_file}")

    print(f"\n📊 Processing complete: {len(successfully_processed)}/{len(new_pdfs)} PDFs processed successfully")

    return all_results

if __name__ == "__main__":
    results = process_new_pdfs()

    if results:
        total_projects = sum(len(r['projects']) for r in results)
        print(f"\n🎉 Successfully processed {len(results)} PDFs with {total_projects} total projects")

        for result in results:
            meeting_date = result['meeting_info'].get('meeting_date', 'Unknown date')
            project_count = len(result['projects'])
            print(f"  • {meeting_date}: {project_count} projects")
    else:
        print("\n📭 No PDFs were processed")