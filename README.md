# JaxWatch

A civic data observatory for Jacksonville, FL government transparency. JaxWatch scrapes government meetings, extracts civic project data, and presents it through prioritized interfaces to help citizens track major developments.

## Overview

JaxWatch operates as a "collection-first MVP" that distinguishes major civic projects from administrative noise using a dual scoring system. It processes documents from DIA Board, DDRB, City Council, and Planning Commission meetings to identify and track development projects across Jacksonville.

## Key Features

### **Dual Scoring System**
- **Confidence Scoring** (0-100): How certain we are this is a real project
- **Importance Scoring** (0-100): How significant the project is to the city

### **Data Sources**
- DIA Board resolutions and meetings
- Downtown Development Review Board (DDRB)
- City Council meetings
- Planning Commission activities

### **Web Interface**
- Admin dashboard with sortable project listings
- Project detail pages with source documents
- Importance-based filtering and search

## Architecture

```
Government Websites → Document Scraping → Project Extraction → Scoring → Web Interface
```

### **Scoring Methodology**

**Confidence Signals (How sure are we this is real?):**
- Document mentions (0-25 points)
- Time span and recency (0-15 points)
- Board diversity (0-20 points)
- Project language (0-15 points)
- Identity consistency (0-25 points)

**Importance Signals (How significant is this?):**
- Financial mentions (0-50 points, 50% weight)
- Project scale indicators (0-25 points, 25% weight)
- Timeline duration (0-15 points, 15% weight)
- Board escalation level (0-15 points, 15% weight)
- Public investment (0-20 points, 20% weight)

## Quick Start

### **Setup**
```bash
# Install dependencies
pip install -r requirements.txt

# Create directory structure
mkdir -p outputs/projects outputs/raw outputs/files
```

### **Data Collection**
```bash
# Collect meeting documents
python -m backend.collector.engine --source dia_board --year 2024

# Extract projects from documents
python -m backend.tools.extract_projects

# Score projects by importance
python -m backend.tools.project_scoring
```

### **Web Interface**
```bash
# Start admin interface
cd admin_ui && python -m http.server 8080

# View at http://localhost:8080/admin.html
```

## Project Examples

**High Importance (60+)**
- Pearl Square / Gateway Jax: Mixed-use riverfront development
- LaVilla Redevelopment: Historic district revitalization
- Shipyards Project: Major waterfront development

**Medium Importance (30-59)**
- Facade improvement grants
- Property dispositions
- Development incentive packages

**Low Importance (<30)**
- Sign installations
- Permit renewals
- Administrative updates

## File Structure

```
backend/
├── collector/           # Document scraping and collection
├── tools/              # Project extraction and scoring
admin_ui/               # Web interface
├── admin.html         # Main dashboard
├── admin.js           # Sorting and filtering logic
├── styles_extras.css  # Importance badge styling
outputs/
├── projects/          # Extracted and scored project data
├── raw/              # Raw meeting documents
└── files/            # Downloaded PDFs and metadata
```

## Key Components

**`backend/tools/project_scoring.py`**: Core scoring system with confidence and importance algorithms

**`backend/tools/extract_projects.py`**: Enhanced project extraction with metadata intelligence for when PDF text isn't available

**`admin_ui/admin.js`**: Web interface with importance-based sorting and user-friendly explanations

## Development

The system successfully addresses the semantic challenge of distinguishing major civic projects from routine administrative items while maintaining transparency about scoring methodology.

**Example Success**: Pearl Square project scoring improved from 17 to 52 points after implementing metadata-based snippet extraction that captures financial arrangements from document URLs and titles.

## Data Pipeline

1. **Collection**: Scrape government websites for meeting documents
2. **Extraction**: Use regex patterns to identify project references
3. **Enhancement**: Extract meaningful snippets from documents and metadata
4. **Scoring**: Apply dual confidence/importance scoring
5. **Display**: Present prioritized results in web interface

This approach enables citizens to efficiently track significant developments without getting lost in routine administrative noise.