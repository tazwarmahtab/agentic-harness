/**
 * Savings Tile — displays BDT saved with trend indicator.
 * Uses textContent for XSS safety.
 */

export function renderSavingsTile(container, { value_bdt, trend_pct, label }) {
  container.innerHTML = '';
  container.className = 'aos-kpi aos-kpi-accent';

  const iconEl = document.createElement('div');
  iconEl.className = 'aos-kpi-icon';
  iconEl.textContent = '💰';

  const valueEl = document.createElement('div');
  valueEl.className = 'aos-kpi-value';
  valueEl.textContent = `৳${Number(value_bdt).toLocaleString()}`;

  const labelEl = document.createElement('div');
  labelEl.className = 'aos-kpi-label';
  labelEl.textContent = label || 'Savings';

  container.appendChild(iconEl);
  container.appendChild(valueEl);
  container.appendChild(labelEl);

  if (trend_pct != null) {
    const trendEl = document.createElement('div');
    trendEl.className = 'aos-kpi-trend';
    const arrow = trend_pct >= 0 ? '↑' : '↓';
    const color = trend_pct >= 0 ? '#10B981' : '#EF4444';
    trendEl.textContent = `${arrow} ${Math.abs(trend_pct).toFixed(1)}%`;
    trendEl.style.color = color;
    container.appendChild(trendEl);
  }
}
