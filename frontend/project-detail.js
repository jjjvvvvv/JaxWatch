$(document).ready(function() {
    let projectData = null;
    let detailMap = null;

    // Get project ID from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('id');

    if (!projectId) {
        showNotFound();
        return;
    }

    // Load project data
    loadProjectData(projectId);

    function loadProjectData(projectId) {
        $.getJSON('municipal-data.json')
            .done(function(data) {
                let projects = Array.isArray(data) ? data : (data.projects || []);

                // Convert municipal data format to frontend format
                projects = projects.map(item => ({
                    ...item,
                    project_id: item.item_number || `${item.board}-${item.date}`,
                    meeting_date: item.date,
                    project_type: item.board || 'Municipal',
                    latitude: item.parcel_lat,
                    longitude: item.parcel_lon,
                    location: item.parcel_address || item.address,
                    title: item.title,
                    request: item.title, // Use title as request for now
                    staff_recommendation: item.status || 'Under Review',
                    owners: 'N/A', // Municipal data doesn't have owners
                    agent: 'N/A',   // Municipal data doesn't have agents
                    planning_district: 'N/A', // Municipal data doesn't have planning districts
                    signs_posted: false,
                    source_pdf: item.url,
                    extracted_at: item.extracted_at,
                    tags: [], // Municipal data doesn't have tags yet
                    category: getProjectCategory(item)
                }));

                // Find the project by ID
                const project = projects.find(p => p.project_id === projectId);

                if (project) {
                    projectData = project;
                    displayProjectDetail(project);
                    updatePageTitle(project);
                } else {
                    showNotFound();
                }
            })
            .fail(function() {
                showNotFound();
            });
    }

    function getProjectCategory(project) {
        const board = (project.board || '').toLowerCase();

        if (board.includes('planning') || board.includes('zoning')) {
            return 'zoning';
        }
        if (board.includes('development') || board.includes('ddrb') || board.includes('private')) {
            return 'private_development';
        }
        if (board.includes('infrastructure') || board.includes('transportation') || board.includes('public works')) {
            return 'infrastructure';
        }
        if (board.includes('council') || board.includes('public')) {
            return 'public_projects';
        }

        if (project.source_id) {
            const source = project.source_id.toLowerCase();
            if (source.includes('private')) return 'private_development';
            if (source.includes('infrastructure')) return 'infrastructure';
            if (source.includes('public')) return 'public_projects';
            if (source.includes('planning')) return 'zoning';
        }

        return 'zoning';
    }

    function displayProjectDetail(project) {
        $('#loading').hide();
        $('#project-detail-content').show();

        // Header information
        $('#detail-title').text(project.title);
        $('#detail-id').text(project.project_id);
        $('#detail-type').text(project.project_type);
        $('#detail-meeting-date').text(formatDate(project.meeting_date));

        // Location and status
        const location = project.location || 'Location not specified';
        const hasValidLocation = project.latitude && project.longitude &&
                                typeof project.latitude === 'number' && typeof project.longitude === 'number';

        if (hasValidLocation) {
            $('#detail-location').html(`${escapeHtml(location)}`);
        } else {
            $('#detail-location').html(`${escapeHtml(location)} <em>(Location cannot be mapped)</em>`);
            $('#detail-location').addClass('location-error');
        }

        // Status with styling
        const statusClass = getStatusClass(project.staff_recommendation);
        $('#detail-status').text(project.staff_recommendation).addClass(statusClass);

        // Project details
        $('#detail-request').text(project.request || 'N/A');
        $('#detail-council-district').text(project.council_district || 'N/A');
        $('#detail-planning-district').text(project.planning_district || 'N/A');
        $('#detail-owners').text(project.owners || 'N/A');
        $('#detail-agent').text(project.agent || 'N/A');
        $('#detail-staff-recommendation').text(project.staff_recommendation || 'N/A');
        $('#detail-signs-posted').text(project.signs_posted ? 'Yes' : 'No');

        // Source information
        $('#detail-source-pdf').text(project.source_pdf || 'N/A');
        $('#detail-extracted-at').text(formatDateTime(project.extracted_at));

        // Tags - use descriptive formatting
        if (project.tags && project.tags.length > 0) {
            const tagsHtml = project.tags.map(tag => {
                const displayText = formatTagForDisplay(tag);
                return `<span class="tag">${escapeHtml(displayText)}</span>`;
            }).join('');
            $('#detail-tags').html(tagsHtml);
        } else {
            $('#detail-tags-section').hide();
        }

        // Initialize map
        initializeDetailMap(project);

        // Set up action buttons
        setupActionButtons(project);
    }

    function initializeDetailMap(project) {
        if (project.latitude && project.longitude) {
            // Show map section
            $('#detail-map-section').show();

            // Initialize map
            detailMap = L.map('detail-map').setView([project.latitude, project.longitude], 15);

            // Add tile layer
            L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '© OpenStreetMap contributors'
            }).addTo(detailMap);

            // Add project marker
            const markerColor = getCategoryColor(project.category || 'zoning');
            const marker = L.circleMarker([project.latitude, project.longitude], {
                color: '#fff',
                weight: 2,
                opacity: 1,
                fillColor: markerColor,
                fillOpacity: 0.8,
                radius: 8
            }).addTo(detailMap);

            // Add popup to marker
            marker.bindPopup(`
                <div style="text-align: center; min-width: 200px;">
                    <strong>${escapeHtml(project.project_id)}</strong><br>
                    <em>${escapeHtml(project.project_type)}</em><br>
                    ${escapeHtml(project.location || 'Location not specified')}
                </div>
            `).openPopup();
        } else {
            // Hide map section if no coordinates
            $('#detail-map-section').hide();
        }
    }

    function setupActionButtons(project) {
        $('#view-on-main-map').click(function() {
            // Navigate back to main map with this project highlighted
            const mainMapUrl = `index.html#map-project-${encodeURIComponent(project.project_id)}`;
            window.location.href = mainMapUrl;
        });
    }

    function updatePageTitle(project) {
        document.title = `${project.project_id} - ${project.title} - Jacksonville Planning Commission Tracker`;
    }

    function showNotFound() {
        $('#loading').hide();
        $('#project-not-found').show();
    }

    // Helper functions
    function formatDate(dateString) {
        if (!dateString) return 'N/A';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        } catch (e) {
            return dateString;
        }
    }

    function formatDateTime(dateString) {
        if (!dateString) return 'N/A';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit'
            });
        } catch (e) {
            return dateString;
        }
    }

    function getStatusClass(recommendation) {
        if (!recommendation || typeof recommendation !== 'string') return 'status-other';

        const rec = recommendation.toLowerCase();
        if (rec.includes('approve')) return 'status-approve';
        if (rec.includes('defer')) return 'status-defer';
        if (rec.includes('deny')) return 'status-deny';
        return 'status-other';
    }

    function getCategoryColor(category) {
        const colors = {
            'zoning': '#8b1538',              // Deep Red - Zoning & Hearings
            'private_development': '#2c5530',  // Forest Green - Private Development
            'public_projects': '#1a4c7a',     // Navy Blue - Public Projects
            'infrastructure': '#8b4513'       // Saddle Brown - Infrastructure
        };
        return colors[category] || '#8b1538';
    }

    function formatTagForDisplay(tag) {
        const tagDisplayMap = {
            'administrative_deviation': 'Administrative Deviation',
            'exception': 'Exception',
            'variance': 'Variance',
            'land_use': 'Land Use Change',
            'pud': 'Large Development',
            'residential': 'Residential',
            'commercial': 'Commercial',
            'mixed_use': 'Mixed Use',
            'restaurant': 'Restaurant',
            'office': 'Office',
            'medical': 'Medical/Healthcare',
            'automotive': 'Automotive',
            'alcohol_sales': 'Alcohol Sales',
            'drive_through': 'Drive-Through',
            'parking': 'Parking',
            'storage': 'Storage/Warehouse',
            'gas_station': 'Gas Station',
            'setbacks': 'Setback Changes',
            'density': 'Density Changes',
            'downtown': 'Downtown',
            'riverside': 'Riverside',
            'avondale': 'Avondale',
            'beaches': 'Beaches Area',
            'westside': 'Westside',
            'northside': 'Northside',
            'southside': 'Southside',
            'mandarin': 'Mandarin',
            'large_development': 'Large Development',
            '100plus_units': '100+ Units',
            '50plus_units': '50+ Units'
        };

        return tagDisplayMap[tag] || tag.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    function getProjectTypeColor(projectType) {
        const colors = {
            'PUD': '#007bff',      // Blue
            'Exception': '#28a745', // Green
            'Variance': '#ffc107',  // Yellow
            'Land Use': '#dc3545',  // Red
            'Administrative Deviation': '#6f42c1', // Purple
            'Rezoning': '#fd7e14',  // Orange
            'Overlay': '#20c997',   // Teal
            'Amendment': '#6c757d'  // Gray
        };

        // Find matching color or default to blue
        for (const [type, color] of Object.entries(colors)) {
            if (projectType && projectType.toUpperCase().includes(type.toUpperCase())) {
                return color;
            }
        }
        return '#007bff';
    }

    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }
});