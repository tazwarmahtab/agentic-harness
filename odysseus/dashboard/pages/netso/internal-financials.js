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
    // KPI strip
    renderKpiStrip(kpiStrip, [
      { label: 'DSCR', value: state.netsoFinancials?.dscr?.toFixed(2) || '—', icon: '📊', accent: true },
      { label: 'IRR', value: `${(state.netsoFinancials?.irrPct || 0).toFixed(1)}%`, icon: '📈' },
      { label: 'NPV', value: `BDT ${(state.netsoFinancials?.npvBDT || 0).toLocaleString()}`, icon: '💵' },
      { label: 'Payback', value: `${state.netsoFinancials?.paybackYears || 0} yrs`, icon: '⏳' },
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

  const items = [
    { label: 'LCOE', value: `BDT ${(state.netsoFinancials?.lcoeBDT || 0).toFixed(2)}/kWh` },
    { label: 'Tariff', value: `BDT ${(state.netsoFinancials?.tariffBDT || 0).toFixed(2)}/kWh` },
    { label: 'OPEX', value: `BDT ${(state.netsoFinancials?.annualOpexBDT || 0).toLocaleString()}` },
    { label: 'CAPEX', value: `BDT ${(state.netsoFinancials?.capexBDT || 0).toLocaleString()}` },
    { label: 'Debt Service', value: `BDT ${(state.netsoFinancials?.annualDebtServiceBDT || 0).toLocaleString()}` },
    { label: 'Equity IRR', value: `${(state.netsoFinancials?.equityIrrPct || 0).toFixed(1)}%` },
  ];

  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-financial-card';
    card.innerHTML = `
      <div class="aos-financial-label">${item.label}</div>
      <div class="aos-financial-value">${item.value}</div>
    `;
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
  table.innerHTML = `
    <thead>
      <tr>
        <th>Metric</th>
        <th>Scenario A</th>
        <th>Scenario B</th>
        <th>Δ</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector('tbody');
  if (state.netsoFinancials?.scenarios) {
    const metrics = [
      { label: 'DSCR', key: 'dscr', format: (v) => v.toFixed(2) },
      { label: 'IRR', key: 'irrPct', format: (v) => `${v.toFixed(1)}%` },
      { label: 'NPV', key: 'npvBDT', format: (v) => `BDT ${v.toLocaleString()}` },
      { label: 'Payback', key: 'paybackYears', format: (v) => `${v} yrs` },
      { label: 'LCOE', key: 'lcoeBDT', format: (v) => `BDT ${v.toFixed(2)}/kWh` },
      { label: 'Tariff', key: 'tariffBDT', format: (v) => `BDT ${v.toFixed(2)}/kWh` },
    ];

    metrics.forEach((metric) => {
      const row = document.createElement('tr');
      const scenarioA = state.netsoFinancials.scenarios.A[metric.key] || 0;
      const scenarioB = state.netsoFinancials.scenarios.B[metric.key] || 0;
      const delta = scenarioB - scenarioA;
      const deltaSign = delta >= 0 ? '+' : '';
      const deltaColor = delta >= 0 ? '#10B981' : '#EF4444';

      row.innerHTML = `
        <td>${metric.label}</td>
        <td style="color: ${SCENARIO_COLORS.A}">${metric.format(scenarioA)}</td>
        <td style="color: ${SCENARIO_COLORS.B}">${metric.format(scenarioB)}</td>
        <td style="color: ${deltaColor}">${deltaSign}${metric.format(delta)}</td>
      `;
      tbody.appendChild(row);
    });
  }

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

  const items = [
    { label: 'Total Debt', value: `BDT ${(state.netsoFinancials?.totalDebtBDT || 0).toLocaleString()}` },
    { label: 'Term Loan', value: `BDT ${(state.netsoFinancials?.termLoanBDT || 0).toLocaleString()}` },
    { label: 'Working Capital', value: `BDT ${(state.netsoFinancials?.workingCapitalBDT || 0).toLocaleString()}` },
    { label: 'Interest Rate', value: `${(state.netsoFinancials?.interestRatePct || 0).toFixed(2)}%` },
    { label: 'Tenor', value: `${state.netsoFinancials?.tenorYears || 0} yrs` },
    { label: 'Grace Period', value: `${state.netsoFinancials?.gracePeriodYears || 0} yrs` },
  ];

  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-debt-card';
    card.innerHTML = `
      <div class="aos-debt-label">${item.label}</div>
      <div class="aos-debt-value">${item.value}</div>
    `;
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

  const items = [
    { label: 'Annual Revenue', value: `BDT ${(state.netsoFinancials?.annualRevenueBDT || 0).toLocaleString()}` },
    { label: 'Annual OPEX', value: `BDT ${(state.netsoFinancials?.annualOpexBDT || 0).toLocaleString()}` },
    { label: 'EBITDA', value: `BDT ${(state.netsoFinancials?.ebitdaBDT || 0).toLocaleString()}` },
    { label: 'Debt Service', value: `BDT ${(state.netsoFinancials?.annualDebtServiceBDT || 0).toLocaleString()}` },
    { label: 'Net Income', value: `BDT ${(state.netsoFinancials?.netIncomeBDT || 0).toLocaleString()}` },
  ];

  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-financial-card';
    card.innerHTML = `
      <div class="aos-financial-label">${item.label}</div>
      <div class="aos-financial-value">${item.value}</div>
    `;
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
  table.innerHTML = `
    <thead>
      <tr>
        <th>Level</th>
        <th>DSCR Floor</th>
        <th>IRR Floor</th>
        <th>NPV Floor</th>
        <th>Payback Ceiling</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector('tbody');
  if (state.netsoFinancials?.approvalThresholds) {
    Object.entries(state.netsoFinancials.approvalThresholds).forEach(([level, thresholds]) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${level}</td>
        <td>${thresholds.dscrFloor?.toFixed(2) || '—'}</td>
        <td>${thresholds.irrFloorPct?.toFixed(1) || '—'}%</td>
        <td>BDT ${thresholds.npvFloorBDT?.toLocaleString() || '—'}</td>
        <td>${thresholds.paybackCeilingYears || '—'} yrs</td>
      `;
      tbody.appendChild(row);
    });
  }

  container.appendChild(table);
}