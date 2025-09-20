# JaxWatch Quick Reference

## 📍 Always start here:
```bash
cd /Users/jjjvvvvv/Desktop/JaxWatch
```

## 🔄 Most Common Tasks

### Upload irregular PDF (90% of your use cases)
```bash
make upload-web
```
→ Go to http://localhost:5001, upload PDF with metadata

### Check what needs attention
```bash
make upload-pending-reviews
```

### Fix extraction errors
```bash
make admin-web
```
→ Go to http://localhost:5002, review and correct

### See current status
```bash
make upload-status
make upload-correction-stats
```

### Automatic check for new documents
```bash
make observatory
```

## 🆘 Quick Fixes

### "Duplicate detected" but it's a new version
- This is normal for amended documents
- System should allow "potential amendments"
- If blocked, check: `make upload-dedup-stats`

### "No projects found"
- Automatically flagged for review
- Run: `make admin-web`
- Manually add missing projects

### Processing failed
- Check: `make upload-status`
- Look for "failed" items
- Usually means PDF is corrupted or image-only

### Website data seems old
- Your website shows `all-projects.json`
- New system processes to same file
- Check: `ls -la all-projects.json` for recent timestamp

## 📊 Status Commands
```bash
make upload-dedup-stats      # What's been processed
make upload-version-stats    # Document versions
make upload-correction-stats # Error corrections
make upload-pending-reviews  # Needs human review
```

## 🏥 Health Monitoring

### Check system health
```bash
make health-status
```

### View detailed source health
```bash
make health-source SOURCE=planning_commission
```

### Start health dashboard
```bash
make health-web
```
→ Go to http://localhost:5003

### Export health report
```bash
make health-report
```

## 🌐 Web Interfaces
- **Upload**: `make upload-web` → http://localhost:5001
- **Admin**: `make admin-web` → http://localhost:5002
- **Health**: `make health-web` → http://localhost:5003
- **Main site**: `make serve` → http://localhost:8000