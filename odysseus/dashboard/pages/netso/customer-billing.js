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

    // KPI strip
    renderKpiStrip(kpiStrip, [
      { label: 'Current Invoice', value: bill.current_invoice ? `৳${bill.current_invoice.amount_bdt?.toLocaleString()}` : '—', icon: '📄', accent: true },
      { label: 'Due Date', value: bill.current_invoice?.due_date || '—', icon: '📅' },
      { label: 'Status', value: bill.current_invoice?.status || '—', icon: getStatusIcon(bill.current_invoice?.status) },
      { label: 'Outstanding', value: bill.outstanding_summary ? `৳${bill.outstanding_summary.total_bdt?.toLocaleString()}` : '—', icon: '💳' },
      { label: 'Overdue', value: bill.outstanding_summary?.overdue_count > 0 ? `${bill.outstanding_summary.overdue_count} invoices` : 'None', icon: bill.outstanding_summary?.overdue_count > 0 ? '🚨' : '✅' },
    ]);

    // Current invoice
    renderInvoiceSection(invoiceSection, bill.current_invoice);

    // Outstanding summary
    renderOutstandingSection(outstandingSection, bill.outstanding_summary);

    // Payment history
    renderHistorySection(historySection, bill.payment_history);
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
  period.textContent = `Period: ${invoice.period}`;

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

  const items = [
    { label: 'Total Outstanding', value: `৳${summary.total_bdt?.toLocaleString()}` },
    { label: 'Pending Invoices', value: summary.pending_count },
    { label: 'Overdue Invoices', value: summary.overdue_count },
    { label: 'Oldest Overdue', value: summary.oldest_overdue_date || 'None' },
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
  table.innerHTML = `
    <thead>
      <tr>
        <th>Period</th>
        <th>Amount</th>
        <th>Status</th>
        <th>Due Date</th>
        <th>Paid Date</th>
      </tr>
    </thead>
    <tbody>
      ${history.map((invoice) => `
        <tr>
          <td>${invoice.period}</td>
          <td>৳${invoice.amount_bdt?.toLocaleString()}</td>
          <td><span style="color: ${INVOICE_STATUS_COLORS[invoice.status?.toLowerCase()] || '#6B7280'}">${invoice.status}</span></td>
          <td>${invoice.due_date}</td>
          <td>${invoice.paid_date || '—'}</td>
        </tr>
      `).join('')}
    </tbody>
  `;

  container.appendChild(table);
}