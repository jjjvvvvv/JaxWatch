#!/usr/bin/env python3

import pdfplumber

def extract_pdf_text(pdf_path):
    """Extract text from PDF file and print for analysis"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"PDF has {len(pdf.pages)} pages")
            print("\n" + "="*50)
            print("EXTRACTING TEXT FROM ALL PAGES:")
            print("="*50)

            all_text = ""
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    print(f"\n--- PAGE {i+1} ---")
                    print(page_text)
                    all_text += page_text + "\n"
                else:
                    print(f"\n--- PAGE {i+1} --- (No extractable text)")

            return all_text
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return None

if __name__ == "__main__":
    pdf_file = "sample-pc-agenda-10-03-24.pdf"
    text = extract_pdf_text(pdf_file)

    if text:
        print("\n" + "="*50)
        print("LOOKING FOR PROJECT PATTERNS:")
        print("="*50)

        # Look for common patterns that might indicate zoning projects
        patterns_to_find = [
            "PUD", "LUZ", "VAR", "Variance", "Ordinance",
            "Application", "Applicant", "Project", "Zoning"
        ]

        for pattern in patterns_to_find:
            if pattern.lower() in text.lower():
                print(f"Found pattern: {pattern}")