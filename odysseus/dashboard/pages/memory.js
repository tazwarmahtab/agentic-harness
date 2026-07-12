/**
 * Memory Page — 3-layer memory visibility.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Memory Explorer';
  header.appendChild(title);
  container.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'aos-memory-grid';
  container.appendChild(grid);

  const unsub = store.subscribe((state) => {
    renderMemory(grid, state.memory);
  });
  store.loadMemory();
  return unsub;
}

function renderMemory(container, memory) {
  container.innerHTML = '';
  if (!memory) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No memory data available';
    container.appendChild(empty);
    return;
  }

  const layers = [
    { key: 'long_term', label: 'Long-Term', icon: '📚' },
    { key: 'episodic', label: 'Episodic', icon: '📅' },
    { key: 'semantic', label: 'Semantic', icon: '🧩' },
  ];

  layers.forEach(({ key, label, icon }) => {
    const card = document.createElement('div');
    card.className = 'aos-memory-card';

    const cardIcon = document.createElement('div');
    cardIcon.className = 'aos-memory-icon';
    cardIcon.textContent = icon;

    const cardLabel = document.createElement('div');
    cardLabel.className = 'aos-memory-label';
    cardLabel.textContent = label;

    const count = document.createElement('div');
    count.className = 'aos-memory-count';
    count.textContent = memory[key]?.count ?? memory[key] ?? '—';

    card.appendChild(cardIcon);
    card.appendChild(cardLabel);
    card.appendChild(count);
    container.appendChild(card);
  });

  if (memory.total != null) {
    const total = document.createElement('div');
    total.className = 'aos-memory-total';
    const tLabel = document.createElement('span');
    tLabel.textContent = 'Total entries: ';
    const tValue = document.createElement('strong');
    tValue.textContent = String(memory.total);
    total.appendChild(tLabel);
    total.appendChild(tValue);
    container.appendChild(total);
  }
}
