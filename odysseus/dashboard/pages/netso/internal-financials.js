/**
 * Netso Internal Financials Page — unit economics, scenario comparison, debt structure, approvals.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../../stores/dashboard.js';
import { renderKpiStrip } from '../../widgets/kpi-tile.js';

const SCENARIO_COLORS = {
  A: '#3B82F6',
  B: '#10B981',
};

export function render(container) {
  container.innerHTML = '';

  // KPI strip
  const kpiStrip = document.createElement('div');
  kpiStrip.className = 'aos-kpi-strip';
  container.appendChild(kpiStrip);

  // Unit economics
  const unitEconomicsSection = document.createElement('div');
  unitEconomicsSection.className = 'aos-section';
  container.appendChild(unitEconomicsSection);

  // Scenario comparison
  const scenarioSection = document.createElement('div');
  scenarioSection.className = 'aos-section';
  container.appendChild(scenarioSection);

  // Debt structure
  const debtSection = document.createElement('div');
  debtSection.className = 'aos-section';
  container.appendChild(debtSection);

  // Portfolio financials
  const portfolioSection = document.createElement('div');
  portfolioSection.className = 'aos-section';
  container.appendChild(portfolioSection);

  // Approval thresholds
  const approvalSection = document.createElement('div');
  approvalSection.className = 'aos-section';
  container.appendChild(approvalSection);

  const unsub = store.subscribe((state) => {
    const fin = state.netsoFinancials;
    if (!fin) return;

    // KPI strip — backend: scenarios.scenario_a.{dscr, levered_irr_pct, payback_years}
    renderKpiStrip(kpiStrip, [
      { label: 'DSCR', value: fin.scenarios?.scenario_a?.dscr?.toFixed(2) || '—', icon: '📊', accent: true },
      { label: 'IRR', value: `${(fin.scenarios?.scenario_a?.levered_irr_pct || 0).toFixed(1)}%`, icon: '📈' },
      { label: 'Portfolio Net', value: `BDT ${(fin.portfolio_financials?.net_monthly_bdt || 0).toLocaleString()}`, icon: '💵' },
      { label: 'Payback', value: `${fin.scenarios?.scenario_a?.payback_years || 0} yrs`, icon: '⏳' },
    ]);

    // Unit economics
    renderUnitEconomics(unitEconomicsSection, state);

    // Scenario comparison
    renderScenarioComparison(scenarioSection, state);

    // Debt structure
    renderDebtStructure(debtSection, state);

    // Portfolio financials
    renderPortfolioFinancials(portfolioSection, state);

    // Approval thresholds
    renderApprovalThresholds(approvalSection, state);
  });

  // Initial load
  store.loadNetsoFinancials();

  return unsub;
}

function renderUnitEconomics(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Unit Economics';
  container.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'aos-financial-grid';

  // Backend unit_economics: {capex_per_kw_bdt, opex_per_kw_bdt, ppa_rate_bdt_per_kwh, true_variable_rate_bdt_per_kwh, customer_savings_pct, nem_export_rate_bdt_per_kwh, capacity_factor_pct}
  const ue = state.netsoFinancials?.unit_economics || {};
  const items = [
    { label: 'CAPEX/kW', value: `BDT ${(ue.capex_per_kw_bdt || 0).toLocaleString()}` },
    { label: 'OPEX/kW', value: `BDT ${(ue.opex_per_kw_bdt || 0).toLocaleString()}` },
    { label: 'PPA Rate', value: `BDT ${(ue.ppa_rate_bdt_per_kwh || 0).toFixed(2)}/kWh` },
    { label: 'True Variable Rate', value: `BDT ${(ue.true_variable_rate_bdt_per_kwh || 0).toFixed(2)}/kWh` },
    { label: 'Customer Savings', value: `${(ue.customer_savings_pct || 0).toFixed(1)}%` },
    { label: 'NEM Export Rate', value: `BDT ${(ue.nem_export_rate_bdt_per_kwh || 0).toFixed(2)}/kWh` },
    { label: 'Capacity Factor', value: `${(ue.capacity_factor_pct || 0).toFixed(1)}%` },
  ];

  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-financial-card';

    const labelEl = document.createElement('div');
    labelEl.className = 'aos-financial-label';
    labelEl.textContent = item.label;

    const valueEl = document.createElement('div');
    valueEl.className = 'aos-financial-value';
    valueEl.textContent = item.value;

    card.appendChild(labelEl);
    card.appendChild(valueEl);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function renderScenarioComparison(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Scenario Comparison (A vs B)';
  container.appendChild(header);

  const table = document.createElement('table');
  table.className = 'aos-table';

  // Backend scenarios: {scenario_a: {capex_per_kw, dscr, payback_years, levered_irr_pct}, scenario_b: {...}}
  const scenarios = state.netsoFinancials?.scenarios;
  if (!scenarios) {
    container.appendChild(table);
    return;
  }

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['Metric', 'Scenario A', 'Scenario B', 'Δ'].forEach((text) => {
    const th = document.createElement('th');
    th.textContent = text;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  const metrics = [
    { label: 'CAPEX/kW', key: 'capex_per_kw', format: (v) => `BDT ${v?.toLocaleString()}` },
    { label: 'DSCR', key: 'dscr', format: (v) => v?.toFixed(2) || '—' },
    { label: 'IRR', key: 'levered_irr_pct', format: (v) => `${v?.toFixed(1) || 0}%` },
    { label: 'Payback', key: 'payback_years', format: (v) => `${v || 0} yrs` },
  ];

  metrics.forEach((metric) => {
    const aVal = scenarios.scenario_a?.[metric.key] || 0;
    const bVal = scenarios.scenario_b?.[metric.key] || 0;
    const delta = bVal - aVal;
    const deltaSign = delta >= 0 ? '+' : '';
    const deltaColor = delta >= 0 ? '#10B981' : '#EF4444';

    const row = document.createElement('tr');

    const tdLabel = document.createElement('td');
    tdLabel.textContent = metric.label;
    row.appendChild(tdLabel);

    const tdA = document.createElement('td');
    tdA.style.color = SCENARIO_COLORS.A;
    tdA.textContent = metric.format(aVal);
    row.appendChild(tdA);

    const tdB = document.createElement('td');
    tdB.style.color = SCENARIO_COLORS.B;
    tdB.textContent = metric.format(bVal);
    row.appendChild(tdB);

    const tdDelta = document.createElement('td');
    tdDelta.style.color = deltaColor;
    tdDelta.textContent = `${deltaSign}${metric.format(delta)}`;
    row.appendChild(tdDelta);

    tbody.appendChild(row);
  });
  table.appendChild(tbody);

  container.appendChild(table);
}

function renderDebtStructure(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Debt Structure';
  container.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'aos-debt-grid';

  // Backend debt_structure: {idcol_debt_pct, idcol_interest_pct, idcol_term_years}
  const ds = state.netsoFinancials?.debt_structure || {};
  const items = [
    { label: 'IDCOL Debt %', value: `${(ds.idcol_debt_pct || 0).toFixed(0)}%` },
    { label: 'IDCOL Interest', value: `${(ds.idcol_interest_pct || 0).toFixed(2)}%` },
    { label: 'IDCOL Term', value: `${ds.idcol_term_years || 0} yrs` },
  ];

  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-debt-card';

    const labelEl = document.createElement('div');
    labelEl.className = 'aos-debt-label';
    labelEl.textContent = item.label;

    const valueEl = document.createElement('div');
    valueEl.className = 'aos-debt-value';
    valueEl.textContent = item.value;

    card.appendChild(labelEl);
    card.appendChild(valueEl);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function renderPortfolioFinancials(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Portfolio Financials';
  container.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'aos-financial-grid';

  // Backend portfolio_financials: {total_capex_bdt, monthly_revenue_bdt, ytd_revenue_bdt, annual_opex_bdt, monthly_opex_bdt, net_monthly_bdt}
  const pf = state.netsoFinancials?.portfolio_financials || {};
  const items = [
    { label: 'Total CAPEX', value: `BDT ${(pf.total_capex_bdt || 0).toLocaleString()}` },
    { label: 'Monthly Revenue', value: `BDT ${(pf.monthly_revenue_bdt || 0).toLocaleString()}` },
    { label: 'YTD Revenue', value: `BDT ${(pf.ytd_revenue_bdt || 0).toLocaleString()}` },
    { label: 'Annual OPEX', value: `BDT ${(pf.annual_opex_bdt || 0).toLocaleString()}` },
    { label: 'Monthly OPEX', value: `BDT ${(pf.monthly_opex_bdt || 0).toLocaleString()}` },
    { label: 'Net Monthly', value: `BDT ${(pf.net_monthly_bdt || 0).toLocaleString()}` },
  ];

  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-financial-card';

    const labelEl = document.createElement('div');
    labelEl.className = 'aos-financial-label';
    labelEl.textContent = item.label;

    const valueEl = document.createElement('div');
    valueEl.className = 'aos-financial-value';
    valueEl.textContent = item.value;

    card.appendChild(labelEl);
    card.appendChild(valueEl);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function renderApprovalThresholds(container, state) {
  container.innerHTML = '';
  const header = document.createElement('h3');
  header.className = 'aos-section-title';
  header.textContent = 'Approval Thresholds';
  container.appendChild(header);

  const table = document.createElement('table');
  table.className = 'aos-table';

  // Backend approval_thresholds: {proposal_value_bdt, dscr_escalation_floor, dscr_alert_floor}
  const at = state.netsoFinancials?.approval_thresholds;
  if (!at) {
    container.appendChild(table);
    return;
  }

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['Threshold', 'Value'].forEach((text) => {
    const th = document.createElement('th');
    th.textContent = text;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  const rows = [
    ['Proposal Value', `BDT ${(at.proposal_value_bdt || 0).toLocaleString()}`],
    ['DSCR Escalation Floor', at.dscr_escalation_floor?.toFixed(2) || '—'],
    ['DSCR Alert Floor', at.dscr_alert_floor?.toFixed(2) || '—'],
  ];

  rows.forEach(([label, value]) => {
    const row = document.createElement('tr');

    const tdLabel = document.createElement('td');
    tdLabel.textContent = label;
    row.appendChild(tdLabel);

    const tdValue = document.createElement('td');
    tdValue.textContent = value;
    row.appendChild(tdValue);

    tbody.appendChild(row);
  });
  table.appendChild(tbody);

  container.appendChild(table);
}
