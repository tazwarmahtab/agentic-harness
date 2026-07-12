/**
 * AOS Dashboard — main entry point.
 * Exports openPanel() / closePanel() for Odysseus ModalManager integration.
 *
 * Usage in Odysseus app.js:
 *   import aosDashboard from './dashboard/index.js';
 *   Modals.register('aos-dashboard-modal', {
 *     railBtnId: 'rail-aos',
 *     restoreFn: () => aosDashboard.openPanel(),
 *     closeFn:   () => aosDashboard.closePanel(),
 *   });
 *   _routeOpen['/aos'] = () => { _collapseSidebarToRail(); aosDashboard.openPanel(); };
 */

import store from './stores/dashboard.js';
import ws from './services/websocket.js';
import { renderLayout, getContentEl, highlightNav } from './layouts/dashboard-layout.js';

import * as overviewPage from './pages/overview.js';
import * as harnessesPage from './pages/harnesses.js';
import * as pipelinesPage from './pages/pipelines.js';
import * as approvalsPage from './pages/approvals.js';
import * as memoryPage from './pages/memory.js';
import * as entitiesPage from './pages/entities.js';
import * as eventsPage from './pages/events.js';
import * as salesPage from './pages/sales.js';
import * as systemPage from './pages/system.js';

const PAGES = {
  overview:   overviewPage,
  harnesses:  harnessesPage,
  pipelines:  pipelinesPage,
  approvals:  approvalsPage,
  memory:     memoryPage,
  entities:   entitiesPage,
  events:     eventsPage,
  sales:      salesPage,
  system:     systemPage,
};

let _isOpen = false;
let _currentUnsub = null;
let _storeUnsub = null;

function _ensurePanel() {
  let modal = document.getElementById('aos-dashboard-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'aos-dashboard-modal';
    modal.className = 'modal hidden';
    const content = document.createElement('div');
    content.className = 'modal-content aos-dashboard-modal-content';
    content.id = 'aos-dashboard-root';
    modal.appendChild(content);
    document.body.appendChild(modal);
  }
  return modal;
}

function _renderCurrentPage(page) {
  const contentEl = getContentEl();
  if (!contentEl) return;

  // Unsubscribe from previous page
  if (_currentUnsub) {
    _currentUnsub();
    _currentUnsub = null;
  }

  // Disconnect WebSocket when switching pages
  ws.disconnect();

  const pageModule = PAGES[page];
  if (pageModule?.render) {
    _currentUnsub = pageModule.render(contentEl);
  } else {
    contentEl.textContent = `Page "${page}" not found`;
  }

  highlightNav(page);
}

export function openPanel() {
  if (_isOpen) return;
  _isOpen = true;

  const modal = _ensurePanel();
  modal.classList.remove('hidden');

  const root = document.getElementById('aos-dashboard-root');
  renderLayout(root);

  // Subscribe to page changes
  _storeUnsub = store.subscribe((state) => {
    if (state.currentPage) _renderCurrentPage(state.currentPage);
  });

  // Initial page render
  _renderCurrentPage(store.state.currentPage || 'overview');

  // Start auto-refresh
  store.startAutoRefresh(30000);
  store.loadDashboard();
}

export function closePanel() {
  if (!_isOpen) return;
  _isOpen = false;

  if (_currentUnsub) { _currentUnsub(); _currentUnsub = null; }
  if (_storeUnsub) { _storeUnsub(); _storeUnsub = null; }

  ws.disconnect();
  store.stopAutoRefresh();

  const modal = document.getElementById('aos-dashboard-modal');
  if (modal) modal.classList.add('hidden');

  // Restore sidebar if Odysseus helper exists
  if (window._restoreSidebarIfRouteCollapsed) {
    window._restoreSidebarIfRouteCollapsed();
  }
}

export function isOpen() { return _isOpen; }

export default { openPanel, closePanel, isOpen };
