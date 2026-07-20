"use strict";

/**
 * Netso Customer Billing Page — Invoice details and payment history.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../../stores/dashboard.js';
import { renderKpiStrip } from '../../widgets/kpi-tile.js';

const INVOICE_STATUS_COLORS = {
  paid: '#10B981',
  pending: '#F59E0B',
  overdue: '#EF4444',
};

export function render(container) {
  container.innerHTML = '';

  // KPI strip
  const kpiStrip = document.createElement('div');
  kpiStrip.className = 'aos-kpi-strip';
  container.appendChild(kpiStrip);

  // Current invoice
  const invoiceSection = document.createElement('div');
  invoiceSection.className = 'aos-section';
  container.appendChild(invoiceSection);

  // Outstanding summary
  const outstandingSection = document.createElement('div');
  outstandingSection.className = 'aos-section';
  container.appendChild(outstandingSection);

  // Payment history
  const historySection = document.createElement('div');
  historySection.className = 'aos-section';
  container.appendChild(historySection);

  const unsub = store.subscribe((state) => {
    const bill = state.netsoBilling;
    if (!bill) return;

    // KPI strip — backend: current_invoice.{amount_bdt, due_date, status}, outstanding.{total_bdt, overdue_count}
    renderKpiStrip(kpiStrip, [
      { label: 'Current Invoice', value: bill.current_invoice ? `৳${bill.current_invoice.amount_bdt?.toLocaleString()}` : '—', icon: '📄', accent: true },
      { label: 'Due Date', value: bill.current_invoice?.due_date || '—', icon: '📅' },
      { label: 'Status', value: bill.current_invoice?.status || '—', icon: getStatusIcon(bill.current_invoice?.status) },
      { label: 'Outstanding', value: bill.outstanding ? `৳${bill.outstanding.total_bdt?.toLocaleString()}` : '—', icon: '💳' },
      { label: 'Overdue', value: bill.outstanding?.overdue_count > 0 ? `${bill.outstanding.overdue_count} invoices` : 'None', icon: bill.outstanding?.overdue_count > 0 ? '🚨' : '✅' },
    ]);

    // Current invoice
    renderInvoiceSection(invoiceSection, bill.current_invoice);

    // Outstanding summary — backend key: outstanding
    renderOutstandingSection(outstandingSection, bill.outstanding);

    // Payment history — backend key: history
    renderHistorySection(historySection, bill.history);
  });

  // Initial load
  store.loadNetsoBilling();

  return unsub;
}

function getStatusIcon(status) {
  if (!status) return '❓';
  const icons = {
    paid: '✅',
    pending: '⏳',
    overdue: '🚨',
  };
  return icons[status.toLowerCase()] || '❓';
}

function renderInvoiceSection(container, invoice) {
  container.innerHTML = '';
  if (!invoice) return;

  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Current Invoice';
  container.appendChild(title);

  const card = document.createElement('div');
  card.className = 'aos-invoice-card';

  const amount = document.createElement('div');
  amount.className = 'aos-invoice-amount';
  amount.textContent = `৳${invoice.amount_bdt?.toLocaleString()}`;

  const status = document.createElement('div');
  status.className = 'aos-invoice-status';
  status.textContent = invoice.status;
  status.style.color = INVOICE_STATUS_COLORS[invoice.status?.toLowerCase()] || '#6B7280';

  const dueDate = document.createElement('div');
  dueDate.className = 'aos-invoice-due';
  dueDate.textContent = `Due: ${invoice.due_date}`;

  const period = document.createElement('div');
  period.className = 'aos-invoice-period';
  // Backend invoice has 'month' field, not 'period'
  period.textContent = `Period: ${invoice.month}`;

  card.appendChild(amount);
  card.appendChild(status);
  card.appendChild(dueDate);
  card.appendChild(period);
  container.appendChild(card);
}

function renderOutstandingSection(container, summary) {
  container.innerHTML = '';
  if (!summary) return;

  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Outstanding Summary';
  container.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'aos-outstanding-grid';

  // Backend outstanding: {total_bdt, overdue_count, overdue_amount_bdt}
  const items = [
    { label: 'Total Outstanding', value: `৳${summary.total_bdt?.toLocaleString()}` },
    { label: 'Overdue Invoices', value: summary.overdue_count },
    { label: 'Overdue Amount', value: `৳${summary.overdue_amount_bdt?.toLocaleString()}` },
  ];

  items.forEach(({ label, value }) => {
    const card = document.createElement('div');
    card.className = 'aos-outstanding-card';

    const labelEl = document.createElement('div');
    labelEl.className = 'aos-outstanding-label';
    labelEl.textContent = label;

    const valueEl = document.createElement('div');
    valueEl.className = 'aos-outstanding-value';
    valueEl.textContent = value;

    card.appendChild(labelEl);
    card.appendChild(valueEl);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function renderHistorySection(container, history) {
  container.innerHTML = '';
  if (!history?.length) return;

  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Payment History';
  container.appendChild(title);

  const table = document.createElement('table');
  table.className = 'aos-table';

  // Build table safely with DOM APIs (no innerHTML for dynamic data)
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['Invoice ID', 'Amount', 'Status', 'Generation', 'Paid Date'].forEach((text) => {
    const th = document.createElement('th');
    th.textContent = text;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  // Backend history items: {invoice_id, amount_bdt, status, paid_date, generation_kwh}
  history.forEach((invoice) => {
    const row = document.createElement('tr');

    const tdId = document.createElement('td');
    tdId.textContent = invoice.invoice_id;
    row.appendChild(tdId);

    const tdAmount = document.createElement('td');
    tdAmount.textContent = `৳${invoice.amount_bdt?.toLocaleString()}`;
    row.appendChild(tdAmount);

    const tdStatus = document.createElement('td');
    const statusSpan = document.createElement('span');
    statusSpan.textContent = invoice.status;
    statusSpan.style.color = INVOICE_STATUS_COLORS[invoice.status?.toLowerCase()] || '#6B7280';
    tdStatus.appendChild(statusSpan);
    row.appendChild(tdStatus);

    const tdGen = document.createElement('td');
    tdGen.textContent = `${invoice.generation_kwh?.toLocaleString()} kWh`;
    row.appendChild(tdGen);

    const tdPaid = document.createElement('td');
    tdPaid.textContent = invoice.paid_date || '—';
    row.appendChild(tdPaid);

    tbody.appendChild(row);
  });
  table.appendChild(tbody);

  container.appendChild(table);
}
