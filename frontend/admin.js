// Enhanced JaxWatch Admin Interface
class AdminApp {
    constructor() {
        this.currentCoordinates = null;
        this.currentProjects = [];
        this.filteredProjects = [];
        this.currentSection = 'add-project';

        this.init();
    }

    init() {
        this.bindEvents();
        this.checkAuth();
        this.showSection('add-project');
    }

    bindEvents() {
        // Navigation
        $('.nav-btn').on('click', (e) => this.handleNavigation(e));
        $('#logout-btn').on('click', () => this.logout());

        // Add Project Form
        $('#project-form').on('submit', (e) => this.saveProject(e));
        $('#geocode-btn').on('click', () => this.geocodeAddress());
        $('#category').on('change', () => this.autoGenerateProjectId());
        $('#project-id').on('input', function() {
            $(this).val($(this).val().toUpperCase());
        });

        // Project Management
        $('#project-search').on('input', () => this.filterProjects());
        $('#project-filter-source, #project-filter-flagged').on('change', () => this.filterProjects());

        // Document ready handlers
        $(document).on('click', '.project-item-header', (e) => this.toggleProjectDetails(e));
        $(document).on('click', '.action-btn', (e) => this.handleProjectAction(e));
    }

    async checkAuth() {
        try {
            const response = await fetch('/admin/check-auth');
            const data = await response.json();

            if (!data.authenticated) {
                window.location.href = '/admin/login';
                return;
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            window.location.href = '/admin/login';
        }
    }

    async logout() {
        try {
            await fetch('/admin/logout', { method: 'POST' });
            window.location.href = '/admin/login';
        } catch (error) {
            console.error('Logout failed:', error);
            window.location.href = '/admin/login';
        }
    }

    handleNavigation(e) {
        const targetSection = $(e.target).attr('id').replace('nav-', '') + '-section';

        // Update nav buttons
        $('.nav-btn').removeClass('active');
        $(e.target).addClass('active');

        // Show target section
        this.showSection(targetSection.replace('-section', ''));
    }

    showSection(section) {
        this.currentSection = section;

        // Hide all sections
        $('.admin-section').hide();

        // Show target section
        $(`#${section}-section`).show();

        // Load section data
        switch(section) {
            case 'manage-projects':
                this.loadProjects();
                break;
            case 'system-health':
                this.loadSystemHealth();
                break;
        }
    }

    // ===== ADD PROJECT FUNCTIONALITY =====

    geocodeAddress() {
        const location = $('#location').val().trim();

        if (!location) {
            alert('Please enter a location before geocoding.');
            return;
        }

        const searchLocation = location.toLowerCase().includes('jacksonville')
            ? location
            : `${location}, Jacksonville, FL`;

        $('#geocode-btn').prop('disabled', true).text('Geocoding...');

        const geocodeUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchLocation)}&limit=1&countrycodes=us`;

        $.getJSON(geocodeUrl)
            .done((data) => {
                if (data && data.length > 0) {
                    const result = data[0];
                    this.currentCoordinates = {
                        latitude: parseFloat(result.lat),
                        longitude: parseFloat(result.lon)
                    };

                    $('#coordinates-display').html(`
                        <p><strong>Found coordinates:</strong></p>
                        <p>Latitude: ${this.currentCoordinates.latitude}</p>
                        <p>Longitude: ${this.currentCoordinates.longitude}</p>
                        <p>Display Name: ${result.display_name}</p>
                    `);
                    $('#geocode-results').show();
                } else {
                    alert('No coordinates found for this location. The project will be saved without coordinates.');
                    this.currentCoordinates = null;
                    $('#geocode-results').hide();
                }
            })
            .fail(() => {
                alert('Geocoding failed. The project will be saved without coordinates.');
                this.currentCoordinates = null;
                $('#geocode-results').hide();
            })
            .always(() => {
                $('#geocode-btn').prop('disabled', false).text('Geocode Address');
            });
    }

    saveProject(e) {
        e.preventDefault();

        const formData = {
            slug: this.generateSlug($('#project-id').val(), $('#location').val()),
            project_id: $('#project-id').val(),
            title: $('#title').val(),
            location: $('#location').val(),
            category: $('#category').val(),
            project_type: $('#project-type').val() || 'Manual Entry',
            project_scale: $('#project-scale').val() || 'neighborhood',
            request: $('#request').val(),
            estimated_value: $('#estimated-value').val() ? parseInt($('#estimated-value').val()) : null,
            meeting_date: $('#meeting-date').val() || new Date().toISOString().split('T')[0],
            council_district: $('#council-district').val()?.split(' ')[1] || null,
            data_source: $('#data-source').val(),
            owners: $('#owners').val(),
            agent: $('#agent').val(),
            status: $('#status').val(),
            staff_recommendation: $('#status').val(),
            source_pdf: $('#source-url').val(),
            extracted_at: new Date().toISOString(),
            signs_posted: false,
            tags: [$('#category').val()],
            latitude: this.currentCoordinates?.latitude || null,
            longitude: this.currentCoordinates?.longitude || null,
            manually_added: true,
            last_edited_by: 'admin',
            last_edited_date: new Date().toISOString()
        };

        // Validate required fields
        if (!formData.project_id || !formData.title || !formData.location || !formData.category || !formData.data_source) {
            alert('Please fill in all required fields (marked with *).');
            return;
        }

        // Save project via API
        this.saveProjectToAPI(formData);
    }

    async saveProjectToAPI(project) {
        try {
            const response = await fetch('/api/admin/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(project)
            });

            if (response.ok) {
                $('#success-message').show();
                $('#project-form')[0].reset();
                this.currentCoordinates = null;
                $('#geocode-results').hide();

                setTimeout(() => {
                    $('#success-message').hide();
                }, 3000);
            } else {
                const error = await response.text();
                alert(`Error saving project: ${error}`);
            }
        } catch (error) {
            console.error('Save failed:', error);
            alert('Error saving project. Please try again.');
        }
    }

    autoGenerateProjectId() {
        const category = $('#category').val();
        const currentId = $('#project-id').val();

        if (!currentId && category) {
            const now = new Date();
            const year = now.getFullYear().toString().slice(-2);
            const month = (now.getMonth() + 1).toString().padStart(2, '0');
            const day = now.getDate().toString().padStart(2, '0');

            let prefix = '';
            switch(category) {
                case 'private_development':
                    prefix = 'DEV';
                    break;
                case 'public_projects':
                    prefix = 'PUB';
                    break;
                case 'infrastructure':
                    prefix = 'INF';
                    break;
                default:
                    prefix = 'MAN';
            }

            const suggestedId = `${prefix}-${year}-${month}${day}-001`;
            $('#project-id').val(suggestedId);
        }
    }

    generateSlug(projectId, location) {
        const combined = `${projectId} ${location}`;
        return combined.toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .trim();
    }

    // ===== PROJECT MANAGEMENT FUNCTIONALITY =====

    async loadProjects() {
        try {
            $('#projects-list').html('<div class="loading">Loading projects...</div>');

            const response = await fetch('/api/admin/projects');
            if (!response.ok) {
                throw new Error('Failed to load projects');
            }

            const data = await response.json();
            this.currentProjects = data.projects || [];
            this.filteredProjects = [...this.currentProjects];

            this.renderProjects();
        } catch (error) {
            console.error('Failed to load projects:', error);
            $('#projects-list').html('<div class="loading">Error loading projects</div>');
        }
    }

    filterProjects() {
        const searchTerm = $('#project-search').val().toLowerCase();
        const sourceFilter = $('#project-filter-source').val();
        const flaggedFilter = $('#project-filter-flagged').val();

        this.filteredProjects = this.currentProjects.filter(project => {
            // Search filter
            const matchesSearch = !searchTerm ||
                (project.title && project.title.toLowerCase().includes(searchTerm)) ||
                (project.location && project.location.toLowerCase().includes(searchTerm)) ||
                (project.project_id && project.project_id.toLowerCase().includes(searchTerm));

            // Source filter
            const matchesSource = !sourceFilter || project.data_source === sourceFilter;

            // Flagged filter
            const matchesFlagged = !flaggedFilter ||
                (flaggedFilter === 'true' && (project.flagged || project.manually_flagged)) ||
                (flaggedFilter === 'false' && !project.flagged && !project.manually_flagged);

            return matchesSearch && matchesSource && matchesFlagged;
        });

        this.renderProjects();
    }

    renderProjects() {
        if (this.filteredProjects.length === 0) {
            $('#projects-list').html('<div class="loading">No projects found</div>');
            return;
        }

        const projectsHtml = this.filteredProjects.map(project => this.renderProjectItem(project)).join('');
        $('#projects-list').html(projectsHtml);
    }

    renderProjectItem(project) {
        const flags = this.getProjectFlags(project);
        const flagBadges = flags.map(flag => `<span class="flag-badge ${flag.class}">${flag.text}</span>`).join('');

        return `
            <div class="project-item" data-project-id="${project.project_id || project.item_number}">
                <div class="project-item-header">
                    <div>
                        <h4 class="project-item-title">${project.title || 'Untitled Project'}</h4>
                        <div class="project-item-meta">
                            ${project.location || 'No location'} • ${project.data_source || 'Unknown source'}
                            ${project.last_edited_date ? ' • Last edited: ' + new Date(project.last_edited_date).toLocaleDateString() : ''}
                        </div>
                        <div class="project-flags">${flagBadges}</div>
                    </div>
                    <div class="project-item-actions">
                        <button class="action-btn edit" data-action="edit" data-project-id="${project.project_id || project.item_number}">Edit</button>
                        ${project.flagged || project.manually_flagged
                            ? '<button class="action-btn unflag" data-action="unflag">Unflag</button>'
                            : '<button class="action-btn flag" data-action="flag">Flag</button>'
                        }
                    </div>
                </div>
                <div class="project-item-details">
                    ${this.renderProjectDetails(project)}
                </div>
            </div>
        `;
    }

    renderProjectDetails(project) {
        const details = [
            { label: 'Project ID', value: project.project_id || project.item_number || 'N/A' },
            { label: 'Category', value: project.category || 'N/A' },
            { label: 'Project Type', value: project.project_type || 'N/A' },
            { label: 'Status', value: project.status || 'N/A' },
            { label: 'Council District', value: project.council_district || 'N/A' },
            { label: 'Estimated Value', value: project.estimated_value ? `$${project.estimated_value.toLocaleString()}` : 'N/A' },
            { label: 'Meeting Date', value: project.meeting_date || 'N/A' },
            { label: 'Owners', value: project.owners || 'N/A' },
            { label: 'Agent', value: project.agent || 'N/A' }
        ];

        const detailsHtml = details.map(detail => `
            <div class="project-detail-item">
                <div class="project-detail-label">${detail.label}</div>
                <div class="project-detail-value">${detail.value}</div>
            </div>
        `).join('');

        return `
            <div class="project-detail-grid">
                ${detailsHtml}
            </div>
            ${project.request ? `<div class="project-detail-item"><div class="project-detail-label">Description</div><div class="project-detail-value">${project.request}</div></div>` : ''}
            ${project.source_pdf ? `<div class="project-detail-item"><div class="project-detail-label">Source Document</div><div class="project-detail-value"><a href="${project.source_pdf}" target="_blank">View PDF</a></div></div>` : ''}
        `;
    }

    getProjectFlags(project) {
        const flags = [];

        if (project.flagged && !project.manually_flagged) {
            flags.push({ class: 'auto-flagged', text: 'Auto Flagged' });
        }

        if (project.manually_flagged) {
            flags.push({ class: 'manual-flagged', text: 'Manual Flag' });
        }

        if (project.source_verified) {
            flags.push({ class: 'verified', text: 'Verified' });
        }

        if (project.manually_added) {
            flags.push({ class: 'verified', text: 'Manual Entry' });
        }

        return flags;
    }

    toggleProjectDetails(e) {
        if ($(e.target).hasClass('action-btn')) {
            return; // Don't toggle if clicking action button
        }

        const $details = $(e.currentTarget).siblings('.project-item-details');
        $details.toggleClass('expanded');
    }

    async handleProjectAction(e) {
        e.stopPropagation();

        const action = $(e.target).data('action');
        const projectId = $(e.target).data('project-id') || $(e.target).closest('.project-item').data('project-id');

        switch(action) {
            case 'edit':
                this.editProject(projectId);
                break;
            case 'flag':
                this.flagProject(projectId, true);
                break;
            case 'unflag':
                this.flagProject(projectId, false);
                break;
        }
    }

    editProject(projectId) {
        const project = this.currentProjects.find(p => (p.project_id || p.item_number) === projectId);
        if (!project) {
            alert('Project not found');
            return;
        }

        // For now, just show an alert. In a full implementation, this would open an edit modal
        alert(`Edit functionality for project ${projectId} would be implemented here. For MVP, use the Add Project form to create new entries.`);
    }

    async flagProject(projectId, flagged) {
        try {
            const reason = flagged ? prompt('Enter reason for flagging this project:') : '';
            if (flagged && !reason) {
                return; // User cancelled
            }

            const response = await fetch(`/api/admin/projects/${projectId}/flag`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ flagged, reason })
            });

            if (response.ok) {
                // Reload projects to show updated flags
                this.loadProjects();
            } else {
                const error = await response.text();
                alert(`Error ${flagged ? 'flagging' : 'unflagging'} project: ${error}`);
            }
        } catch (error) {
            console.error('Flag operation failed:', error);
            alert(`Error ${flagged ? 'flagging' : 'unflagging'} project. Please try again.`);
        }
    }

    // ===== SYSTEM HEALTH FUNCTIONALITY =====

    async loadSystemHealth() {
        try {
            $('#health-report').html('<div class="loading">Loading health report...</div>');

            const response = await fetch('/api/admin/health');
            if (!response.ok) {
                throw new Error('Failed to load health report');
            }

            const healthData = await response.json();
            this.renderHealthReport(healthData);
        } catch (error) {
            console.error('Failed to load health report:', error);
            $('#health-report').html('<div class="loading">Error loading health report</div>');
        }
    }

    renderHealthReport(data) {
        const summary = data.system_summary || {};
        const sources = data.source_details || [];

        const healthHtml = `
            <div class="health-summary">
                <div class="health-card">
                    <h3>Overall Status</h3>
                    <div class="metric">${summary.overall_status || 'Unknown'}</div>
                    <span class="status ${summary.overall_status || 'warning'}">${summary.overall_status || 'Unknown'}</span>
                </div>
                <div class="health-card">
                    <h3>Success Rate</h3>
                    <div class="metric">${summary.overall_success_rate || 0}%</div>
                    <span class="status ${this.getStatusClass(summary.overall_success_rate)}">Rate</span>
                </div>
                <div class="health-card">
                    <h3>Total Sources</h3>
                    <div class="metric">${summary.total_sources || 0}</div>
                    <span class="status healthy">Active</span>
                </div>
                <div class="health-card">
                    <h3>Documents Processed</h3>
                    <div class="metric">${summary.total_documents_processed || 0}</div>
                    <span class="status healthy">Total</span>
                </div>
            </div>

            <h3>Source Details</h3>
            <div class="sources-list">
                ${sources.map(source => this.renderSourceHealth(source)).join('')}
            </div>

            <p><strong>Last Updated:</strong> ${new Date(summary.last_updated || Date.now()).toLocaleString()}</p>
        `;

        $('#health-report').html(healthHtml);
    }

    renderSourceHealth(source) {
        return `
            <div class="health-card">
                <h3>${source.source_name}</h3>
                <div class="metric">${source.success_rate_24h || 0}%</div>
                <span class="status ${this.getStatusClass(source.success_rate_24h)}">24h Success</span>
                <p>Documents: ${source.total_documents_processed || 0}</p>
                <p>Last Poll: ${source.last_successful_poll ? new Date(source.last_successful_poll).toLocaleString() : 'Never'}</p>
                ${source.last_error_message ? `<p style="color: #dc3545; font-size: 12px;">Last Error: ${source.last_error_message}</p>` : ''}
            </div>
        `;
    }

    getStatusClass(successRate) {
        if (successRate >= 80) return 'healthy';
        if (successRate >= 60) return 'warning';
        return 'critical';
    }
}

// Initialize the admin app when document is ready
$(document).ready(() => {
    new AdminApp();
});