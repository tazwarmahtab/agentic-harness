# Netso Customer Dashboard — Design Spec

**Date:** 2026-07-20
**Status:** Draft for review
**Scope:** Extend Odysseus dashboard with Netso customer-facing and internal ops views, role-gated.

## 1. Purpose

Add a Netso-specific dashboard to the existing Odysseus Mission Control UI. Two audiences:

- **Customers** (e.g., CGS) see their solar installation performance, energy savings, and PPA billing.
- **Internal operators** see the customer portfolio, financial projections, and DSCR alerts.

Both live inside the same Odysseus shell, gated by a `role` field in the existing pub/sub store.

## 2. Architecture

### 2.1 Frontend

Extend the existing Odysseus vanilla JS dashboard. No new framework.

**New files:**

```
odysseus/dashboard/
  pages/netso/
    netso-overview.js
    customer-generation.js
    customer-savings.js
    customer-billing.js
    internal-portfolio.js
    internal-financials.js
  widgets/
    savings-tile.js
    dscr-banner.js
```

**Modified files:**

- `odysseus/dashboard/stores/dashboard.js` — add `role`, Netso state fields, `loadNetsoXxx()` methods
- `odysseus/dashboard/layouts/dashboard-layout.js` — add Netso NAV_ITEMS filtered by role
- `odysseus/dashboard/services/api.js` — add `getNetsoXxx()` client methods
- `odysseus/dashboard/index.js` — register Netso pages in `PAGES` map

**Cut from v1 (YAGNI):**

- `internal-pipeline.js` — no live sales CRM yet; add when SIGNAL persona is active
- `generation-chart.js` widget — requires a charting library; replace with trend indicators (↑/↓ percentage) for now

### 2.2 Backend

New service module + API endpoints in the AOS engine, proxied through Odysseus.

**New files:**

```
aos/services/
  netso_customer.py        # frozen dataclasses + to_dict() per endpoint
odysseus/routes/
  netso_routes.py          # proxy routes mounted at /api/netso/*
```

**Modified files:**

- `aos/api.py` — mount Netso router
- `odysseus/routes/__init__.py` — register Netso proxy router

### 2.3 Data Sources

- **Financial constants** — read from `aos/constants.py` (`NETSO_FINANCIAL` dict) and `aos/ventures/netso/venture.yml`
- **Customer data** — seed JSON files in `aos/ventures/netso/seed/` for MVP (real database later)
- **Live generation** — WebSocket channel `netso.generation.{site_id}` (stub for MVP)

## 3. Role Gating

The existing `DashboardStore` gains a `role` field:

```js
role: 'internal' // 'customer' | 'internal' | 'admin'
```

Sidebar navigation filters pages by role:

```js
const NETSO_NAV = [
  { id: 'netso-overview',   icon: '🏠', label: 'Overview',   roles: ['customer', 'internal', 'admin'] },
  { id: 'netso-generation', icon: '☀️', label: 'Generation', roles: ['customer', 'admin'] },
  { id: 'netso-savings',    icon: '💰', label: 'Savings',    roles: ['customer', 'admin'] },
  { id: 'netso-billing',    icon: '📄', label: 'Billing',    roles: ['customer', 'admin'] },
  { id: 'netso-portfolio',  icon: '🏢', label: 'Portfolio',  roles: ['internal', 'admin'] },
  { id: 'netso-financials', icon: '📈', label: 'Financials', roles: ['internal', 'admin'] },
];
```

**Customer identity (MVP):** Query parameter `?site_id=CGS-001`. No multi-tenancy, no login beyond existing `AOS_API_TOKEN`. Admin view includes a customer selector dropdown at the top.

## 4. API Endpoints

All responses follow the existing pattern: flat dicts, snake_case keys, no wrapper envelope.

### 4.1 `GET /api/netso/customers/{site_id}/generation`

Returns solar generation data for a customer site.

```json
{
  "customer_id": "CGS-001",
  "customer_name": "Comprehensive Garment Solutions",
  "system_capacity_kw": 850,
  "current_month": {
    "generation_kwh": 12750,
    "capacity_factor_pct": 16.5,
    "availability_pct": 98.2,
    "grid_export_kwh": 1850,
    "self_consumption_pct": 85.5
  },
  "ytd": {
    "generation_kwh": 76500,
    "grid_export_kwh": 11100,
    "self_consumption_pct": 85.5
  },
  "trend": [
    {"month": "2026-01", "generation_kwh": 11200},
    {"month": "2026-02", "generation_kwh": 11800},
    {"month": "2026-03", "generation_kwh": 12750}
  ],
  "alerts": [],
  "last_updated": "2026-07-20T08:00:00+06:00"
}
```

### 4.2 `GET /api/netso/customers/{site_id}/savings`

Savings breakdown vs grid rate. All values derived from ground-truth constants.

```json
{
  "customer_id": "CGS-001",
  "customer_name": "Comprehensive Garment Solutions",
  "system_capacity_kw": 850,
  "grid_rate_bdt_per_kwh": 12.98,
  "ppa_rate_bdt_per_kwh": 10.00,
  "savings_pct": 23.0,
  "current_month": {
    "generation_kwh": 12750,
    "grid_cost_bdt": 165495.00,
    "ppa_cost_bdt": 127500.00,
    "savings_bdt": 37995.00
  },
  "ytd": {
    "generation_kwh": 76500,
    "grid_cost_bdt": 992970.00,
    "ppa_cost_bdt": 765000.00,
    "savings_bdt": 227970.00
  },
  "lifetime_projected": {
    "total_savings_bdt": 3825450.00,
    "payback_years": 4.1,
    "irr_pct": 68.7
  },
  "escalation": {
    "rate": 3.0,
    "next_escalation_date": "2029-01-01",
    "projected_ppa_after_escalation": 10.30
  },
  "trend": [
    {"month": "2026-01", "savings_bdt": 33600.00},
    {"month": "2026-02", "savings_bdt": 35400.00},
    {"month": "2026-03", "savings_bdt": 37995.00}
  ]
}
```

**Math notes:**
- `grid_cost_bdt` = `generation_kwh` × 12.98 (true variable rate, NEVER blended)
- `savings_bdt` = `grid_cost_bdt` − `ppa_cost_bdt`
- `lifetime_projected.total_savings_bdt` = `system_capacity_kw` × 16.5% CF × 8,760 hrs × 25 yrs × (12.98 − 10.00) = ~3.83M BDT

### 4.3 `GET /api/netso/customers/{site_id}/billing`

PPA invoices and payment history.

```json
{
  "customer_id": "CGS-001",
  "customer_name": "Comprehensive Garment Solutions",
  "billing_cycle": "2026-07",
  "current_invoice": {
    "invoice_id": "INV-2026-07-CGS001",
    "generation_kwh": 12750,
    "ppa_rate_bdt_per_kwh": 10.00,
    "amount_bdt": 127500.00,
    "status": "pending",
    "due_date": "2026-08-15",
    "payment_method": "bank_transfer"
  },
  "outstanding": {
    "total_bdt": 127500.00,
    "overdue_count": 0,
    "overdue_amount_bdt": 0.00
  },
  "history": [
    {
      "invoice_id": "INV-2026-06-CGS001",
      "amount_bdt": 122100.00,
      "status": "paid",
      "paid_date": "2026-07-10",
      "generation_kwh": 12210
    }
  ]
}
```

**Note:** DSCR is a project-level metric, not per-customer. It lives on the `/api/netso/financials` endpoint only.
```

### 4.4 `GET /api/netso/portfolio`

Aggregated view across all customers (internal only).

```json
{
  "total_customers": 5,
  "total_capacity_kw": 4250,
  "portfolio_status": {
    "active": 4,
    "in_installation": 1,
    "churned": 0
  },
  "generation_summary": {
    "current_month_kwh": 63750,
    "ytd_kwh": 382500,
    "capacity_factor_avg_pct": 16.5
  },
  "financial_summary": {
    "pipeline_value_bdt": 21250000,
    "monthly_revenue_bdt": 637500,
    "ytd_revenue_bdt": 3825000,
    "ytd_savings_delivered_bdt": 1144350
  },
  "customers": [
    {
      "customer_id": "CGS-001",
      "customer_name": "Comprehensive Garment Solutions",
      "capacity_kw": 850,
      "status": "active",
      "monthly_generation_kwh": 12750,
      "monthly_savings_bdt": 38145,
      "health_score": 0.98
    }
  ],
  "alerts": {
    "dscr_breaches": 0,
    "overdue_invoices": 0,
    "system_faults": 0
  },
  "financial_constants": {
    "capex_per_kw": 55000,
    "ppa_rate": 10.00,
    "customer_savings_pct": 23.0,
    "true_variable_rate": 12.98
  }
}
```

### 4.5 `GET /api/netso/financials`

Unit economics and scenario analysis (internal only).

```json
{
  "venture_id": "VEN-NETSO-001",
  "venture_name": "Netso Energy",
  "unit_economics": {
    "capex_per_kw_bdt": 55000,
    "opex_per_kw_bdt": 1000,
    "ppa_rate_bdt_per_kwh": 10.00,
    "true_variable_rate_bdt_per_kwh": 12.98,
    "customer_savings_pct": 23.0,
    "nem_export_rate_bdt_per_kwh": 6.4523,
    "capacity_factor_pct": 16.5
  },
  "scenarios": {
    "scenario_a": {
      "capex_per_kw": 55000,
      "dscr": 2.25,
      "payback_years": 4.1,
      "levered_irr_pct": 68.7
    },
    "scenario_b": {
      "capex_per_kw": 40000,
      "dscr": 3.09,
      "payback_years": 3.0,
      "levered_irr_pct": 114.1,
      "conditional": true,
      "condition": "NBR confirmation of 0% import duty"
    }
  },
  "debt_structure": {
    "idcol_debt_pct": 80,
    "idcol_interest_pct": 6.0,
    "idcol_term_years": 10
  },
  "portfolio_financials": {
    "total_capex_bdt": 233750000,
    "monthly_revenue_bdt": 637500,
    "ytd_revenue_bdt": 3825000,
    "annual_opex_bdt": 4250000,
    "monthly_opex_bdt": 354167,
    "net_monthly_bdt": 283333
  },
  "approval_thresholds": {
    "proposal_value_bdt": 5000000,
    "dscr_escalation_floor": 2.25,
    "dscr_alert_floor": 2.0
  },
  "model_accuracy": null
}
```

## 5. Pages

### 5.0 Netso Overview (`netso-overview.js`)

Landing page for all Netso roles. Combines key metrics from all views into a single summary.

**Customer view:**
- KPI strip: system capacity, current month generation, current month savings (BDT), next invoice amount, savings percentage
- Quick status: system health, last generation update, next billing date
- Links to detailed pages (generation, savings, billing)

**Internal view:**
- KPI strip: total customers, total capacity, monthly revenue, DSCR status, overdue invoices
- Portfolio health: active vs in-installation vs churned
- DSCR alert banner (if breaches exist)
- Links to detailed pages (portfolio, financials)

### 5.1 Customer: Generation (`customer-generation.js`)

- KPI strip: system capacity (kW), current month generation (kWh), capacity factor (%), availability (%), self-consumption (%)
- Trend indicators: month-over-month generation change (↑/↓ percentage), no chart library
- YTD summary row
- Alerts section (empty for MVP, reserved for system faults)
- Loading skeleton: gray KPI tile placeholders until data arrives
- Error state: "Unable to load generation data" toast + retry button

### 5.2 Customer: Savings (`customer-savings.js`)

- KPI strip: grid rate vs PPA rate, current month savings (BDT), savings percentage, YTD savings
- `savings-tile.js` widget: displays BDT saved with trend arrow (↑/↓ %)
- Escalation info: next escalation date, projected PPA rate after escalation
- Lifetime projection: total savings, payback years, IRR
- Loading skeleton + error state

### 5.3 Customer: Billing (`customer-billing.js`)

- Current invoice card: invoice ID, amount (BDT), status badge, due date
- Outstanding summary: total outstanding, overdue count
- Payment history table: last 12 invoices with status (paid/pending/overdue)
- Loading skeleton + error state

### 5.4 Internal: Portfolio (`internal-portfolio.js`)

- Aggregate KPI strip: total customers, total capacity (kW), monthly generation, monthly revenue
- Customer list table: name, capacity, status, monthly generation, monthly savings, health score
- Customer selector dropdown at the top (admin view) — switches the customer-facing pages below
- Alert summary: DSCR breaches, overdue invoices, system faults
- Loading skeleton + error state

### 5.5 Internal: Financials (`internal-financials.js`)

- Unit economics card: CAPEX/kW, OPEX/kW, PPA rate, variable rate, savings %, capacity factor
- Scenario comparison: Scenario A vs Scenario B side-by-side (DSCR, payback, IRR)
- Debt structure: IDCOL terms
- Portfolio financials: total CAPEX, monthly revenue, YTD revenue, net monthly
- Approval thresholds
- **DSCR alert banner** (`dscr-banner.js`): persistent red banner if any customer's DSCR < 2.0, impossible to miss. Shows customer name + current DSCR value.

## 6. Widgets

### 6.1 `savings-tile.js`

Displays BDT saved with a trend indicator. Takes `{ value_bdt, trend_pct, label }` props. Uses `textContent` for XSS safety. Trend arrow: ↑ green if positive, ↓ red if negative.

### 6.2 `dscr-banner.js`

Full-width red banner rendered at the top of the dashboard shell (not inside a page). **Internal-only** — only renders when `state.role` is `'internal'` or `'admin'`. Checks `state.portfolio.alerts.dscr_breaches > 0` on every store update. If breaches exist, shows: "⚠️ DSCR Alert: {customer_name} at {dscr_value} — below 2.0 floor". Dismissible per session (not per page). Customers never see this banner — DSCR is a project-level metric, not customer-facing.

## 7. Loading and Error Patterns

All pages must handle three states:

1. **Loading** — show skeleton KPI tiles (gray pulsing placeholders matching existing `aos-kpi-tile` dimensions)
2. **Success** — render data
3. **Error** — show error message with retry button, log to console (no `console.log` in production — use the existing error channel)

## 8. Seed Data

MVP uses JSON seed files instead of a database:

```
aos/ventures/netso/seed/
  customers.json         # customer profiles + site metadata
  generation.json        # monthly generation data per site
  billing.json           # invoice history per site
```

Seed data covers 1 customer (CGS-001) with 3 months of history. Enough to demo all pages.

## 9. Testing

- **Backend:** Unit tests for each service function (frozen dataclass construction, `to_dict()` output shape). Integration tests for API endpoints (FastAPI `TestClient`).
- **Frontend:** Manual verification via Odysseus dashboard. No JS test framework in the existing stack.
- **Coverage target:** 60% minimum (matches existing `pyproject.toml` threshold).

## 10. What's NOT in Scope

- Real database / ORM (seed JSON only for MVP)
- User authentication beyond existing `AOS_API_TOKEN`
- Multi-tenancy isolation (admin sees everything, customer sees their site via query param)
- Mobile-responsive layout (existing CSS handles basics)
- `internal-pipeline.js` (no live sales CRM yet)
- `generation-chart.js` widget (no charting library; trend indicators instead)
- WebSocket live generation stream (stub only, real data later)

## 11. Build Order

1. Seed data files (`aos/ventures/netso/seed/`)
2. Backend service (`aos/services/netso_customer.py`) + frozen dataclasses
3. API endpoints (`aos/api.py` additions)
4. Odysseus proxy routes (`odysseus/routes/netso_routes.py`)
5. Store extensions (`stores/dashboard.js` — role, Netso state, load methods)
6. API client methods (`services/api.js`)
7. Layout + nav filtering (`layouts/dashboard-layout.js`)
8. Widgets (`savings-tile.js`, `dscr-banner.js`)
9. Netso overview page (`netso-overview.js`)
10. Customer pages (generation → savings → billing)
11. Internal pages (portfolio → financials)
12. Tests (backend service + API endpoints)
13. Page registration (`index.js` PAGES map)
