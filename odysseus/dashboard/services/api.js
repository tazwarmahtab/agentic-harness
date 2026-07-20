/**
 * AOS Dashboard API Client.
 * All requests go through Odysseus proxy (never direct to port 7001).
 */

const API_BASE = '/api/aos';
const NETSO_API_BASE = '/api/netso';

class AosApi {
  constructor(baseUrl = API_BASE, netsoBaseUrl = NETSO_API_BASE) {
    this.baseUrl = baseUrl;
    this.netsoBaseUrl = netsoBaseUrl;
  }

  async _get(path) {
    const resp = await fetch(this.baseUrl + path);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return resp.json();
  }

  async _getNetso(path) {
    const resp = await fetch(this.netsoBaseUrl + path);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return resp.json();
  }

  async _post(path, body = {}) {
    const resp = await fetch(this.baseUrl + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return resp.json();
  }

  // ── Aggregate ──────────────────────────────────────────────────────────
  getDashboard()       { return this._get('/dashboard'); }

  // ── Harnesses ──────────────────────────────────────────────────────────
  getHarnesses()       { return this._get('/harnesses'); }
  getSummary()         { return this._get('/summary'); }

  // ── Pipeline ───────────────────────────────────────────────────────────
  getPipelineStatus()  { return this._get('/pipeline/status'); }
  getPipelineHistory() { return this._get('/pipeline/history'); }

  // ── Approvals ──────────────────────────────────────────────────────────
  getApprovals()                   { return this._get('/approvals'); }
  approve(id)                      { return this._post(`/approvals/${id}/approve`); }
  reject(id)                       { return this._post(`/approvals/${id}/reject`); }

  // ── Memory ─────────────────────────────────────────────────────────────
  getMemorySummary()   { return this._get('/memory/summary'); }

  // ── Events ─────────────────────────────────────────────────────────────
  getEvents()          { return this._get('/events'); }
  getEntityIndex()     { return this._get('/entity-index'); }

  // ── Netso Customer Dashboard ───────────────────────────────────────────
  getNetsoGeneration(siteId) { return this._getNetso(`/customers/${siteId}/generation`); }
  getNetsoSavings(siteId)    { return this._getNetso(`/customers/${siteId}/savings`); }
  getNetsoBilling(siteId)    { return this._getNetso(`/customers/${siteId}/billing`); }
  getNetsoPortfolio()        { return this._getNetso('/portfolio'); }
  getNetsoFinancials()       { return this._getNetso('/financials'); }

  // ── Sales ──────────────────────────────────────────────────────────────
  getSalesStatus()     { return this._get('/sales/status'); }

  // ── System ─────────────────────────────────────────────────────────────
  getSystemStatus()    { return this._get('/system/status'); }
  getAgents()          { return this._get('/agents'); }
  getHealth()          { return this._get('/health'); }
  getWsStats()         { return this._get('/ws/stats'); }
}

export const api = new AosApi();
export default api;
