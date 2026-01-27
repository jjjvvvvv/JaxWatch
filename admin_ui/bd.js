/**
 * JaxWatch BD Radar - Dashboard JS
 */

// Data paths
const DATA_PATHS = {
  projects: 'data/projects.json',
  signals: 'data/signals.json',
  meetings: 'data/meetings.json'
};

// Jacksonville downtown coordinates
const JAX_CENTER = [30.3271, -81.6556];

// Signal emoji mapping
const SIGNAL_EMOJI = {
  big_money: { emoji: '💰', label: 'Big Money' },
  active_incentives: { emoji: '🎯', label: 'Active Incentives' },
  complexity: { emoji: '🔧', label: 'Complex Project' },
  trouble: { emoji: '⚠️', label: 'Trouble Signs' },
  new_opportunity: { emoji: '🆕', label: 'New Opportunity' }
};

// Known project locations (geocoded addresses for Jacksonville)
const PROJECT_LOCATIONS = {
  'baptist-hotel': { lat: 30.3155, lng: -81.6591, name: 'Baptist Hotel' },
  'regions-bank': { lat: 30.3271, lng: -81.6556, name: 'Regions Bank' },
  'mosh-demolition': { lat: 30.3230, lng: -81.6610, name: 'MOSH' },
  'riverfront-plaza': { lat: 30.3245, lng: -81.6580, name: 'Riverfront Plaza' },
  'gateway-n7': { lat: 30.3320, lng: -81.6620, name: 'Gateway N7' },
  'former-courthouse': { lat: 30.3280, lng: -81.6540, name: 'Former Courthouse' },
  'duval-212': { lat: 30.3290, lng: -81.6570, name: 'Duval 212' },
  '231-north-laura': { lat: 30.3295, lng: -81.6555, name: '231 N Laura St' },
  '44-w-monroe': { lat: 30.3285, lng: -81.6545, name: '44 W Monroe St' }
};

// State
let projectsData = {};
let signalsData = {};
let meetingsData = [];
let map = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  initMap();
  await loadData();
  renderDashboard();
  setupEventListeners();
});

// Initialize Leaflet map
function initMap() {
  map = L.map('project-map').setView(JAX_CENTER, 14);

  // Dark tile layer
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 19
  }).addTo(map);
}

// Load data from JSON files
async function loadData() {
  try {
    // Load projects
    const projectsRes = await fetch(DATA_PATHS.projects);
    if (projectsRes.ok) {
      projectsData = await projectsRes.json();
    }

    // Load signals
    const signalsRes = await fetch(DATA_PATHS.signals);
    if (signalsRes.ok) {
      signalsData = await signalsRes.json();
    }

    // Load meetings (may not exist yet)
    try {
      const meetingsRes = await fetch(DATA_PATHS.meetings);
      if (meetingsRes.ok) {
        meetingsData = await meetingsRes.json();
      }
    } catch (e) {
      // Meetings file may not exist
      meetingsData = [];
    }
  } catch (err) {
    console.error('Failed to load data:', err);
  }
}

// Render the full dashboard
function renderDashboard() {
  renderStats();
  renderMap();
  renderMeetings();
  renderHotOpportunities();
  renderAllProjects();
}

// Render stats cards
function renderStats() {
  const projects = projectsData.projects || {};
  const projectList = Object.values(projects);

  document.getElementById('total-projects').textContent = projectList.length;

  // Count hot opportunities (projects with signals)
  const hotCount = projectList.filter(p => p.bd_signals && p.bd_signals.length > 0).length;
  document.getElementById('hot-count').textContent = hotCount;

  // Sum investments
  let totalInvestment = 0;
  projectList.forEach(p => {
    if (p.total_investment) {
      const match = p.total_investment.match(/\$?([\d,.]+)\s*(million|m)?/i);
      if (match) {
        let amount = parseFloat(match[1].replace(/,/g, ''));
        if (match[2] && match[2].toLowerCase().startsWith('m')) {
          amount *= 1000000;
        }
        totalInvestment += amount;
      }
    }
  });

  document.getElementById('total-investment').textContent = totalInvestment > 0
    ? formatMoney(totalInvestment)
    : '-';

  // Last updated
  if (projectsData.updated_at) {
    const date = new Date(projectsData.updated_at);
    document.getElementById('last-updated').textContent = date.toLocaleDateString();
  }
}

// Render map markers
function renderMap() {
  const projects = projectsData.projects || {};

  // Clear existing markers
  map.eachLayer(layer => {
    if (layer instanceof L.Marker) {
      map.removeLayer(layer);
    }
  });

  Object.entries(projects).forEach(([id, project]) => {
    // Try to find location
    let location = PROJECT_LOCATIONS[id];

    // Fuzzy match by name
    if (!location) {
      const nameKey = Object.keys(PROJECT_LOCATIONS).find(key =>
        project.name.toLowerCase().includes(key.replace(/-/g, ' ')) ||
        key.includes(project.name.toLowerCase().replace(/\s+/g, '-'))
      );
      if (nameKey) location = PROJECT_LOCATIONS[nameKey];
    }

    // Default to downtown with slight offset
    if (!location) {
      location = {
        lat: JAX_CENTER[0] + (Math.random() - 0.5) * 0.01,
        lng: JAX_CENTER[1] + (Math.random() - 0.5) * 0.01
      };
    }

    // Determine marker color
    const isHot = project.bd_signals && project.bd_signals.length > 0;
    const markerColor = isHot ? '#f59e0b' : '#38bdf8';

    // Create custom icon
    const icon = L.divIcon({
      className: 'custom-marker',
      html: `<div style="
        width: 12px;
        height: 12px;
        background: ${markerColor};
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 0 ${isHot ? '10px' : '4px'} ${markerColor};
      "></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8]
    });

    const marker = L.marker([location.lat, location.lng], { icon }).addTo(map);

    // Popup content
    const signals = (project.bd_signals || []).map(s => SIGNAL_EMOJI[s]?.emoji || '').join(' ');
    marker.bindPopup(`
      <div class="popup-title">${signals} ${project.name}</div>
      <div class="popup-meta">${project.developer || 'Unknown developer'}</div>
      ${project.total_investment ? `<div class="popup-meta">${project.total_investment}</div>` : ''}
    `);

    marker.on('click', () => showProjectModal(id));
  });
}

// Render recent meetings
function renderMeetings() {
  const container = document.getElementById('recent-meetings');
  const projects = projectsData.projects || {};

  // Group projects by meeting date
  const meetingsByDate = {};
  Object.entries(projects).forEach(([id, project]) => {
    (project.mentions || []).forEach(mention => {
      const date = mention.date;
      if (!meetingsByDate[date]) {
        meetingsByDate[date] = {
          date,
          source: mention.source,
          projects: []
        };
      }
      meetingsByDate[date].projects.push({
        id,
        name: project.name,
        hot: project.bd_signals && project.bd_signals.length > 0,
        url: mention.url
      });
    });
  });

  // Sort by date descending
  const sortedMeetings = Object.values(meetingsByDate)
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 5);

  if (sortedMeetings.length === 0) {
    container.innerHTML = '<p class="muted">No recent meetings found</p>';
    return;
  }

  container.innerHTML = sortedMeetings.map(meeting => `
    <div class="meeting-card">
      <div class="meeting-date">${formatDate(meeting.date)}</div>
      <div class="meeting-title">${formatSourceName(meeting.source)} Meeting</div>
      <div class="meeting-projects">
        ${meeting.projects.map(p => `
          <span class="project-tag ${p.hot ? 'hot' : ''}" onclick="showProjectModal('${p.id}')">${p.name}</span>
        `).join('')}
      </div>
    </div>
  `).join('');
}

// Render hot opportunities
function renderHotOpportunities() {
  const container = document.getElementById('hot-opportunities');
  const projects = projectsData.projects || {};

  // Filter to projects with signals
  const hotProjects = Object.entries(projects)
    .filter(([id, p]) => p.bd_signals && p.bd_signals.length > 0)
    .sort((a, b) => (b[1].bd_signals?.length || 0) - (a[1].bd_signals?.length || 0))
    .slice(0, 6);

  if (hotProjects.length === 0) {
    container.innerHTML = '<p class="muted">No hot opportunities detected</p>';
    return;
  }

  container.innerHTML = hotProjects.map(([id, project]) => `
    <div class="project-card hot" onclick="showProjectModal('${id}')">
      <div class="card-header">
        <h3 class="card-title">${project.name}</h3>
        <div class="signals-badges">
          ${(project.bd_signals || []).map(s =>
            `<span class="signal-badge" title="${SIGNAL_EMOJI[s]?.label || s}">${SIGNAL_EMOJI[s]?.emoji || ''}</span>`
          ).join('')}
        </div>
      </div>
      <div class="card-meta">${project.developer || 'Unknown developer'}</div>
      ${project.total_investment ? `<div class="card-investment">${project.total_investment}</div>` : ''}
      ${project.incentives && project.incentives.length > 0 ? `
        <div class="card-incentives">
          ${project.incentives.slice(0, 3).map(inc => `
            <span class="incentive-tag">${formatIncentiveType(inc.type)} ${inc.amount || ''}</span>
          `).join('')}
        </div>
      ` : ''}
      <div class="card-footer">
        <span>First seen: ${project.first_seen || '-'}</span>
        <span>${project.stage || '-'}</span>
      </div>
    </div>
  `).join('');
}

// Render all projects table
function renderAllProjects(filter = '') {
  const container = document.getElementById('all-projects');
  const projects = projectsData.projects || {};
  const typeFilter = document.getElementById('type-filter').value;

  let projectList = Object.entries(projects);

  // Apply search filter
  if (filter) {
    const lowerFilter = filter.toLowerCase();
    projectList = projectList.filter(([id, p]) =>
      p.name.toLowerCase().includes(lowerFilter) ||
      (p.developer || '').toLowerCase().includes(lowerFilter)
    );
  }

  // Apply type filter
  if (typeFilter) {
    projectList = projectList.filter(([id, p]) => p.type === typeFilter);
  }

  // Sort by last updated
  projectList.sort((a, b) => (b[1].last_updated || '').localeCompare(a[1].last_updated || ''));

  document.getElementById('result-count').textContent = `${projectList.length} projects`;

  if (projectList.length === 0) {
    container.innerHTML = '<div class="empty-state">No projects found</div>';
    return;
  }

  container.innerHTML = `
    <table class="projects-table">
      <thead>
        <tr>
          <th>Project</th>
          <th>Developer</th>
          <th>Type</th>
          <th>Investment</th>
          <th>Stage</th>
          <th>Signals</th>
        </tr>
      </thead>
      <tbody>
        ${projectList.map(([id, p]) => `
          <tr onclick="showProjectModal('${id}')">
            <td class="project-name">${p.name}</td>
            <td>${p.developer || '-'}</td>
            <td>${p.type || '-'}</td>
            <td>${p.total_investment || '-'}</td>
            <td>${p.stage || '-'}</td>
            <td class="signals">
              ${(p.bd_signals || []).map(s =>
                `<span title="${SIGNAL_EMOJI[s]?.label || s}">${SIGNAL_EMOJI[s]?.emoji || ''}</span>`
              ).join('')}
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

// Show project modal
function showProjectModal(projectId) {
  const projects = projectsData.projects || {};
  const project = projects[projectId];

  if (!project) return;

  const modal = document.getElementById('project-modal');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');

  const signals = (project.bd_signals || []).map(s =>
    `<span title="${SIGNAL_EMOJI[s]?.label || s}">${SIGNAL_EMOJI[s]?.emoji || ''}</span>`
  ).join(' ');

  title.innerHTML = `${signals} ${project.name}`;

  body.innerHTML = `
    <div class="detail-grid">
      <div class="detail-item">
        <div class="detail-label">Developer</div>
        <div class="detail-value">${project.developer || 'Unknown'}</div>
      </div>
      <div class="detail-item">
        <div class="detail-label">Project Type</div>
        <div class="detail-value">${project.type || '-'}</div>
      </div>
      <div class="detail-item">
        <div class="detail-label">Stage</div>
        <div class="detail-value">${project.stage || '-'}</div>
      </div>
      <div class="detail-item">
        <div class="detail-label">Location</div>
        <div class="detail-value">${project.location || '-'}</div>
      </div>
      <div class="detail-item" style="grid-column: span 2">
        <div class="detail-label">Total Investment</div>
        <div class="detail-value large">${project.total_investment || 'Not specified'}</div>
      </div>
    </div>

    ${project.incentives && project.incentives.length > 0 ? `
      <div class="detail-section">
        <h3>Incentives</h3>
        <div class="card-incentives">
          ${project.incentives.map(inc => `
            <span class="incentive-tag">
              ${formatIncentiveType(inc.type)}: ${inc.amount || 'TBD'} (${inc.status || 'pending'})
            </span>
          `).join('')}
        </div>
      </div>
    ` : ''}

    ${project.mentions && project.mentions.length > 0 ? `
      <div class="detail-section">
        <h3>Timeline / Mentions</h3>
        <ul class="timeline-list">
          ${project.mentions.map(m => `
            <li class="timeline-item">
              <div class="timeline-date">${formatDate(m.date)}</div>
              <div class="timeline-action">${m.action || 'Mentioned in meeting'}</div>
              <div class="timeline-source">
                Resolution: ${m.resolution || '-'} |
                <a href="${m.url}" target="_blank">View Source Document</a>
              </div>
            </li>
          `).join('')}
        </ul>
      </div>
    ` : ''}

    <div class="detail-section">
      <h3>Metadata</h3>
      <div class="detail-grid">
        <div class="detail-item">
          <div class="detail-label">First Seen</div>
          <div class="detail-value">${project.first_seen || '-'}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">Last Updated</div>
          <div class="detail-value">${project.last_updated || '-'}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">Mention Count</div>
          <div class="detail-value">${project.mentions?.length || 0}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">Status</div>
          <div class="detail-value">${project.status || 'active'}</div>
        </div>
      </div>
    </div>
  `;

  modal.hidden = false;
}

// Close modal
function closeModal() {
  document.getElementById('project-modal').hidden = true;
}

// Setup event listeners
function setupEventListeners() {
  // Search
  document.getElementById('search-input').addEventListener('input', (e) => {
    renderAllProjects(e.target.value);
  });

  // Type filter
  document.getElementById('type-filter').addEventListener('change', () => {
    renderAllProjects(document.getElementById('search-input').value);
  });

  // Close modal on background click
  document.getElementById('project-modal').addEventListener('click', (e) => {
    if (e.target.id === 'project-modal') {
      closeModal();
    }
  });

  // Close modal on escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal();
    }
  });
}

// Utility functions
function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatMoney(amount) {
  if (amount >= 1000000000) {
    return `$${(amount / 1000000000).toFixed(1)}B`;
  } else if (amount >= 1000000) {
    return `$${(amount / 1000000).toFixed(1)}M`;
  } else if (amount >= 1000) {
    return `$${(amount / 1000).toFixed(0)}K`;
  }
  return `$${amount}`;
}

function formatSourceName(source) {
  const names = {
    'dia_board': 'DIA Board',
    'dia_ddrb': 'DDRB',
    'city_council': 'City Council',
    'planning_commission': 'Planning Commission'
  };
  return names[source] || source;
}

function formatIncentiveType(type) {
  const types = {
    'rev_grant': 'REV Grant',
    'completion_grant': 'Completion Grant',
    'loan': 'Loan',
    'tax_rebate': 'Tax Rebate',
    'land_sale': 'Land Sale'
  };
  return types[type] || type;
}

// Expose to global for onclick handlers
window.showProjectModal = showProjectModal;
window.closeModal = closeModal;
