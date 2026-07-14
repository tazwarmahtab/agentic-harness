/**
 * Status Dot widget — colored indicator with label.
 * Uses textContent for safe rendering.
 */

export function getStatusColor(status) {
  const colors = {
    ok: '#10B981',
    running: '#10B981',
    active: '#10B981',
    idle: '#6E7681',
    error: '#EF4444',
    warning: '#F59E0B',
    offline: '#6E7681',
    online: '#10B981',
  };
  return colors[status] || '#6E7681';
}

export function renderStatusDot(container, status, label = '') {
  container.innerHTML = '';
  container.className = 'aos-status-indicator';

  const dot = document.createElement('span');
  dot.className = 'aos-dot';
  dot.style.backgroundColor = getStatusColor(status);

  container.appendChild(dot);

  if (label) {
    const text = document.createElement('span');
    text.className = 'aos-status-label';
    text.textContent = label;
    container.appendChild(text);
  }
}
