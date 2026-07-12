/**
 * Pipelines Page — orchestrate pipeline status, phases, history.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'aos-section-header';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Orchestrate Pipeline';
  const refreshBtn = document.createElement('button');
  refreshBtn.className = 'aos-btn aos-btn-ghost';
  refreshBtn.textContent = '↻ Refresh';
  refreshBtn.addEventListener('click', () => { store.loadPipeline(); });
  header.appendChild(title);
  header.appendChild(refreshBtn);
  container.appendChild(header);

  const content = document.createElement('div');
  content.className = 'aos-pipeline-content';
  container.appendChild(content);

  const unsub = store.subscribe((state) => {
    renderPipeline(content, state.pipeline);
  });
  store.loadPipeline();
  return unsub;
}

const PHASES = ['SPEC', 'AUTOPLAN', 'IMPLEMENT', 'REVIEWLOOP', 'SHIP'];

function renderPipeline(container, pipeline) {
  container.innerHTML = '';

  if (!pipeline) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No active pipeline';
    container.appendChild(empty);
    return;
  }

  // Phase timeline
  const timeline = document.createElement('div');
  timeline.className = 'aos-phase-timeline';
  PHASES.forEach((phase) => {
    const step = document.createElement('div');
    step.className = 'aos-phase-step';

    const phaseData = pipeline.phases?.[phase] || {};
    const status = phaseData.status || 'pending';
    step.classList.add(`aos-phase-${status}`);

    const dot = document.createElement('div');
    dot.className = 'aos-phase-dot';
    dot.textContent = status === 'passed' ? '✓' : status === 'failed' ? '✗' : status === 'running' ? '⟳' : '○';

    const label = document.createElement('div');
    label.className = 'acos-phase-label';
    label.textContent = phase;

    step.appendChild(dot);
    step.appendChild(label);
    timeline.appendChild(step);
  });
  container.appendChild(timeline);

  // Current phase detail
  const detail = document.createElement('div');
  detail.className = 'aos-pipeline-detail';

  const currentPhase = document.createElement('div');
  currentPhase.className = 'aos-detail-row';
  const cpLabel = document.createElement('span');
  cpLabel.className = 'aos-detail-label';
  cpLabel.textContent = 'Current Phase:';
  const cpValue = document.createElement('span');
  cpValue.className = 'aos-detail-value';
  cpValue.textContent = pipeline.current_phase || '—';
  currentPhase.appendChild(cpLabel);
  currentPhase.appendChild(cpValue);
  detail.appendChild(currentPhase);

  if (pipeline.review_score != null) {
    const score = document.createElement('div');
    score.className = 'aos-detail-row';
    const sLabel = document.createElement('span');
    sLabel.className = 'aos-detail-label';
    sLabel.textContent = 'Review Score:';
    const sValue = document.createElement('span');
    sValue.className = 'aos-detail-value';
    sValue.textContent = `${pipeline.review_score}/10`;
    score.appendChild(sLabel);
    score.appendChild(sValue);
    detail.appendChild(score);
  }

  if (pipeline.retry_count != null) {
    const retry = document.createElement('div');
    retry.className = 'aos-detail-row';
    const rLabel = document.createElement('span');
    rLabel.className = 'aos-detail-label';
    rLabel.textContent = 'Retries:';
    const rValue = document.createElement('span');
    rValue.className = 'aos-detail-value';
    rValue.textContent = String(pipeline.retry_count);
    retry.appendChild(rLabel);
    retry.appendChild(rValue);
    detail.appendChild(retry);
  }

  container.appendChild(detail);
}
