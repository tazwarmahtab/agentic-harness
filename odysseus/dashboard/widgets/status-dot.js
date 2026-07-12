/**
 * Status Dot widget — colored indicator with label.
 * Uses textContent for safe rendering.
 */

export function getStatusColor(status) {
  const colors = {
    ok: '#22c55e',
    running: '#3b82f6',
    active: '#3b82f6',
    idle: '#6b7280',
    error: '#ef4444',
    warning: '#f59e0b',
    offline: '#6b7280',
    online: '#22c55e',
  };
  return colors[status] || '#6b7280';
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
