/**
 * AOS Dashboard Store — central state management.
 * Lightweight pub/sub store. No framework dependency.
 */

import api from '../services/api.js';

class DashboardStore {
  constructor() {
    this._state = {
      // Connection
      engineOnline: false,
      wsConnections: 0,
      wsMaxConnections: 10,

      // KPIs
      harnessCount: 0,
      testCount: 0,
      memoryDomains: 0,
      entityCount: 0,
      eventCount: 0,
      approvalCount: 0,
      healthScore: null,

      // Live data
      harnesses: [],
      pipeline: null,
      approvals: [],
      memory: null,
      sales: null,
      system: null,
      agents: [],
      events: [],
      entityIndex: null,

      // UI
      currentPage: 'overview',
      loading: false,
      error: null,
      lastUpdated: null,
    };
    this._listeners = new Set();
    this._refreshTimer = null;
  }

  get state() { return this._state; }

  subscribe(callback) {
    this._listeners.add(callback);
    return () => this._listeners.delete(callback);
  }

  _update(partial) {
    this._state = { ...this._state, ...partial, lastUpdated: new Date() };
    this._listeners.forEach((cb) => {
      try { cb(this._state); } catch (e) { console.error('Store listener error:', e); }
    });
  }

  // ── Data Fetching ───────────────────────────────────────────────────────

  async loadDashboard() {
    this._update({ loading: true, error: null });
    try {
      const data = await api.getDashboard();
      this._update({
        loading: false,
        engineOnline: true,
        harnessCount: data.harnesses ?? 0,
        testCount: data.tests ?? 0,
        memoryDomains: data.memory_domains ?? 0,
        entityCount: data.entity_count ?? 0,
        eventCount: data.event_count ?? 0,
        approvalCount: data.approval_count ?? 0,
        healthScore: data.health_score ?? null,
        wsConnections: data.ws_connections ?? 0,
        wsMaxConnections: data.ws_max_connections ?? 10,
      });
    } catch (e) {
      this._update({ loading: false, engineOnline: false, error: e.message });
    }
  }

  async loadHarnesses() {
    try {
      const data = await api.getHarnesses();
      this._update({ harnesses: Array.isArray(data) ? data : [] });
    } catch (e) { console.error('Failed to load harnesses:', e); }
  }

  async loadPipeline() {
    try {
      const data = await api.getPipelineStatus();
      this._update({ pipeline: data });
    } catch (e) { console.error('Failed to load pipeline:', e); }
  }

  async loadApprovals() {
    try {
      const data = await api.getApprovals();
      this._update({ approvals: Array.isArray(data) ? data : [] });
    } catch (e) { console.error('Failed to load approvals:', e); }
  }

  async loadMemory() {
    try {
      const data = await api.getMemorySummary();
      this._update({ memory: data });
    } catch (e) { console.error('Failed to load memory:', e); }
  }

  async loadSales() {
    try {
      const data = await api.getSalesStatus();
      this._update({ sales: data });
    } catch (e) { console.error('Failed to load sales:', e); }
  }

  async loadSystem() {
    try {
      const data = await api.getSystemStatus();
      this._update({ system: data });
    } catch (e) { console.error('Failed to load system:', e); }
  }

  async loadAgents() {
    try {
      const data = await api.getAgents();
      this._update({ agents: Array.isArray(data) ? data : [] });
    } catch (e) { console.error('Failed to load agents:', e); }
  }

  async loadEvents() {
    try {
      const data = await api.getEvents();
      this._update({ events: data });
    } catch (e) { console.error('Failed to load events:', e); }
  }

  async loadEntityIndex() {
    try {
      const data = await api.getEntityIndex();
      this._update({ entityIndex: data });
    } catch (e) { console.error('Failed to load entity index:', e); }
  }

  // ── Actions ────────────────────────────────────────────────────────────

  async approveDecision(id) {
    await api.approve(id);
    await this.loadApprovals();
  }

  async rejectDecision(id) {
    await api.reject(id);
    await this.loadApprovals();
  }

  setPage(page) {
    this._update({ currentPage: page });
  }

  // ── Auto-refresh ───────────────────────────────────────────────────────

  startAutoRefresh(intervalMs = 30000) {
    this.stopAutoRefresh();
    this._refreshTimer = setInterval(() => this.loadDashboard(), intervalMs);
  }

  stopAutoRefresh() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
  }
}

export const store = new DashboardStore();
export default store;
