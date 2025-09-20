# Firestore Deployment Configuration

This document outlines how to set up Google Cloud Firestore for JaxWatch municipal data storage.

## Prerequisites

1. Google Cloud account with billing enabled
2. Firebase CLI installed (`npm install -g firebase-tools`)
3. Service account for GitHub Actions

## Setup Steps

### 1. Create Firebase Project

```bash
# Login to Firebase
firebase login

# Initialize project (run from repository root)
firebase init

# Select:
# - Firestore (configure rules and indexes)
# - Hosting (optional, for frontend deployment)

# Choose existing project or create new one
# Project ID should be: jaxwatch-municipal or similar
```

### 2. Deploy Firestore Rules and Indexes

```bash
# Deploy Firestore configuration
firebase deploy --only firestore

# Deploy hosting (optional)
firebase deploy --only hosting
```

### 3. Create Service Account for GitHub Actions

```bash
# Create service account
gcloud iam service-accounts create jaxwatch-github-actions \
    --description="Service account for JaxWatch GitHub Actions" \
    --display-name="JaxWatch GitHub Actions"

# Grant Firestore permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:jaxwatch-github-actions@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

# Create and download key
gcloud iam service-accounts keys create ~/jaxwatch-service-account.json \
    --iam-account=jaxwatch-github-actions@PROJECT_ID.iam.gserviceaccount.com
```

### 4. Configure GitHub Secrets

Add these secrets to your GitHub repository:

- `GOOGLE_CLOUD_PROJECT`: Your Firebase project ID
- `GOOGLE_APPLICATION_CREDENTIALS_JSON`: Contents of the service account JSON file
- `FIREBASE_TOKEN`: Firebase CLI token (get with `firebase login:ci`)

### 5. Environment Variables

Set these environment variables:

```bash
# For local development
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# For production (GitHub Actions)
export GOOGLE_CLOUD_PROJECT="${{ secrets.GOOGLE_CLOUD_PROJECT }}"
# Service account credentials are set up via JSON in GitHub Actions
```

## Firestore Data Structure

### Collection: `municipal_items`

Each document represents a municipal agenda item with this structure:

```json
{
  "board": "Planning Commission",
  "date": "2025-09-20",
  "title": "Zoning application review",
  "url": "https://example.com/agenda.pdf",
  "notes": ["Public hearing required", "Traffic study needed"],
  "item_number": "PC-2025-123",
  "parcel_address": "123 Main Street, Jacksonville, FL",
  "parcel_lat": 30.3322,
  "parcel_lon": -81.6557,
  "council_district": "7",
  "status": "Under Review",
  "flagged": false,
  "source_id": "planning_commission",
  "extracted_at": "2025-09-20T10:30:00Z",
  "written_to_firestore_at": "2025-09-20T10:30:05Z",
  "document_id": "planning_commission_2025-09-20_PC-2025-123"
}
```

### Indexes

The following composite indexes are configured:

1. `source_id` (ASC) + `date` (DESC) - for querying by data source
2. `board` (ASC) + `date` (DESC) - for querying by municipal board
3. `flagged` (ASC) + `date` (DESC) - for finding flagged items
4. `council_district` (ASC) + `date` (DESC) - for district-specific queries

## Security Rules

- **Public read access**: Anyone can read municipal data (transparency)
- **Restricted write access**: Only authenticated service accounts can write
- **Admin writes**: GitHub Actions uses service account with admin privileges

## Local Development

For local development without Firestore:

1. Data automatically falls back to local JSON files in `data/outputs/`
2. No authentication required for local storage
3. Frontend can read from both sources

## Monitoring and Costs

- Monitor Firestore usage in Google Cloud Console
- Set up billing alerts
- Municipal data typically generates low costs (< $5/month for Jacksonville scale)
- Consider Firestore emulator for development

## Backup Strategy

1. GitHub Actions automatically commits data to repository
2. Firestore provides automatic backups
3. Export functionality available via `gcloud firestore export`

## Troubleshooting

### Authentication Issues

```bash
# Check service account permissions
gcloud auth list
gcloud projects get-iam-policy PROJECT_ID

# Test Firestore access
python -c "
from google.cloud import firestore
db = firestore.Client()
print('Firestore connection successful')
"
```

### GitHub Actions Issues

1. Verify `GOOGLE_APPLICATION_CREDENTIALS_JSON` secret is valid JSON
2. Check service account has required permissions
3. Ensure project ID matches in all configurations

### Local Development Issues

1. Verify `GOOGLE_APPLICATION_CREDENTIALS` points to valid file
2. Check `GOOGLE_CLOUD_PROJECT` environment variable
3. Confirm service account key has not expired