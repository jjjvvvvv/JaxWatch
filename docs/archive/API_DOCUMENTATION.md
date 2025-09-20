# JaxWatch API Documentation

## Overview

JaxWatch provides a comprehensive API for accessing municipal project data across Jacksonville. The system collects data from multiple sources and presents it through a unified REST-like interface.

## Data Sources

| Source | Status | Data Types | Update Frequency |
|--------|---------|------------|------------------|
| Planning Commission | ✅ Active | Zoning, Variances, Land Use | Weekly |
| City Council | ✅ Ready | Public Projects, Infrastructure | Weekly (configurable) |
| Development Services | 📋 Planned | Permits, Private Development | TBD |
| Public Works | 📋 Planned | Infrastructure Projects | TBD |

## Endpoints

### Primary Data Endpoint

**GET** `/all-projects.json`

Returns all projects across all data sources in unified format.

**Response Format:**
```json
{
  "last_updated": "2025-09-18T17:16:28.746951",
  "total_projects": 16,
  "schema_version": "2.0",
  "sources": ["planning_commission"],
  "projects": [
    {
      "slug": "project-identifier",
      "project_id": "V-25-06",
      "title": "Project Title",
      "project_type": "zoning|private_dev|public_project|infrastructure",
      "decision_stage": "approved|denied|deferred|review",
      "authority_level": "planning|council|staff",
      "data_source": "planning_commission|city_council",
      "meeting_date": "Thursday, June 5, 2025",
      "location": "7051 Ramoth Drive",
      "council_district": "2",
      "geographic_scope": "parcel|neighborhood|district|citywide",
      "financial_data": {
        "estimated_value": 100000,
        "budget_allocated": null,
        "funding_source": "general_fund"
      },
      "related_projects": [
        {
          "project_id": "related-id",
          "relationship_type": "same_location|sequential|prerequisite",
          "description": "Relationship description"
        }
      ],
      "tags": ["variance", "residential"],
      "latitude": 30.3322,
      "longitude": -81.6557
    }
  ]
}
```

### Legacy Endpoints

**GET** `/summary.json` - Lightweight summary with recent projects
**GET** `/extracted-*.json` - Legacy format files (deprecated)

## Data Schema

### Project Types

- **`zoning`** - Zoning changes, variances, administrative deviations
- **`private_dev`** - Private development projects, subdivisions, site plans
- **`public_project`** - City-funded projects, public facilities
- **`infrastructure`** - Roads, utilities, transportation projects

### Decision Stages

- **`proposal`** - Initial application/proposal stage
- **`review`** - Under staff or board review
- **`hearing`** - Scheduled for public hearing
- **`approved`** - Approved by decision-making body
- **`denied`** - Denied by decision-making body
- **`deferred`** - Deferred to future meeting
- **`construction`** - Under construction
- **`completed`** - Project completed

### Authority Levels

- **`staff`** - Administrative/staff-level decision
- **`planning`** - Planning Commission authority
- **`council`** - City Council authority
- **`board`** - Other board/commission authority

### Geographic Scope

- **`parcel`** - Single property/parcel
- **`block`** - City block level
- **`neighborhood`** - Neighborhood impact
- **`district`** - Council district wide
- **`citywide`** - City-wide impact
- **`regional`** - Multi-jurisdictional

## Cross-References

The system automatically identifies related projects based on:

- **Same Location** - Projects at identical addresses
- **Geographic Proximity** - Projects within close geographic proximity
- **Sequential** - Related project sequences (phases, companion items)
- **Prerequisite** - Projects that depend on others
- **Related** - General relationship between projects

## Query Capabilities

While the API currently provides full dataset access, the frontend supports:

- **Search** - Full-text search across project titles, locations, descriptions
- **Filtering** - By project type, decision stage, council district, authority level
- **Sorting** - By meeting date, project type, location
- **Geographic** - Map-based visualization when coordinates available

## Data Freshness

- **Planning Commission**: Updated weekly after meetings (Thursdays)
- **Real-time Status**: Check `last_updated` timestamp in response
- **Update Frequency**: Configurable per data source
- **Historical Data**: Maintains historical decisions and status changes

## Rate Limiting

Currently no rate limiting implemented. The static JSON files can be accessed directly.

## Error Handling

Standard HTTP status codes:

- **200** - Success
- **404** - File not found
- **500** - Server error during data processing

## Data Quality

### Validation
- All projects validated against unified schema
- Automatic data type conversion and normalization
- Cross-reference validation between related projects

### Coverage
- **Planning Commission**: 90%+ meeting coverage since 2024
- **Historical Data**: Archives available back to 2019 (via legacy system)
- **Geocoding**: Automatic address geocoding when location provided

## Integration Examples

### JavaScript
```javascript
fetch('/all-projects.json')
  .then(response => response.json())
  .then(data => {
    console.log(`${data.total_projects} projects from ${data.sources.length} sources`);
    // Process projects
    data.projects.forEach(project => {
      console.log(`${project.project_id}: ${project.title}`);
    });
  });
```

### Python
```python
import requests

response = requests.get('http://localhost:8000/all-projects.json')
data = response.json()

# Filter by project type
zoning_projects = [p for p in data['projects'] if p['project_type'] == 'zoning']
print(f"Found {len(zoning_projects)} zoning projects")

# Find projects in specific district
district_7 = [p for p in data['projects'] if p['council_district'] == '7']
```

### Command Line
```bash
# Get total project count
curl -s http://localhost:8000/all-projects.json | jq '.total_projects'

# List all project types
curl -s http://localhost:8000/all-projects.json | jq -r '.projects[].project_type' | sort | uniq

# Find projects with related items
curl -s http://localhost:8000/all-projects.json | jq '.projects[] | select(.related_projects | length > 0)'
```

## Schema Evolution

### Version History
- **v1.0** - Legacy Planning Commission format
- **v2.0** - Unified schema across all data sources (current)

### Migration
- Automatic migration from v1 to v2 format
- Backward compatibility maintained
- Legacy fields preserved where possible

### Future Versions
- v2.1: Enhanced financial tracking
- v2.2: Approval workflow modeling
- v3.0: Real-time updates and webhooks

## Observatory Commands

For data collection and processing:

```bash
# Update all data sources
make observatory

# Test data pipeline
make observatory-test

# Check system status
make observatory-status

# Update specific source
make observatory-update-planning
```

## Support

- **Documentation**: See README.md for setup and usage
- **Issues**: Report problems via project issue tracker
- **Development**: See DEVELOPMENT_ROADMAP.md for implementation status

---

*Last updated: September 18, 2024*
*Schema version: 2.0*