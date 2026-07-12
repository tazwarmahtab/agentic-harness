/**
 * Entities Page — entity index with graph visualization.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

let _viewMode = 'grid'; // 'grid' | 'graph'
let _selectedType = null;

export function render(container) {
  container.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Entity Explorer';
  header.appendChild(title);

  // View toggle
  const toggle = document.createElement('div');
  toggle.className = 'aos-view-toggle';
  const gridBtn = document.createElement('button');
  gridBtn.className = `aos-view-btn${_viewMode === 'grid' ? ' active' : ''}`;
  gridBtn.textContent = '▦ Grid';
  gridBtn.addEventListener('click', () => { _viewMode = 'grid'; updateView(container); });
  const graphBtn = document.createElement('button');
  graphBtn.className = `aos-view-btn${_viewMode === 'graph' ? ' active' : ''}`;
  graphBtn.textContent = '◎ Graph';
  graphBtn.addEventListener('click', () => { _viewMode = 'graph'; updateView(container); });
  toggle.appendChild(gridBtn);
  toggle.appendChild(graphBtn);
  header.appendChild(toggle);
  container.appendChild(header);

  // Content
  const content = document.createElement('div');
  content.className = 'aos-entity-content';
  container.appendChild(content);

  // Stats
  const stats = document.createElement('div');
  stats.className = 'aos-entity-stats';
  container.appendChild(stats);

  const unsub = store.subscribe((state) => {
    updateView(container);
    renderStats(stats, state.entityIndex);
  });

  function updateView() {
    renderEntityContent(content, store.state.entityIndex);
  }

  store.loadEntityIndex();
  return unsub;
}

function renderEntityContent(container, entityIndex) {
  container.innerHTML = '';
  if (!entityIndex) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'Loading entity data...';
    container.appendChild(empty);
    return;
  }

  const byType = entityIndex.by_type || {};
  const types = Object.keys(byType);

  // Type filter chips
  const chips = document.createElement('div');
  chips.className = 'aos-type-chips';
  const allChip = document.createElement('button');
  allChip.className = `aos-chip${!_selectedType ? ' active' : ''}`;
  allChip.textContent = `All (${entityIndex.total ?? 0})`;
  allChip.addEventListener('click', () => { _selectedType = null; renderEntityContent(container, entityIndex); });
  chips.appendChild(allChip);

  types.forEach((type) => {
    const chip = document.createElement('button');
    chip.className = `aos-chip${_selectedType === type ? ' active' : ''}`;
    chip.textContent = `${type} (${byType[type]})`;
    chip.addEventListener('click', () => { _selectedType = type; renderEntityContent(container, entityIndex); });
    chips.appendChild(chip);
  });
  container.appendChild(chips);

  if (_viewMode === 'grid') {
    renderGridView(container, byType, _selectedType);
  } else {
    renderGraphView(container, byType, entityIndex.total || 0);
  }
}

function renderGridView(container, byType, selectedType) {
  const grid = document.createElement('div');
  grid.className = 'aos-entity-grid';

  Object.entries(byType).forEach(([type, count]) => {
    if (selectedType && selectedType !== type) return;

    const card = document.createElement('div');
    card.className = 'aos-entity-card';
    card.dataset.type = type;

    const icon = document.createElement('div');
    icon.className = 'aos-entity-icon';
    icon.textContent = getEntityIcon(type);

    const typeName = document.createElement('div');
    typeName.className = 'aos-entity-type';
    typeName.textContent = type;

    const countEl = document.createElement('div');
    countEl.className = 'aos-entity-count';
    countEl.textContent = String(count);

    card.appendChild(icon);
    card.appendChild(typeName);
    card.appendChild(countEl);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function renderGraphView(container, byType, total) {
  const graph = document.createElement('div');
  graph.className = 'aos-entity-graph';

  // Force-directed layout approximation using CSS
  const center = document.createElement('div');
  center.className = 'aos-graph-center';
  const centerLabel = document.createElement('div');
  centerLabel.className = 'aos-graph-center-label';
  centerLabel.textContent = `AOS (${total})`;
  center.appendChild(centerLabel);

  const types = Object.entries(byType);
  const angleStep = (2 * Math.PI) / types.length;
  const radius = 140;

  types.forEach(([type, count], i) => {
    if (selectedType && selectedType !== type) return;

    const angle = angleStep * i - Math.PI / 2;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;

    const node = document.createElement('div');
    node.className = 'aos-graph-node';
    node.style.transform = `translate(${x}px, ${y}px)`;

    const nodeIcon = document.createElement('div');
    nodeIcon.className = 'aos-graph-node-icon';
    nodeIcon.textContent = getEntityIcon(type);

    const nodeLabel = document.createElement('div');
    nodeLabel.className = 'aos-graph-node-label';
    nodeLabel.textContent = type;

    const nodeCount = document.createElement('div');
    nodeCount.className = 'aos-graph-node-count';
    nodeCount.textContent = String(count);

    node.appendChild(nodeIcon);
    node.appendChild(nodeLabel);
    node.appendChild(nodeCount);

    // Connection line (SVG)
    const line = document.createElement('div');
    line.className = 'aos-graph-line';
    line.style.width = `${radius}px`;
    line.style.transform = `rotate(${(angle * 180) / Math.PI}deg)`;

    graph.appendChild(line);
    graph.appendChild(node);
  });

  graph.appendChild(center);
  container.appendChild(graph);
}

function renderStats(container, entityIndex) {
  container.innerHTML = '';
  if (!entityIndex) return;

  const total = entityIndex.total ?? 0;
  const types = Object.keys(entityIndex.by_type || {}).length;

  const stats = [
    { label: 'Total Entities', value: String(total) },
    { label: 'Entity Types', value: String(types) },
  ];

  stats.forEach(({ label, value }) => {
    const row = document.createElement('div');
    row.className = 'aos-stat-row';
    const l = document.createElement('span');
    l.className = 'aos-stat-label';
    l.textContent = label;
    const v = document.createElement('span');
    v.className = 'aos-stat-value';
    v.textContent = value;
    row.appendChild(l);
    row.appendChild(v);
    container.appendChild(row);
  });
}

function getEntityIcon(type) {
  const icons = {
    venture: '🏢', customer: '👤', project: '📁', proposal: '📄',
    contract: '📝', invoice: '💰', meeting: '📅', decision: '⚖️',
    blocker: '🚧', task: '✅', handoff: '🤝', harness: '🔗',
    agent: '🤖', memory: '🧠', workflow: '🔄', approval: '👍',
    artifact: '📦', alert: '🔔',
  };
  return icons[type] || '📌';
}
