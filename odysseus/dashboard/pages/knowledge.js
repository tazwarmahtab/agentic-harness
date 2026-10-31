/** Scoped file browser. Folder membership is a view of existing prospect jobs. */
import api from '../services/api.js';
import store from '../stores/dashboard.js';

function node(tag, text, parent, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  if (parent) parent.append(el);
  return el;
}

export function render(container) {
  container.replaceChildren();
  const root = node('section', undefined, container, 'knowledge');
  let active = true, jobs = [], selected = null, category = 'all', loadedScope = null;
  let generation = 0, controller = new AbortController();
  const pending = store.state.selectedProspect;
  node('p', 'Your project evidence, in one place', root, 'knowledge-eyebrow');
  node('h2', 'Knowledge & Files', root);
  node('p', 'Browse saved prospect folders. Originals are supplied claims; generated files remain drafts until reviewed. Folder placement does not grant access.', root, 'aos-page-desc');
  const form = node('form', undefined, root, 'knowledge-controls');
  function field(label, name, value, type = 'text') {
    const wrapper = node('div', undefined, form);
    const lab = node('label', label, wrapper);
    const el = node('input', undefined, wrapper);
    el.id = 'knowledge-' + name; lab.htmlFor = el.id;
    el.value = value; el.type = type; el.required = true;
    if (type === 'password') el.autocomplete = 'off';
    return el;
  }
  const credential = field('Founder API token (memory only)', 'token', api.token, 'password');
  const venture = field('Venture', 'venture', pending?.venture || 'netso');
  const project = field('Project', 'project', pending?.project || 'prospect-review');
  const load = node('button', 'Load project files', form, 'aos-btn aos-btn-primary');
  load.type = 'submit';
  const status = node('p', 'Choose a project and load its saved records.', root);
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const workspace = node('div', undefined, root, 'knowledge-workspace');
  const sidebar = node('details', undefined, workspace, 'knowledge-tree');
  sidebar.open = matchMedia('(min-width: 901px)').matches;
  node('summary', 'Browse folders', sidebar);
  const tree = node('div', undefined, sidebar);
  const main = node('section', undefined, workspace, 'knowledge-main');
  const breadcrumb = node('p', 'Project files', main, 'knowledge-breadcrumb');
  const searchLabel = node('label', 'Search folder names and filenames', main);
  const search = node('input', undefined, main);
  search.id = 'knowledge-search'; search.type = 'search'; searchLabel.htmlFor = search.id;
  const cards = node('div', undefined, main, 'knowledge-folders');
  const toolbar = node('div', undefined, main, 'knowledge-toolbar');
  const filters = [];
  for (const [key, label] of [['all', 'All files'], ['original', 'Originals'], ['generated', 'Generated']]) {
    const b = node('button', label, toolbar, 'aos-btn'); b.type = 'button';
    b.addEventListener('click', () => { category = key; draw(); });
    filters.push([key, b]);
  }
  const rows = node('div', undefined, main, 'knowledge-files');
  const detail = node('section', undefined, main, 'knowledge-detail');
  detail.hidden = true;

  function button(parent, label, action, className = 'aos-btn') {
    const b = node('button', label, parent, className); b.type = 'button';
    b.addEventListener('click', action); return b;
  }
  function clear(message) {
    generation++; controller.abort(); controller = new AbortController();
    jobs = []; selected = null; loadedScope = null; load.disabled = false;
    detail.replaceChildren(); detail.hidden = true; draw(); status.textContent = message;
  }
  credential.addEventListener('input', () => {
    api.setToken(credential.value);
    clear('Credentials changed. Load the project again.');
  });
  for (const input of [venture, project]) input.addEventListener('input', () => clear('Scope changed. Load the project again.'));

  function items(job) {
    const originals = job.sources.map(source => ({
      title: source.filename, kind: 'original', state: 'Supplied · unverified', job, source,
      content: source.passages.map(p => `[${source.locator_kind} ${p.page}]\n${p.text}`).join('\n\n'),
    }));
    if (!job.output) return originals;
    const state = `${job.status} · ${job.mode || 'generated'}`;
    return originals.concat([
      { title: 'Meeting brief', kind: 'generated', state, job,
        content: job.output.review_note + '\n\n' + job.output.facts.map(f => {
          const source = job.sources.find(s => s.id === f.source_id);
          return `${source?.filename || f.source_id} · ${source?.locator_kind || 'locator'} ${f.page}\n${f.quote}`;
        }).join('\n\n') },
      { title: 'Confirmation checklist', kind: 'generated', state, job,
        content: job.output.missing_information.map(i => `${i.question} [${i.status}]`).join('\n\n') },
      { title: 'Follow-up draft', kind: 'generated', state, job, content: job.output.follow_up },
    ]);
  }
  async function download(item) {
    const s = loadedScope, ticket = generation;
    if (!s) return;
    try {
      const query = new URLSearchParams({venture: s.venture, project: s.project});
      const response = await fetch(`/api/prospects/${encodeURIComponent(item.job.id)}/sources/${encodeURIComponent(item.source.id)}?${query}`, {
        headers: {Authorization: `Bearer ${credential.value}`}, cache: 'no-store', signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Download failed (${response.status}).`);
      const blob = await response.blob();
      if (!active || ticket !== generation) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = item.title; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { if (active && ticket === generation) status.textContent = error.message; }
  }
  function inspect(item) {
    detail.replaceChildren(); detail.hidden = false;
    const title = node('h3', item.title, detail); title.tabIndex = -1;
    node('p', `${item.job.prospect} / ${item.state}`, detail);
    if (item.source) {
      node('p', 'SHA-256: ' + item.source.sha256, detail, 'knowledge-hash');
      button(detail, 'Download original', () => download(item));
    } else node('p', 'Saved revision: ' + item.job.output_hash, detail, 'knowledge-hash');
    button(detail, 'Open brief and review', () => {
      store.openProspect(item.job.id, loadedScope.venture, loadedScope.project);
    });
    const history = node('div', undefined, detail);
    const historyButton = button(detail, 'View revision and review history', async () => {
      const s = loadedScope, ticket = generation;
      historyButton.disabled = true;
      try {
        const query = new URLSearchParams(s);
        const records = await Promise.all(['versions', 'events'].map(async endpoint => {
          const response = await fetch(`/api/prospects/${encodeURIComponent(item.job.id)}/${endpoint}?${query}`, {
            headers: {Authorization: `Bearer ${credential.value}`}, cache: 'no-store', signal: controller.signal,
          });
          if (!response.ok) throw new Error(`History unavailable (${response.status}).`);
          return [endpoint, await response.json()];
        }));
        if (active && ticket === generation) {
          history.replaceChildren();
          node('h4', 'Revision and review history', history);
          const saved = Object.fromEntries(records);
          const revisions = node('ul', undefined, history);
          for (const version of saved.versions) {
            node('li', `${new Date(version.at * 1000).toLocaleString()} · Revision ${version.output_hash.slice(0, 12)}${version.output_hash === item.job.output_hash ? ' · current' : ''}`, revisions);
          }
          const events = node('ol', undefined, history);
          for (const event of saved.events) {
            node('li', `${new Date(event.at * 1000).toLocaleString()} · ${event.kind.replaceAll('_', ' ')}${event.data.decision ? ' · ' + event.data.decision : ''}${event.data.reviewer ? ' · ' + event.data.reviewer : ''}`, events);
          }
        }
      } catch (error) { if (active && ticket === generation) node('p', error.message, history); }
      finally { historyButton.disabled = false; }
    });
    node('pre', item.content, detail);
    button(detail, 'Close preview', () => { detail.hidden = true; search.focus(); });
    title.focus();
  }
  function draw() {
    tree.replaceChildren(); cards.replaceChildren(); rows.replaceChildren();
    breadcrumb.textContent = loadedScope ? `${loadedScope.venture} / ${loadedScope.project} / ${selected ? jobs.find(j => j.id === selected)?.prospect : 'All folders'}` : 'Project files';
    const all = button(tree, `All prospect folders (${jobs.length})`, () => { selected = null; detail.hidden = true; draw(); });
    all.setAttribute('aria-pressed', String(selected === null));
    for (const job of jobs) {
      const b = button(tree, job.prospect, () => { selected = job.id; detail.hidden = true; draw(); });
      b.setAttribute('aria-pressed', String(selected === job.id));
    }
    const term = search.value.trim().toLocaleLowerCase();
    const visible = jobs.filter(j => (!selected || j.id === selected));
    for (const job of visible.filter(j => !term || j.prospect.toLocaleLowerCase().includes(term) || items(j).some(i => i.title.toLocaleLowerCase().includes(term)))) {
      const b = button(cards, '', () => { selected = job.id; detail.hidden = true; draw(); }, 'knowledge-folder');
      b.setAttribute('aria-label', 'Open folder: ' + job.prospect);
      const art = node('span', undefined, b, 'knowledge-folder-art'); art.setAttribute('aria-hidden', 'true');
      node('span', '', art, 'knowledge-paper'); node('span', '', art, 'knowledge-paper second'); node('span', '', art, 'knowledge-pocket');
      node('strong', job.prospect, b);
      node('span', `${job.sources.length} originals · ${job.output ? 3 : 0} generated`, b);
      node('small', job.status.replaceAll('_', ' ') + ' · Created ' + new Date(job.created_at * 1000).toLocaleDateString(), b);
    }
    for (const [key, b] of filters) b.setAttribute('aria-pressed', String(category === key));
    let count = 0;
    for (const job of visible) for (const item of items(job)) {
      if (category !== 'all' && item.kind !== category) continue;
      if (term && !`${job.prospect} ${item.title}`.toLocaleLowerCase().includes(term)) continue;
      count++;
      const row = node('div', undefined, rows, 'knowledge-file');
      const name = button(row, item.title, () => inspect(item), 'knowledge-file-name');
      name.setAttribute('aria-label', `Preview ${item.title} in ${job.prospect}`);
      node('span', job.prospect, row, 'knowledge-file-folder');
      node('span', item.state, row, 'knowledge-file-status');
    }
    if (!count) node('p', loadedScope ? 'No files match this view.' : 'Load a project to see its files.', rows);
  }
  search.addEventListener('input', draw);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    clear('Loading project files…');
    const ticket = generation;
    const s = {venture: venture.value, project: project.value};
    api.setToken(credential.value); load.disabled = true;
    try {
      const response = await fetch('/api/prospects?' + new URLSearchParams(s), {
        headers: {Authorization: `Bearer ${credential.value}`}, cache: 'no-store', signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Could not load files (${response.status}). Check your token and project scope.`);
      const data = await response.json();
      if (!active || ticket !== generation) return;
      // The list API intentionally returns summaries, not document bodies.
      // Hydrate authorized records with bounded concurrency; never paint partial scopes.
      const records = new Array(data.length);
      let next = 0;
      await Promise.all(Array.from({length: Math.min(4, data.length)}, async () => {
        while (next < data.length) {
          const index = next++;
          const record = await fetch(`/api/prospects/${encodeURIComponent(data[index].id)}?${new URLSearchParams(s)}`, {
            headers: {Authorization: `Bearer ${credential.value}`}, cache: 'no-store', signal: controller.signal,
          });
          if (!record.ok) throw new Error(`Could not load a prospect folder (${record.status}). Reload this project.`);
          records[index] = await record.json();
        }
      }));
      if (!active || ticket !== generation) return;
      jobs = records; loadedScope = s; draw();
      status.textContent = `${jobs.length} prospect folders loaded. Showing up to the latest 100 records in this scope. Generated artifacts are views, not additional stored source files.`;
    } catch (error) { if (active && ticket === generation) status.textContent = error.message; }
    finally { if (active && ticket === generation) load.disabled = false; }
  });
  draw();
  return () => { active = false; controller.abort(); };
}
