/**
 * Netso Internal Portfolio Page — aggregate KPIs, customer list, site selector, alerts.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../../stores/dashboard.js';
import { renderKpiStrip } from '../../widgets/kpi-tile.js';

const ALERT_LEVEL_COLORS = {
  critical: '#EF4444',
  warning: '#F59E0B',
  info: '#3B82F6',
};

export function render(container) {
  container.innerHTML = '';

  // KPI strip
  const kpiStrip = document.createElement('div');
  kpiStrip.className = 'aos-kpi-strip';
  container.appendChild(kpiStrip);

  // Customer selector
  const selectorSection = document.createElement('div');
  selectorSection.className = 'aos-section';
  container.appendChild(selectorSection);

  // Customer table
  const tableSection = document.createElement('div');
  tableSection.className = 'aos-section';
  container.appendChild(tableSection);

  // Alerts
  const alertsSection = document.createElement('div');
  alertsSection.className = 'aos-section';
  container.appendChild(alertsSection);

  const unsub = store.subscribe((state) => {
    const port = state.netsoPortfolio;
    if (!port) return;

    // KPI strip — backend: total_customers, total_capacity_kw, financial_summary.monthly_revenue_bdt, generation_summary.current_month_kwh
    renderKpiStrip(kpiStrip, [
      { label: 'Customers', value: port.total_customers ?? 0, icon: '👥', accent: true },
      { label: 'Capacity', value: `${port.total_capacity_kw?.toLocaleString()} kW`, icon: '⚡' },
      { label: 'Revenue', value: `BDT ${(port.financial_summary?.monthly_revenue_bdt || 0).toLocaleString()}`, icon: '💰' },
      { label: 'Generation', value: `${(port.generation_summary?.current_month_kwh || 0).toLocaleString()} kWh`, icon: '🔋' },
    ]);

    // Customer selector
    renderCustomerSelector(selectorSection, state);

    // Customer table
    renderCustomerTable(tableSection, state);

    // Alerts — backend alerts: {dscr_breaches, overdue_invoices, system_faults}
    renderAlerts(alertsSection, state);
  });

  // Initial load
  store.loadNetsoPortfolio();

  return unsub;
}

function renderCustomerSelector(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Customer Site';
  container.appendChild(header);

  const selector = document.createElement('select');
  selector.className = 'aos-select';

  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Select a customer site...';
  selector.appendChild(defaultOption);

  // Backend customers: [{customer_id, customer_name, capacity_kw, ...}]
  if (state.netsoPortfolio?.customers) {
    state.netsoPortfolio.customers.forEach((customer) => {
      const option = document.createElement('option');
      option.value = customer.customer_id;
      option.textContent = `${customer.customer_name} (${customer.customer_id})`;
      if (customer.customer_id === state.siteId) option.selected = true;
      selector.appendChild(option);
    });
  }

  selector.addEventListener('change', (e) => {
    store.setSiteId(e.target.value);
  });

  container.appendChild(selector);
}

function renderCustomerTable(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Customer List';
  container.appendChild(header);

  const table = document.createElement('table');
  table.className = 'aos-table';

  // Build table safely with DOM APIs
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['Name', 'Customer ID', 'Capacity (kW)', 'Monthly Generation (kWh)', 'Status'].forEach((text) => {
    const th = document.createElement('th');
    th.textContent = text;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  // Backend customers: {customer_id, customer_name, capacity_kw, status, monthly_generation_kwh, health_score}
  if (state.netsoPortfolio?.customers) {
    state.netsoPortfolio.customers.forEach((customer) => {
      const row = document.createElement('tr');

      const tdName = document.createElement('td');
      tdName.textContent = customer.customer_name;
      row.appendChild(tdName);

      const tdId = document.createElement('td');
      tdId.textContent = customer.customer_id;
      row.appendChild(tdId);

      const tdCap = document.createElement('td');
      tdCap.textContent = customer.capacity_kw?.toLocaleString();
      row.appendChild(tdCap);

      const tdGen = document.createElement('td');
      tdGen.textContent = customer.monthly_generation_kwh?.toLocaleString();
      row.appendChild(tdGen);

      const tdStatus = document.createElement('td');
      const dot = document.createElement('span');
      dot.className = 'aos-dot';
      dot.style.backgroundColor = customer.status === 'active' ? '#10B981' : '#6B7280';
      tdStatus.appendChild(dot);
      tdStatus.appendChild(document.createTextNode(` ${customer.status}`));
      row.appendChild(tdStatus);

      tbody.appendChild(row);
    });
  }
  table.appendChild(tbody);

  container.appendChild(table);
}

function renderAlerts(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Alerts';
  container.appendChild(header);

  const alertsGrid = document.createElement('div');
  alertsGrid.className = 'aos-alerts-grid';

  const port = state.netsoPortfolio;
  // Backend alerts: {dscr_breaches, overdue_invoices, system_faults}
  if (port?.alerts) {
    const alertItems = [];
    if (port.alerts.dscr_breaches > 0) {
      alertItems.push({ level: 'critical', title: 'DSCR Breaches', message: `${port.alerts.dscr_breaches} DSCR breach(es) detected` });
    }
    if (port.alerts.overdue_invoices > 0) {
      alertItems.push({ level: 'warning', title: 'Overdue Invoices', message: `${port.alerts.overdue_invoices} overdue invoice(s)` });
    }
    if (port.alerts.system_faults > 0) {
      alertItems.push({ level: 'critical', title: 'System Faults', message: `${port.alerts.system_faults} system fault(s)` });
    }

    if (alertItems.length > 0) {
      alertItems.forEach((alert) => {
        const alertCard = document.createElement('div');
        alertCard.className = 'aos-alert-card';

        const dot = document.createElement('span');
        dot.className = 'aos-dot';
        dot.style.backgroundColor = ALERT_LEVEL_COLORS[alert.level] || '#6B7280';

        const title = document.createElement('div');
        title.className = 'aos-alert-title';
        title.textContent = alert.title;

        const message = document.createElement('div');
        message.className = 'aos-alert-message';
        message.textContent = alert.message;

        alertCard.appendChild(dot);
        alertCard.appendChild(title);
        alertCard.appendChild(message);
        alertsGrid.appendChild(alertCard);
      });
    } else {
      const noAlerts = document.createElement('div');
      noAlerts.className = 'aos-alert-empty';
      noAlerts.textContent = 'No active alerts';
      alertsGrid.appendChild(noAlerts);
    }
  } else {
    const noAlerts = document.createElement('div');
    noAlerts.className = 'aos-alert-empty';
    noAlerts.textContent = 'No active alerts';
    alertsGrid.appendChild(noAlerts);
  }

  container.appendChild(alertsGrid);
}
