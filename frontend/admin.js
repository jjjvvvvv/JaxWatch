$(document).ready(function() {
    let currentCoordinates = null;

    // Form submission handler
    $('#project-form').on('submit', function(e) {
        e.preventDefault();
        saveProject();
    });

    // Geocoding handler
    $('#geocode-btn').on('click', function() {
        geocodeAddress();
    });

    function geocodeAddress() {
        const location = $('#location').val().trim();

        if (!location) {
            alert('Please enter a location before geocoding.');
            return;
        }

        // Add "Jacksonville, FL" if not already present
        const searchLocation = location.toLowerCase().includes('jacksonville')
            ? location
            : `${location}, Jacksonville, FL`;

        $('#geocode-btn').prop('disabled', true).text('Geocoding...');

        // Use Nominatim API for geocoding
        const geocodeUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchLocation)}&limit=1&countrycodes=us`;

        $.getJSON(geocodeUrl)
            .done(function(data) {
                if (data && data.length > 0) {
                    const result = data[0];
                    currentCoordinates = {
                        latitude: parseFloat(result.lat),
                        longitude: parseFloat(result.lon)
                    };

                    $('#coordinates-display').html(`
                        <p><strong>Found coordinates:</strong></p>
                        <p>Latitude: ${currentCoordinates.latitude}</p>
                        <p>Longitude: ${currentCoordinates.longitude}</p>
                        <p>Display Name: ${result.display_name}</p>
                    `);
                    $('#geocode-results').show();
                } else {
                    alert('No coordinates found for this location. The project will be saved without coordinates.');
                    currentCoordinates = null;
                    $('#geocode-results').hide();
                }
            })
            .fail(function() {
                alert('Geocoding failed. The project will be saved without coordinates.');
                currentCoordinates = null;
                $('#geocode-results').hide();
            })
            .always(function() {
                $('#geocode-btn').prop('disabled', false).text('Geocode Address');
            });
    }

    function saveProject() {
        // Collect form data
        const formData = {
            slug: generateSlug($('#project-id').val(), $('#location').val()),
            project_id: $('#project-id').val(),
            title: $('#title').val(),
            location: $('#location').val(),
            category: $('#category').val(),
            project_type: $('#project-type').val() || 'Manual Entry',
            project_scale: $('#project-scale').val() || 'neighborhood',
            request: $('#request').val(),
            estimated_value: $('#estimated-value').val() ? parseInt($('#estimated-value').val()) : null,
            meeting_date: $('#meeting-date').val() || new Date().toISOString().split('T')[0],
            council_district: $('#council-district').val()?.split(' ')[1] || null, // Extract number
            data_source: $('#data-source').val(),
            owners: $('#owners').val(),
            agent: $('#agent').val(),
            status: $('#status').val(),
            staff_recommendation: $('#status').val(),
            source_pdf: $('#source-url').val(),
            extracted_at: new Date().toISOString(),
            signs_posted: false, // Default for manual entries
            tags: [$('#category').val()],
            latitude: currentCoordinates?.latitude || null,
            longitude: currentCoordinates?.longitude || null,
            completion_timeline: null // Can be added later
        };

        // Validate required fields
        if (!formData.project_id || !formData.title || !formData.location || !formData.category || !formData.data_source) {
            alert('Please fill in all required fields (marked with *).');
            return;
        }

        // Save to localStorage for now (in a real app, this would go to a backend)
        saveProjectToStorage(formData);

        // Show success message
        $('#success-message').show();

        // Reset form
        $('#project-form')[0].reset();
        currentCoordinates = null;
        $('#geocode-results').hide();

        // Hide success message after 3 seconds
        setTimeout(() => {
            $('#success-message').hide();
        }, 3000);
    }

    function generateSlug(projectId, location) {
        // Create a URL-friendly slug
        const combined = `${projectId} ${location}`;
        return combined.toLowerCase()
            .replace(/[^\w\s-]/g, '') // Remove special characters
            .replace(/\s+/g, '-') // Replace spaces with hyphens
            .replace(/-+/g, '-') // Replace multiple hyphens with single
            .trim();
    }

    function saveProjectToStorage(project) {
        // Get existing projects from localStorage
        let projects = [];
        try {
            const stored = localStorage.getItem('observatory_manual_projects');
            if (stored) {
                projects = JSON.parse(stored);
            }
        } catch (e) {
            console.error('Error reading stored projects:', e);
        }

        // Add new project
        projects.push(project);

        // Save back to localStorage
        try {
            localStorage.setItem('observatory_manual_projects', JSON.stringify(projects));
            console.log('Project saved successfully:', project.project_id);
        } catch (e) {
            console.error('Error saving project:', e);
            alert('Error saving project. Please try again.');
        }
    }

    // Auto-format project ID as user types
    $('#project-id').on('input', function() {
        let value = $(this).val().toUpperCase();
        $(this).val(value);
    });

    // Auto-generate project ID for certain categories
    $('#category').on('change', function() {
        const category = $(this).val();
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
                    prefix = 'MAN'; // Manual
            }

            const suggestedId = `${prefix}-${year}-${month}${day}-001`;
            $('#project-id').val(suggestedId);
        }
    });
});