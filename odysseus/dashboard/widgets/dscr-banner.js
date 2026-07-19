/**
 * DSCR Alert Banner — persistent red banner for DSCR breaches.
 * Internal-only — only renders for internal/admin roles.
 * Uses textContent for XSS safety.
 */

import store from '../stores/dashboard.js';

let _bannerEl = null;
let _unsub = null;

export function initDscrBanner() {
  if (_unsub) return;

  _unsub = store.subscribe((state) => {
    if (state.role === 'customer') {
      if (_bannerEl) { _bannerEl.remove(); _bannerEl = null; }
      return;
    }

    const breaches = state.netsoPortfolio?.alerts?.dscr_breaches ?? 0;
    if (breaches > 0 && !_bannerEl) {
      _bannerEl = document.createElement('div');
      _bannerEl.className = 'aos-dscr-banner';
      _bannerEl.setAttribute('role', 'alert');
      _bannerEl.style.cssText = 'background:#DC2626;color:#fff;padding:8px 16px;text-align:center;font-weight:600;position:sticky;top:0;z-index:100;';

      const text = document.createElement('span');
      text.textContent = `⚠️ DSCR Alert: ${breaches} customer(s) below 2.0 floor`;
      _bannerEl.appendChild(text);

      const dismiss = document.createElement('button');
      dismiss.textContent = '✕';
      dismiss.style.cssText = 'background:none;border:none;color:#fff;margin-left:12px;cursor:pointer;font-size:14px;';
      dismiss.addEventListener('click', () => {
        if (_bannerEl) { _bannerEl.remove(); _bannerEl = null; }
      });
      _bannerEl.appendChild(dismiss);

      const main = document.querySelector('.aos-main');
      if (main) main.prepend(_bannerEl);
    } else if (breaches === 0 && _bannerEl) {
      _bannerEl.remove();
      _bannerEl = null;
    }
  });
}

export function destroyDscrBanner() {
  if (_unsub) { _unsub(); _unsub = null; }
  if (_bannerEl) { _bannerEl.remove(); _bannerEl = null; }
}
