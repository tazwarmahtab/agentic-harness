/**
 * Approvals Page — pending decisions with approve/reject actions.
 * Uses textContent for all dynamic values (XSS-safe).
 */

import store from '../stores/dashboard.js';

export function render(container) {
  container.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'aos-section-header';

  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Approval Queue';

  const refreshBtn = document.createElement('button');
  refreshBtn.className = 'aos-btn aos-btn-ghost';
  refreshBtn.textContent = '↻ Refresh';
  refreshBtn.addEventListener('click', () => store.loadApprovals());

  header.appendChild(title);
  header.appendChild(refreshBtn);
  container.appendChild(header);

  const list = document.createElement('div');
  list.className = 'aos-approval-list';
  container.appendChild(list);

  const unsub = store.subscribe((state) => {
    renderApprovalList(list, state.approvals);
  });

  store.loadApprovals();
  return unsub;
}

function renderApprovalList(container, approvals) {
  container.innerHTML = '';

  if (!approvals.length) {
    const empty = document.createElement('div');
    empty.className = 'aos-empty';
    empty.textContent = 'No pending approvals';
    container.appendChild(empty);
    return;
  }

  approvals.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'aos-approval-card';

    const info = document.createElement('div');
    info.className = 'aos-approval-info';

    const desc = document.createElement('div');
    desc.className = 'aos-approval-desc';
    desc.textContent = item.description || item.title || 'Untitled decision';

    const meta = document.createElement('div');
    meta.className = 'aos-approval-meta';
    meta.textContent = `ID: ${item.id || item.approval_id || '—'} | ${item.type || 'decision'}`;

    info.appendChild(desc);
    info.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'aos-approval-actions';

    const approveBtn = document.createElement('button');
    approveBtn.className = 'aos-btn aos-btn-success';
    approveBtn.textContent = '✓ Approve';
    approveBtn.addEventListener('click', async () => {
      approveBtn.disabled = true;
      approveBtn.textContent = '...';
      try {
        await store.approveDecision(item.id || item.approval_id);
      } catch (e) {
        approveBtn.textContent = 'Failed';
      }
    });

    const rejectBtn = document.createElement('button');
    rejectBtn.className = 'aos-btn aos-btn-danger';
    rejectBtn.textContent = '✗ Reject';
    rejectBtn.addEventListener('click', async () => {
      rejectBtn.disabled = true;
      rejectBtn.textContent = '...';
      try {
        await store.rejectDecision(item.id || item.approval_id);
      } catch (e) {
        rejectBtn.textContent = 'Failed';
      }
    });

    actions.appendChild(approveBtn);
    actions.appendChild(rejectBtn);

    card.appendChild(info);
    card.appendChild(actions);
    container.appendChild(card);
  });
}
