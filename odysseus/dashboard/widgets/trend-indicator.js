/**
 * Trend Indicator widget — renders an arrow with color based on trend direction.
 * Uses textContent for XSS safety.
 *
 * @param {number} value - Trend percentage (positive = up, negative = down)
 * @param {string} label - Optional label text
 * @returns {HTMLElement} DOM element with trend arrow and text
 */
export function renderTrendIndicator(value, icons, colors) {
  const el = document.createElement('span');
  el.className = 'aos-trend-indicator';

  const direction = value > 0 ? 'up' : value < 0 ? 'down' : 'flat';
  const arrow = icons?.[direction] || (value > 0 ? '↑' : value < 0 ? '↓' : '→');
  const color = colors?.[direction] || '#6B7280';

  el.textContent = arrow;
  el.style.color = color;
  el.style.fontWeight = 'bold';
  el.style.marginRight = '4px';

  return el;
}
