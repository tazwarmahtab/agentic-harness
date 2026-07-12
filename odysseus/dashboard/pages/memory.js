/**
 * Memory Page — enhanced 3-layer memory explorer with search and details.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

let _searchTerm = '';
let _selectedLayer = null;

export function render(container) {
  container.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Memory Explorer';
  header.appendChild(title);
  container.appendChild(header);

  // Search bar
  const search = document.createElement('div');
  search.className = 'aos-search-bar';
  const searchInput = document.createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = 'Search memories...';
  searchInput.className = 'aos-search-input';
  searchInput.addEventListener('input', (e) => {
    _searchTerm = e.target.value.toLowerCase();
    renderContent(content, store.state.memory);
  });
  search.appendChild(searchInput);
  container.appendChild(search);

  // Layer tabs
  const tabs = document.createElement('div');
  tabs.className = 'aos-layer-tabs';
  ['all', 'long_term', 'episodic', 'semantic'].forEach((layer) => {
    const tab = document.createElement('button');
    tab.className = `aos-layer-tab${_selectedLayer === layer || (!_selectedLayer && layer === 'all') ? ' active' : ''}`;
    tab.textContent = layer === 'all' ? 'All Layers' : layer.replace('_', '-');
    tab.addEventListener('click', () => {
      _selectedLayer = layer === 'all' ? null : layer;
      tabs.querySelectorAll('.aos-layer-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      renderContent(content, store.state.memory);
    });
    tabs.appendChild(tab);
  });
  container.appendChild(tabs);

  // Content area
  const content = document.createElement('div');
  content.className = 'aos-memory-content';
  container.appendChild(content);

  // Stats bar
  const stats = document.createElement('div');
  stats.className = 'aos-memory-stats';
  container.appendChild(stats);

  const unsub = store.subscribe((state) => {
    renderContent(content, state.memory);
    renderStats(stats, state.memory);
  });
  store.loadMemory();
  return unsub;
}

function renderContent(container, memory) {
  container.innerHTML = '';
  if (!memory) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'Loading memory data...';
    container.appendChild(empty);
    return;
  }

  // Layer cards with counts
  const layers = [
    { key: 'long_term', label: 'Long-Term Memory', icon: '📚', desc: 'Persistent knowledge and facts' },
    { key: 'episodic', label: 'Episodic Memory', icon: '📅', desc: 'Events, interactions, experiences' },
    { key: 'semantic', label: 'Semantic Memory', icon: '🧩', desc: 'Concepts, relationships, meanings' },
  ];

  const grid = document.createElement('div');
  grid.className = 'aos-memory-grid';

  layers.forEach(({ key, label, icon, desc }) => {
    if (_selectedLayer && _selectedLayer !== key) return;

    const data = memory[key] || {};
    const entries = data.entries || [];
    const count = data.count ?? entries.length ?? 0;

    const card = document.createElement('div');
    card.className = 'aos-memory-card';
    card.dataset.layer = key;

    const cardHeader = document.createElement('div');
    cardHeader.className = 'aos-memory-card-header';

    const cardIcon = document.createElement('div');
    cardIcon.className = 'aos-memory-icon';
    cardIcon.textContent = icon;

    const cardInfo = document.createElement('div');
    cardInfo.className = 'aos-memory-card-info';

    const cardLabel = document.createElement('div');
    cardLabel.className = 'aos-memory-label';
    cardLabel.textContent = label;

    const cardDesc = document.createElement('div');
    cardDesc.className = 'aos-memory-desc';
    cardDesc.textContent = desc;

    const countEl = document.createElement('div');
    countEl.className = 'aos-memory-count';
    countEl.textContent = String(count);

    cardInfo.appendChild(cardLabel);
    cardInfo.appendChild(cardDesc);
    cardHeader.appendChild(cardIcon);
    cardHeader.appendChild(cardInfo);
    cardHeader.appendChild(countEl);
    card.appendChild(cardHeader);

    // Entry list (filtered by search)
    if (entries.length) {
      const list = document.createElement('div');
      list.className = 'aos-memory-entries';

      const filtered = _searchTerm
        ? entries.filter((e) => {
            const text = JSON.stringify(e).toLowerCase();
            return text.includes(_searchTerm);
          })
        : entries.slice(0, 10); // Show first 10 by default

      filtered.forEach((entry) => {
        const item = document.createElement('div');
        item.className = 'aos-memory-entry';

        const content = document.createElement('div');
        content.className = 'aos-memory-entry-content';
        content.textContent = typeof entry === 'string' ? entry : (entry.content || entry.text || JSON.stringify(entry).slice(0, 150));

        if (entry.timestamp) {
          const ts = document.createElement('div');
          ts.className = 'aos-memory-entry-time';
          ts.textContent = entry.timestamp;
          item.appendChild(ts);
        }

        item.appendChild(content);
        list.appendChild(item);
      });

      if (_searchTerm && filtered.length === 0) {
        const noMatch = document.createElement('div');
        noMatch.className = 'aos-empty';
        noMatch.textContent = `No memories matching "${_searchTerm}"`;
        list.appendChild(noMatch);
      }

      card.appendChild(list);
    }

    grid.appendChild(card);
  });

  container.appendChild(grid);

  // Growth visualization (simple bar chart)
  if (memory.growth) {
    const growthSection = document.createElement('div');
    growthSection.className = 'aos-section';
    const growthTitle = document.createElement('h4');
    growthTitle.className = 'aos-section-subtitle';
    growthTitle.textContent = 'Memory Growth';
    growthSection.appendChild(growthTitle);

    const chart = document.createElement('div');
    chart.className = 'aos-growth-chart';
    renderGrowthChart(chart, memory.growth);
    growthSection.appendChild(chart);
    container.appendChild(growthSection);
  }
}

function renderGrowthChart(container, growth) {
  container.innerHTML = '';
  const entries = Object.entries(growth).slice(-12); // Last 12 data points
  if (!entries.length) return;

  const maxVal = Math.max(...entries.map(([, v]) => v || 0), 1);

  entries.forEach(([period, count]) => {
    const bar = document.createElement('div');
    bar.className = 'aos-growth-bar';

    const fill = document.createElement('div');
    fill.className = 'aos-growth-fill';
    fill.style.height = `${((count || 0) / maxVal) * 100}%`;

    const label = document.createElement('div');
    label.className = 'aos-growth-label';
    label.textContent = period;

    const value = document.createElement('div');
    value.className = 'aos-growth-value';
    value.textContent = String(count || 0);

    bar.appendChild(fill);
    bar.appendChild(label);
    bar.appendChild(value);
    container.appendChild(bar);
  });
}

function renderStats(container, memory) {
  container.innerHTML = '';
  if (!memory) return;

  const total = memory.total ?? 0;
  const rows = [
    { label: 'Total Entries', value: String(total) },
    { label: 'Long-Term', value: String(memory.long_term?.count ?? 0) },
    { label: 'Episodic', value: String(memory.episodic?.count ?? 0) },
    { label: 'Semantic', value: String(memory.semantic?.count ?? 0) },
  ];

  rows.forEach(({ label, value }) => {
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
