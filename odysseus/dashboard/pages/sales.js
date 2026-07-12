/**
 * Sales Page — enhanced sales dashboard with AI reasoning and pipeline.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

let _expandedLead = null;

export function render(container) {
  container.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Sales Dashboard';
  header.appendChild(title);
  container.appendChild(header);

  // Content
  const content = document.createElement('div');
  content.className = 'aos-sales-content';
  container.appendChild(content);

  // Pipeline actions
  const actionsSection = document.createElement('div');
  actionsSection.className = 'aos-section';
  actionsSection.style.marginTop = '1.5rem';
  const actionsTitle = document.createElement('h4');
  actionsTitle.className = 'aos-section-subtitle';
  actionsTitle.textContent = 'Pipeline History';
  actionsSection.appendChild(actionsTitle);
  const actionsList = document.createElement('div');
  actionsList.className = 'aos-pipeline-actions';
  actionsSection.appendChild(actionsList);
  container.appendChild(actionsSection);

  const unsub = store.subscribe((state) => {
    renderSalesContent(content, state.sales);
    renderPipelineActions(actionsList, state.sales);
  });
  store.loadSales();
  return unsub;
}

function renderSalesContent(container, sales) {
  container.innerHTML = '';
  if (!sales) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'Loading sales data...';
    container.appendChild(empty);
    return;
  }

  // Current lead card
  if (sales.current_lead || sales.lead_name) {
    const leadCard = document.createElement('div');
    leadCard.className = 'aos-sales-lead-card';

    const leadHeader = document.createElement('div');
    leadHeader.className = 'aos-lead-header';

    const leadIcon = document.createElement('div');
    leadIcon.className = 'aos-lead-icon';
    leadIcon.textContent = '🎯';

    const leadInfo = document.createElement('div');
    leadInfo.className = 'aos-lead-info';

    const leadName = document.createElement('div');
    leadName.className = 'aos-lead-name';
    leadName.textContent = sales.current_lead || sales.lead_name || '—';

    const leadStage = document.createElement('div');
    leadStage.className = 'aos-lead-stage';
    leadStage.textContent = sales.stage || sales.current_phase || '—';

    leadInfo.appendChild(leadName);
    leadInfo.appendChild(leadStage);
    leadHeader.appendChild(leadIcon);
    leadHeader.appendChild(leadInfo);
    leadCard.appendChild(leadHeader);

    // Lead details
    const details = [
      { label: 'Lead Score', value: sales.lead_score != null ? `${(sales.lead_score * 100).toFixed(0)}%` : null },
      { label: 'ICP Match', value: sales.icp_match != null ? (sales.icp_match ? 'Yes' : 'No') : null },
      { label: 'Outreach', value: sales.outreach_channel || null },
      { label: 'Proposal Value', value: sales.proposal_value_bdt ? `BDT ${sales.proposal_value_bdt.toLocaleString()}` : null },
      { label: 'Last Contact', value: sales.last_contact || null },
      { label: 'Next Action', value: sales.next_action || null },
    ];

    details.forEach(({ label, value }) => {
      if (value == null) return;
      const row = document.createElement('div');
      row.className = 'aos-detail-row';
      const l = document.createElement('span');
      l.className = 'aos-detail-label';
      l.textContent = `${label}:`;
      const v = document.createElement('span');
      v.className = 'aos-detail-value';
      v.textContent = value;
      row.appendChild(l);
      row.appendChild(v);
      leadCard.appendChild(row);
    });

    container.appendChild(leadCard);
  }

  // AI Reasoning
  if (sales.ai_reasoning || sales.reasoning) {
    const reasoningSection = document.createElement('div');
    reasoningSection.className = 'aos-sales-reasoning';

    const reasoningTitle = document.createElement('h4');
    reasoningTitle.className = 'aos-section-subtitle';
    reasoningTitle.textContent = '🤖 AI Reasoning';
    reasoningSection.appendChild(reasoningTitle);

    const reasoningText = document.createElement('div');
    reasoningText.className = 'aos-reasoning-text';
    reasoningText.textContent = sales.ai_reasoning || sales.reasoning;
    reasoningSection.appendChild(reasoningText);

    container.appendChild(reasoningSection);
  }

  // Conversion metrics
  if (sales.conversion_metrics || sales.metrics) {
    const metrics = sales.conversion_metrics || sales.metrics;
    const metricsSection = document.createElement('div');
    metricsSection.className = 'aos-sales-metrics';

    const metricsTitle = document.createElement('h4');
    metricsTitle.className = 'aos-section-subtitle';
    metricsTitle.textContent = 'Conversion Metrics';
    metricsSection.appendChild(metricsTitle);

    const metricsGrid = document.createElement('div');
    metricsGrid.className = 'aos-metrics-grid';

    Object.entries(metrics).forEach(([key, value]) => {
      const card = document.createElement('div');
      card.className = 'aos-metric-card';
      const label = document.createElement('div');
      label.className = 'aos-metric-label';
      label.textContent = key.replace(/_/g, ' ');
      const val = document.createElement('div');
      val.className = 'aos-metric-value';
      val.textContent = typeof value === 'number' ? value.toLocaleString() : String(value);
      card.appendChild(label);
      card.appendChild(val);
      metricsGrid.appendChild(card);
    });

    metricsSection.appendChild(metricsGrid);
    container.appendChild(metricsSection);
  }

  // Objections
  if (sales.objections?.length) {
    const objSection = document.createElement('div');
    objSection.className = 'aos-section';
    const objTitle = document.createElement('h4');
    objTitle.className = 'aos-section-subtitle';
    objTitle.textContent = 'Objections';
    objSection.appendChild(objTitle);

    sales.objections.forEach((obj) => {
      const item = document.createElement('div');
      item.className = 'aos-objection-item';
      item.textContent = `• ${obj}`;
      objSection.appendChild(item);
    });

    container.appendChild(objSection);
  }

  // Deal outcome
  if (sales.deal_outcome) {
    const outcome = document.createElement('div');
    outcome.className = `aos-deal-outcome aos-deal-${sales.deal_outcome}`;
    const outcomeLabel = document.createElement('span');
    outcomeLabel.textContent = 'Outcome: ';
    const outcomeValue = document.createElement('strong');
    outcomeValue.textContent = sales.deal_outcome;
    outcome.appendChild(outcomeLabel);
    outcome.appendChild(outcomeValue);
    container.appendChild(outcome);
  }
}

function renderPipelineActions(container, sales) {
  container.innerHTML = '';
  const actions = sales?.pipeline_actions || [];

  if (!actions.length) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No pipeline actions recorded';
    container.appendChild(empty);
    return;
  }

  actions.forEach((action) => {
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
