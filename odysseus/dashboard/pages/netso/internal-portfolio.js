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
    // KPI strip
    renderKpiStrip(kpiStrip, [
      { label: 'Customers', value: state.netsoPortfolio?.customerCount || 0, icon: '👥', accent: true },
      { label: 'Capacity', value: `${state.netsoPortfolio?.totalCapacityMW || 0} MW`, icon: '⚡' },
      { label: 'Revenue', value: `BDT ${(state.netsoPortfolio?.monthlyRevenueBDT || 0).toLocaleString()}`, icon: '💰' },
      { label: 'Generation', value: `${(state.netsoPortfolio?.monthlyGenerationMWh || 0).toLocaleString()} MWh`, icon: '🔋' },
    ]);

    // Customer selector
    renderCustomerSelector(selectorSection, state);

    // Customer table
    renderCustomerTable(tableSection, state);

    // Alerts
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
  selector.innerHTML = '<option value="">Select a customer site...</option>';

  if (state.netsoPortfolio?.customers) {
    state.netsoPortfolio.customers.forEach((customer) => {
      const option = document.createElement('option');
      option.value = customer.siteId;
      option.textContent = `${customer.name} (${customer.siteId})`;
      if (customer.siteId === state.siteId) option.selected = true;
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
  table.innerHTML = `
    <thead>
      <tr>
        <th>Name</th>
        <th>Site ID</th>
        <th>Capacity (kW)</th>
        <th>Monthly Generation (kWh)</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector('tbody');
  if (state.netsoPortfolio?.customers) {
    state.netsoPortfolio.customers.forEach((customer) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${customer.name}</td>
        <td>${customer.siteId}</td>
        <td>${customer.capacityKW.toLocaleString()}</td>
        <td>${customer.monthlyGenerationKWh.toLocaleString()}</td>
        <td><span class="aos-dot" style="background-color: ${customer.status === 'active' ? '#10B981' : '#6B7280'}"></span> ${customer.status}</td>
      `;
      tbody.appendChild(row);
    });
  }

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

  if (state.netsoPortfolio?.alerts && state.netsoPortfolio.alerts.length > 0) {
    state.netsoPortfolio.alerts.forEach((alert) => {
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

  container.appendChild(alertsGrid);
}