/**
 * Pipeline Page — Kanban view of deal pipeline.
 * Shows deals grouped by stage with capacity and PPA info.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';

  // Header
  const header = document.createElement('div');
  header.className = 'aos-section-header';

  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Deal Pipeline';

  const refreshBtn = document.createElement('button');
  refreshBtn.className = 'aos-btn aos-btn-ghost';
  refreshBtn.textContent = '↻ Refresh';
  refreshBtn.addEventListener('click', () => loadPipeline(container));

  header.appendChild(title);
  header.appendChild(refreshBtn);
  container.appendChild(header);

  // Pipeline grid
  const grid = document.createElement('div');
  grid.className = 'aos-pipeline-grid';
  grid.id = 'pipeline-grid';
  container.appendChild(grid);

  loadPipeline(container);
}

async function loadPipeline(container) {
  const grid = container.querySelector('#pipeline-grid');
  if (!grid) return;

  grid.innerHTML = '<p style="color:var(--aos-text-muted)">Loading pipeline…</p>';

  try {
    const resp = await fetch('/api/aos/deals');
    if (!resp.ok) throw new Error(`${resp.status}`);
    const data = await resp.json();
    renderPipeline(grid, data);
  } catch (e) {
    grid.innerHTML = `<p style="color:var(--aos-error)">Failed to load pipeline: ${e.message}</p>`;
  }
}

const STAGE_LABELS = {
  lead: '🔵 Lead',
  qualified: '🟡 Qualified',
  loi_signed: '📋 LOI Signed',
  ppa_draft: '📝 PPA Draft',
  ppa_signed: '✅ PPA Signed',
  site_assessment: '🔍 Site Assessment',
  installation: '🔧 Installation',
  commissioned: '⚡ Commissioned',
  revenue: '💰 Revenue',
};

function renderPipeline(grid, data) {
  grid.innerHTML = '';

  const deals = data.deals || [];
  if (deals.length === 0) {
    grid.innerHTML = '<p style="color:var(--aos-text-muted)">No deals in pipeline.</p>';
    return;
  }

  // Group by stage
  const grouped = {};
  for (const deal of deals) {
    const stage = deal.stage || 'unknown';
    if (!grouped[stage]) grouped[stage] = [];
    grouped[stage].push(deal);
  }

  // Render each stage column
  for (const [stage, stageDeals] of Object.entries(grouped)) {
    const col = document.createElement('div');
    col.className = 'aos-pipeline-column';

    const colHeader = document.createElement('h4');
    colHeader.className = 'aos-pipeline-stage-header';
    colHeader.textContent = STAGE_LABELS[stage] || stage;
    col.appendChild(colHeader);

    for (const deal of stageDeals) {
      const card = document.createElement('div');
      card.className = 'aos-card';

      const name = document.createElement('div');
      name.className = 'aos-card-title';
      name.textContent = deal.customer;
      card.appendChild(name);

      if (deal.capacity_kw > 0) {
        const cap = document.createElement('div');
        cap.className = 'aos-card-meta';
        cap.textContent = `${deal.capacity_kw} kWp · BDT ${deal.ppa_rate}/kWh`;
        card.appendChild(cap);
      }

      if (deal.notes && deal.notes.length > 0) {
        const notes = document.createElement('div');
        notes.className = 'aos-card-notes';
        notes.textContent = deal.notes[0];
        card.appendChild(notes);
      }

      col.appendChild(card);
    }

    grid.appendChild(col);
  }
}
