/**
 * Netso Overview — landing page for all Netso roles.
 * Customer view: generation + savings + billing summary.
 * Internal view: portfolio + financials summary.
 */

import store from '../../stores/dashboard.js';
import { renderKpiStrip } from '../../widgets/kpi-tile.js';

export function render(container) {
  container.innerHTML = '';

  const kpiStrip = document.createElement('div');
  kpiStrip.className = 'aos-kpi-strip';
  container.appendChild(kpiStrip);

  const detailSection = document.createElement('div');
  detailSection.className = 'aos-section';
  container.appendChild(detailSection);

  const unsub = store.subscribe((state) => {
    const role = state.role || 'internal';

    if (role === 'customer') {
      renderCustomerOverview(kpiStrip, detailSection, state);
    } else {
      renderInternalOverview(kpiStrip, detailSection, state);
    }
  });

  store.loadNetsoGeneration();
  store.loadNetsoSavings();
  store.loadNetsoBilling();
  store.loadNetsoPortfolio();

  return unsub;
}

function renderCustomerOverview(kpiStrip, detailSection, state) {
  const gen = state.netsoGeneration;
  const sav = state.netsoSavings;
  const bill = state.netsoBilling;

  renderKpiStrip(kpiStrip, [
    { label: 'System', value: gen ? `${gen.system_capacity_kw} kW` : '—', icon: '⚡', accent: true },
    { label: 'Generation', value: gen ? `${gen.current_month?.generation_kwh?.toLocaleString()} kWh` : '—', icon: '☀️' },
    { label: 'Savings', value: sav ? `৳${sav.current_month?.savings_bdt?.toLocaleString()}` : '—', icon: '💰' },
    { label: 'Savings %', value: sav ? `${sav.savings_pct}%` : '—', icon: '📉' },
    { label: 'Next Invoice', value: bill ? `৳${bill.current_invoice?.amount_bdt?.toLocaleString()}` : '—', icon: '📄' },
  ]);

  detailSection.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Quick Links';
  detailSection.appendChild(title);

  const links = [
    { page: 'netso-generation', label: '📊 View detailed generation data' },
    { page: 'netso-savings', label: '💰 View savings breakdown' },
    { page: 'netso-billing', label: '📄 View billing history' },
  ];

  links.forEach(({ page, label }) => {
    const link = document.createElement('button');
    link.className = 'aos-nav-item';
    link.textContent = label;
    link.addEventListener('click', () => store.setPage(page));
    detailSection.appendChild(link);
  });
}

function renderInternalOverview(kpiStrip, detailSection, state) {
  const port = state.netsoPortfolio;

  renderKpiStrip(kpiStrip, [
    { label: 'Customers', value: port?.total_customers ?? '—', icon: '🏢', accent: true },
    { label: 'Capacity', value: port ? `${port.total_capacity_kw?.toLocaleString()} kW` : '—', icon: '⚡' },
    { label: 'Monthly Revenue', value: port ? `৳${port.financial_summary?.monthly_revenue_bdt?.toLocaleString()}` : '—', icon: '💰' },
    { label: 'Monthly Gen', value: port ? `${port.generation_summary?.current_month_kwh?.toLocaleString()} kWh` : '—', icon: '☀️' },
    { label: 'DSCR Breaches', value: port?.alerts?.dscr_breaches ?? 0, icon: port?.alerts?.dscr_breaches > 0 ? '🚨' : '✅' },
  ]);

  detailSection.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Portfolio Status';
  detailSection.appendChild(title);

  if (port?.customers) {
    const table = document.createElement('table');
    table.className = 'aos-table';
    table.innerHTML = `
      <thead><tr><th>Customer</th><th>Capacity</th><th>Status</th><th>Monthly Gen</th><th>Health</th></tr></thead>
      <tbody>${port.customers.map((c) => `
        <tr>
          <td>${c.customer_name}</td>
          <td>${c.capacity_kw} kW</td>
          <td>${c.status}</td>
          <td>${c.monthly_generation_kwh?.toLocaleString()} kWh</td>
          <td>${(c.health_score * 100).toFixed(0)}%</td>
        </tr>
      `).join('')}</tbody>
    `;
    detailSection.appendChild(table);
  }
}
