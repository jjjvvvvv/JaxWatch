(function () {
  var PRIMARY_PATH = 'data/projects_index.json';

  var state = {
    projects: [],
    filtered: [],
    sortField: 'importance_score',
    sortDirection: 'desc'
  };

  var elements = {};

  function initDomRefs() {
    elements.search = $('#search-input');
    elements.statusFilter = $('#status-filter');
    elements.year = $('#year-filter');
    elements.confidenceFilter = $('#confidence-filter');
    elements.count = $('#result-count');
    elements.status = $('#status-message');
    elements.table = $('#projects-table');
    elements.tbody = $('#projects-table tbody');
    elements.headers = $('#projects-table thead th');

    // Dashboard elements
    elements.activeCount = $('#active-count');
    elements.totalInvestment = $('#total-investment');
    elements.onSchedulePercent = $('#on-schedule-percent');
    elements.reviewNeededCount = $('#review-needed-count');
    elements.lastUpdated = $('#last-updated');
  }

  function attachListeners() {
    elements.search.on('input', debounce(applyFilters, 150));
    elements.statusFilter.on('change', applyFilters);
    elements.confidenceFilter.on('change', applyFilters);
    if (elements.year && elements.year.length) {
      elements.year.on('change', applyFilters);
    }
    elements.headers.on('click', handleHeaderClick);
  }

  function handleHeaderClick() {
    var sortKey = $(this).data('sort');
    if (!sortKey) return;
    if (state.sortField === sortKey) {
      state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      state.sortField = sortKey;
      state.sortDirection = sortKey === 'name' ? 'asc' : 'desc';
    }
    render();
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
    elements.status.text('Loading projects…').show();
    elements.table.attr('hidden', true);

    $.getJSON(PRIMARY_PATH)
      .done(function (data) {
        processProjects(data);
      })
      .fail(function () {
        handleDataLoadFailure();
      });
  }

  function processProjects(raw, options) {
    if (!Array.isArray(raw)) {
      handleDataLoadFailure();
      return;
    }

    state.projects = raw.map(normaliseProject);
    state.filtered = state.projects.slice();
    populateYearFilter();
    updateDashboard();
    applyFilters();
    if (options && options.note) {
      elements.status.text(options.note).show();
    } else {
      elements.status.hide();
    }
    elements.table.removeAttr('hidden');
  }

  function handleDataLoadFailure() {
    console.error('DIA Accountability Tracker: ERROR – no valid extracted_accountability.json found.');
    elements.table.attr('hidden', true);
    elements.status.text('⚠️ No accountability data available. Please copy outputs/projects/extracted_accountability.json into admin_ui/data/ before running.').show();
    elements.count.text('0 results');
  }

  function normaliseProject(project) {
    var lastUpdate = project.last_update || project.date_opened || project.meeting_date || '';
    var parsedDate = parseDate(lastUpdate);
    var year = parsedDate ? String(parsedDate.getFullYear()) : '';

    // Use new scoring fields
    var confidenceLevel = project.confidence_level || 'low';
    var importanceScore = project.importance_score || 0;
    var moneyMentioned = project.money_mentions && project.money_mentions.length > 0;

    // Get last mentioned date from mentions
    var lastMentioned = '';
    if (project.mentions && project.mentions.length > 0) {
      var dates = project.mentions
        .map(function(m) { return m.meeting_date; })
        .filter(Boolean)
        .sort()
        .reverse();
      lastMentioned = dates[0] || '';
    }

    // Extract legacy accountability fields for backward compatibility
    var publicInvestment = project.public_investment || {};
    var promises = project.promises || {};
    var extractionConfidence = project.extraction_confidence || {};

    return {
      id: project.id || '',
      name: project.name || project.title || project.id || '',
      developer: project.developer || '—',
      status: project.status || 'needs_review',

      // New scoring system fields
      importance_score: importanceScore,
      confidence: confidenceLevel,
      confidence_score: project.confidence_score || 0,
      money_mentioned: moneyMentioned,
      last_mentioned: lastMentioned,

      // Legacy fields for compatibility
      total_investment: publicInvestment.total_approved || null,
      promised_units: promises.residential_units ? promises.residential_units.promised : null,
      completion_date: promises.completion_date || '—',
      review_needed: project.pending_review || extractionConfidence.manual_review_needed !== false,
      year: year,
      summary: project.summary || '',

      // Display helpers
      display_ranking: project.display_ranking || {},

      raw: project
    };
  }

  function updateDashboard() {
    var activeProjects = state.projects.filter(function (p) {
      return p.status === 'in_progress' || p.status === 'needs_review';
    });

    var totalInvestment = state.projects.reduce(function (sum, p) {
      return sum + (p.total_investment || 0);
    }, 0);

    var onScheduleCount = state.projects.filter(function (p) {
      return p.status === 'in_progress' && !p.delayed;
    }).length;

    var reviewNeeded = state.projects.filter(function (p) {
      return p.review_needed;
    }).length;

    // Update dashboard
    elements.activeCount.text(activeProjects.length);
    elements.totalInvestment.text('$' + formatCurrency(totalInvestment));

    var onSchedulePercent = activeProjects.length > 0
      ? Math.round((onScheduleCount / activeProjects.length) * 100)
      : 0;
    elements.onSchedulePercent.text(onSchedulePercent + '%');
    elements.reviewNeededCount.text(reviewNeeded);
    elements.lastUpdated.text(new Date().toLocaleDateString());
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

  function populateYearFilter() {
    if (!elements.year) return;
    var yearSet = new Set();
    state.projects.forEach(function (project) {
      if (project.year) {
        yearSet.add(project.year);
      }
    });
    var years = Array.from(yearSet).sort(function (a, b) {
      return b.localeCompare(a);
    });
    var options = ['<option value="">All years</option>'];
    years.forEach(function (year) {
      options.push('<option value="' + escapeHtml(year) + '">' + escapeHtml(year) + '</option>');
    });
    elements.year.html(options.join(''));
    elements.year.val('');
  }

  function applyFilters() {
    var term = (elements.search.val() || '').trim().toLowerCase();
    var status = elements.statusFilter.val() || '';
    var confidence = elements.confidenceFilter.val() || '';
    var year = elements.year ? elements.year.val() || '' : '';

    state.filtered = state.projects.filter(function (project) {
      // Status filter
      if (status && project.status !== status) return false;

      // Confidence filter
      if (confidence && project.confidence !== confidence) return false;

      // Year filter
      if (year && project.year !== year) return false;

      // Search term
      if (!term) return true;
      var haystack = [
        project.id,
        project.name,
        project.developer,
        project.status,
        project.confidence
      ].join(' ').toLowerCase();
      return haystack.indexOf(term) !== -1;
    });

    render();
  }

  function render() {
    sortProjects();
    renderTable();
    updateCount();
  }

  function sortProjects() {
    var field = state.sortField;
    var direction = state.sortDirection === 'asc' ? 1 : -1;

    state.filtered.sort(function (a, b) {
      var aVal = a[field] || '';
      var bVal = b[field] || '';

      // Handle date fields
      if (field === 'last_update' || field === 'last_mentioned') {
        var aDate = parseDate(aVal);
        var bDate = parseDate(bVal);
        if (!aDate && !bDate) return 0;
        if (!aDate) return 1;
        if (!bDate) return -1;
        return (aDate - bDate) * direction;
      }

      // Handle numeric fields
      if (field === 'importance_score' || field === 'confidence_score') {
        var aNum = parseFloat(aVal) || 0;
        var bNum = parseFloat(bVal) || 0;
        return (aNum - bNum) * direction;
      }

      // Handle string fields
      aVal = aVal.toString().toLowerCase();
      bVal = bVal.toString().toLowerCase();
      if (aVal === bVal) return 0;
      return aVal > bVal ? direction : -direction;
    });

    updateHeaderIndicators();
  }

  function createProjectNameCell(project) {
    var container = $('\u003cdiv class="project-name-container" /\u003e');
    var nameEl = $('\u003cdiv class="project-name" /\u003e').text(project.name || '—');
    container.append(nameEl);

    if (project.summary && project.summary.length > 0) {
      var summaryEl = $('\u003cdiv class="project-summary" /\u003e').text(project.summary);
      container.append(summaryEl);
    }

    return container;
  }

  function createImportanceCell(project) {
    var container = $('\u003cdiv class="importance-container" /\u003e');
    var score = project.importance_score || 0;
    var level = score >= 60 ? 'High' : (score >= 30 ? 'Medium' : 'Low');

    var scoreEl = $('\u003cdiv class="importance-score" /\u003e')
      .text(score + ' (' + level + ')');
    container.append(scoreEl);

    // Add explanation if available
    var ranking = project.display_ranking || {};
    if (ranking.rank_explanation) {
      var explanationEl = $('\u003cdiv class="importance-explanation" /\u003e')
        .text(ranking.rank_explanation);
      container.append(explanationEl);
    }

    return container;
  }

  function updateHeaderIndicators() {
    elements.headers.removeClass('sorted-asc sorted-desc');
    elements.headers.each(function () {
      var header = $(this);
      if (header.data('sort') === state.sortField) {
        header.addClass(state.sortDirection === 'asc' ? 'sorted-asc' : 'sorted-desc');
      }
    });
  }

  function renderTable() {
    elements.tbody.empty();

    if (!state.filtered.length) {
      elements.tbody.append(
        $('<tr />').append(
          $('<td />')
            .attr('colspan', 7)
            .attr('data-label', 'Notice')
            .text('No projects match the current filters.')
        )
      );
      return;
    }

    state.filtered.forEach(function (project) {
      var detailUrl = 'project.html?id=' + encodeURIComponent(project.id || '');
      var row = $('<tr />');

      // Add status class for row styling
      if (project.status === 'delayed') {
        row.addClass('status-delayed');
      } else if (project.status === 'completed') {
        row.addClass('status-completed');
      } else if (project.confidence === 'not_extracted') {
        row.addClass('needs-extraction');
      }

      var cells = [
        { label: 'Project Name', content: createProjectNameCell(project) },
        {
          label: 'Importance',
          content: createImportanceCell(project),
          class: 'importance-' + (project.importance_score >= 60 ? 'high' : (project.importance_score >= 30 ? 'medium' : 'low'))
        },
        {
          label: 'Status',
          content: formatStatus(project.status),
          class: 'status-' + project.status
        },
        {
          label: 'Last Mentioned',
          content: project.last_mentioned || '—'
        },
        {
          label: '$ Mentioned',
          content: project.money_mentioned ? 'Yes' : 'No',
          class: project.money_mentioned ? 'money-yes' : ''
        },
        {
          label: 'Confident',
          content: formatConfidence(project.confidence),
          class: 'confidence-' + project.confidence
        }
      ];

      cells.forEach(function (cell) {
        var td = $('\u003ctd /\u003e').attr('data-label', cell.label);

        // Handle content that is already a jQuery object
        if (cell.content instanceof jQuery) {
          td.append(cell.content);
        } else {
          td.text(cell.content);
        }

        if (cell.class) {
          td.addClass(cell.class);
        }
        row.append(td);
      });

      // Make the entire row clickable to go to the detail page
      row.addClass('clickable-row').on('click', function () {
        window.location.href = detailUrl;
      });

      elements.tbody.append(row);
    });
  }

  function formatStatus(status) {
    var statusMap = {
      'needs_review': 'Needs Review',
      'in_progress': 'In Progress',
      'completed': 'Completed',
      'delayed': 'Delayed',
      'cancelled': 'Cancelled'
    };
    return statusMap[status] || status || '—';
  }

  function formatConfidence(confidence) {
    var confidenceMap = {
      'high': 'High',
      'medium': 'Medium',
      'low': 'Low',
      'not_extracted': 'Needs Extraction'
    };
    return confidenceMap[confidence] || confidence || '—';
  }



  function updateCount() {
    elements.count.text(state.filtered.length + ' results');
  }

  function parseDate(value) {
    if (!value) return null;
    var parsed = new Date(value);
    if (isNaN(parsed.getTime()) && typeof value === 'string') {
      var parts = value.split('-');
      if (parts.length === 3) {
        parsed = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
      }
    }
    return isNaN(parsed.getTime()) ? null : parsed;
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
