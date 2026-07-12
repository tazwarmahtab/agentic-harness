/**
 * Entities Page — entity index breakdown.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Entity Explorer';
  header.appendChild(title);
  container.appendChild(header);

  const content = document.createElement('div');
  content.className = 'aos-entity-content';
  container.appendChild(content);

  const unsub = store.subscribe((state) => {
    renderEntities(content, state.entityIndex);
  });
  store.loadEntityIndex();
  return unsub;
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
