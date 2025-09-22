# 🏗️ Jacksonville Planning Commission Tracker

A comprehensive tool to track development projects and zoning applications from Jacksonville Planning Commission meetings.

## ✨ Features

### 🔍 **Interactive Project Browser**
- **Click any project card** to view detailed information in a modal
- **Search** by location, applicant, project type, or keywords
- **Filter** by project type, council district, and approval status
- **Source Links** - Direct access to original PDF documents

### 📊 **Real Data Integration**
- Extracts data from official Jacksonville Planning Commission agenda PDFs
- Includes project details: location, type, staff recommendation, owners, agents
- Tracks council/planning districts and project status
- Links to original source documents

### 📱 **Mobile-Responsive Design**
- Clean, modern interface that works on all devices
- Interactive modals for detailed project views
- Real-time statistics and filtering

## 🚀 Quick Start

### Option 1: Use Makefile (Recommended)
```bash
make setup && make install && make extract && make serve
```

### Option 2: Manual Setup
```bash
# Setup project structure
python3 scripts/setup.py

# Install dependencies
pip3 install -r requirements.txt

# Extract data from sample PDF
python3 extract_projects_robust.py

# Start development server
python3 -m http.server 8000
```

Then visit **http://localhost:8000** to view the tracker.

## 📂 Project Structure

```
/
├── index.html                    # Main web interface with modal support
├── styles.css                   # Responsive CSS with modal styles
├── app.js                       # JavaScript with project detail modals
├── extract_projects_robust.py   # Robust PDF extraction with error handling
├── all-projects.json            # Aggregated project data for website
├── sample-pc-agenda-10-03-24.pdf # Sample October 2024 agenda
├── scripts/
│   ├── setup.py                # Project initialization
│   ├── fetch_latest_agendas.py  # Download new agendas
│   ├── process_new_pdfs.py      # Process multiple PDFs
│   └── update_website_data.py   # Aggregate data for website
├── .github/workflows/
│   └── update-data.yml          # GitHub Actions automation
└── Makefile                     # Development commands
```

## 📄 Current Data

**October 3, 2024 Meeting** - 22 projects extracted including:
- **13 Land Use/Zoning** applications
- **3 Exceptions** for commercial/retail uses
- **3 Minor Modifications** to existing developments
- **2 Administrative Deviations**
- **1 Variance** for property setbacks

### 📋 Project Types Tracked
- **PUD** (Planned Unit Development) - Large residential/mixed-use developments
- **Exception** - Commercial use permissions in specific zones
- **Variance** - Property setback and dimensional modifications
- **Land Use/Zoning** - Comprehensive plan and zoning changes
- **Administrative Deviation** - Minor plan modifications
- **Minor Modification** - Changes to existing approved projects

## 🔗 Data Sources & Documentation

### **Source Documents**
All data comes from official Jacksonville Planning Commission meeting agendas:
- **October 3, 2024**: [View Original PDF](https://www.jacksonville.gov/getattachment/Departments/Planning-and-Development/Current-Planning-Division/Planning-Commission/10-03-24-agenda.pdf.aspx?lang=en-US)

*Click "Source Documents" in the interface to see all available meetings*

### **Official Planning Commission**
- **Website**: [Jacksonville Planning Commission](https://www.jacksonville.gov/departments/planning-and-development/planning-commission.aspx)
- **Meeting Schedule**: 2nd and 4th Thursdays at 1:00 PM
- **Location**: Edward Ball Building, 1st Floor Hearing Room 1002
- **Contact**: Planning Department (904) 255-7800

## 🤖 Automated Features

### **PDF Processing Pipeline**
1. **Robust Extraction**: Error handling, data validation, parsing warnings
2. **Data Quality Checks**: Validates extracted projects and identifies issues
3. **Source Tracking**: Maintains links to original PDF documents
4. **Metadata**: Extraction timestamps, processing results, warnings

### **Web Interface Enhancements**
- **Project Detail Modals**: Click any project for complete information
- **Source PDF Links**: Direct access to original documents
- **Data Documentation**: Built-in explanation of data sources and collection
- **Multi-meeting Support**: Designed to handle data from multiple meetings

## 📈 Adding New Data

### **Adding New PDFs**
1. Place PDF files in the project directory
2. Run: `python3 process_all_pdfs.py`
3. The system will automatically:
   - Extract projects from new PDFs
   - Update the aggregated data file
   - Maintain source PDF links

### **Automation Setup**
The project includes GitHub Actions for:
- Weekly agenda fetching
- Automatic PDF processing
- Website deployment

## 🛠️ Development Commands

```bash
# Setup and initialization
make setup          # Initialize project structure
make install         # Install Python dependencies

# Data processing
make extract         # Extract from sample PDF
make fetch           # Download latest agendas (when URLs available)
make process         # Process any new PDFs
make update          # Update aggregated website data
make pipeline        # Run full update pipeline

# Development
make serve           # Start local development server
make clean           # Clean up generated files
make fresh           # Fresh setup from scratch
```

## 🔍 Technical Details

### **PDF Extraction**
- Uses `pdfplumber` for reliable text extraction
- Multiple regex patterns to handle format variations
- Comprehensive error handling and validation
- Generates structured JSON output with metadata

### **Data Format**
Each project includes 15+ fields:
- **Identification**: Project ID, type, slug
- **Location**: Address, council/planning districts
- **Process**: Meeting date, staff recommendation, status
- **Parties**: Property owners, agents/representatives
- **Details**: Request description, tags, source PDF link

### **Web Technology**
- **Frontend**: HTML5, CSS3, JavaScript + jQuery
- **Responsive**: Mobile-first design with CSS Grid/Flexbox
- **Interactive**: Modal overlays, real-time filtering, search
- **Deployment**: Static hosting ready (GitHub Pages, Netlify, etc.)

## 🎯 Next Steps

1. **Expand Data Coverage**: Add more 2024/2025 Planning Commission meetings
2. **Historical Data**: Backfill with older meetings if archives are available
3. **Enhanced Features**: Map integration, timeline analysis, vote tracking
4. **Automation**: Fully automated agenda fetching and processing

---

*This tracker contains real data extracted from Jacksonville Planning Commission meetings. All information comes directly from official city documents.*
 
## 🚀 Deployment

This project auto-deploys to Vercel via GitHub Actions.

- Daily Run (6am ET): Executes the municipal observatory, aggregates data, commits `frontend/municipal-data.json`, and deploys to Vercel.
- Manual Runs: You can trigger both `Daily Observatory Run` and `Update Data` workflows from the Actions tab.

### Vercel Authentication
To enable deploys:
1. Generate a Vercel Personal Token: https://vercel.com/account/tokens
2. Add it as a GitHub Actions secret: `VERCEL_TOKEN`.
3. On the next run, GitHub Actions will build and deploy to your Vercel project.

If no token is set, workflows will skip deploy and log:

⚠️  Skipping Vercel deploy — VERCEL_TOKEN not configured.
# Test
