# JaxWatch Enhanced System User Guide

## 🎯 What This New System Does For You

### **The Problem We Solved**
You were concerned about:
- Jacksonville departments publishing PDFs irregularly
- How to automatically collect data when schedules are unpredictable
- Ensuring data quality and catching extraction errors
- Handling document amendments and corrections

### **What You Now Have**
A **complete automation and quality control system** that:

1. **Automatically checks for new documents** on different schedules for each department
2. **Handles irregular PDFs** through a manual upload interface when automatic checking misses things
3. **Detects and prevents duplicate processing** (saves time and keeps data clean)
4. **Tracks document versions** (original agendas vs. amended agendas)
5. **Automatically flags questionable extractions** for human review
6. **Provides admin tools** to fix extraction errors without touching code

## 📂 Getting Started

### **Directory Location**
Always run commands from your main JaxWatch directory:
```bash
cd /Users/jjjvvvvv/Desktop/JaxWatch
```

### **Check What You Have**
First, let's see the current state:
```bash
make upload-dedup-stats
make upload-version-stats
make upload-correction-stats
```

## 🔄 Daily Operations

### **1. Check for New Documents Automatically**
The system can now poll Jacksonville websites automatically:
```bash
# Check current polling schedule
python3 -c "from municipal_observatory import MunicipalObservatory; obs = MunicipalObservatory(); status = obs.get_polling_status(); print('Polling sources:', list(status.get('sources', {}).keys())); [print(f'  {name}: next check {info.get(\"next_scheduled\", \"not scheduled\")}') for name, info in status.get('sources', {}).items()]"

# Force check all sources now
make observatory
```

### **2. Handle Irregular PDFs (Your Most Common Use Case)**
When a department uploads a PDF outside their normal schedule:

```bash
# Option A: Use the web interface (easiest)
make upload-web
# Then go to http://localhost:5001 in your browser
# Upload the PDF, fill in the form, click "Upload & Queue for Processing"

# Option B: Command line
# First, copy the PDF to a temp location and use Python:
python3 -c "
from manual_upload import ManualUploadManager
from pathlib import Path

manager = ManualUploadManager()

# Add the PDF to processing queue
metadata = {
    'department': 'planning_commission',  # or city_council, public_works, etc.
    'document_type': 'agenda',           # or minutes, report, amendment
    'meeting_date': '2024-10-15',        # YYYY-MM-DD format
    'notes': 'Special meeting agenda'
}

result = manager.add_to_queue(Path('/path/to/your/downloaded.pdf'), metadata)
print('Upload result:', result)
"

# Then process it
make upload-process
```

### **3. Check Processing Status**
```bash
# See what's in the queue
make upload-status

# See if anything needs human review
make upload-pending-reviews

# See recent corrections
make upload-correction-stats
```

## 🔧 Quality Control & Error Correction

### **When Documents Need Review**
The system automatically flags documents that might have extraction problems:

```bash
# Check what needs review
make upload-pending-reviews

# Start the admin interface to review and correct
make admin-web
# Go to http://localhost:5002 in your browser
```

### **Common Scenarios:**

**Scenario 1: PDF was scanned (image) instead of text**
- System will use OCR but flag for review
- You'll see it in pending reviews
- Use admin interface to verify the extracted projects are correct

**Scenario 2: Missing project in extraction**
- Open admin interface
- Find the document in pending reviews
- Click "Add Missing Project"
- Fill in the project details manually

**Scenario 3: Incorrect project details**
- Open admin interface
- Find the project that needs correction
- Click "Correct" next to the project
- Fix the specific field (location, title, etc.)

## 📋 Understanding Your Data

### **Document Versions**
The system now tracks when Jacksonville publishes amended agendas:

```bash
# See version history
make upload-version-stats

# Get details about a specific version
python3 -c "
from manual_upload import ManualUploadManager
manager = ManualUploadManager()
# Replace 'version_id' with actual ID from version stats
history = manager.get_document_history('your_version_id_here')
for version in history:
    print(f'Version: {version[\"metadata\"][\"version_number\"]} ({version[\"metadata\"][\"version_type\"]})')
    print(f'Date: {version[\"metadata\"][\"created_at\"]}')
    print(f'Changes: {version[\"metadata\"][\"changes_summary\"]}')
    print()
"
```

### **Deduplication Protection**
Prevents you from accidentally processing the same document twice:

```bash
# See what's already been processed
make upload-dedup-stats

# The system will automatically reject duplicates and tell you why
```

## 🌐 Web Interfaces

### **Upload Interface** (for irregular PDFs)
```bash
make upload-web
```
- Go to http://localhost:5001
- Upload PDFs with proper metadata
- Monitor processing queue
- See status of all uploads

### **Admin Interface** (for corrections)
```bash
make admin-web
```
- Go to http://localhost:5002
- Review flagged documents
- Make corrections to extraction errors
- Verify corrections before they're applied

### **Health Dashboard** (for system monitoring)
```bash
make health-web
```
- Go to http://localhost:5003
- Monitor source health and success rates
- View response times and failure patterns
- Get recommendations for system improvements

## 📊 Monitoring & Maintenance

### **Daily Checks**
```bash
# Quick status of all systems
echo "=== JaxWatch System Status ==="
make health-status
echo ""
make upload-status
echo ""
make upload-pending-reviews
echo ""
make upload-correction-stats
```

### **Weekly Maintenance**
```bash
# Check deduplication database
make upload-dedup-stats

# Review version tracking
make upload-version-stats

# Clean up old temporary files
make clean-enhanced
```

## 🔍 Troubleshooting

### **"Nothing happens when I run make observatory"**
The polling system may not find new documents. This is normal if:
- No new documents have been published
- Documents are found but are duplicates of ones already processed

### **"PDF upload failed - duplicate detected"**
This means you've already processed this exact file. Check:
```bash
make upload-dedup-stats
```
If it's a legitimate new version (amended agenda), the system should detect it as "potential_amendment" and allow it.

### **"Processing failed"**
Check what went wrong:
```bash
make upload-status
# Look for items with "failed" status
```

Most failures are due to:
- Corrupted PDF files
- PDFs that are entirely images with no text
- Very large files (>50MB)

### **"No projects extracted from agenda"**
This gets automatically flagged for review:
```bash
make upload-pending-reviews
make admin-web  # Then review and add missing projects manually
```

## 🎯 Practical Examples

### **Example 1: Planning Commission publishes special agenda**
```bash
# Download the PDF to your desktop, then:
cd /Users/jjjvvvvv/Desktop/JaxWatch
make upload-web
# Upload via web interface with metadata:
# - Department: planning_commission
# - Type: agenda
# - Date: meeting date
# - Notes: "Special meeting for rezoning applications"
```

### **Example 2: City Council amends an agenda**
```bash
# The system will detect this as a potential amendment
# Upload the amended agenda - it won't be rejected as duplicate
# Check version tracking to see the relationship:
make upload-version-stats
```

### **Example 3: You notice extraction missed a project**
```bash
make admin-web
# Go to http://localhost:5002
# Find the document in pending reviews
# Click "Add Missing Project"
# Fill in: Project ID, Title, Location, Type, etc.
# Click "Verify" to confirm the correction
```

## 📈 What This Means for Your Website

### **Improved Data Quality**
- **Fewer missed projects** (automatic flagging catches problems)
- **Cleaner data** (deduplication prevents duplicates)
- **Version control** (track when agendas get amended)
- **Audit trail** (see exactly what corrections were made)

### **Consistent Updates**
- **Automatic checking** means you don't have to manually monitor websites
- **Manual upload** handles irregular publications
- **Quality control** ensures bad extractions get human review

### **Future Growth**
- **Easy to add new departments** (just configure their polling schedule)
- **Handles different document formats** (OCR for scanned PDFs)
- **Scales up** as Jacksonville publishes more documents

## 🚀 Next Steps

1. **Try the upload interface**: `make upload-web` and upload a PDF
2. **Check the admin interface**: `make admin-web` and explore the correction tools
3. **Set up a daily routine**: Check `make upload-pending-reviews` each day
4. **Configure automatic polling**: Once you're comfortable, set up scheduled runs of `make observatory`

The enhanced system gives you **reliability, quality control, and scalability** - exactly what you need for consistent civic data collection in Jacksonville's unpredictable publishing environment.