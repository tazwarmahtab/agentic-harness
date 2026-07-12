/**
 * Events Page — filterable, searchable event timeline with details.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

let _activeFilter = 'all';
let _searchTerm = '';
let _expandedEvent = null;

export function render(container) {
  container.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Event Log';
  header.appendChild(title);
  container.appendChild(header);

  // Search
  const search = document.createElement('div');
  search.className = 'aos-search-bar';
  const searchInput = document.createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = 'Search events...';
  searchInput.className = 'aos-search-input';
  searchInput.addEventListener('input', (e) => {
    _searchTerm = e.target.value.toLowerCase();
    renderTimeline(timeline, store.state.events);
  });
  search.appendChild(searchInput);
  container.appendChild(search);

  // Filter bar
  const filterBar = document.createElement('div');
  filterBar.className = 'aos-filter-bar';
  const types = ['all', 'memory', 'tool', 'approval', 'pipeline', 'system', 'sales', 'entity', 'error', 'agent'];
  types.forEach((t) => {
    const btn = document.createElement('button');
    btn.className = `aos-filter-btn${_activeFilter === t ? ' active' : ''}`;
    btn.textContent = t === 'all' ? 'All' : t;
    btn.addEventListener('click', () => {
      _activeFilter = t;
      filterBar.querySelectorAll('.aos-filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      renderTimeline(timeline, store.state.events);
    });
    filterBar.appendChild(btn);
  });
  container.appendChild(filterBar);

  // Event count
  const countEl = document.createElement('div');
  countEl.className = 'aos-event-count-bar';
  countEl.id = 'aos-event-count';
  container.appendChild(countEl);

  // Timeline
  const timeline = document.createElement('div');
  timeline.className = 'aos-event-timeline';
  container.appendChild(timeline);

  const unsub = store.subscribe((state) => {
    renderTimeline(timeline, state.events);
    renderCount(countEl, state.events);
  });
  store.loadEvents();
  return unsub;
}

function renderTimeline(container, events) {
  container.innerHTML = '';
  const raw = events?.events || events?.by_type || events || [];
  const items = Array.isArray(raw) ? raw : Object.entries(raw).map(([type, count]) => ({ type, count }));

  let filtered = _activeFilter === 'all' ? items : items.filter((e) => (e.type || e.event_type) === _activeFilter);

  if (_searchTerm) {
    filtered = filtered.filter((e) => {
      const text = JSON.stringify(e).toLowerCase();
      return text.includes(_searchTerm);
    });
  }

  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = _searchTerm ? `No events matching "${_searchTerm}"` : 'No events recorded';
    container.appendChild(empty);
    return;
  }

  filtered.forEach((event, idx) => {
    const entry = document.createElement('div');
    entry.className = `aos-event-entry${_expandedEvent === idx ? ' expanded' : ''}`;

    const header = document.createElement('div');
    header.className = 'aos-event-header';
    header.addEventListener('click', () => {
      _expandedEvent = _expandedEvent === idx ? null : idx;
      renderTimeline(container, events);
    });

    const type = document.createElement('span');
    type.className = 'aos-event-type';
    type.textContent = event.type || event.event_type || 'unknown';

    const badge = document.createElement('span');
    badge.className = 'aos-event-badge';
    badge.textContent = getEventBadge(event.type || event.event_type);

    const count = document.createElement('span');
    count.className = 'aos-event-count';
    count.textContent = event.count != null ? `×${event.count}` : '';

    const expandIcon = document.createElement('span');
    expandIcon.className = 'aos-event-expand';
    expandIcon.textContent = _expandedEvent === idx ? '▾' : '▸';

    header.appendChild(type);
    header.appendChild(badge);
    header.appendChild(count);
    header.appendChild(expandIcon);
    entry.appendChild(header);

    // Expanded detail
    if (_expandedEvent === idx) {
      const detail = document.createElement('div');
      detail.className = 'aos-event-detail';

      if (event.details) {
        const detailText = document.createElement('div');
        detailText.className = 'aos-event-detail-text';
        detailText.textContent = typeof event.details === 'string' ? event.details : JSON.stringify(event.details, null, 2);
        detail.appendChild(detailText);
      }

      if (event.timestamp) {
        const ts = document.createElement('div');
        ts.className = 'aos-event-timestamp';
        ts.textContent = `Time: ${event.timestamp}`;
        detail.appendChild(ts);
      }

      if (event.source) {
        const src = document.createElement('div');
        src.className = 'aos-event-source';
        src.textContent = `Source: ${event.source}`;
        detail.appendChild(src);
      }

      entry.appendChild(detail);
    }

    container.appendChild(entry);
  });
}

function renderCount(container, events) {
  container.innerHTML = '';
  const raw = events?.events || events?.by_type || events || [];
  const items = Array.isArray(raw) ? raw : Object.entries(raw).map(([type, count]) => ({ type, count }));
  const total = items.reduce((sum, e) => sum + (e.count || 1), 0);

  const countText = document.createElement('span');
  countText.className = 'aos-event-total-count';
  countText.textContent = `${total} events total`;
  container.appendChild(countText);
}

function getEventBadge(type) {
  const badges = {
    memory: '🧠', tool: '🔧', approval: '✅', pipeline: '🔄',
    system: '🖥️', sales: '💰', entity: '🕸️', error: '❌', agent: '🤖',
  };
  return badges[type] || '📋';
}
