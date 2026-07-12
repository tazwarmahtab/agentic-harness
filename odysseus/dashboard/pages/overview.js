/**
 * Overview Page — KPI tiles, health score, quick status.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';
import { renderKpiStrip } from '../widgets/kpi-tile.js';

export function render(container) {
  container.innerHTML = '';

  // KPI strip
  const kpiStrip = document.createElement('div');
  kpiStrip.className = 'aos-kpi-strip';
  container.appendChild(kpiStrip);

  // Status section
  const statusSection = document.createElement('div');
  statusSection.className = 'aos-section';
  container.appendChild(statusSection);

  const unsub = store.subscribe((state) => {
    renderKpiStrip(kpiStrip, [
      { label: 'Harnesses', value: state.harnessCount, icon: '🔗', accent: true },
      { label: 'Tests', value: state.testCount, icon: '🧪' },
      { label: 'Memory', value: state.memoryDomains, icon: '🧠' },
      { label: 'Entities', value: state.entityCount, icon: '🕸️' },
      { label: 'Events', value: state.eventCount, icon: '📋' },
      { label: 'Approvals', value: state.approvalCount, icon: '✅' },
      { label: 'WS Links', value: `${state.wsConnections}/${state.wsMaxConnections}`, icon: '🔌' },
      { label: 'Health', value: state.healthScore != null ? `${(state.healthScore * 100).toFixed(0)}%` : '—', icon: '💓' },
    ]);

    renderStatusSection(statusSection, state);
  });

  // Initial load
  store.loadDashboard();

  return unsub;
}

function renderStatusSection(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'System Status';
  container.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'aos-status-grid';

  const items = [
    { label: 'Engine', status: state.engineOnline ? 'online' : 'offline' },
    { label: 'Pipeline', status: state.pipeline ? 'active' : 'idle' },
    { label: 'Approvals', status: state.approvalCount > 0 ? 'warning' : 'ok' },
  ];

  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-status-card';

    const dot = document.createElement('span');
    dot.className = 'aos-dot';
    const dotColor = { online: '#22c55e', offline: '#ef4444', active: '#3b82f6', idle: '#6b7280', warning: '#f59e0b', ok: '#22c55e' };
    dot.style.backgroundColor = dotColor[item.status] || '#6b7280';

    const label = document.createElement('span');
    label.className = 'aos-status-label';
    label.textContent = item.label;

    const statusText = document.createElement('span');
    statusText.className = 'aos-status-value';
    statusText.textContent = item.status;

    card.appendChild(dot);
    card.appendChild(label);
    card.appendChild(statusText);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}
