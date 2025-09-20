# 🏗️ Civic Data MVP — Project Outline (Planning Commission Focus)

## 🎯 Goal

Automatically fetch, extract, and structure Jacksonville Planning Commission agenda data (starting from 2024) into usable, trackable, and extendable project records.

---

## ⚙️ Tech Stack

| Component         | Tool/Tech                          |
|------------------|------------------------------------|
| Scraper          | Python (`requests`, `BeautifulSoup`) |
| PDF Parser       | `pdfplumber`                       |
| Storage format   | Markdown w/ YAML frontmatter OR JSON |
| Backfill         | CLI or script                      |
| Fetch frequency  | Cron job, GitHub Actions, or manual run |
| Summarizer (opt) | Claude, OpenAI, or local LLM later |

---

## 📁 Project Structure

```bash
/civic-data/
├── /data/
│   ├── /projects/
│   │   ├── pud-2024-001-san-marco-townhomes.md
│   │   └── ...
│   └── /meetings/
│       ├── planning-2024-01-12.json
├── /scripts/
│   ├── fetch_agenda_list.py
│   ├── download_pdf.py
│   ├── parse_pdf.py
│   ├── extract_projects.py
│   └── generate_md.py
├── /utils/
│   └── slugify.py
```

---

## 📄 Project Data Structure (Markdown + YAML)

### `pud-2024-001-san-marco-townhomes.md`

```md
---
slug: pud-2024-001-san-marco-townhomes
project_id: PUD-2024-001
meeting_date: 2024-01-12
title: "San Marco Townhomes"
applicant: "San Marco Holdings, LLC"
location: "Atlantic Blvd & Kings Ave"
project_type: "PUD"
request: "32-unit townhome development with reduced setbacks"
status: "Scheduled for Planning Commission review"
ordinance_id: "ORD 2024-015"
district: "5"
source_pdf: "https://coj.net/.../PlanningCommissionAgenda_20240112.pdf"
tags: ["infill", "townhomes", "density"]
vote_history: []
timeline:
  submitted: 2023-12-01
  first_hearing: 2024-01-12
  last_updated: 2024-01-12
---
```

---

## 📊 Meeting-Level Structure (JSON)

### `planning-2024-01-12.json`

```json
{
  "meeting_date": "2024-01-12",
  "source_url": "https://coj.net/.../PlanningCommissionAgenda_20240112.pdf",
  "projects": [
    {
      "project_id": "PUD-2024-001",
      "title": "San Marco Townhomes",
      "slug": "pud-2024-001-san-marco-townhomes",
      "applicant": "San Marco Holdings, LLC",
      "location": "Atlantic Blvd & Kings Ave",
      "project_type": "PUD",
      "request": "32-unit townhome development with reduced setbacks"
    }
  ]
}
```

---

## ✅ MVP Script Flow

1. `fetch_agenda_list.py` – Scrape list of Planning Commission agenda PDFs
2. `download_pdf.py` – Download selected PDFs
3. `parse_pdf.py` – Use `pdfplumber` to extract and clean text
4. `extract_projects.py` – Use regex to find zoning cases (PUD, LUZ, VAR)
5. `generate_md.py` – Write each project as a Markdown file with YAML frontmatter

---

## 🔁 Optional Enhancements (Later)

- AI-generated summaries
- Council vote history
- Delay tracking (timeline analysis)
- Map overlays
- Full frontend in SvelteKit

---

## ✅ Summary: Claude’s Implementation Path

1. Scrape Planning Commission agendas (2024–present)
2. Download PDFs
3. Parse text using `pdfplumber`
4. Extract zoning projects (ID, title, applicant, location, summary)
5. Write `.md` files per project in `/data/projects/`
6. (Optional) Index vote data and timelines later