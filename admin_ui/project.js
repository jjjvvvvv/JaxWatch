(function () {
  var DATA_PATH = 'data/projects_index.json';

  var elements = {};
  var projectId = getQueryParam('id');

  function initDomRefs() {
    elements.title = $('#project-title');
    elements.status = $('#detail-status');
    elements.content = $('#detail-content');
  }

  function getQueryParam(key) {
    var params = new URLSearchParams(window.location.search);
    return params.get(key);
  }

  function loadProject() {
    if (!projectId) {
      showError('⚠️ Missing project id in URL.');
      return;
    }

    $.getJSON(DATA_PATH)
      .done(function (data) {
        if (!Array.isArray(data)) {
          showDataError();
          return;
        }

        var project = data.find(function (item) {
          return item && String(item.id) === projectId;
        });

        if (!project) {
          showError('⚠️ Project not found: ' + escapeHtml(projectId));
          return;
        }

        renderProject(project);
      })
      .fail(function () {
        showDataError();
      });
  }

  function showDataError() {
    console.error('Jacksonville Observer admin: ERROR – no valid projects_index.json found.');
    showError('⚠️ No project data available. Please copy outputs/projects/projects_index.json into admin_ui/data/ before running.');
  }

  function showError(message) {
    elements.status.text(message).show();
    elements.content.attr('hidden', true).empty();
    elements.title.text('Project Detail');
  }

  function renderProject(project) {
    elements.status.hide();
    elements.content.removeAttr('hidden');

    // Enhanced Header
    var name = project.name || project.title || project.id || '';
    elements.title.text(name);

    var importanceScore = project.importance_score || 0;
    var importanceLabel = importanceScore >= 50 ? 'High' : (importanceScore >= 20 ? 'Medium' : 'Low');
    var importanceClass = importanceScore >= 50 ? 'high' : (importanceScore >= 20 ? 'medium' : 'low');

    var headerMeta = [
      '<span class="badge importance-' + importanceClass + '">Priority: ' + importanceLabel + '</span>',
      '<span class="badge doc-type">' + (project.doc_type || 'Project') + '</span>',
      '<span class="badge status-' + (project.status || 'active') + '">' + (project.status || 'Active') + '</span>'
    ].join(' ');

    var financialsHtml = '';
    if (project.top_financials && project.top_financials.length > 0) {
      financialsHtml = '<div class="financial-summary"><strong>Mentioned Amounts:</strong> ' +
        project.top_financials.join(', ') + '</div>';
    }

    // Metadata Grid
    var metaItems = [
      { label: 'Canonical ID', value: project.id },
      { label: 'Last Mentioned', value: project.last_mentioned || project.meeting_date || '—' },
      { label: 'Total Mentions', value: (project.mentions ? project.mentions.length : 0) },
      { label: 'Money Mentioned', value: project.money_mentioned ? 'Yes' : 'No' }
    ];

    var metaHtml = '<ul class="detail-meta">' + metaItems.map(function (item) {
      return (
        '<li>' +
        '<span class="label">' + escapeHtml(item.label) + '</span>' +
        '<span class="value">' + escapeHtml(item.value) + '</span>' +
        '</li>'
      );
    }).join('') + '</ul>';

    // Primary Sources (Mentions)
    var mentions = project.mentions || [];
    var sourcesHtml = '';

    if (mentions.length) {
      sourcesHtml = '<div class="sources-list">' + mentions.map(function (m) {
        var pageTag = m.page && m.page > 0 ? '<span class="page-tag">Page ' + m.page + '</span>' : '';
        var financialTag = m.financials && m.financials.length ?
          '<div class="financial-tag">💵 ' + m.financials.join(', ') + '</div>' : '';
        var docLink = m.url ? '<a href="' + m.url + '" target="_blank" class="doc-link">View Document</a>' : '';

        return '<div class="source-card">' +
          '<div class="source-header">' +
          '<strong>' + escapeHtml(m.meeting_date || '') + '</strong> ' +
          '<span class="source-type">' + escapeHtml(m.doc_type || 'Document') + '</span>' +
          '</div>' +
          '<h4>' + escapeHtml(m.title || m.meeting_title || 'Untitled Source') + '</h4>' +
          '<div class="source-meta">' +
          pageTag +
          docLink +
          '</div>' +
          '<blockquote class="snippet">' +
          escapeHtml(m.snippet || '') +
          '</blockquote>' +
          financialTag +
          '</div>';
      }).join('') + '</div>';
    } else {
      sourcesHtml = '<p>No sources found.</p>';
    }

    elements.content.html(
      '<div class="project-header-block">' +
      headerMeta +
      '<p class="project-desc">' + escapeHtml(project.summary || 'No description available.') + '</p>' +
      financialsHtml +
      '</div>' +
      metaHtml +
      '<h3>Primary Sources & Traceability</h3>' +
      sourcesHtml
    );
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
    loadProject();
  });
})();
