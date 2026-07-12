/**
 * Dashboard Layout — sidebar + header + main content area.
 * Glass-morphism design matching Odysseus aesthetic.
 */

import store from '../stores/dashboard.js';

const NAV_ITEMS = [
  { id: 'overview',     icon: '⚡', label: 'Overview' },
  { id: 'harnesses',    icon: '🔗', label: 'Harnesses' },
  { id: 'pipelines',    icon: '🔄', label: 'Pipelines' },
  { id: 'approvals',    icon: '✅', label: 'Approvals' },
  { id: 'memory',       icon: '🧠', label: 'Memory' },
  { id: 'entities',     icon: '🕸️', label: 'Entities' },
  { id: 'events',       icon: '📋', label: 'Events' },
  { id: 'sales',        icon: '💰', label: 'Sales' },
  { id: 'system',       icon: '🖥️', label: 'System' },
];

export function renderLayout(container) {
  container.innerHTML = `
    <div class="aos-dash">
      <nav class="aos-sidebar" id="aos-sidebar">
        <div class="aos-sidebar-header">
          <span class="aos-logo-icon">⚡</span>
          <span class="aos-logo-text">AOS</span>
        </div>
        <div class="aos-nav" id="aos-nav"></div>
        <div class="aos-sidebar-footer">
          <div class="aos-engine-badge" id="aos-engine-badge">
            <span class="aos-dot"></span>
            <span class="aos-dot-label">Engine</span>
          </div>
        </div>
      </nav>
      <main class="aos-main">
        <header class="aos-header" id="aos-header">
          <h1 class="aos-page-title" id="aos-page-title">Overview</h1>
          <div class="aos-header-actions">
            <span class="aos-status-text" id="aos-status-text"></span>
            <button class="aos-btn aos-btn-ghost" id="aos-refresh-btn" title="Refresh">↻</button>
          </div>
        </header>
        <div class="aos-content" id="aos-content"></div>
      </main>
    </div>
  `;

  renderNav(container.querySelector('#aos-nav'));
  bindEvents(container);
}

function renderNav(navEl) {
  navEl.innerHTML = NAV_ITEMS.map((item) => `
    <button class="aos-nav-item" data-page="${item.id}">
      <span class="aos-nav-icon">${item.icon}</span>
      <span class="aos-nav-label">${item.label}</span>
    </button>
  `).join('');

  navEl.addEventListener('click', (e) => {
    const btn = e.target.closest('.aos-nav-item');
    if (!btn) return;
    const page = btn.dataset.page;
    store.setPage(page);
    setActiveNav(page);
    document.getElementById('aos-page-title').textContent =
      NAV_ITEMS.find((n) => n.id === page)?.label || page;
  });
}

function setActiveNav(page) {
  document.querySelectorAll('.aos-nav-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.page === page);
  });
}

function bindEvents(container) {
  container.querySelector('#aos-refresh-btn')?.addEventListener('click', () => {
    store.loadDashboard();
  });

  // Update engine badge on state change
  store.subscribe((state) => {
    const badge = container.querySelector('#aos-engine-badge');
    if (badge) {
      badge.classList.toggle('online', state.engineOnline);
      badge.classList.toggle('offline', !state.engineOnline);
    }
    const status = container.querySelector('#aos-status-text');
    if (status) {
      status.textContent = state.loading ? 'Loading...' :
        state.engineOnline ? 'Online' : 'Offline';
    }
  });
}

export function getContentEl() {
  return document.getElementById('aos-content');
}

export function highlightNav(page) {
  setActiveNav(page);
}
