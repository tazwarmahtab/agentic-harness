/**
 * Events Page — filterable event timeline.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Event Log';
  header.appendChild(title);
  container.appendChild(header);

  const filterBar = document.createElement('div');
  filterBar.className = 'aos-filter-bar';
  const filterLabel = document.createElement('span');
  filterLabel.textContent = 'Filter: ';
  filterBar.appendChild(filterLabel);
  const allBtn = createFilterBtn('all', 'All', true);
  filterBar.appendChild(allBtn);
  const types = ['memory', 'tool', 'approval', 'pipeline', 'system', 'sales', 'entity', 'error', 'agent'];
  types.forEach((t) => filterBar.appendChild(createFilterBtn(t, t)));
  container.appendChild(filterBar);

  const timeline = document.createElement('div');
  timeline.className = 'aos-event-timeline';
  container.appendChild(timeline);

  let activeFilter = 'all';

  function createFilterBtn(type, label, active = false) {
    const btn = document.createElement('button');
    btn.className = `aos-filter-btn${active ? ' active' : ''}`;
    btn.textContent = label;
    btn.addEventListener('click', () => {
      activeFilter = type;
      filterBar.querySelectorAll('.aos-filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      renderEvents(timeline, store.state.events, type);
    });
    return btn;
  }

  const unsub = store.subscribe((state) => {
    renderEvents(timeline, state.events, activeFilter);
  });
  store.loadEvents();
  return unsub;
}

function renderEvents(container, events, filter) {
  container.innerHTML = '';
  const list = events?.by_type || events?.events || events || [];
  const items = Array.isArray(list) ? list : Object.entries(list).map(([type, count]) => ({ type, count }));

  const filtered = filter === 'all' ? items : items.filter((e) => (e.type || e.event_type) === filter);

  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = filter === 'all' ? 'No events recorded' : `No ${filter} events`;
    container.appendChild(empty);
    return;
  }

  filtered.forEach((event) => {
    const entry = document.createElement('div');
    entry.className = 'aos-event-entry';

    const type = document.createElement('span');
    type.className = 'aos-event-type';
    type.textContent = event.type || event.event_type || 'unknown';

    const count = document.createElement('span');
    count.className = 'aos-event-count';
    count.textContent = event.count != null ? `×${event.count}` : '';

    entry.appendChild(type);
    entry.appendChild(count);
    container.appendChild(entry);
  });
}
