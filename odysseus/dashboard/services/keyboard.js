/**
 * Keyboard Navigation — Cmd+K command palette, page shortcuts.
 * Accessible: all actions reachable via keyboard.
 */

import store from '../stores/dashboard.js';

const SHORTCUTS = [
  { key: '1', label: 'Overview', page: 'overview' },
  { key: '2', label: 'Harnesses', page: 'harnesses' },
  { key: '3', label: 'Pipelines', page: 'pipelines' },
  { key: '4', label: 'Approvals', page: 'approvals' },
  { key: '5', label: 'Memory', page: 'memory' },
  { key: '6', label: 'Entities', page: 'entities' },
  { key: '7', label: 'Events', page: 'events' },
  { key: '8', label: 'Sales', page: 'sales' },
  { key: '9', label: 'System', page: 'system' },
];

let _paletteOpen = false;
let _paletteEl = null;
let _onKeyDown = null;

export function initKeyboardShortcuts() {
  _onKeyDown = (e) => {
    // Cmd+K / Ctrl+K — open command palette
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      togglePalette();
      return;
    }

    // Escape — close palette
    if (e.key === 'Escape' && _paletteOpen) {
      closePalette();
      return;
    }

    // Number keys (no modifier) — navigate to page (only when not in input)
    if (!e.metaKey && !e.ctrlKey && !e.altKey && !_paletteOpen) {
      const target = e.target;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;

      const shortcut = SHORTCUTS.find((s) => s.key === e.key);
      if (shortcut) {
        e.preventDefault();
        store.setPage(shortcut.page);
      }
    }
  };

  document.addEventListener('keydown', _onKeyDown);
}

export function destroyKeyboardShortcuts() {
  if (_onKeyDown) {
    document.removeEventListener('keydown', _onKeyDown);
    _onKeyDown = null;
  }
  closePalette();
}

function togglePalette() {
  if (_paletteOpen) {
    closePalette();
  } else {
    openPalette();
  }
}

function openPalette() {
  if (_paletteOpen) return;
  _paletteOpen = true;

  _paletteEl = document.createElement('div');
  _paletteEl.className = 'aos-command-palette';
  _paletteEl.setAttribute('role', 'dialog');
  _paletteEl.setAttribute('aria-label', 'Command palette');

  const backdrop = document.createElement('div');
  backdrop.className = 'aos-palette-backdrop';
  backdrop.addEventListener('click', closePalette);

  const dialog = document.createElement('div');
  dialog.className = 'aos-palette-dialog';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'aos-palette-input';
  input.placeholder = 'Type a page name...';
  input.setAttribute('aria-label', 'Search pages');
  input.addEventListener('input', () => filterPalette(input.value));

  const list = document.createElement('div');
  list.className = 'aos-palette-list';
  list.id = 'aos-palette-list';

  renderPaletteItems(list, '');

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const active = list.querySelector('.aos-palette-item.active') || list.querySelector('.aos-palette-item');
      if (active) {
        const page = active.dataset.page;
        if (page) {
          store.setPage(page);
          closePalette();
        }
      }
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      navigatePalette(list, e.key === 'ArrowDown' ? 1 : -1);
    }
  });

  dialog.appendChild(input);
  dialog.appendChild(list);
  _paletteEl.appendChild(backdrop);
  _paletteEl.appendChild(dialog);
  document.body.appendChild(_paletteEl);

  requestAnimationFrame(() => input.focus());
}

function closePalette() {
  _paletteOpen = false;
  if (_paletteEl) {
    _paletteEl.remove();
    _paletteEl = null;
  }
}

function filterPalette(term) {
  const list = document.getElementById('aos-palette-list');
  if (list) renderPaletteItems(list, term.toLowerCase());
}

function renderPaletteItems(container, term) {
  container.innerHTML = '';
  const items = SHORTCUTS.filter((s) => !term || s.label.toLowerCase().includes(term));

  items.forEach((item, idx) => {
    const el = document.createElement('div');
    el.className = `aos-palette-item${idx === 0 ? ' active' : ''}`;
    el.dataset.page = item.page;
    el.setAttribute('role', 'option');

    const key = document.createElement('span');
    key.className = 'aos-palette-key';
    key.textContent = item.key;

    const label = document.createElement('span');
    label.className = 'aos-palette-label';
    label.textContent = item.label;

    el.appendChild(key);
    el.appendChild(label);

    el.addEventListener('click', () => {
      store.setPage(item.page);
      closePalette();
    });

    el.addEventListener('mouseenter', () => {
      container.querySelectorAll('.aos-palette-item').forEach((i) => i.classList.remove('active'));
      el.classList.add('active');
    });

    container.appendChild(el);
  });

  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'aos-palette-empty';
    empty.textContent = 'No matching pages';
    container.appendChild(empty);
  }
}

function navigatePalette(list, direction) {
  const items = list.querySelectorAll('.aos-palette-item');
  if (!items.length) return;

  let idx = -1;
  items.forEach((item, i) => {
    if (item.classList.contains('active')) idx = i;
  });

  items.forEach((item) => item.classList.remove('active'));
  idx = (idx + direction + items.length) % items.length;
  items[idx].classList.add('active');
  items[idx].scrollIntoView({ block: 'nearest' });
}
