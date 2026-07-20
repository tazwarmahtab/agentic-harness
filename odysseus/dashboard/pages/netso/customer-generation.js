"use strict";

/**
 * Netso Customer Generation Page — Detailed generation metrics and trends.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../../stores/dashboard.js';
import { renderKpiStrip } from '../../widgets/kpi-tile.js';
import { renderTrendIndicator } from '../../widgets/trend-indicator.js';

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

  // Trends section
  const trendsSection = document.createElement('div');
  trendsSection.className = 'aos-section';
  container.appendChild(trendsSection);

  // YTD summary
  const ytdSection = document.createElement('div');
  ytdSection.className = 'aos-section';
  container.appendChild(ytdSection);

  const unsub = store.subscribe((state) => {
    const gen = state.netsoGeneration;
    if (!gen) return;

    // KPI strip — backend: current_month.capacity_factor_pct, availability_pct, self_consumption_pct
    renderKpiStrip(kpiStrip, [
      { label: 'System Capacity', value: `${gen.system_capacity_kw?.toLocaleString()} kW`, icon: '⚡', accent: true },
      { label: 'Generation', value: `${gen.current_month?.generation_kwh?.toLocaleString()} kWh`, icon: '☀️' },
      { label: 'Capacity Factor', value: `${gen.current_month?.capacity_factor_pct?.toFixed(1)}%`, icon: '📊' },
      { label: 'Availability', value: `${gen.current_month?.availability_pct?.toFixed(1)}%`, icon: '🔄' },
      { label: 'Self-Consumption', value: `${gen.current_month?.self_consumption_pct?.toFixed(1)}%`, icon: '🏠' },
    ]);

    // Trends section
    renderTrendsSection(trendsSection, gen);

    // YTD summary
    renderYtdSection(ytdSection, gen);
  });

  // Initial load
  store.loadNetsoGeneration();

  return unsub;
}

function renderTrendsSection(container, gen) {
  container.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Month-over-Month Trends';
  container.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'aos-trend-grid';

  // Backend trend array: [{month, generation_kwh}]
  // Compute trends from the trend array
  const trendData = gen.trend || [];
  const latest = trendData.length > 0 ? trendData[trendData.length - 1] : null;
  const prev = trendData.length > 1 ? trendData[trendData.length - 2] : null;

  const genTrend = latest && prev
    ? ((latest.generation_kwh - prev.generation_kwh) / prev.generation_kwh * 100)
    : null;

  const trends = [
    {
      label: 'Generation',
      value: gen.current_month?.generation_kwh?.toLocaleString(),
      trend: genTrend,
      unit: 'kWh',
    },
    {
      label: 'Capacity Factor',
      value: gen.current_month?.capacity_factor_pct?.toFixed(1),
      trend: genTrend,
      unit: '%',
    },
    {
      label: 'Availability',
      value: gen.current_month?.availability_pct?.toFixed(1),
      trend: null,
      unit: '%',
    },
    {
      label: 'Self-Consumption',
      value: gen.current_month?.self_consumption_pct?.toFixed(1),
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
    valueEl.textContent = `${value} ${unit}`;

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

function renderYtdSection(container, gen) {
  container.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Year-to-Date Summary';
  container.appendChild(title);

  // Backend ytd: {generation_kwh, grid_export_kwh, self_consumption_pct}
  const ytd = gen.ytd;
  if (!ytd) return;

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
    ['Total Generation', `${ytd.generation_kwh?.toLocaleString()} kWh`],
    ['Grid Export', `${ytd.grid_export_kwh?.toLocaleString()} kWh`],
    ['Self-Consumption', `${ytd.self_consumption_pct?.toFixed(1)}%`],
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
}
