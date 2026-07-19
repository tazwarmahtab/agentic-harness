"use strict";

/**
 * Netso Customer Savings Page — Savings breakdown, trends, and projections.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../../stores/dashboard.js';
import { renderKpiStrip } from '../../widgets/kpi-tile.js';
import { renderTrendIndicator } from '../../widgets/trend-indicator.js';
import { renderSavingsTile } from '../../widgets/savings-tile.js';

const TREND_ICONS = {
  up: '↑',
  down: '↓',
  flat: '→',
};

const TREND_COLORS = {
  up: '#10B981',
  down: '#EF4444',
  flat: '#6B7280',
};

export function render(container) {
  container.innerHTML = '';

  // KPI strip
  const kpiStrip = document.createElement('div');
  kpiStrip.className = 'aos-kpi-strip';
  container.appendChild(kpiStrip);

  // Current savings tile
  const savingsTileSection = document.createElement('div');
  savingsTileSection.className = 'aos-section';
  container.appendChild(savingsTileSection);

  // Trends section
  const trendsSection = document.createElement('div');
  trendsSection.className = 'aos-section';
  container.appendChild(trendsSection);

  // Lifetime projection
  const projectionSection = document.createElement('div');
  projectionSection.className = 'aos-section';
  container.appendChild(projectionSection);

  const unsub = store.subscribe((state) => {
    const sav = state.netsoSavings;
    if (!sav) return;

    // KPI strip
    renderKpiStrip(kpiStrip, [
      { label: 'Grid Rate', value: `৳${sav.grid_rate_bdt?.toLocaleString()}`, icon: '🔌', accent: true },
      { label: 'PPA Rate', value: `৳${sav.ppa_rate_bdt?.toLocaleString()}`, icon: '☀️' },
      { label: 'Current Savings', value: `৳${sav.current_month?.savings_bdt?.toLocaleString()}`, icon: '💰' },
      { label: 'YTD Savings', value: `৳${sav.ytd_savings_bdt?.toLocaleString()}`, icon: '📅' },
      { label: 'Savings %', value: `${sav.savings_pct?.toFixed(1)}%`, icon: '📈' },
    ]);

    // Current savings tile
    renderSavingsTileSection(savingsTileSection, sav);

    // Trends section
    renderTrendsSection(trendsSection, sav);

    // Lifetime projection
    renderProjectionSection(projectionSection, sav);
  });

  // Initial load
  store.loadNetsoSavings();

  return unsub;
}

function renderSavingsTileSection(container, sav) {
  container.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Current Month Savings';
  container.appendChild(title);

  renderSavingsTile(container, {
    savings: sav.current_month?.savings_bdt,
    trend: sav.trends?.savings,
    gridRate: sav.grid_rate_bdt,
    ppaRate: sav.ppa_rate_bdt,
  });
}

function renderTrendsSection(container, sav) {
  container.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Month-over-Month Trends';
  container.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'aos-trend-grid';

  const trends = [
    {
      label: 'Savings',
      value: sav.current_month?.savings_bdt?.toLocaleString(),
      trend: sav.trends?.savings,
      unit: '৳',
    },
    {
      label: 'Savings %',
      value: sav.savings_pct?.toFixed(1),
      trend: sav.trends?.savings_pct,
      unit: '%',
    },
  ];

  trends.forEach(({ label, value, trend, unit }) => {
    if (value === undefined || trend === undefined) return;

    const card = document.createElement('div');
    card.className = 'aos-trend-card';

    const labelEl = document.createElement('div');
    labelEl.className = 'aos-trend-label';
    labelEl.textContent = label;

    const valueEl = document.createElement('div');
    valueEl.className = 'aos-trend-value';
    valueEl.textContent = `${unit}${value}`;

    const trendEl = document.createElement('div');
    trendEl.className = 'aos-trend-indicator';
    trendEl.appendChild(renderTrendIndicator(trend, TREND_ICONS, TREND_COLORS));
    trendEl.appendChild(document.createTextNode(` ${Math.abs(trend)}%`));

    card.appendChild(labelEl);
    card.appendChild(valueEl);
    card.appendChild(trendEl);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function renderProjectionSection(container, sav) {
  container.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Lifetime Projection';
  container.appendChild(title);

  const projection = sav.lifetime_projection;
  if (!projection) return;

  const table = document.createElement('table');
  table.className = 'aos-table';
  table.innerHTML = `
    <thead>
      <tr>
        <th>Year</th>
        <th>Projected Savings (৳)</th>
        <th>Cumulative Savings (৳)</th>
      </tr>
    </thead>
    <tbody>
      ${projection.yearly_projections?.map((p) => `
        <tr>
          <td>${p.year}</td>
          <td>${p.projected_savings_bdt?.toLocaleString()}</td>
          <td>${p.cumulative_savings_bdt?.toLocaleString()}</td>
        </tr>
      `).join('')}
    </tbody>
  `;

  container.appendChild(table);

  // Escalation info
  const escalation = document.createElement('div');
  escalation.className = 'aos-escalation-info';
  escalation.innerHTML = `
    <p>PPA rate escalates at <strong>${projection.escalation_rate}% annually</strong>.</p>
    <p>Estimated lifetime savings: <strong>৳${projection.total_lifetime_savings_bdt?.toLocaleString()}</strong>.</p>
  `;
  container.appendChild(escalation);
}