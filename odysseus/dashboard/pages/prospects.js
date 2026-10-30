/** Founder OS prospect workflow. Every document/model string is rendered as text. */
import api from '../services/api.js';

let token = ''; // Memory only: never persisted to storage, URLs or logs.

function element(tag, text, parent) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (parent) parent.appendChild(node);
  return node;
}

export function render(container) {
  container.replaceChildren();
  let active = true;
  const intro = element('p', 'Supply documents, inspect the evidence, and review a draft. Approval never sends a message.', container);
  intro.className = 'aos-page-desc';
  const grid = element('div', undefined, container);
  grid.className = 'prospect-grid';
  const inputPanel = element('section', undefined, grid);
  inputPanel.className = 'prospect-panel';
  element('h2', 'Prepare a meeting', inputPanel);
  const form = element('form', undefined, inputPanel);
  function field(label, name, type, value = '') {
    const id = `prospect-${name}`;
    const lab = element('label', label, form);
    lab.htmlFor = id;
    const node = element('input', undefined, form);
    node.id = id; node.name = name; node.type = type; node.value = value;
    node.required = true;
    return node;
  }
  const credential = field('Founder API token (kept in memory)', 'token', 'password', token);
  credential.autocomplete = 'off';
  credential.addEventListener('input', () => { token = credential.value; api.setToken?.(token); });
  const venture = field('Venture', 'venture', 'text', 'netso');
  const project = field('Project', 'project', 'text', 'prospect-review');
  const prospect = field('Prospect name', 'name', 'text');
  const purpose = field('Meeting purpose', 'purpose', 'text');
  const documents = field('Documents — TXT, MD, DOCX, text PDF', 'files', 'file');
  documents.multiple = true; documents.accept = '.txt,.md,.docx,.pdf';
  element('p', 'Maximum 12 files; 5 MiB each; 10 MiB combined. Scanned PDFs require OCR.', form);
  const submit = element('button', 'Create brief locally', form);
  submit.className = 'aos-btn aos-btn-primary'; submit.type = 'submit';
  const restore = element('button', 'Load saved jobs', inputPanel);
  restore.className = 'aos-btn'; restore.type = 'button';
  const jobs = element('div', undefined, inputPanel);
  const status = element('p', '', inputPanel);
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const result = element('section', undefined, grid);
  result.className = 'prospect-panel';
  element('h2', 'Brief and review', result);
  element('p', 'Create a brief or reopen a saved job.', result);

  function scope() { return { venture: venture.value, project: project.value }; }
  function query(s) { return '?' + new URLSearchParams(s).toString(); }
  async function request(path, method = 'GET', body) {
    if (!token) throw new Error('Enter your founder API token.');
    const response = await fetch('/api/prospects' + path, {
      method, headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined, cache: 'no-store',
    });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({}));
      throw new Error(typeof problem.detail === 'string' ? problem.detail : `Request failed (${response.status})`);
    }
    return response;
  }
  async function json(path, method, body) { return (await request(path, method, body)).json(); }
  async function work(action) {
    submit.disabled = true; restore.disabled = true;
    status.textContent = 'Working…';
    try { await action(); if (active) status.textContent = 'Saved. Review the evidence before using the draft.'; }
    catch (err) { if (active) status.textContent = err.message; }
    finally { submit.disabled = false; restore.disabled = false; }
  }
  async function loadJobs() {
    const rows = await json(query(scope()));
    if (!active) return;
    jobs.replaceChildren();
    for (const row of rows) {
      const button = element('button', `${row.prospect} · ${row.status}`, jobs);
      button.className = 'aos-btn';
      button.addEventListener('click', () => work(async () => {
        const s = scope();
        const job = await json('/' + row.id + query(s));
        if (active) show(job, s);
      }));
    }
    if (!rows.length) element('p', 'No saved jobs in this scope.', jobs);
  }
  function show(job, s) {
    result.replaceChildren();
    element('h2', job.prospect, result);
    element('p', `${job.status} · ${job.mode || 'not analyzed'} · ${job.purpose}`, result);
    element('small', `Job: ${job.id}`, result);
    if (!job.output) {
      element('p', job.error || 'Source intake is saved. Generate the brief to continue.', result);
      const retry = element('button', 'Generate / retry locally', result);
      retry.className = 'aos-btn';
      retry.addEventListener('click', () => work(async () => show(await json('/' + job.id + '/generate' + query(s), 'POST', {}), s)));
      return;
    }
    element('h3', 'Evidence from supplied documents', result);
    element('p', job.output.review_note, result);
    for (const fact of job.output.facts) {
      const source = job.sources.find((source) => source.id === fact.source_id);
      element('blockquote', fact.quote, result);
      const cite = element('button', `${source.filename} · ${source.locator_kind} ${fact.page}`, result);
      cite.className = 'aos-btn';
      cite.addEventListener('click', () => {
        let details = cite.nextElementSibling;
        if (!details || !details.classList.contains('source-passage')) {
          details = document.createElement('pre'); details.className = 'source-passage';
          details.textContent = source.passages.find((p) => p.page === fact.page)?.text || 'Passage unavailable';
          cite.after(details);
        } else details.remove();
      });
    }
    element('h3', 'Missing information / confirmation checklist', result);
    const questions = element('ul', undefined, result);
    for (const item of job.output.missing_information) element('li', item.question + ' [' + item.status.replaceAll('_', ' ') + ']', questions);
    element('h3', 'Draft follow-up', result);
    const label = element('label', 'Editable draft — saving creates a new review version', result);
    label.htmlFor = 'prospect-draft';
    const draft = element('textarea', undefined, result);
    draft.id = 'prospect-draft'; draft.value = job.output.follow_up; draft.maxLength = 10000;
    const save = element('button', 'Save draft changes', result);
    save.className = 'aos-btn';
    save.addEventListener('click', () => work(async () => show(await json('/' + job.id + '/draft' + query(s), 'PATCH', { output_hash: job.output_hash, text: draft.value }), s)));
    element('p', 'Review applies to this saved version only. There is no send action.', result);
    const version = element('small', 'Version: ' + job.output_hash, result);
    version.style.overflowWrap = 'anywhere';
    const buttons = [];
    for (const decision of ['approve', 'reject', 'defer']) {
      const button = element('button', decision === 'approve' ? 'Approve for use' : decision === 'reject' ? 'Reject version' : 'Defer review', result);
      button.className = 'aos-btn'; buttons.push(button);
      button.disabled = ['approved', 'rejected'].includes(job.status);
      button.addEventListener('click', () => work(async () => {
        if (draft.value !== job.output.follow_up) throw new Error('Save your draft changes before reviewing.');
        const updated = await json('/' + job.id + '/review' + query(s), 'POST', { output_hash: job.output_hash, decision });
        if (active) show(updated, s);
      }));
    }
    draft.addEventListener('input', () => buttons.forEach((b) => { b.disabled = draft.value !== job.output.follow_up || ['approved', 'rejected'].includes(job.status); }));
    element('h3', 'Original documents', result);
    for (const source of job.sources) {
      const download = element('button', `Download ${source.filename}`, result);
      download.className = 'aos-btn';
      download.addEventListener('click', () => work(async () => {
        const response = await request('/' + job.id + '/sources/' + source.id + query(s));
        const url = URL.createObjectURL(await response.blob());
        const a = document.createElement('a'); a.href = url; a.download = source.filename; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }));
    }
  }
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    work(async () => {
      const files = [...documents.files];
      if (!files.length || files.length > 12 || files.some((f) => f.size > 5 * 1024 * 1024) || files.reduce((n, f) => n + f.size, 0) > 10 * 1024 * 1024) throw new Error('Select 1–12 files within the displayed limits.');
      const uploads = [];
      for (const file of files) {
        const content = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file); });
        uploads.push({ filename: file.name, content_b64: content });
      }
      const s = scope();
      const job = await json('', 'POST', { ...s, prospect: prospect.value, purpose: purpose.value, documents: uploads });
      if (active) show(job, s);
      const generated = await json('/' + job.id + '/generate' + query(s), 'POST', {});
      if (active) show(generated, s);
    });
  });
  restore.addEventListener('click', () => work(loadJobs));
  return () => { active = false; };
}
