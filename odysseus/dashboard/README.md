# AOS Dashboard — Mission Control UI

Modular dashboard for the Agent Operating System. Built for Odysseus integration.

## Architecture

```
dashboard/
├── index.js              # Entry point — openPanel() / closePanel()
├── dashboard.css         # Glass-morphism styles (Odysseus theme-aware)
├── services/
│   ├── api.js            # REST API client (proxies through Odysseus)
│   └── websocket.js      # WS client with auto-reconnect
├── stores/
│   └── dashboard.js      # Central state store (pub/sub)
├── layouts/
│   └── dashboard-layout.js  # Sidebar + header + content shell
├── pages/
│   ├── overview.js       # KPI tiles + system status
│   ├── harnesses.js      # Harness grid + live execution stream
│   ├── pipelines.js      # Orchestrate pipeline phases
│   ├── approvals.js      # Approval queue with approve/reject
│   ├── memory.js         # 3-layer memory explorer
│   ├── entities.js       # Entity index breakdown
│   ├── events.js         # Filterable event timeline
│   ├── sales.js          # Sales graph status
│   └── system.js         # System metrics + agent health
└── widgets/
    ├── kpi-tile.js       # KPI display widget
    └── status-dot.js     # Colored status indicator
```

## Odysseus Integration

```js
// In app.js
import aosDashboard from './dashboard/index.js';
import './dashboard/dashboard.css';

Modals.register('aos-dashboard-modal', {
  railBtnId: 'rail-aos',
  restoreFn: () => aosDashboard.openPanel(),
  closeFn:   () => aosDashboard.closePanel(),
});

_routeOpen['/aos'] = () => {
  _collapseSidebarToRail();
  aosDashboard.openPanel();
};
```

## Design Principles

- **No framework** — vanilla JS, zero dependencies
- **textContent only** — XSS-safe rendering (no innerHTML with dynamic data)
- **Glass-morphism** — uses Odysseus CSS custom properties
- **Modular** — each page is independent, loads on demand
- **Real-time** — WebSocket for live execution streaming
- **Pub/sub store** — no framework state management needed
