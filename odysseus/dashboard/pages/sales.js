/**
 * Sales Page — sales graph status and pipeline view.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Sales Dashboard';
  header.appendChild(title);
  container.appendChild(header);

  const content = document.createElement('div');
  content.className = 'aos-sales-content';
  container.appendChild(content);

  const unsub = store.subscribe((state) => {
    renderSales(content, state.sales);
  });
  store.loadSales();
  return unsub;
}

function renderSales(container, sales) {
  container.innerHTML = '';
  if (!sales) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No sales data available';
    container.appendChild(empty);
    return;
  }

  const fields = [
    { key: 'current_lead', label: 'Current Lead' },
    { key: 'stage', label: 'Stage' },
    { key: 'last_contact', label: 'Last Contact' },
    { key: 'next_action', label: 'Next Action' },
    { key: 'probability', label: 'Probability' },
    { key: 'proposal_value', label: 'Proposal Value' },
  ];

  fields.forEach(({ key, label }) => {
    if (sales[key] == null) return;
    const row = document.createElement('div');
    row.className = 'aos-detail-row';
    const l = document.createElement('span');
    l.className = 'aos-detail-label';
    l.textContent = `${label}:`;
    const v = document.createElement('span');
    v.className = 'aos-detail-value';
    v.textContent = String(sales[key]);
    row.appendChild(l);
    row.appendChild(v);
    container.appendChild(row);
  });

  if (sales.pipeline_actions?.length) {
    const actionsTitle = document.createElement('h4');
    actionsTitle.className = 'aos-section-subtitle';
    actionsTitle.textContent = 'Pipeline Actions';
    container.appendChild(actionsTitle);

    sales.pipeline_actions.forEach((action) => {
      const entry = document.createElement('div');
      entry.className = 'aos-pipeline-action';
      const phase = document.createElement('span');
      phase.className = 'aos-action-phase';
      phase.textContent = action.phase || '—';
      const act = document.createElement('span');
      act.className = 'aos-action-text';
      act.textContent = action.action || '—';
      const ts = document.createElement('span');
      ts.className = 'aos-action-time';
      ts.textContent = action.timestamp || '';
      entry.appendChild(phase);
      entry.appendChild(act);
      entry.appendChild(ts);
      container.appendChild(entry);
    });
  }
}
