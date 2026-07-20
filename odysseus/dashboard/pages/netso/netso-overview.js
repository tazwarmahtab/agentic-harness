/**
 * Netso Overview — landing page for all Netso roles.
 * Customer view: generation + savings + billing summary.
 * Internal view: portfolio + financials summary.
 * Uses textContent for all dynamic values (XSS-safe).
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

  // Backend generation: system_capacity_kw, current_month.generation_kwh
  // Backend savings: current_month.savings_bdt, savings_pct
  // Backend billing: current_invoice.amount_bdt
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
    { page: 'netso-generation', label: 'View detailed generation data' },
    { page: 'netso-savings', label: 'View savings breakdown' },
    { page: 'netso-billing', label: 'View billing history' },
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
  if (!port) return;

  // Backend: total_customers, total_capacity_kw, financial_summary.monthly_revenue_bdt,
  // generation_summary.current_month_kwh, alerts.dscr_breaches
  renderKpiStrip(kpiStrip, [
    { label: 'Customers', value: port.total_customers ?? '—', icon: '🏢', accent: true },
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

  // Build table safely with DOM APIs
  if (port?.customers) {
    const table = document.createElement('table');
    table.className = 'aos-table';

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    ['Customer', 'Capacity', 'Status', 'Monthly Gen', 'Health'].forEach((text) => {
      const th = document.createElement('th');
      th.textContent = text;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    // Backend customers: {customer_id, customer_name, capacity_kw, status, monthly_generation_kwh, health_score}
    port.customers.forEach((c) => {
      const row = document.createElement('tr');

      const tdName = document.createElement('td');
      tdName.textContent = c.customer_name;
      row.appendChild(tdName);

      const tdCap = document.createElement('td');
      tdCap.textContent = `${c.capacity_kw} kW`;
      row.appendChild(tdCap);

      const tdStatus = document.createElement('td');
      tdStatus.textContent = c.status;
      row.appendChild(tdStatus);

      const tdGen = document.createElement('td');
      tdGen.textContent = `${c.monthly_generation_kwh?.toLocaleString()} kWh`;
      row.appendChild(tdGen);

      const tdHealth = document.createElement('td');
      // health_score is 0-1, display as percentage
      tdHealth.textContent = `${(c.health_score * 100).toFixed(0)}%`;
      row.appendChild(tdHealth);

      tbody.appendChild(row);
    });
    table.appendChild(tbody);

    detailSection.appendChild(table);
  }
}
