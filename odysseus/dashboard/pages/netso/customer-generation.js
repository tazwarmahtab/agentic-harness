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

    // KPI strip
    renderKpiStrip(kpiStrip, [
      { label: 'System Capacity', value: `${gen.system_capacity_kw?.toLocaleString()} kW`, icon: '⚡', accent: true },
      { label: 'Generation', value: `${gen.current_month?.generation_kwh?.toLocaleString()} kWh`, icon: '☀️' },
      { label: 'Capacity Factor', value: `${gen.current_month?.capacity_factor?.toFixed(1)}%`, icon: '📊' },
      { label: 'Availability', value: `${gen.current_month?.availability?.toFixed(1)}%`, icon: '🔄' },
      { label: 'Self-Consumption', value: `${gen.current_month?.self_consumption?.toFixed(1)}%`, icon: '🏠' },
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

  const trends = [
    {
      label: 'Generation',
      value: gen.current_month?.generation_kwh?.toLocaleString(),
      trend: gen.trends?.generation,
      unit: 'kWh',
    },
    {
      label: 'Capacity Factor',
      value: gen.current_month?.capacity_factor?.toFixed(1),
      trend: gen.trends?.capacity_factor,
      unit: '%',
    },
    {
      label: 'Availability',
      value: gen.current_month?.availability?.toFixed(1),
      trend: gen.trends?.availability,
      unit: '%',
    },
    {
      label: 'Self-Consumption',
      value: gen.current_month?.self_consumption?.toFixed(1),
      trend: gen.trends?.self_consumption,
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
    valueEl.textContent = `${value} ${unit}`;

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

function renderYtdSection(container, gen) {
  container.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Year-to-Date Summary';
  container.appendChild(title);

  const ytd = gen.ytd_summary;
  if (!ytd) return;

  const table = document.createElement('table');
  table.className = 'aos-table';
  table.innerHTML = `
    <thead>
      <tr>
        <th>Metric</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Total Generation</td>
        <td>${ytd.total_generation_kwh?.toLocaleString()} kWh</td>
      </tr>
      <tr>
        <td>Average Capacity Factor</td>
        <td>${ytd.avg_capacity_factor?.toFixed(1)}%</td>
      </tr>
      <tr>
        <td>Average Availability</td>
        <td>${ytd.avg_availability?.toFixed(1)}%</td>
      </tr>
      <tr>
        <td>Average Self-Consumption</td>
        <td>${ytd.avg_self_consumption?.toFixed(1)}%</td>
      </tr>
    </tbody>
  `;

  container.appendChild(table);
}