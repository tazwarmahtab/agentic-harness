/**
 * System Page — health, metrics, agents.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'System Status';
  header.appendChild(title);
  container.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'aos-system-grid';
  container.appendChild(grid);

  const agentsSection = document.createElement('div');
  agentsSection.className = 'aos-section';
  const agentsTitle = document.createElement('h3');
  agentsTitle.className = 'aos-section-title';
  agentsTitle.textContent = 'Agents';
  agentsSection.appendChild(agentsTitle);
  const agentsList = document.createElement('div');
  agentsList.className = 'aos-agents-list';
  agentsSection.appendChild(agentsList);
  container.appendChild(agentsSection);

  const unsub = store.subscribe((state) => {
    renderSystem(grid, state.system);
    renderAgents(agentsList, state.agents);
  });
  store.loadSystem();
  store.loadAgents();
  return unsub;
}

function renderSystem(container, system) {
  container.innerHTML = '';
  if (!system) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No system data available';
    container.appendChild(empty);
    return;
  }

  const metrics = [
    { key: 'cpu', label: 'CPU' },
    { key: 'memory', label: 'Memory' },
    { key: 'uptime', label: 'Uptime' },
    { key: 'ws_connections', label: 'WS Connections' },
    { key: 'api_status', label: 'API Status' },
  ];

  metrics.forEach(({ key, label }) => {
    if (system[key] == null) return;
    const card = document.createElement('div');
    card.className = 'aos-metric-card';
    const l = document.createElement('div');
    l.className = 'aos-metric-label';
    l.textContent = label;
    const v = document.createElement('div');
    v.className = 'aos-metric-value';
    v.textContent = String(system[key]);
    card.appendChild(l);
    card.appendChild(v);
    container.appendChild(card);
  });
}

function renderAgents(container, agents) {
  container.innerHTML = '';
  if (!agents.length) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No agents registered';
    container.appendChild(empty);
    return;
  }

  agents.forEach((agent) => {
    const card = document.createElement('div');
    card.className = 'aos-agent-card';

    const name = document.createElement('div');
    name.className = 'aos-agent-name';
    name.textContent = agent.name || agent.agent_id || '—';

    const status = document.createElement('div');
    status.className = 'aos-agent-status';
    status.textContent = agent.status || 'idle';

    const tokens = document.createElement('div');
    tokens.className = 'aos-agent-tokens';
    tokens.textContent = agent.tokens_used ? `${agent.tokens_used} tokens` : '';

    card.appendChild(name);
    card.appendChild(status);
    card.appendChild(tokens);
    container.appendChild(card);
  });
}

function renderEntities(container, entityIndex) {
  container.innerHTML = '';
  if (!entityIndex) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No entity data available';
    container.appendChild(empty);
    return;
  }

  const total = document.createElement('div');
  total.className = 'aos-entity-total';
  const tLabel = document.createElement('span');
  tLabel.textContent = 'Total entities: ';
  const tValue = document.createElement('strong');
  tValue.textContent = String(entityIndex.total ?? 0);
  total.appendChild(tLabel);
  total.appendChild(tValue);
  container.appendChild(total);

  const byType = entityIndex.by_type || {};
  const grid = document.createElement('div');
  grid.className = 'aos-entity-grid';

  Object.entries(byType).forEach(([type, count]) => {
    const card = document.createElement('div');
    card.className = 'aos-entity-card';
    const t = document.createElement('div');
    t.className = 'aos-entity-type';
    t.textContent = type;
    const c = document.createElement('div');
    c.className = 'aos-entity-count';
    c.textContent = String(count);
    card.appendChild(t);
    card.appendChild(c);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}
