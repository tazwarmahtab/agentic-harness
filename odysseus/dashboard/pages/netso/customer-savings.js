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

    // KPI strip — backend: grid_rate_bdt_per_kwh, ppa_rate_bdt_per_kwh, current_month.savings_bdt
    renderKpiStrip(kpiStrip, [
      { label: 'Grid Rate', value: `৳${sav.grid_rate_bdt_per_kwh?.toLocaleString()}`, icon: '🔌', accent: true },
      { label: 'PPA Rate', value: `৳${sav.ppa_rate_bdt_per_kwh?.toLocaleString()}`, icon: '☀️' },
      { label: 'Current Savings', value: `৳${sav.current_month?.savings_bdt?.toLocaleString()}`, icon: '💰' },
      { label: 'YTD Savings', value: `৳${sav.ytd?.savings_bdt?.toLocaleString()}`, icon: '📅' },
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

  // Fix: match renderSavingsTile signature: (container, { value_bdt, trend_pct, label })
  renderSavingsTile(container, {
    value_bdt: sav.current_month?.savings_bdt,
    trend_pct: null,
    label: 'Monthly Savings',
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

  // Backend trend array: [{month, savings_bdt}]
  const trendData = sav.trend || [];
  const latest = trendData.length > 0 ? trendData[trendData.length - 1] : null;
  const prev = trendData.length > 1 ? trendData[trendData.length - 2] : null;

  const savingsTrend = latest && prev
    ? ((latest.savings_bdt - prev.savings_bdt) / prev.savings_bdt * 100)
    : null;

  const trends = [
    {
      label: 'Savings',
      value: sav.current_month?.savings_bdt?.toLocaleString(),
      trend: savingsTrend,
      unit: '৳',
    },
    {
      label: 'Savings %',
      value: sav.savings_pct?.toFixed(1),
      trend: null,
      unit: '%',
    },
  ];

  trends.forEach(({ label, value, trend, unit }) => {
    if (value === undefined) return;

    const card = document.createElement('div');
    card.className = 'aos-trend-card';

    const labelEl = document.createElement('div');
    labelEl.className = 'aos-trend-label';
    labelEl.textContent = label;

    const valueEl = document.createElement('div');
    valueEl.className = 'aos-trend-value';
    valueEl.textContent = `${unit}${value}`;

    card.appendChild(labelEl);
    card.appendChild(valueEl);

    if (trend != null) {
      const trendEl = document.createElement('div');
      trendEl.className = 'aos-trend-indicator';
      trendEl.appendChild(renderTrendIndicator(trend, TREND_ICONS, TREND_COLORS));
      trendEl.appendChild(document.createTextNode(` ${Math.abs(trend).toFixed(1)}%`));
      card.appendChild(trendEl);
    }

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

  // Backend lifetime_projected: {total_savings_bdt, payback_years, irr_pct}
  const projection = sav.lifetime_projected;
  if (!projection) return;

  const table = document.createElement('table');
  table.className = 'aos-table';

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['Metric', 'Value'].forEach((text) => {
    const th = document.createElement('th');
    th.textContent = text;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  const rows = [
    ['Total Lifetime Savings', `৳${projection.total_savings_bdt?.toLocaleString()}`],
    ['Payback Period', `${projection.payback_years} yrs`],
    ['Levered IRR', `${projection.irr_pct?.toFixed(1)}%`],
  ];
  rows.forEach(([label, value]) => {
    const row = document.createElement('tr');
    const td1 = document.createElement('td');
    td1.textContent = label;
    const td2 = document.createElement('td');
    td2.textContent = value;
    row.appendChild(td1);
    row.appendChild(td2);
    tbody.appendChild(row);
  });
  table.appendChild(tbody);

  container.appendChild(table);

  // Escalation info — backend: escalation.{rate, next_escalation_date, projected_ppa_after_escalation}
  const escalation = sav.escalation;
  if (escalation) {
    const escalationDiv = document.createElement('div');
    escalationDiv.className = 'aos-escalation-info';

    const interval = escalation.interval_years || 3;
    const p1 = document.createElement('p');
    p1.textContent = `PPA rate escalates ${escalation.rate}% every ${interval} years.`;
    escalationDiv.appendChild(p1);

    const p2 = document.createElement('p');
    p2.textContent = `Next escalation: ${escalation.next_escalation_date}. Projected PPA after escalation: ৳${escalation.projected_ppa_after_escalation}/kWh.`;
    escalationDiv.appendChild(p2);

    container.appendChild(escalationDiv);
  }
}
