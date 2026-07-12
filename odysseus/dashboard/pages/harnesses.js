/**
 * Harnesses Page — grid of harness cards with live status and launch ability.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';
import ws from '../services/websocket.js';

let _unsubWs = null;

export function render(container) {
  container.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'aos-section-header';

  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Harnesses';

  const refreshBtn = document.createElement('button');
  refreshBtn.className = 'aos-btn aos-btn-ghost';
  refreshBtn.textContent = '↻ Refresh';
  refreshBtn.addEventListener('click', () => store.loadHarnesses());

  header.appendChild(title);
  header.appendChild(refreshBtn);
  container.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'aos-harness-grid';
  grid.id = 'aos-harness-grid';
  container.appendChild(grid);

  // Live log
  const logSection = document.createElement('div');
  logSection.className = 'aos-section';
  logSection.style.marginTop = '1rem';

  const logTitle = document.createElement('h3');
  logTitle.className = 'aos-section-title';
  logTitle.textContent = 'Live Execution Stream';
  logSection.appendChild(logTitle);

  const log = document.createElement('div');
  log.className = 'aos-execution-log';
  log.id = 'aos-execution-log';
  logSection.appendChild(log);
  container.appendChild(logSection);

  const unsub = store.subscribe((state) => {
    renderHarnessGrid(grid, state.harnesses, log);
  });

  // WebSocket live events
  _unsubWs = ws.on('node_update', (data) => {
    addLogEntry(log, data.node, 'info', data.state_diff);
  });
  ws.on('completed', (data) => {
    addLogEntry(log, `Completed: ${data.state_summary?.cycle_id || 'cycle'}`, 'success');
    store.loadHarnesses();
    store.loadDashboard();
  });
  ws.on('error', (data) => {
    addLogEntry(log, `Error: ${data.message}`, 'error');
  });

  store.loadHarnesses();

  return () => {
    unsub();
    if (_unsubWs) _unsubWs();
    ws.disconnect();
  };
}

function renderHarnessGrid(grid, harnesses, log) {
  grid.innerHTML = '';
  if (!harnesses.length) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No harnesses discovered';
    grid.appendChild(empty);
    return;
  }

  harnesses.forEach((h) => {
    const card = document.createElement('div');
    card.className = 'aos-harness-card';
    card.dataset.harness = h.name;

    const dot = document.createElement('div');
    dot.className = 'aos-card-dot';

    const name = document.createElement('div');
    name.className = 'aos-card-name';
    name.textContent = h.name;

    const id = document.createElement('div');
    id.className = 'aos-card-id';
    id.textContent = h.id;

    const venture = document.createElement('div');
    venture.className = 'aos-card-venture';
    venture.textContent = h.venture || '—';

    const arrow = document.createElement('div');
    arrow.className = 'aos-card-arrow';
    arrow.textContent = '→';

    card.appendChild(dot);
    card.appendChild(name);
    card.appendChild(id);
    card.appendChild(venture);
    card.appendChild(arrow);

    card.addEventListener('click', () => launchHarness(h.name, card, log));
    grid.appendChild(card);
  });
}

function launchHarness(name, card, log) {
  if (ws.isConnected) {
    addLogEntry(log, 'Execution in progress — please wait.', 'warning');
    return;
  }

  card.classList.add('aos-running');
  const dot = card.querySelector('.aos-card-dot');
  if (dot) dot.classList.add('active');

  addLogEntry(log, `Launching ${name}...`, 'info');
  ws.connect(name);
}

function addLogEntry(log, message, type = 'info', detail = null) {
  const entry = document.createElement('div');
  entry.className = `aos-log-entry aos-log-${type}`;

  const ts = document.createElement('span');
  ts.className = 'aos-log-time';
  ts.textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });

  const msg = document.createElement('span');
  msg.className = 'aos-log-msg';
  msg.textContent = message;

  entry.appendChild(ts);
  entry.appendChild(msg);

  if (detail) {
    const detailEl = document.createElement('div');
    detailEl.className = 'aos-log-detail';
    detailEl.textContent = typeof detail === 'string' ? detail : JSON.stringify(detail).slice(0, 120);
    entry.appendChild(detailEl);
  }

  log.prepend(entry);
  while (log.children.length > 100) log.lastChild.remove();
}
