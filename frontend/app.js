$(document).ready(function() {
    let allProjects = [];
    let filteredProjects = [];
    let map = null;
    let mapMarkers = [];

    // Load and initialize data
    loadProjectData();

    // Initialize UI elements
    setActiveCategory('all');  // Ensure proper tab state initialization
    updateSearchPlaceholder('all');
    updateMapLegend('all');

    // Event listeners
    $('#search').on('input', filterProjects);
    $('#board-filter, #date-filter, #project-type-filter, #council-district-filter, #status-filter').on('change', filterProjects);

    // Category tab event listeners
    $('.category-tab').on('click', function() {
        const category = $(this).data('category');
        setActiveCategory(category);
        filterProjects();
    });

    // Project card click handlers
    $(document).on('click', '.project-card', function(e) {
        // Don't navigate if clicking on metadata links, buttons, or PDF links
        if ($(e.target).hasClass('metadata-link') ||
            $(e.target).hasClass('view-details-btn') ||
            $(e.target).hasClass('source-btn') ||
            $(e.target).closest('a, button').length > 0) {
            return;
        }

        const projectId = $(this).data('project-id');
        window.location.href = `project-detail.html?id=${encodeURIComponent(projectId)}`;
    });

    // Handle view details button click (redundant but kept for explicit handling)
    $(document).on('click', '.view-details-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const projectId = $(this).data('project-id');
        window.location.href = `project-detail.html?id=${encodeURIComponent(projectId)}`;
    });

    $('#source-docs-link').on('click', function(e) {
        e.preventDefault();
        showSourceDocs();
    });

    $('#glossary-link').on('click', function(e) {
        e.preventDefault();
        showGlossary();
    });

    $('.glossary-close').on('click', function() {
        $('#glossary-modal').hide();
    });

    // Initialize jargon translation system
    initializeJargonTranslation();

    // View switching
    $(document).on('click', '#list-view-btn', function() {
        switchToListView();
    });

    $(document).on('click', '#map-view-btn', function() {
        switchToMapView();
    });


    // Metadata link click handler
    $(document).on('click', '.metadata-link', function(e) {
        e.preventDefault();
        e.stopPropagation(); // Prevent project card click

        const type = $(this).data('type');
        const value = $(this).data('value');
        showDirectoryView(type, value);
    });

    function loadProjectData() {
        // Try to load from new municipal data first, fallback to legacy all-projects.json
        $.getJSON('municipal-data.json')
            .done(function(data) {
                allProjects = Array.isArray(data) ? data : (data.projects || []);

                // Convert municipal data format to frontend format
                allProjects = allProjects.map(item => ({
                    ...item,
                    // Map fields for frontend compatibility
                    project_id: item.item_number || `${item.board}-${item.date}`,
                    meeting_date: item.date,
                    project_type: item.board || 'Municipal',
                    latitude: item.parcel_lat,
                    longitude: item.parcel_lon,
                    address: item.parcel_address || item.location,
                    // Keep original fields
                    board: item.board,
                    council_district: item.council_district,
                    status: item.status,
                    flagged: item.flagged
                }));

                // Sort projects by meeting date (newest first) then by item number
                allProjects.sort((a, b) => {
                    // First sort by meeting date (newest first)
                    const dateA = new Date(a.meeting_date || '1900-01-01');
                    const dateB = new Date(b.meeting_date || '1900-01-01');

                    if (dateB.getTime() !== dateA.getTime()) {
                        return dateB.getTime() - dateA.getTime();
                    }

                    // Then by item number (ascending within same meeting)
                    const itemA = parseInt(a.item_number || '0');
                    const itemB = parseInt(b.item_number || '0');
                    return itemA - itemB;
                });

                filteredProjects = [...allProjects];

                // Update summary info
                const summary = data.summary || {};
                if (summary.date_range) {
                    const earliest = formatDate(summary.date_range.earliest);
                    const latest = formatDate(summary.date_range.latest);
                    $('#date-range').text(`${earliest} - ${latest}`);
                }

                // Update data source info
                if (data.sources) {
                    const sourceCount = Object.keys(data.sources).length;
                    const lastUpdate = data.timestamp ? new Date(data.timestamp).toLocaleString() : 'Unknown';
                    $('#data-source-info').html(`
                        <small class="text-muted">
                            Municipal Observatory Data | ${sourceCount} sources | Updated: ${lastUpdate}
                        </small>
                    `);

                    // Update footer with detailed source information
                    const sourceDetails = Object.entries(data.sources).map(([id, info]) =>
                        `${info.total_items} items from ${id.replace('_', ' ').toLowerCase()}`
                    ).join(' • ');
                    $('#data-source-details').html(`<strong>Latest Collection:</strong> ${sourceDetails} • Last updated: ${lastUpdate}`);
                }

                // Populate filter options
                populateFilters();

                // Initialize filtering (this sets up filteredProjects properly)
                filterProjects();

                // Display projects and show content
                displayProjects();
                updateStats(data);
            })
            .fail(function() {
                // Fallback to legacy all-projects.json
                console.warn('Municipal data not found, trying legacy all-projects.json...');
                $.getJSON('all-projects.json')
                    .done(function(data) {
                        allProjects = Array.isArray(data) ? data : (data.projects || []);
                        populateFilters();
                        filterProjects();
                        displayProjects();
                        updateStats(data);
                    })
                    .fail(function() {
                        $('#projects-list').html('<p style="color: #dc3545; padding: 20px;">Error loading project data. Please check that municipal-data.json or all-projects.json exists.</p>');
                    });
            });
    }

    function populateFilters() {
        // Boards
        const boards = [...new Set(allProjects.map(p => p.board))].sort();
        boards.forEach(board => {
            $('#board-filter').append(`<option value="${board}">${board}</option>`);
        });

        // Project types
        const projectTypes = [...new Set(allProjects.map(p => p.project_type))].sort();
        projectTypes.forEach(type => {
            $('#project-type-filter').append(new Option(type, type));
        });

        // Council districts with representative names
        const districtNames = {
            '1': 'Ken Amaro',
            '2': 'Mike Gay',
            '3': 'Will Lahnen',
            '4': 'Kevin Carrico (President)',
            '5': 'Joe Carlucci',
            '6': 'Michael Boylan',
            '7': 'Jimmy Peluso',
            '8': 'Reggie Gaffney, Jr.',
            '9': 'Tyrona Clark-Murray',
            '10': 'Ju\'Coby Pittman',
            '11': 'Raul Arias',
            '12': 'Randy White',
            '13': 'Rory Diamond',
            '14': 'Rahman Johnson'
        };

        const councilDistricts = [...new Set(allProjects.map(p => p.council_district))].sort((a, b) => parseInt(a) - parseInt(b));
        councilDistricts.forEach(district => {
            const representative = districtNames[district] || 'Unknown Representative';
            $('#council-district-filter').append(new Option(`District ${district} - ${representative}`, district));
        });

        // Status options (based on staff recommendations)
        const statuses = [...new Set(allProjects.map(p => {
            const rec = p.staff_recommendation;
            if (rec.includes('APPROVE')) return 'Approve';
            if (rec.includes('DEFER')) return 'Defer';
            if (rec.includes('DENY')) return 'Deny';
            return 'Other';
        }))].sort();
        statuses.forEach(status => {
            $('#status-filter').append(new Option(status, status));
        });
    }

    let activeCategory = 'all';

    function setActiveCategory(category) {
        activeCategory = category;
        // Update both sets of category tabs (list view and map view)
        $('.category-tab').removeClass('active');
        $(`.category-tab[data-category="${category}"]`).addClass('active');
        updateSearchPlaceholder(category);
        updateMapLegend(category);
    }

    function getProjectCategory(project) {
        // Map board names to UI categories
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

        // Default fallback based on source_id
        if (project.source_id) {
            const source = project.source_id.toLowerCase();
            if (source.includes('private')) return 'private_development';
            if (source.includes('infrastructure')) return 'infrastructure';
            if (source.includes('public')) return 'public_projects';
            if (source.includes('planning')) return 'zoning';
        }

        return 'zoning'; // Default category
    }

    function filterProjects() {
        const searchTerm = $('#search').val().toLowerCase();
        const boardFilter = $('#board-filter').val();
        const dateFilter = $('#date-filter').val();
        const projectTypeFilter = $('#project-type-filter').val();
        const councilDistrictFilter = $('#council-district-filter').val();
        const statusFilter = $('#status-filter').val();

        filteredProjects = allProjects.filter(project => {
            // Category filter - map board names to categories
            let projectCategory = getProjectCategory(project);

            if (activeCategory !== 'all' && projectCategory !== activeCategory) {
                return false;
            }
            // Search filter - handle null values safely
            const searchMatch = !searchTerm ||
                (project.title || '').toLowerCase().includes(searchTerm) ||
                (project.location || '').toLowerCase().includes(searchTerm) ||
                (project.owners || '').toLowerCase().includes(searchTerm) ||
                (project.agent || '').toLowerCase().includes(searchTerm) ||
                (project.project_id || '').toLowerCase().includes(searchTerm) ||
                (project.request || '').toLowerCase().includes(searchTerm);

            // Board filter
            const boardMatch = !boardFilter || project.board === boardFilter;

            // Date filter
            let dateMatch = true;
            if (dateFilter) {
                const projectDate = new Date(project.meeting_date || project.date);
                const cutoffDate = new Date();
                cutoffDate.setDate(cutoffDate.getDate() - parseInt(dateFilter));
                dateMatch = projectDate >= cutoffDate;
            }

            // Project type filter
            const typeMatch = !projectTypeFilter || project.project_type === projectTypeFilter;

            // Council district filter
            const districtMatch = !councilDistrictFilter || project.council_district === councilDistrictFilter;

            // Status filter
            const statusMatch = !statusFilter || (project.status && project.status.includes(statusFilter));

            return searchMatch && boardMatch && dateMatch && typeMatch && districtMatch && statusMatch;
        });

        displayProjects();
        updateStats();

        // Update map if it's currently visible
        if (map && $('#map-content').is(':visible')) {
            addProjectMarkers();
        }
    }

    function displayProjects() {
        const $projectsList = $('#projects-list');
        const $noResults = $('#no-results');

        if (filteredProjects.length === 0) {
            $projectsList.hide();
            $noResults.show();
            return;
        }

        $noResults.hide();
        $projectsList.show();

        const projectsHtml = filteredProjects.map(project => createProjectCard(project)).join('');
        $projectsList.html(projectsHtml);
    }

    function createProjectCard(project) {
        const status = project.status || 'Unknown';
        const location = project.parcel_address || project.address || 'Location not specified';
        const board = project.board || 'Unknown Board';
        const councilDistrict = project.council_district ? `District ${project.council_district}` : '';

        // Determine category color based on board
        const categoryColor = getBoardColor(board);

        // Format date
        const meetingDate = formatDateShort(project.meeting_date || project.date);

        // Flagged badge
        const flaggedBadge = project.flagged ? '<span class="flagged-badge">⚠️ Flagged</span>' : '';

        // Create notes preview
        const notes = project.notes || [];
        const notesPreview = notes.length > 0 ? notes[0].substring(0, 100) + (notes[0].length > 100 ? '...' : '') : '';

        return `
            <div class="project-card" data-project-id="${escapeHtml(project.project_id)}" style="border-left-color: ${categoryColor};" data-lat="${project.parcel_lat || ''}" data-lon="${project.parcel_lon || ''}">
                <div class="project-header">
                    <div class="project-board">${escapeHtml(board)}</div>
                    <div class="project-meeting-date">${meetingDate}</div>
                    ${flaggedBadge}
                </div>

                <div class="project-title">${escapeHtml(project.title)}</div>

                <div class="project-meta">
                    <div class="project-location">📍 ${escapeHtml(location)}</div>
                    <div class="project-status">📋 ${escapeHtml(status)}</div>
                    ${councilDistrict ? `<div class="project-district">🏛️ ${escapeHtml(councilDistrict)}</div>` : ''}
                    ${project.source ? `<div class="project-source">🔗 ${escapeHtml(project.source)}</div>` : ''}
                    ${project.last_updated ? `<div class="project-updated">🕒 ${escapeHtml(new Date(project.last_updated).toLocaleString())}</div>` : ''}
                </div>

                ${notesPreview ? `<div class="project-notes">${escapeHtml(notesPreview)}</div>` : ''}

                <div class="project-card-actions">
                    <a href="${escapeHtml(project.url)}" target="_blank" class="btn btn-primary source-btn">
                        View Source
                    </a>
                </div>
            </div>
        `;
    }

    function updateStats(data) {
        $('#total-projects').text(allProjects.length);
        $('#visible-projects').text(filteredProjects.length);

        // Calculate meeting count from unique meeting dates
        const uniqueMeetings = [...new Set(allProjects.map(p => p.meeting_date))].filter(date => date);
        $('#total-meetings').text(uniqueMeetings.length);

        // Calculate date range
        if (allProjects.length > 0) {
            const dates = allProjects.map(p => new Date(p.meeting_date)).filter(d => !isNaN(d));
            if (dates.length > 0) {
                const earliestDate = new Date(Math.min(...dates));
                const latestDate = new Date(Math.max(...dates));
                const dateRange = `${earliestDate.toLocaleDateString()} - ${latestDate.toLocaleDateString()}`;
                $('#date-range').text(dateRange);
            }
        }
    }

    function getStatusClass(recommendation) {
        if (!recommendation || typeof recommendation !== 'string') return '';
        if (recommendation.includes('APPROVE')) return 'status-approve';
        if (recommendation.includes('DEFER')) return 'status-defer';
        if (recommendation.includes('DENY')) return 'status-deny';
        return '';
    }

    function getStatusCategory(recommendation) {
        if (!recommendation || typeof recommendation !== 'string') return 'Other';
        if (recommendation.includes('APPROVE')) return 'Approve';
        if (recommendation.includes('DEFER')) return 'Defer';
        if (recommendation.includes('DENY')) return 'Deny';
        return 'Other';
    }

    function formatDate(dateString) {
        // Convert "Thursday, October 3, 2024" to a more compact format
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
            });
        } catch (e) {
            return dateString;
        }
    }

    function formatDateShort(dateString) {
        // Format date for display on project cards
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
            });
        } catch (e) {
            return dateString || 'Date N/A';
        }
    }


    function showSourceDocs() {
        // Get unique meeting dates and their source PDFs
        const meetings = {};
        allProjects.forEach(project => {
            const date = project.meeting_date;
            const sourcePdf = project.source_pdf;
            if (date && sourcePdf && !meetings[date]) {
                meetings[date] = sourcePdf;
            }
        });

        const sortedMeetings = Object.keys(meetings).sort((a, b) => {
            const dateA = new Date(a);
            const dateB = new Date(b);
            return dateB.getTime() - dateA.getTime(); // Newest to oldest
        });

        const modalBody = `
            <div class="meeting-info">
                <div class="modal-detail-label">About This Data</div>
                <div class="modal-detail-value">
                    This tracker contains real data extracted from Jacksonville Planning Commission meeting agendas
                    from October 2024 to present. All project information comes directly from official city documents.
                </div>
            </div>

            <div class="modal-detail-item">
                <div class="modal-detail-label">Source Documents</div>
                <div class="modal-detail-value">
                    ${sortedMeetings.map(date => `
                        <div style="margin-bottom: 10px;">
                            <strong>${escapeHtml(date)}:</strong>
                            <a href="${escapeHtml(meetings[date])}" target="_blank" style="color: #1e3a8a; text-decoration: none;">
                                📄 View Planning Commission Agenda PDF
                            </a>
                        </div>
                    `).join('')}
                </div>
            </div>

            <div class="modal-detail-item" style="margin-top: 20px;">
                <div class="modal-detail-label">Data Collection</div>
                <div class="modal-detail-value">
                    <strong>Extraction Method:</strong> Automated PDF parsing using Python<br>
                    <strong>Update Frequency:</strong> Manual updates as new agendas are published<br>
                    <strong>Source:</strong> <a href="https://www.jacksonville.gov/departments/planning-and-development/planning-commission.aspx" target="_blank">Jacksonville Planning Commission</a><br>
                    <strong>Data Types:</strong> PUDs, Exceptions, Variances, Land Use changes, Administrative Deviations
                </div>
            </div>
        `;

        $('#modal-title').text('Data Sources & Documentation');
        $('#modal-body').html(modalBody);
        $('#project-modal').show();
    }

    function showDirectoryView(type, value) {
        // Filter projects by the selected metadata
        const relatedProjects = allProjects.filter(project => {
            switch(type) {
                case 'agent':
                    return project.agent === value;
                case 'owner':
                    return project.owners === value;
                case 'district':
                    return project.council_district === value;
                case 'type':
                    return project.project_type === value;
                default:
                    return false;
            }
        });

        // Generate directory title
        const titles = {
            'agent': `Agent: ${value}`,
            'owner': `Owner: ${value}`,
            'district': `Council District ${value}`,
            'type': `Project Type: ${value}`
        };

        const title = titles[type] || 'Directory';

        // Generate stats
        const totalProjects = relatedProjects.length;
        const approvedCount = relatedProjects.filter(p => p.staff_recommendation.includes('APPROVE')).length;
        const deferredCount = relatedProjects.filter(p => p.staff_recommendation.includes('DEFER')).length;
        const deniedCount = relatedProjects.filter(p => p.staff_recommendation.includes('DENY')).length;

        // Get unique meetings
        const meetings = [...new Set(relatedProjects.map(p => p.meeting_date))].sort().reverse();

        const modalBody = `
            <div class="meeting-info">
                <div class="modal-detail-label">Summary</div>
                <div class="modal-detail-value">
                    Found <strong>${totalProjects}</strong> projects related to ${value}
                    <br><br>
                    <strong>Outcomes:</strong><br>
                    • Approved: ${approvedCount}<br>
                    • Deferred: ${deferredCount}<br>
                    • Denied: ${deniedCount}<br>
                    • Other: ${totalProjects - approvedCount - deferredCount - deniedCount}
                </div>
            </div>

            <div class="modal-detail-item">
                <div class="modal-detail-label">Active in Meetings</div>
                <div class="modal-detail-value">
                    ${meetings.map(date => `<div>• ${escapeHtml(formatDateShort(date))}</div>`).join('')}
                </div>
            </div>

            <div class="modal-detail-item">
                <div class="modal-detail-label">Related Projects</div>
                <div class="modal-detail-value">
                    ${relatedProjects.map(project => `
                        <div style="margin-bottom: 15px; padding: 10px; border: 1px solid #dee2e6; border-radius: 5px;">
                            <strong>${escapeHtml(project.project_id)}</strong> - ${escapeHtml(project.title)}<br>
                            <small style="color: #6c757d;">
                                ${escapeHtml(formatDateShort(project.meeting_date))} • ${escapeHtml(project.staff_recommendation)}
                                ${project.location ? ` • ${escapeHtml(project.location)}` : ''}
                            </small>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        $('#modal-title').text(title);
        $('#modal-body').html(modalBody);
        $('#project-modal').show();
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // View switching functions
    function switchToListView() {
        $('#list-view-btn').addClass('active');
        $('#map-view-btn').removeClass('active');
        $('#list-content').show();
        $('#map-content').hide();
    }

    function switchToMapView() {
        $('#list-view-btn').removeClass('active');
        $('#map-view-btn').addClass('active');
        $('#list-content').hide();
        $('#map-content').show();

        // Initialize map if not already done
        if (!map) {
            initializeMap();
        }

        // Invalidate size to ensure proper rendering after show
        if (map) {
            setTimeout(() => {
                map.invalidateSize();
            }, 100);
        }
    }

    // Map initialization
    function initializeMap() {
        // Center on Jacksonville, FL
        map = L.map('map').setView([30.337, -81.662], 11);

        // Add OpenStreetMap tiles
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // District boundaries removed for now
        // loadDistrictBoundaries();

        // Add project markers
        addProjectMarkers();
    }

    // Add markers for all projects
    function addProjectMarkers() {
        // Clear existing markers
        clearMapMarkers();

        const projectsToShow = filteredProjects;

        // Only show projects with valid coordinates on the map
        const mappableProjects = projectsToShow.filter(project => {
            return project.parcel_lat && project.parcel_lon &&
                typeof project.parcel_lat === 'number' && typeof project.parcel_lon === 'number' &&
                !isNaN(project.parcel_lat) && !isNaN(project.parcel_lon);
        });

        mappableProjects.forEach((project, index) => {
            const lat = project.parcel_lat;
            const lng = project.parcel_lon;

            // Get marker color based on board
            const markerColor = getBoardColor(project.board);

            // Create colored marker with flagged indicator
            const marker = L.circleMarker([lat, lng], {
                color: project.flagged ? '#fbbf24' : '#fff',
                weight: project.flagged ? 3 : 2,
                opacity: 1,
                fillColor: markerColor,
                fillOpacity: 0.8,
                radius: 8
            }).addTo(map);

            // Enhanced popup with more details
            const popupContent = `
                <div style="min-width: 250px;" class="map-popup">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <strong style="color: ${markerColor}; font-size: 14px;">${escapeHtml(project.board)}</strong>
                        ${project.flagged ? '<span style="background: #fef3c7; color: #92400e; padding: 2px 6px; border-radius: 10px; font-size: 10px;">⚠️ Flagged</span>' : ''}
                    </div>
                    <div style="margin: 8px 0; font-weight: 600; line-height: 1.3;">${escapeHtml(project.title)}</div>
                    <div style="color: #6c757d; margin-bottom: 8px; font-size: 12px;">
                        📍 ${escapeHtml(project.parcel_address || project.address || 'Location not specified')}<br>
                        🗓️ ${formatDateShort(project.meeting_date || project.date)}<br>
                        ${project.council_district ? `🏛️ District ${project.council_district}<br>` : ''}
                        📋 ${escapeHtml(project.status || 'Status unknown')}
                    </div>
                    ${project.notes && project.notes.length > 0 ? `
                        <div style="margin: 8px 0; font-size: 11px; color: #777; font-style: italic;">
                            "${escapeHtml(project.notes[0].substring(0, 100))}${project.notes[0].length > 100 ? '...' : ''}"
                        </div>
                    ` : ''}
                    <div style="margin-top: 8px;">
                        <a href="${escapeHtml(project.url)}" target="_blank" style="color: ${markerColor}; text-decoration: none; font-size: 12px; font-weight: 600;">
                            📄 View Source Document
                        </a>
                    </div>
                    <div style="margin-top: 4px;">
                        <button onclick="highlightProjectCard('${escapeHtml(project.project_id)}')" style="background: none; border: 1px solid ${markerColor}; color: ${markerColor}; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;">
                            📍 Find in List
                        </button>
                    </div>
                </div>
            `;

            marker.bindPopup(popupContent);
            mapMarkers.push(marker);
        });

        // Update map legend based on current category
        updateMapLegend(activeCategory);
    }

    // Clear all map markers
    function clearMapMarkers() {
        mapMarkers.forEach(marker => {
            map.removeLayer(marker);
        });
        mapMarkers = [];
    }

    // Highlight project card when clicked from map
    window.highlightProjectCard = function(projectId) {
        // Switch to list view if not already visible
        if (!$('#list-content').is(':visible')) {
            $('#list-view-btn').click();
        }

        // Find and highlight the project card
        const $card = $(`.project-card[data-project-id="${projectId}"]`);
        if ($card.length > 0) {
            // Remove previous highlights
            $('.project-card').removeClass('highlighted');

            // Add highlight to target card
            $card.addClass('highlighted');

            // Scroll to the card
            $card[0].scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });

            // Remove highlight after 3 seconds
            setTimeout(() => {
                $card.removeClass('highlighted');
            }, 3000);
        }
    };

    // Get color for project type
    function getCategoryColor(category) {
        const colors = {
            'zoning': '#1e3a8a',              // Jacksonville Blue - Zoning & Hearings
            'private_development': '#059669',  // Emerald Green - Private Development
            'public_projects': '#dc2626',     // Red - Public Projects
            'infrastructure': '#7c3aed'       // Purple - Infrastructure
        };
        return colors[category] || '#1e3a8a';
    }

    function getBoardColor(board) {
        const colors = {
            'Planning Commission': '#1e3a8a',           // Blue
            'City Council': '#dc2626',                  // Red
            'Downtown Development Review Board': '#7c3aed',  // Purple
            'Development Services': '#059669',          // Green
            'Public Works': '#ea580c',                  // Orange
            'Parks and Recreation': '#16a34a',          // Light Green
            'Transportation': '#0891b2',                // Cyan
            'Infrastructure Committee': '#7c3aed'       // Purple
        };
        return colors[board] || '#6b7280';  // Default gray
    }

    function updateSearchPlaceholder(category) {
        const placeholders = {
            'all': 'Search projects...',
            'zoning': 'Search zoning cases...',
            'private_development': 'Search developments...',
            'public_projects': 'Search public projects...',
            'infrastructure': 'Search infrastructure...'
        };
        const placeholder = placeholders[category] || placeholders['all'];
        $('#search').attr('placeholder', placeholder);
    }

    function updateMapLegend(category) {
        const legendContent = $('#legend-content');

        if (category === 'all') {
            // Show all categories in the legend
            const categories = [
                { key: 'zoning', label: 'Zoning & Hearings' },
                { key: 'private_development', label: 'Private Development' },
                { key: 'public_projects', label: 'Public Projects' },
                { key: 'infrastructure', label: 'Infrastructure' }
            ];

            const legendHtml = categories.map(cat => {
                const color = getCategoryColor(cat.key);
                return `
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: ${color};"></div>
                        <span class="legend-label">${cat.label}</span>
                    </div>
                `;
            }).join('');

            legendContent.html(legendHtml);
        } else if (category === 'zoning') {
            // Show project types for zoning category
            const projectTypes = [
                { key: 'PUD', label: 'PUD' },
                { key: 'Exception', label: 'Exception' },
                { key: 'Variance', label: 'Variance' },
                { key: 'Land Use', label: 'Land Use' },
                { key: 'Administrative Deviation', label: 'Admin Dev' },
                { key: 'Rezoning', label: 'Rezoning' },
                { key: 'Overlay', label: 'Overlay' },
                { key: 'Amendment', label: 'Amendment' }
            ];

            const legendHtml = projectTypes.map(type => {
                const color = getProjectTypeColor(type.key);
                return `
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: ${color};"></div>
                        <span class="legend-label">${type.label}</span>
                    </div>
                `;
            }).join('');

            legendContent.html(legendHtml);
        } else {
            // Show only the active category for other categories
            const categoryNames = {
                'private_development': 'Private Development',
                'public_projects': 'Public Projects',
                'infrastructure': 'Infrastructure'
            };

            const color = getCategoryColor(category);
            const label = categoryNames[category] || 'Projects';

            const legendHtml = `
                <div class="legend-item">
                    <div class="legend-color" style="background-color: ${color};"></div>
                    <span class="legend-label">${label}</span>
                </div>
            `;

            legendContent.html(legendHtml);
        }
    }

    function getProjectTypeColor(projectType) {
        const colors = {
            'PUD': '#1e3a8a',      // Jacksonville Blue
            'Exception': '#059669', // Emerald Green
            'Variance': '#f59e0b',  // Amber
            'Land Use': '#dc2626',  // Red
            'Administrative Deviation': '#7c3aed', // Purple
            'Rezoning': '#ea580c',  // Orange
            'Overlay': '#0891b2',   // Cyan
            'Amendment': '#6b7280'  // Gray
        };

        // Find matching color or default to blue
        for (const [type, color] of Object.entries(colors)) {
            if (projectType && projectType.toUpperCase().includes(type.toUpperCase())) {
                return color;
            }
        }
        return '#1e3a8a'; // Default Jacksonville blue
    }


    // Glossary and Jargon Translation System
    const glossaryData = {
        'Planning & Zoning': {
            'PUD': 'Planned Unit Development - A large mixed-use development project that combines residential, commercial, or office spaces in one area',
            'Administrative Deviation': 'A small change to an approved development plan that staff can approve without a public hearing',
            'Variance': 'Permission to build something that doesn\'t meet standard zoning rules (like building closer to the street than normally allowed)',
            'Exception': 'Permission to use a property for something not typically allowed in that zoning area',
            'Land Use/Zoning': 'Changing what type of activities can happen on a piece of land (residential, commercial, industrial, etc.)',
            'Rezoning': 'Officially changing the zoning classification of a property',
            'Conditional Use': 'A special use that\'s allowed in a zoning area only with specific conditions attached'
        },
        'Process & Approval': {
            'Staff Recommendation': 'What city planning experts think the Planning Commission should decide',
            'Planning Commission': 'A group of appointed citizens who review and vote on development proposals',
            'City Council': 'Elected officials who make final decisions on some planning matters',
            'Public Hearing': 'A meeting where residents can speak for or against a proposal',
            'Deferred': 'Decision postponed to a future meeting for more information',
            'Approved with Conditions': 'Project approved but with specific requirements that must be met'
        },
        'Geographic Areas': {
            'Council District': 'One of 14 areas of Jacksonville, each represented by an elected councilperson',
            'Planning District': 'Geographic areas used by city planners to organize development review',
            'Right-of-Way': 'Public land used for roads, sidewalks, and utilities',
            'Setback': 'Required distance between a building and the property line'
        },
        'Financial Terms': {
            'Estimated Value': 'How much the developer expects the project to cost',
            'Public Infrastructure': 'Roads, water, sewer, and other systems paid for with tax money',
            'Impact Fee': 'Money developers pay to help fund public services needed for new development',
            'TIF District': 'Tax Increment Financing - a way to use future tax increases to pay for improvements now'
        }
    };

    const jargonTranslations = {
        'pud': 'Large mixed-use development project',
        'administrative deviation': 'Small staff-approved change to development plan',
        'variance': 'Permission to break standard zoning rules',
        'exception': 'Permission for non-standard use of property',
        'land use': 'What activities can happen on the land',
        'rezoning': 'Changing the zoning classification',
        'conditional use': 'Special use allowed with conditions',
        'staff recommendation': 'What city experts recommend',
        'planning commission': 'Citizens who review development proposals',
        'public hearing': 'Meeting where residents can speak about proposals',
        'deferred': 'Decision postponed for more information',
        'council district': 'Area represented by an elected councilperson',
        'right-of-way': 'Public land for roads and utilities',
        'setback': 'Required distance from building to property line',
        'impact fee': 'Developer payment for public services',
        'tif': 'Tax increment financing for improvements'
    };

    function showGlossary() {
        let glossaryHtml = '';

        for (const [section, terms] of Object.entries(glossaryData)) {
            glossaryHtml += `<div class="glossary-section">
                <h3>${section}</h3>`;

            for (const [term, definition] of Object.entries(terms)) {
                glossaryHtml += `<div class="glossary-term">
                    <div class="term-name">${term}</div>
                    <div class="term-definition">${definition}</div>
                </div>`;
            }

            glossaryHtml += '</div>';
        }

        $('#glossary-content').html(glossaryHtml);
        $('#glossary-modal').show();
    }

    function initializeJargonTranslation() {
        // Add tooltips to technical terms throughout the interface
        $(document).on('mouseenter', '.jargon-term', function(e) {
            const term = $(this).text().toLowerCase().trim();
            const translation = jargonTranslations[term];

            if (translation) {
                const tooltip = $('#jargon-tooltip');
                tooltip.text(translation);

                const offset = $(this).offset();
                tooltip.css({
                    'top': offset.top - tooltip.outerHeight() - 10,
                    'left': offset.left + ($(this).outerWidth() / 2) - (tooltip.outerWidth() / 2),
                    'display': 'block'
                });
            }
        });

        $(document).on('mouseleave', '.jargon-term', function() {
            $('#jargon-tooltip').hide();
        });
    }

    function wrapJargonTerms(text) {
        if (!text) return text;

        let wrappedText = text;

        // Wrap known jargon terms with spans for tooltip functionality
        for (const term of Object.keys(jargonTranslations)) {
            const regex = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
            wrappedText = wrappedText.replace(regex, '<span class="jargon-term">$&</span>');
        }

        return wrappedText;
    }

    // Tag Display Helper
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

    // District boundaries functionality removed

    // District popup functions removed

});
