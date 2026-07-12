/**
 * KPI Tile widget — displays a single metric with label and optional trend.
 * Safe rendering: uses textContent for dynamic values.
 */

export function renderKpiTile(container, { label, value, accent = false, icon = '' }) {
  container.innerHTML = ''; // clear
  container.className = `aos-kpi${accent ? ' aos-kpi-accent' : ''}`;

  const iconEl = document.createElement('div');
  iconEl.className = 'aos-kpi-icon';
  iconEl.textContent = icon;

  const valueEl = document.createElement('div');
  valueEl.className = 'aos-kpi-value';
  valueEl.textContent = value ?? '—';

  const labelEl = document.createElement('div');
  labelEl.className = 'aos-kpi-label';
  labelEl.textContent = label;

  container.appendChild(iconEl);
  container.appendChild(valueEl);
  container.appendChild(labelEl);
}

export function renderKpiStrip(container, tiles) {
  container.innerHTML = '';
  container.className = 'aos-kpi-strip';
  tiles.forEach((tile) => {
    const el = document.createElement('div');
    renderKpiTile(el, tile);
    container.appendChild(el);
  });
}
