(function () {
  var DATA_PATH = 'data/extracted_accountability.json';

  var state = {
    projects: [],
    filtered: [],
    sortBy: 'investment_desc'
  };

  var elements = {};

  function initDomRefs() {
    elements.search = $('#public-search');
    elements.statusFilter = $('#public-status-filter');
    elements.sort = $('#public-sort');
    elements.resultCount = $('#public-result-count');
    elements.statusMessage = $('#public-status-message');
    elements.container = $('#projects-container');
    elements.lastUpdated = $('#public-last-updated');

    // Overview elements
    elements.recentUpdates = $('#recent-updates');
    elements.totalProjects = $('#total-projects');
    elements.totalInvestment = $('#total-public-investment');
    elements.onSchedule = $('#projects-on-schedule');

    // Buttons
    elements.viewAllBtn = $('#view-all-btn');
    elements.exportBtn = $('#export-data-btn');
    elements.aboutLink = $('#about-link');
    elements.feedbackLink = $('#feedback-link');
  }

  function attachListeners() {
    elements.search.on('input', debounce(applyFilters, 300));
    elements.statusFilter.on('change', applyFilters);
    elements.sort.on('change', function() {
      state.sortBy = $(this).val();
      render();
    });

    elements.viewAllBtn.on('click', function() {
      $('html, body').animate({
        scrollTop: $('.public-controls').offset().top
      }, 500);
    });

    elements.exportBtn.on('click', exportData);
    elements.aboutLink.on('click', showAboutModal);
    elements.feedbackLink.on('click', showFeedbackModal);
  }

  function debounce(fn, delay) {
    var timer;
    return function () {
      var context = this;
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(context, args);
      }, delay);
    };
  }

  function loadProjects() {
    elements.statusMessage.text('Loading projects…').show();
    elements.container.attr('hidden', true);

    $.getJSON(DATA_PATH)
      .done(function (data) {
        processProjects(data);
      })
      .fail(function () {
        handleDataLoadFailure();
      });
  }

  function processProjects(raw) {
    if (!Array.isArray(raw)) {
      handleDataLoadFailure();
      return;
    }

    state.projects = raw.map(normaliseProject).filter(function(p) {
      return p.name && p.name !== '—';  // Filter out projects without names
    });

    state.filtered = state.projects.slice();
    updateOverview();
    applyFilters();
    elements.statusMessage.hide();
    elements.container.removeAttr('hidden');
    elements.lastUpdated.text(new Date().toLocaleDateString());
  }

  function handleDataLoadFailure() {
    elements.container.attr('hidden', true);
    elements.statusMessage.text('⚠️ Unable to load project data. Please try again later.').show();
    elements.resultCount.text('0 projects');
  }

  function normaliseProject(project) {
    var publicInvestment = project.public_investment || {};
    var promises = project.promises || {};
    var accountability = project.accountability || {};

    return {
      id: project.id || '',
      name: project.name || project.title || '',
      developer: project.developer || 'Unknown Developer',
      status: project.status || 'needs_review',
      totalInvestment: publicInvestment.total_approved || 0,
      fundingTypes: publicInvestment.funding_types || [],
      promisedUnits: promises.residential_units ? promises.residential_units.promised : null,
      promisedCompletion: promises.completion_date || null,
      actualUnits: promises.residential_units ? promises.residential_units.delivered : null,
      actualCompletion: project.actual && project.actual.completion_date ? project.actual.completion_date : null,
      completionPercentage: accountability.completion_percentage || 0,
      daysDelayed: accountability.days_delayed || 0,
      notes: accountability.notes || '',
      address: project.address || '',
      dateOpened: project.date_opened || project.meeting_date || '',
      lastUpdate: project.last_update || project.date_opened || '',
      raw: project
    };
  }

  function updateOverview() {
    var totalInvestment = state.projects.reduce(function(sum, p) {
      return sum + (p.totalInvestment || 0);
    }, 0);

    var onScheduleCount = state.projects.filter(function(p) {
      return p.status === 'in_progress' && p.daysDelayed <= 0;
    }).length;

    var activeCount = state.projects.filter(function(p) {
      return p.status === 'in_progress' || p.status === 'needs_review';
    }).length;

    elements.totalProjects.text(state.projects.length);
    elements.totalInvestment.text('$' + formatCurrency(totalInvestment));
    elements.onSchedule.text(Math.round((onScheduleCount / Math.max(activeCount, 1)) * 100) + '%');

    // Update recent updates
    var recentProjects = state.projects
      .filter(function(p) { return p.lastUpdate; })
      .sort(function(a, b) { return new Date(b.lastUpdate) - new Date(a.lastUpdate); })
      .slice(0, 3);

    var updatesHtml = recentProjects.map(function(p) {
      var statusText = formatStatusText(p.status);
      var delay = p.daysDelayed > 0 ? ' (' + p.daysDelayed + ' days delayed)' : '';
      return '<li><strong>' + escapeHtml(p.name) + ':</strong> ' + statusText + delay + '</li>';
    }).join('');

    if (updatesHtml) {
      elements.recentUpdates.html(updatesHtml);
    } else {
      elements.recentUpdates.html('<li>No recent updates available</li>');
    }
  }

  function applyFilters() {
    var searchTerm = (elements.search.val() || '').trim().toLowerCase();
    var statusFilter = elements.statusFilter.val() || '';

    state.filtered = state.projects.filter(function(project) {
      // Status filter
      if (statusFilter && project.status !== statusFilter) {
        return false;
      }

      // Search filter
      if (searchTerm) {
        var searchableText = [
          project.name,
          project.developer,
          project.address,
          project.status
        ].join(' ').toLowerCase();

        if (searchableText.indexOf(searchTerm) === -1) {
          return false;
        }
      }

      return true;
    });

    render();
  }

  function render() {
    sortProjects();
    renderProjectCards();
    updateResultCount();
  }

  function sortProjects() {
    var [field, direction] = state.sortBy.split('_');
    var isAsc = direction === 'asc';

    state.filtered.sort(function(a, b) {
      var aVal, bVal;

      switch(field) {
        case 'investment':
          aVal = a.totalInvestment || 0;
          bVal = b.totalInvestment || 0;
          break;
        case 'date':
          aVal = new Date(a.dateOpened || '1900-01-01');
          bVal = new Date(b.dateOpened || '1900-01-01');
          break;
        case 'name':
          aVal = a.name.toLowerCase();
          bVal = b.name.toLowerCase();
          break;
        case 'status':
          aVal = a.status;
          bVal = b.status;
          break;
        default:
          return 0;
      }

      if (aVal === bVal) return 0;
      var result = aVal > bVal ? 1 : -1;
      return isAsc ? result : -result;
    });
  }

  function renderProjectCards() {
    elements.container.empty();

    if (!state.filtered.length) {
      elements.container.append(
        '<div class="no-results">' +
        '<h3>No projects match your search</h3>' +
        '<p>Try adjusting your filters or search terms.</p>' +
        '</div>'
      );
      return;
    }

    state.filtered.forEach(function(project) {
      var card = createProjectCard(project);
      elements.container.append(card);
    });
  }

  function createProjectCard(project) {
    var statusClass = 'status-' + project.status;
    var statusText = formatStatusText(project.status);

    var investmentText = project.totalInvestment
      ? '$' + formatCurrency(project.totalInvestment) + ' investment'
      : 'Investment amount not disclosed';

    var progressText = '';
    if (project.status === 'in_progress' && project.completionPercentage) {
      progressText = project.completionPercentage + '% complete';
    } else if (project.daysDelayed > 0) {
      progressText = project.daysDelayed + ' days delayed';
    } else if (project.status === 'completed') {
      progressText = 'Project completed';
    }

    var promisesText = '';
    if (project.promisedUnits) {
      promisesText += project.promisedUnits + ' units promised';
      if (project.actualUnits !== null) {
        promisesText += ' → ' + project.actualUnits + ' delivered';
      }
    }

    if (project.promisedCompletion) {
      if (promisesText) promisesText += ' • ';
      promisesText += 'Target: ' + formatDate(project.promisedCompletion);
    }

    var card = $('<div class="project-card ' + statusClass + '"></div>');

    card.html([
      '<div class="card-header">',
        '<h3 class="project-title">' + escapeHtml(project.name) + '</h3>',
        '<span class="project-status">' + statusText + '</span>',
      '</div>',
      '<div class="card-body">',
        '<p class="project-developer"><strong>Developer:</strong> ' + escapeHtml(project.developer) + '</p>',
        '<p class="project-investment">' + investmentText + '</p>',
        promisesText ? '<p class="project-promises">' + promisesText + '</p>' : '',
        progressText ? '<p class="project-progress">' + progressText + '</p>' : '',
        project.address ? '<p class="project-address">' + escapeHtml(project.address) + '</p>' : '',
        project.fundingTypes.length ? '<p class="funding-types">Funding: ' + project.fundingTypes.join(', ') + '</p>' : '',
      '</div>',
      '<div class="card-footer">',
        '<span class="last-update">Updated: ' + formatDate(project.lastUpdate) + '</span>',
      '</div>'
    ].join(''));

    // Add click handler to show more details
    card.on('click', function() {
      showProjectDetail(project);
    });

    return card;
  }

  function showProjectDetail(project) {
    var detailHtml = [
      '<div class="project-detail-modal">',
        '<div class="modal-content">',
          '<div class="modal-header">',
            '<h2>' + escapeHtml(project.name) + '</h2>',
            '<button class="close-modal">×</button>',
          '</div>',
          '<div class="modal-body">',
            '<p><strong>Developer:</strong> ' + escapeHtml(project.developer) + '</p>',
            '<p><strong>Status:</strong> ' + formatStatusText(project.status) + '</p>',
            project.totalInvestment ? '<p><strong>Public Investment:</strong> $' + formatCurrency(project.totalInvestment) + '</p>' : '',
            project.promisedUnits ? '<p><strong>Promised Units:</strong> ' + project.promisedUnits + '</p>' : '',
            project.actualUnits !== null ? '<p><strong>Delivered Units:</strong> ' + project.actualUnits + '</p>' : '',
            project.promisedCompletion ? '<p><strong>Target Completion:</strong> ' + formatDate(project.promisedCompletion) + '</p>' : '',
            project.actualCompletion ? '<p><strong>Actual Completion:</strong> ' + formatDate(project.actualCompletion) + '</p>' : '',
            project.address ? '<p><strong>Location:</strong> ' + escapeHtml(project.address) + '</p>' : '',
            project.notes ? '<p><strong>Notes:</strong> ' + escapeHtml(project.notes) + '</p>' : '',
            '<p><strong>Project ID:</strong> ' + escapeHtml(project.id) + '</p>',
          '</div>',
        '</div>',
      '</div>'
    ].join('');

    var modal = $(detailHtml);
    $('body').append(modal);

    modal.find('.close-modal, .project-detail-modal').on('click', function(e) {
      if (e.target === this) {
        modal.remove();
      }
    });
  }

  function updateResultCount() {
    var total = state.projects.length;
    var filtered = state.filtered.length;
    var text = filtered === total
      ? filtered + ' projects'
      : filtered + ' of ' + total + ' projects';
    elements.resultCount.text(text);
  }

  function formatCurrency(amount) {
    if (!amount || amount === 0) return '0';
    if (amount >= 1000000) {
      return (amount / 1000000).toFixed(1) + 'M';
    }
    if (amount >= 1000) {
      return (amount / 1000).toFixed(0) + 'K';
    }
    return amount.toLocaleString();
  }

  function formatStatusText(status) {
    var statusMap = {
      'needs_review': 'Under Review',
      'in_progress': 'In Progress',
      'completed': 'Completed',
      'delayed': 'Delayed',
      'cancelled': 'Cancelled'
    };
    return statusMap[status] || status;
  }

  function formatDate(dateStr) {
    if (!dateStr) return 'Not specified';
    try {
      var date = new Date(dateStr);
      return date.toLocaleDateString();
    } catch (e) {
      return dateStr;
    }
  }

  function exportData() {
    var csv = 'Project Name,Developer,Status,Investment,Promised Units,Target Completion,Address,Last Update\n';

    state.projects.forEach(function(p) {
      var row = [
        escapeCSV(p.name),
        escapeCSV(p.developer),
        escapeCSV(formatStatusText(p.status)),
        p.totalInvestment || '',
        p.promisedUnits || '',
        p.promisedCompletion || '',
        escapeCSV(p.address),
        p.lastUpdate || ''
      ].join(',');
      csv += row + '\n';
    });

    var blob = new Blob([csv], { type: 'text/csv' });
    var url = window.URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'dia_projects_' + new Date().toISOString().split('T')[0] + '.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  }

  function escapeCSV(text) {
    if (!text) return '';
    text = text.toString();
    if (text.includes(',') || text.includes('"') || text.includes('\n')) {
      return '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
  }

  function showAboutModal() {
    var aboutHtml = [
      '<div class="about-modal">',
        '<div class="modal-content">',
          '<div class="modal-header">',
            '<h2>About DIA Project Accountability Tracker</h2>',
            '<button class="close-modal">×</button>',
          '</div>',
          '<div class="modal-body">',
            '<p><strong>Purpose:</strong> This tracker monitors Jacksonville Downtown Investment Authority (DIA) funded projects to ensure promised deliverables are met.</p>',
            '<p><strong>Data Sources:</strong> DIA Board meeting minutes, resolutions, project agreements, and public records.</p>',
            '<p><strong>What We Track:</strong> Promised vs actual delivery of residential units, commercial space, job creation, completion timelines, and public investment amounts.</p>',
            '<p><strong>Update Frequency:</strong> Data is updated monthly based on DIA board meetings and project reports.</p>',
            '<p><strong>Accountability Questions:</strong> Did projects deliver what was promised? Are timelines being met? How is public money being used?</p>',
            '<p><em>This is a civic accountability tool to promote transparency in public-private development partnerships.</em></p>',
          '</div>',
        '</div>',
      '</div>'
    ].join('');

    showModal(aboutHtml);
  }

  function showFeedbackModal() {
    var feedbackHtml = [
      '<div class="feedback-modal">',
        '<div class="modal-content">',
          '<div class="modal-header">',
            '<h2>Report an Issue</h2>',
            '<button class="close-modal">×</button>',
          '</div>',
          '<div class="modal-body">',
            '<p>Help us improve the accuracy of this tracker:</p>',
            '<ul>',
              '<li>Report incorrect project information</li>',
              '<li>Provide updates on project status</li>',
              '<li>Suggest additional data sources</li>',
              '<li>Request new features</li>',
            '</ul>',
            '<p><strong>Contact:</strong> <a href="mailto:accountability@jaxwatch.org">accountability@jaxwatch.org</a></p>',
            '<p><em>All submissions are reviewed and verified against public records.</em></p>',
          '</div>',
        '</div>',
      '</div>'
    ].join('');

    showModal(feedbackHtml);
  }

  function showModal(html) {
    var modal = $(html);
    $('body').append(modal);

    modal.find('.close-modal').on('click', function() {
      modal.remove();
    });

    modal.on('click', function(e) {
      if (e.target === this) {
        modal.remove();
      }
    });
  }

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  $(function () {
    initDomRefs();
    attachListeners();
    loadProjects();
  });
})();