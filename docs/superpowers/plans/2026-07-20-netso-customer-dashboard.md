# Netso Customer Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Odysseus dashboard with Netso customer-facing (generation, savings, billing) and internal ops (portfolio, financials) views, role-gated via the existing store.

**Architecture:** New backend service module (`netso_customer.py`) with frozen dataclasses serves seed data through FastAPI endpoints, proxied through Odysseus. Frontend adds 6 new pages, 2 widgets, role-based nav filtering, and store extensions — all vanilla JS matching existing patterns.

**Tech Stack:** Python 3.12+ (FastAPI, Pydantic v2, frozen dataclasses), vanilla JavaScript (no framework), existing Odysseus glass-morphism CSS.

## Global Constraints

- Frozen dataclasses for all backend data models (`@dataclass(frozen=True)`)
- `textContent` only for dynamic DOM values (XSS safety)
- No `console.log` in committed code — use `logging` (Python) or existing error channel (JS)
- Financial constants from `aos/constants.py` — NEVER use blended rate for savings
- Coverage minimum: 60% (`fail_under = 60` in pyproject.toml)
- `ruff` for Python lint/format
- AAA pattern for all tests

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `aos/ventures/netso/seed/customers.json` | Customer profiles + site metadata |
| `aos/ventures/netso/seed/generation.json` | Monthly generation data per site |
| `aos/ventures/netso/seed/billing.json` | Invoice history per site |
| `aos/services/netso_customer.py` | Frozen dataclasses + service functions for all 5 endpoints |
| `odysseus/routes/netso_routes.py` | Proxy routes mounted at `/api/netso/*` |
| `tests/test_netso_customer.py` | Unit tests for service + API endpoints |
| `odysseus/dashboard/pages/netso/netso-overview.js` | Landing page for all Netso roles |
| `odysseus/dashboard/pages/netso/customer-generation.js` | Customer: solar generation data |
| `odysseus/dashboard/pages/netso/customer-savings.js` | Customer: savings vs grid rate |
| `odysseus/dashboard/pages/netso/customer-billing.js` | Customer: PPA invoices + history |
| `odysseus/dashboard/pages/netso/internal-portfolio.js` | Internal: all customers + revenue |
| `odysseus/dashboard/pages/netso/internal-financials.js` | Internal: unit economics + DSCR |
| `odysseus/dashboard/widgets/savings-tile.js` | BDT saved with trend indicator |
| `odysseus/dashboard/widgets/dscr-banner.js` | Persistent DSCR alert banner (internal-only) |

### Modified Files

| File | Change |
|------|--------|
| `aos/api.py` | Mount Netso router, add 5 endpoint registrations |
| `odysseus/routes/__init__.py` | Register Netso proxy router |
| `odysseus/dashboard/stores/dashboard.js` | Add `role`, Netso state fields, `loadNetsoXxx()` methods |
| `odysseus/dashboard/services/api.js` | Add `getNetsoXxx()` client methods |
| `odysseus/dashboard/layouts/dashboard-layout.js` | Add Netso NAV_ITEMS filtered by role |
| `odysseus/dashboard/index.js` | Register Netso pages in PAGES map |

---

### Task 1: Seed Data Files

**Files:**
- Create: `aos/ventures/netso/seed/customers.json`
- Create: `aos/ventures/netso/seed/generation.json`
- Create: `aos/ventures/netso/seed/billing.json`

No test needed — these are static data files read by the service.

- [ ] **Step 1: Create customers.json**

```bash
mkdir -p aos/ventures/netso/seed
```

```json
{
  "customers": [
    {
      "customer_id": "CGS-001",
      "customer_name": "Comprehensive Garment Solutions",
      "site_name": "CGS rooftop — Chattogram",
      "system_capacity_kw": 850,
      "status": "active",
      "ppa_start_date": "2026-01-01",
      "ppa_rate_bdt_per_kwh": 10.00,
      "escalation_rate_pct": 3.0,
      "escalation_interval_years": 3,
      "next_escalation_date": "2029-01-01",
      "health_score": 0.98
    }
  ]
}
```

- [ ] **Step 2: Create generation.json**

```json
{
  "CGS-001": {
    "system_capacity_kw": 850,
    "monthly": [
      {"month": "2026-01", "generation_kwh": 11200, "grid_export_kwh": 1680, "availability_pct": 97.5},
      {"month": "2026-02", "generation_kwh": 11800, "grid_export_kwh": 1770, "availability_pct": 98.0},
      {"month": "2026-03", "generation_kwh": 12750, "grid_export_kwh": 1850, "availability_pct": 98.2}
    ]
  }
}
```

- [ ] **Step 3: Create billing.json**

```json
{
  "CGS-001": {
    "invoices": [
      {"invoice_id": "INV-2026-01-CGS001", "month": "2026-01", "generation_kwh": 11200, "ppa_rate_bdt_per_kwh": 10.00, "amount_bdt": 112000.00, "status": "paid", "paid_date": "2026-02-10"},
      {"invoice_id": "INV-2026-02-CGS001", "month": "2026-02", "generation_kwh": 11800, "ppa_rate_bdt_per_kwh": 10.00, "amount_bdt": 118000.00, "status": "paid", "paid_date": "2026-03-10"},
      {"invoice_id": "INV-2026-03-CGS001", "month": "2026-03", "generation_kwh": 12750, "ppa_rate_bdt_per_kwh": 10.00, "amount_bdt": 127500.00, "status": "pending", "due_date": "2026-04-15"}
    ]
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add aos/ventures/netso/seed/
git commit -m "feat: add Netso seed data — customers, generation, billing"
```

---

### Task 2: Backend Service — Frozen Dataclasses

**Files:**
- Create: `aos/services/netso_customer.py`
- Test: `tests/test_netso_customer.py`

**Interfaces:**
- Consumes: seed JSON files, `aos/constants.py` (`NETSO_FINANCIAL`, `TRUE_VARIABLE_RATE`, `PPA_RATE`, etc.)
- Produces: `get_generation(site_id) -> dict`, `get_savings(site_id) -> dict`, `get_billing(site_id) -> dict`, `get_portfolio() -> dict`, `get_financials() -> dict`

- [ ] **Step 1: Write the failing test for dataclass construction**

```python
# tests/test_netso_customer.py
"""Tests for Netso customer dashboard service."""

from __future__ import annotations

import pytest

from aos.services.netso_customer import (
    GenerationData,
    SavingsData,
    BillingData,
    PortfolioData,
    FinancialsData,
    get_generation,
    get_savings,
    get_billing,
    get_portfolio,
    get_financials,
)


@pytest.mark.unit
class TestGenerationData:
    def test_to_dict_has_required_keys(self):
        data = GenerationData(
            customer_id="CGS-001",
            customer_name="Test",
            system_capacity_kw=850,
            current_month={"generation_kwh": 12750},
            ytd={"generation_kwh": 76500},
            trend=[],
            alerts=[],
            last_updated="2026-07-20T08:00:00",
        )
        result = data.to_dict()
        assert "customer_id" in result
        assert "system_capacity_kw" in result
        assert "current_month" in result
        assert "ytd" in result
        assert "trend" in result
        assert "alerts" in result

    def test_to_dict_is_frozen(self):
        data = GenerationData(
            customer_id="CGS-001",
            customer_name="Test",
            system_capacity_kw=850,
            current_month={},
            ytd={},
            trend=[],
            alerts=[],
            last_updated="",
        )
        with pytest.raises(AttributeError):
            data.customer_id = "CHANGED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_netso_customer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aos.services.netso_customer'`

- [ ] **Step 3: Write minimal dataclass stubs**

```python
# aos/services/netso_customer.py
"""Netso customer dashboard service — seed data + financial computations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aos.constants import (
    CAPACITY_FACTOR,
    CUSTOMER_SAVINGS_PCT,
    DSCR_ALERT_FLOOR,
    DSCR_SCENARIO_A,
    DSCR_SCENARIO_B,
    IDCOL_DEBT_PCT,
    IDCOL_INTEREST,
    IDCOL_TERM_YEARS,
    LEVERED_IRR_A,
    LEVERED_IRR_B,
    NEM_EXPORT_RATE,
    OPEX_PER_KW,
    PPA_RATE,
    PROJECT_PAYBACK_A,
    PROJECT_PAYBACK_B,
    CAPEX_PER_KW_SCENARIO_A,
    CAPEX_PER_KW_SCENARIO_B,
    TRUE_VARIABLE_RATE,
)

SEED_DIR = Path(__file__).resolve().parent.parent / "ventures" / "netso" / "seed"


def _load_json(filename: str) -> dict[str, Any]:
    path = SEED_DIR / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text())


@dataclass(frozen=True)
class GenerationData:
    customer_id: str
    customer_name: str
    system_capacity_kw: int
    current_month: dict[str, Any]
    ytd: dict[str, Any]
    trend: list[dict[str, Any]]
    alerts: list[str]
    last_updated: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "system_capacity_kw": self.system_capacity_kw,
            "current_month": self.current_month,
            "ytd": self.ytd,
            "trend": self.trend,
            "alerts": self.alerts,
            "last_updated": self.last_updated,
        }


@dataclass(frozen=True)
class SavingsData:
    customer_id: str
    customer_name: str
    system_capacity_kw: int
    grid_rate_bdt_per_kwh: float
    ppa_rate_bdt_per_kwh: float
    savings_pct: float
    current_month: dict[str, Any]
    ytd: dict[str, Any]
    lifetime_projected: dict[str, Any]
    escalation: dict[str, Any]
    trend: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "system_capacity_kw": self.system_capacity_kw,
            "grid_rate_bdt_per_kwh": self.grid_rate_bdt_per_kwh,
            "ppa_rate_bdt_per_kwh": self.ppa_rate_bdt_per_kwh,
            "savings_pct": self.savings_pct,
            "current_month": self.current_month,
            "ytd": self.ytd,
            "lifetime_projected": self.lifetime_projected,
            "escalation": self.escalation,
            "trend": self.trend,
        }


@dataclass(frozen=True)
class BillingData:
    customer_id: str
    customer_name: str
    billing_cycle: str
    current_invoice: dict[str, Any]
    outstanding: dict[str, Any]
    history: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "billing_cycle": self.billing_cycle,
            "current_invoice": self.current_invoice,
            "outstanding": self.outstanding,
            "history": self.history,
        }


@dataclass(frozen=True)
class PortfolioData:
    total_customers: int
    total_capacity_kw: int
    portfolio_status: dict[str, int]
    generation_summary: dict[str, Any]
    financial_summary: dict[str, Any]
    customers: list[dict[str, Any]]
    alerts: dict[str, int]
    financial_constants: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_customers": self.total_customers,
            "total_capacity_kw": self.total_capacity_kw,
            "portfolio_status": self.portfolio_status,
            "generation_summary": self.generation_summary,
            "financial_summary": self.financial_summary,
            "customers": self.customers,
            "alerts": self.alerts,
            "financial_constants": self.financial_constants,
        }


@dataclass(frozen=True)
class FinancialsData:
    venture_id: str
    venture_name: str
    unit_economics: dict[str, Any]
    scenarios: dict[str, Any]
    debt_structure: dict[str, Any]
    portfolio_financials: dict[str, Any]
    approval_thresholds: dict[str, Any]
    model_accuracy: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "venture_id": self.venture_id,
            "venture_name": self.venture_name,
            "unit_economics": self.unit_economics,
            "scenarios": self.scenarios,
            "debt_structure": self.debt_structure,
            "portfolio_financials": self.portfolio_financials,
            "approval_thresholds": self.approval_thresholds,
            "model_accuracy": self.model_accuracy,
        }


def get_generation(site_id: str) -> GenerationData | None:
    """Get generation data for a customer site."""
    data = _load_json("generation.json")
    site = data.get(site_id)
    if not site:
        return None

    customers = _load_json("customers.json")
    customer = next(
        (c for c in customers.get("customers", []) if c["customer_id"] == site_id),
        None,
    )
    if not customer:
        return None

    monthly = site.get("monthly", [])
    latest = monthly[-1] if monthly else {}
    total_generation = sum(m.get("generation_kwh", 0) for m in monthly)
    total_export = sum(m.get("grid_export_kwh", 0) for m in monthly)
    avg_availability = (
        sum(m.get("availability_pct", 0) for m in monthly) / len(monthly)
        if monthly
        else 0
    )
    capacity_factor = (
        (latest.get("generation_kwh", 0) / (site["system_capacity_kw"] * 730))
        * 100
        if site["system_capacity_kw"] > 0 and latest
        else 0
    )
    self_consumption = (
        ((latest.get("generation_kwh", 0) - latest.get("grid_export_kwh", 0))
         / latest.get("generation_kwh", 1))
        * 100
        if latest.get("generation_kwh", 0) > 0
        else 0
    )

    return GenerationData(
        customer_id=site_id,
        customer_name=customer["customer_name"],
        system_capacity_kw=site["system_capacity_kw"],
        current_month={
            "generation_kwh": latest.get("generation_kwh", 0),
            "capacity_factor_pct": round(capacity_factor, 1),
            "availability_pct": latest.get("availability_pct", 0),
            "grid_export_kwh": latest.get("grid_export_kwh", 0),
            "self_consumption_pct": round(self_consumption, 1),
        },
        ytd={
            "generation_kwh": total_generation,
            "grid_export_kwh": total_export,
            "self_consumption_pct": round(
                ((total_generation - total_export) / total_generation * 100)
                if total_generation > 0
                else 0,
                1,
            ),
        },
        trend=[
            {"month": m["month"], "generation_kwh": m["generation_kwh"]}
            for m in monthly
        ],
        alerts=[],
        last_updated="2026-07-20T08:00:00+06:00",
    )


def get_savings(site_id: str) -> SavingsData | None:
    """Get savings data for a customer site."""
    gen = get_generation(site_id)
    if not gen:
        return None

    customers = _load_json("customers.json")
    customer = next(
        (c for c in customers.get("customers", []) if c["customer_id"] == site_id),
        None,
    )
    if not customer:
        return None

    ppa_rate = customer.get("ppa_rate_bdt_per_kwh", PPA_RATE)
    gen_kwh = gen.current_month.get("generation_kwh", 0)
    ytd_kwh = gen.ytd.get("generation_kwh", 0)

    grid_cost = gen_kwh * TRUE_VARIABLE_RATE
    ppa_cost = gen_kwh * ppa_rate
    savings = grid_cost - ppa_cost

    ytd_grid = ytd_kwh * TRUE_VARIABLE_RATE
    ytd_ppa = ytd_kwh * ppa_rate
    ytd_savings = ytd_grid - ytd_ppa

    cf = CAPACITY_FACTOR / 100
    hrs_per_year = 8760
    lifetime_years = 25
    total_lifetime_kwh = gen.system_capacity_kw * cf * hrs_per_year * lifetime_years
    lifetime_savings = total_lifetime_kwh * (TRUE_VARIABLE_RATE - ppa_rate)

    escalation_rate = customer.get("escalation_rate_pct", 3.0)
    projected_ppa = ppa_rate * (1 + escalation_rate / 100)

    return SavingsData(
        customer_id=site_id,
        customer_name=gen.customer_name,
        system_capacity_kw=gen.system_capacity_kw,
        grid_rate_bdt_per_kwh=TRUE_VARIABLE_RATE,
        ppa_rate_bdt_per_kwh=ppa_rate,
        savings_pct=CUSTOMER_SAVINGS_PCT,
        current_month={
            "generation_kwh": gen_kwh,
            "grid_cost_bdt": round(grid_cost, 2),
            "ppa_cost_bdt": round(ppa_cost, 2),
            "savings_bdt": round(savings, 2),
        },
        ytd={
            "generation_kwh": ytd_kwh,
            "grid_cost_bdt": round(ytd_grid, 2),
            "ppa_cost_bdt": round(ytd_ppa, 2),
            "savings_bdt": round(ytd_savings, 2),
        },
        lifetime_projected={
            "total_savings_bdt": round(lifetime_savings, 2),
            "payback_years": PROJECT_PAYBACK_A,
            "irr_pct": LEVERED_IRR_A,
        },
        escalation={
            "rate": escalation_rate,
            "next_escalation_date": customer.get("next_escalation_date", ""),
            "projected_ppa_after_escalation": round(projected_ppa, 2),
        },
        trend=[
            {"month": t["month"], "savings_bdt": round(t["generation_kwh"] * (TRUE_VARIABLE_RATE - ppa_rate), 2)}
            for t in gen.trend
        ],
    )


def get_billing(site_id: str) -> BillingData | None:
    """Get billing data for a customer site."""
    data = _load_json("billing.json")
    site = data.get(site_id)
    if not site:
        return None

    customers = _load_json("customers.json")
    customer = next(
        (c for c in customers.get("customers", []) if c["customer_id"] == site_id),
        None,
    )
    if not customer:
        return None

    invoices = site.get("invoices", [])
    current = next((i for i in invoices if i["status"] == "pending"), None)
    if not current and invoices:
        current = invoices[-1]

    paid = [i for i in invoices if i["status"] == "paid"]
    overdue = [i for i in invoices if i["status"] == "overdue"]
    outstanding_total = sum(i["amount_bdt"] for i in invoices if i["status"] != "paid")

    return BillingData(
        customer_id=site_id,
        customer_name=customer["customer_name"],
        billing_cycle=current["month"] if current else "",
        current_invoice=current or {},
        outstanding={
            "total_bdt": outstanding_total,
            "overdue_count": len(overdue),
            "overdue_amount_bdt": sum(i["amount_bdt"] for i in overdue),
        },
        history=[
            {
                "invoice_id": i["invoice_id"],
                "amount_bdt": i["amount_bdt"],
                "status": i["status"],
                "paid_date": i.get("paid_date", ""),
                "generation_kwh": i["generation_kwh"],
            }
            for i in invoices
        ],
    )


def get_portfolio() -> PortfolioData:
    """Get aggregated portfolio view across all customers."""
    customers_data = _load_json("customers.json")
    gen_data = _load_json("generation.json")
    billing_data = _load_json("billing.json")

    customers = customers_data.get("customers", [])
    total_capacity = sum(c.get("system_capacity_kw", 0) for c in customers)
    active = sum(1 for c in customers if c.get("status") == "active")
    in_install = sum(1 for c in customers if c.get("status") == "in_installation")

    total_gen_month = 0
    total_gen_ytd = 0
    total_revenue_month = 0
    total_savings_month = 0
    customer_summaries = []

    for c in customers:
        cid = c["customer_id"]
        gen = gen_data.get(cid, {})
        monthly = gen.get("monthly", [])
        latest = monthly[-1] if monthly else {}
        gen_month = latest.get("generation_kwh", 0)
        gen_ytd = sum(m.get("generation_kwh", 0) for m in monthly)
        ppa_rate = c.get("ppa_rate_bdt_per_kwh", PPA_RATE)
        rev_month = gen_month * ppa_rate
        sav_month = gen_month * (TRUE_VARIABLE_RATE - ppa_rate)

        total_gen_month += gen_month
        total_gen_ytd += gen_ytd
        total_revenue_month += rev_month
        total_savings_month += sav_month

        customer_summaries.append({
            "customer_id": cid,
            "customer_name": c["customer_name"],
            "capacity_kw": c.get("system_capacity_kw", 0),
            "status": c.get("status", "unknown"),
            "monthly_generation_kwh": gen_month,
            "monthly_savings_bdt": round(sav_month, 2),
            "health_score": c.get("health_score", 0),
        })

    invoices_all = []
    for inv_list in billing_data.values():
        invoices_all.extend(inv_list.get("invoices", []))
    overdue_count = sum(1 for i in invoices_all if i.get("status") == "overdue")

    return PortfolioData(
        total_customers=len(customers),
        total_capacity_kw=total_capacity,
        portfolio_status={
            "active": active,
            "in_installation": in_install,
            "churned": 0,
        },
        generation_summary={
            "current_month_kwh": total_gen_month,
            "ytd_kwh": total_gen_ytd,
            "capacity_factor_avg_pct": CAPACITY_FACTOR,
        },
        financial_summary={
            "pipeline_value_bdt": total_capacity * CAPEX_PER_KW_SCENARIO_A,
            "monthly_revenue_bdt": round(total_revenue_month, 2),
            "ytd_revenue_bdt": round(total_revenue_month * 3, 2),
            "ytd_savings_delivered_bdt": round(total_savings_month * 3, 2),
        },
        customers=customer_summaries,
        alerts={
            "dscr_breaches": 0,
            "overdue_invoices": overdue_count,
            "system_faults": 0,
        },
        financial_constants={
            "capex_per_kw": CAPEX_PER_KW_SCENARIO_A,
            "ppa_rate": PPA_RATE,
            "customer_savings_pct": CUSTOMER_SAVINGS_PCT,
            "true_variable_rate": TRUE_VARIABLE_RATE,
        },
    )


def get_financials() -> FinancialsData:
    """Get unit economics and scenario analysis."""
    portfolio = get_portfolio()
    total_capex = portfolio.total_capacity_kw * CAPEX_PER_KW_SCENARIO_A
    monthly_opex = (portfolio.total_capacity_kw * OPEX_PER_KW) / 12

    return FinancialsData(
        venture_id="VEN-NETSO-001",
        venture_name="Netso Energy",
        unit_economics={
            "capex_per_kw_bdt": CAPEX_PER_KW_SCENARIO_A,
            "opex_per_kw_bdt": OPEX_PER_KW,
            "ppa_rate_bdt_per_kwh": PPA_RATE,
            "true_variable_rate_bdt_per_kwh": TRUE_VARIABLE_RATE,
            "customer_savings_pct": CUSTOMER_SAVINGS_PCT,
            "nem_export_rate_bdt_per_kwh": NEM_EXPORT_RATE,
            "capacity_factor_pct": CAPACITY_FACTOR,
        },
        scenarios={
            "scenario_a": {
                "capex_per_kw": CAPEX_PER_KW_SCENARIO_A,
                "dscr": DSCR_SCENARIO_A,
                "payback_years": PROJECT_PAYBACK_A,
                "levered_irr_pct": LEVERED_IRR_A,
            },
            "scenario_b": {
                "capex_per_kw": CAPEX_PER_KW_SCENARIO_B,
                "dscr": DSCR_SCENARIO_B,
                "payback_years": PROJECT_PAYBACK_B,
                "levered_irr_pct": LEVERED_IRR_B,
                "conditional": True,
                "condition": "NBR confirmation of 0% import duty",
            },
        },
        debt_structure={
            "idcol_debt_pct": IDCOL_DEBT_PCT,
            "idcol_interest_pct": IDCOL_INTEREST,
            "idcol_term_years": IDCOL_TERM_YEARS,
        },
        portfolio_financials={
            "total_capex_bdt": total_capex,
            "monthly_revenue_bdt": portfolio.financial_summary["monthly_revenue_bdt"],
            "ytd_revenue_bdt": portfolio.financial_summary["ytd_revenue_bdt"],
            "annual_opex_bdt": round(monthly_opex * 12, 2),
            "monthly_opex_bdt": round(monthly_opex, 2),
            "net_monthly_bdt": round(
                portfolio.financial_summary["monthly_revenue_bdt"] - monthly_opex, 2
            ),
        },
        approval_thresholds={
            "proposal_value_bdt": 5_000_000,
            "dscr_escalation_floor": DSCR_SCENARIO_A,
            "dscr_alert_floor": DSCR_ALERT_FLOOR,
        },
        model_accuracy=None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_netso_customer.py::TestGenerationData -v`
Expected: PASS

- [ ] **Step 5: Write remaining tests**

```python
# Append to tests/test_netso_customer.py

@pytest.mark.unit
class TestGetGeneration:
    def test_returns_generation_for_valid_site(self):
        result = get_generation("CGS-001")
        assert result is not None
        assert result.customer_id == "CGS-001"
        assert result.system_capacity_kw == 850
        assert "generation_kwh" in result.current_month

    def test_returns_none_for_unknown_site(self):
        result = get_generation("NONEXISTENT")
        assert result is None

    def test_to_dict_matches_spec_shape(self):
        result = get_generation("CGS-001")
        assert result is not None
        d = result.to_dict()
        assert set(d.keys()) == {
            "customer_id", "customer_name", "system_capacity_kw",
            "current_month", "ytd", "trend", "alerts", "last_updated",
        }


@pytest.mark.unit
class TestGetSavings:
    def test_returns_savings_for_valid_site(self):
        result = get_savings("CGS-001")
        assert result is not None
        assert result.grid_rate_bdt_per_kwh == 12.98
        assert result.ppa_rate_bdt_per_kwh == 10.00
        assert result.savings_pct == 23.0

    def test_savings_math_is_correct(self):
        result = get_savings("CGS-001")
        assert result is not None
        gen_kwh = result.current_month["generation_kwh"]
        expected_grid = gen_kwh * 12.98
        expected_ppa = gen_kwh * 10.00
        expected_savings = expected_grid - expected_ppa
        assert result.current_month["grid_cost_bdt"] == round(expected_grid, 2)
        assert result.current_month["ppa_cost_bdt"] == round(expected_ppa, 2)
        assert result.current_month["savings_bdt"] == round(expected_savings, 2)

    def test_returns_none_for_unknown_site(self):
        assert get_savings("NONEXISTENT") is None


@pytest.mark.unit
class TestGetBilling:
    def test_returns_billing_for_valid_site(self):
        result = get_billing("CGS-001")
        assert result is not None
        assert result.customer_id == "CGS-001"
        assert len(result.history) == 3

    def test_current_invoice_is_pending(self):
        result = get_billing("CGS-001")
        assert result is not None
        assert result.current_invoice["status"] == "pending"

    def test_outstanding_matches_pending(self):
        result = get_billing("CGS-001")
        assert result is not None
        pending = [i for i in result.history if i["status"] == "pending"]
        expected = sum(i["amount_bdt"] for i in pending)
        assert result.outstanding["total_bdt"] == expected

    def test_returns_none_for_unknown_site(self):
        assert get_billing("NONEXISTENT") is None


@pytest.mark.unit
class TestGetPortfolio:
    def test_returns_portfolio_with_customers(self):
        result = get_portfolio()
        assert result.total_customers >= 1
        assert len(result.customers) >= 1

    def test_financial_constants_match_ground_truth(self):
        result = get_portfolio()
        fc = result.financial_constants
        assert fc["true_variable_rate"] == 12.98
        assert fc["ppa_rate"] == 10.00
        assert fc["customer_savings_pct"] == 23.0


@pytest.mark.unit
class TestGetFinancials:
    def test_returns_financials_with_scenarios(self):
        result = get_financials()
        assert result.scenarios["scenario_a"]["dscr"] == 2.25
        assert result.scenarios["scenario_b"]["dscr"] == 3.09

    def test_opex_is_monthly_not_annual(self):
        result = get_financials()
        annual = result.portfolio_financials["annual_opex_bdt"]
        monthly = result.portfolio_financials["monthly_opex_bdt"]
        assert monthly == round(annual / 12, 2)
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/test_netso_customer.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add aos/services/netso_customer.py tests/test_netso_customer.py
git commit -m "feat: Netso customer dashboard service — frozen dataclasses + seed data"
```

---

### Task 3: API Endpoints

**Files:**
- Modify: `aos/api.py` (add 5 routes)
- Test: `tests/test_netso_customer.py` (append API tests)

**Interfaces:**
- Consumes: `get_generation()`, `get_savings()`, `get_billing()`, `get_portfolio()`, `get_financials()` from Task 2
- Produces: REST endpoints at `/api/netso/*`

- [ ] **Step 1: Write failing API tests**

```python
# Append to tests/test_netso_customer.py

import pytest
from fastapi.testclient import TestClient

from aos.api import app


@pytest.mark.integration
class TestNetsoEndpoints:
    def setup_method(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_generation_valid_site(self):
        resp = self.client.get("/api/netso/customers/CGS-001/generation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_id"] == "CGS-001"
        assert "current_month" in data

    def test_generation_unknown_site(self):
        resp = self.client.get("/api/netso/customers/NONEXISTENT/generation")
        assert resp.status_code == 404

    def test_savings_valid_site(self):
        resp = self.client.get("/api/netso/customers/CGS-001/savings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["grid_rate_bdt_per_kwh"] == 12.98

    def test_billing_valid_site(self):
        resp = self.client.get("/api/netso/customers/CGS-001/billing")
        assert resp.status_code == 200
        assert "history" in resp.json()

    def test_portfolio(self):
        resp = self.client.get("/api/netso/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_customers" in data
        assert "customers" in data

    def test_financials(self):
        resp = self.client.get("/api/netso/financials")
        assert resp.status_code == 200
        data = resp.json()
        assert data["venture_id"] == "VEN-NETSO-001"
        assert "scenarios" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_netso_customer.py::TestNetsoEndpoints -v`
Expected: FAIL with 404/405 errors (endpoints don't exist yet)

- [ ] **Step 3: Add endpoints to aos/api.py**

Read `aos/api.py` to find the last route, then append:

```python
# ── Netso Customer Dashboard ────────────────────────────────────────────────

from aos.services.netso_customer import (
    get_generation,
    get_savings,
    get_billing,
    get_portfolio,
    get_financials,
)


@app.get("/api/netso/customers/{site_id}/generation")
async def netso_generation(site_id: str) -> dict:
    data = get_generation(site_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return data.to_dict()


@app.get("/api/netso/customers/{site_id}/savings")
async def netso_savings(site_id: str) -> dict:
    data = get_savings(site_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return data.to_dict()


@app.get("/api/netso/customers/{site_id}/billing")
async def netso_billing(site_id: str) -> dict:
    data = get_billing(site_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return data.to_dict()


@app.get("/api/netso/portfolio")
async def netso_portfolio() -> dict:
    return get_portfolio().to_dict()


@app.get("/api/netso/financials")
async def netso_financials() -> dict:
    return get_financials().to_dict()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_netso_customer.py::TestNetsoEndpoints -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add aos/api.py tests/test_netso_customer.py
git commit -m "feat: add Netso REST endpoints — generation, savings, billing, portfolio, financials"
```

---

### Task 4: Odysseus Proxy Routes

**Files:**
- Create: `odysseus/routes/netso_routes.py`
- Modify: `odysseus/routes/__init__.py`

**Interfaces:**
- Consumes: AOS engine endpoints from Task 3 (`/api/netso/*`)
- Produces: Odysseus proxy routes at `/api/netso/*`

- [ ] **Step 1: Create netso_routes.py**

Follow the exact pattern from `aos_routes.py`:

```python
# odysseus/routes/netso_routes.py
"""Odysseus proxy routes — Netso customer dashboard API."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

AOS_ENGINE_URL = os.getenv("AOS_ENGINE_URL", "http://127.0.0.1:7001")

_http_client: httpx.AsyncClient | None = None

router = APIRouter(prefix="/api/netso", tags=["netso"])


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(base_url=AOS_ENGINE_URL, timeout=10.0)
    return _http_client


@router.get("/customers/{site_id}/generation")
async def proxy_generation(site_id: str) -> Any:
    try:
        resp = await _get_client().get(f"/api/netso/customers/{site_id}/generation")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/customers/{site_id}/savings")
async def proxy_savings(site_id: str) -> Any:
    try:
        resp = await _get_client().get(f"/api/netso/customers/{site_id}/savings")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/customers/{site_id}/billing")
async def proxy_billing(site_id: str) -> Any:
    try:
        resp = await _get_client().get(f"/api/netso/customers/{site_id}/billing")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/portfolio")
async def proxy_portfolio() -> Any:
    try:
        resp = await _get_client().get("/api/netso/portfolio")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/financials")
async def proxy_financials() -> Any:
    try:
        resp = await _get_client().get("/api/netso/financials")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)
```

- [ ] **Step 2: Register in odysseus/routes/__init__.py**

Read the file, then add the Netso router import and registration following the existing pattern.

- [ ] **Step 3: Commit**

```bash
git add odysseus/routes/netso_routes.py odysseus/routes/__init__.py
git commit -m "feat: add Odysseus proxy routes for Netso customer dashboard"
```

---

### Task 5: Store Extensions + API Client

**Files:**
- Modify: `odysseus/dashboard/stores/dashboard.js`
- Modify: `odysseus/dashboard/services/api.js`

**Interfaces:**
- Consumes: API endpoints from Task 4
- Produces: `store.state.role`, `store.state.netsoGeneration`, `store.state.netsoSavings`, `store.state.netsoBilling`, `store.state.netsoPortfolio`, `store.state.netsoFinancials`, `store.setRole()`, `store.loadNetsoXxx()` methods

- [ ] **Step 1: Add API client methods**

Append to `odysseus/dashboard/services/api.js`:

```javascript
  // ── Netso Customer Dashboard ───────────────────────────────────────────
  getNetsoGeneration(siteId) { return this._get(`/netso/customers/${siteId}/generation`); }
  getNetsoSavings(siteId)    { return this._get(`/netso/customers/${siteId}/savings`); }
  getNetsoBilling(siteId)    { return this._get(`/netso/customers/${siteId}/billing`); }
  getNetsoPortfolio()        { return this._get('/netso/portfolio'); }
  getNetsoFinancials()       { return this._get('/netso/financials'); }
```

- [ ] **Step 2: Add store state fields and load methods**

Add to the `_state` object in `DashboardStore` constructor:

```javascript
      // Netso customer dashboard
      role: 'internal',  // 'customer' | 'internal' | 'admin'
      siteId: 'CGS-001',
      netsoGeneration: null,
      netsoSavings: null,
      netsoBilling: null,
      netsoPortfolio: null,
      netsoFinancials: null,
```

Add methods after `loadEntityIndex()`:

```javascript
  // ── Netso Customer Dashboard ───────────────────────────────────────────

  setRole(role) {
    this._update({ role });
  }

  setSiteId(siteId) {
    this._update({ siteId });
  }

  async loadNetsoGeneration() {
    try {
      const data = await api.getNetsoGeneration(this._state.siteId);
      this._update({ netsoGeneration: data });
    } catch (e) { console.error('Failed to load netso generation:', e); }
  }

  async loadNetsoSavings() {
    try {
      const data = await api.getNetsoSavings(this._state.siteId);
      this._update({ netsoSavings: data });
    } catch (e) { console.error('Failed to load netso savings:', e); }
  }

  async loadNetsoBilling() {
    try {
      const data = await api.getNetsoBilling(this._state.siteId);
      this._update({ netsoBilling: data });
    } catch (e) { console.error('Failed to load netso billing:', e); }
  }

  async loadNetsoPortfolio() {
    try {
      const data = await api.getNetsoPortfolio();
      this._update({ netsoPortfolio: data });
    } catch (e) { console.error('Failed to load netso portfolio:', e); }
  }

  async loadNetsoFinancials() {
    try {
      const data = await api.getNetsoFinancials();
      this._update({ netsoFinancials: data });
    } catch (e) { console.error('Failed to load netso financials:', e); }
  }
```

- [ ] **Step 3: Commit**

```bash
git add odysseus/dashboard/stores/dashboard.js odysseus/dashboard/services/api.js
git commit -m "feat: add Netso store state, role, and API client methods"
```

---

### Task 6: Layout + Nav Filtering

**Files:**
- Modify: `odysseus/dashboard/layouts/dashboard-layout.js`

**Interfaces:**
- Consumes: `store.state.role` from Task 5
- Produces: Filtered sidebar navigation

- [ ] **Step 1: Add Netso NAV_ITEMS and filter logic**

Replace the `NAV_ITEMS` constant and `renderNav` function:

```javascript
const NAV_ITEMS = [
  { id: 'overview',     icon: '⚡', label: 'Overview' },
  { id: 'harnesses',    icon: '🔗', label: 'Harnesses' },
  { id: 'pipelines',    icon: '🔄', label: 'Pipelines' },
  { id: 'approvals',    icon: '✅', label: 'Approvals' },
  { id: 'memory',       icon: '🧠', label: 'Memory' },
  { id: 'entities',     icon: '🕸️', label: 'Entities' },
  { id: 'events',       icon: '📋', label: 'Events' },
  { id: 'sales',        icon: '💰', label: 'Sales' },
  { id: 'system',       icon: '🖥️', label: 'System' },
];

const NETSO_NAV = [
  { id: 'netso-overview',   icon: '🏠', label: 'Netso Overview',   roles: ['customer', 'internal', 'admin'] },
  { id: 'netso-generation', icon: '☀️', label: 'Generation',       roles: ['customer', 'admin'] },
  { id: 'netso-savings',    icon: '💰', label: 'Savings',          roles: ['customer', 'admin'] },
  { id: 'netso-billing',    icon: '📄', label: 'Billing',          roles: ['customer', 'admin'] },
  { id: 'netso-portfolio',  icon: '🏢', label: 'Portfolio',        roles: ['internal', 'admin'] },
  { id: 'netso-financials', icon: '📈', label: 'Financials',       roles: ['internal', 'admin'] },
];
```

Update `renderNav` to filter by role:

```javascript
function renderNav(navEl) {
  const role = store.state.role || 'internal';
  const allItems = [...NAV_ITEMS, ...NETSO_NAV.filter((item) => item.roles.includes(role))];

  navEl.innerHTML = allItems.map((item) => `
    <button class="aos-nav-item" data-page="${item.id}" role="menuitem" aria-label="${item.label}" tabindex="0">
      <span class="aos-nav-icon" aria-hidden="true">${item.icon}</span>
      <span class="aos-nav-label">${item.label}</span>
    </button>
  `).join('');

  navEl.addEventListener('click', (e) => {
    const btn = e.target.closest('.aos-nav-item');
    if (!btn) return;
    const page = btn.dataset.page;
    store.setPage(page);
    setActiveNav(page);
    document.getElementById('aos-page-title').textContent =
      allItems.find((n) => n.id === page)?.label || page;
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add odysseus/dashboard/layouts/dashboard-layout.js
git commit -m "feat: add role-based Netso nav filtering to dashboard layout"
```

---

### Task 7: Widgets — Savings Tile + DSCR Banner

**Files:**
- Modify: `odysseus/dashboard/widgets/savings-tile.js` (update existing)
- Create: `odysseus/dashboard/widgets/dscr-banner.js`

- [ ] **Step 1: Update savings-tile.js**

The existing `kpi-tile.js` handles generic KPIs. The savings tile adds trend indication:

```javascript
// odysseus/dashboard/widgets/savings-tile.js
/**
 * Savings Tile — displays BDT saved with trend indicator.
 * Uses textContent for XSS safety.
 */

export function renderSavingsTile(container, { value_bdt, trend_pct, label }) {
  container.innerHTML = '';
  container.className = 'aos-kpi aos-kpi-accent';

  const iconEl = document.createElement('div');
  iconEl.className = 'aos-kpi-icon';
  iconEl.textContent = '💰';

  const valueEl = document.createElement('div');
  valueEl.className = 'aos-kpi-value';
  valueEl.textContent = `৳${Number(value_bdt).toLocaleString()}`;

  const labelEl = document.createElement('div');
  labelEl.className = 'aos-kpi-label';
  labelEl.textContent = label || 'Savings';

  container.appendChild(iconEl);
  container.appendChild(valueEl);
  container.appendChild(labelEl);

  if (trend_pct != null) {
    const trendEl = document.createElement('div');
    trendEl.className = 'aos-kpi-trend';
    const arrow = trend_pct >= 0 ? '↑' : '↓';
    const color = trend_pct >= 0 ? '#10B981' : '#EF4444';
    trendEl.textContent = `${arrow} ${Math.abs(trend_pct).toFixed(1)}%`;
    trendEl.style.color = color;
    container.appendChild(trendEl);
  }
}
```

- [ ] **Step 2: Create dscr-banner.js**

```javascript
// odysseus/dashboard/widgets/dscr-banner.js
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
```

- [ ] **Step 3: Commit**

```bash
git add odysseus/dashboard/widgets/
git commit -m "feat: add Netso savings tile widget and DSCR alert banner"
```

---

### Task 8: Netso Overview Page

**Files:**
- Create: `odysseus/dashboard/pages/netso/netso-overview.js`
- Modify: `odysseus/dashboard/index.js` (register page)

**Interfaces:**
- Consumes: `store.state.role`, `store.state.netsoPortfolio`, `store.state.netsoGeneration`, `store.state.netsoSavings`, `store.state.netsoBilling`
- Produces: `render(container)` function

- [ ] **Step 1: Create netso-overview.js**

```javascript
// odysseus/dashboard/pages/netso/netso-overview.js
/**
 * Netso Overview — landing page for all Netso roles.
 * Customer view: generation + savings + billing summary.
 * Internal view: portfolio + financials summary.
 */

import store from '../../stores/dashboard.js';
import { renderKpiStrip } from '../../widgets/kpi-tile.js';

export function render(container) {
  container.innerHTML = '';

  const kpiStrip = document.createElement('div');
  kpiStrip.className = 'aos-kpi-strip';
  container.appendChild(kpiStrip);

  const detailSection = document.createElement('div');
  detailSection.className = 'aos-section';
  container.appendChild(detailSection);

  const unsub = store.subscribe((state) => {
    const role = state.role || 'internal';

    if (role === 'customer') {
      renderCustomerOverview(kpiStrip, detailSection, state);
    } else {
      renderInternalOverview(kpiStrip, detailSection, state);
    }
  });

  store.loadNetsoGeneration();
  store.loadNetsoSavings();
  store.loadNetsoBilling();
  store.loadNetsoPortfolio();

  return unsub;
}

function renderCustomerOverview(kpiStrip, detailSection, state) {
  const gen = state.netsoGeneration;
  const sav = state.netsoSavings;
  const bill = state.netsoBilling;

  renderKpiStrip(kpiStrip, [
    { label: 'System', value: gen ? `${gen.system_capacity_kw} kW` : '—', icon: '⚡', accent: true },
    { label: 'Generation', value: gen ? `${gen.current_month?.generation_kwh?.toLocaleString()} kWh` : '—', icon: '☀️' },
    { label: 'Savings', value: sav ? `৳${sav.current_month?.savings_bdt?.toLocaleString()}` : '—', icon: '💰' },
    { label: 'Savings %', value: sav ? `${sav.savings_pct}%` : '—', icon: '📉' },
    { label: 'Next Invoice', value: bill ? `৳${bill.current_invoice?.amount_bdt?.toLocaleString()}` : '—', icon: '📄' },
  ]);

  detailSection.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Quick Links';
  detailSection.appendChild(title);

  const links = [
    { page: 'netso-generation', label: '📊 View detailed generation data' },
    { page: 'netso-savings', label: '💰 View savings breakdown' },
    { page: 'netso-billing', label: '📄 View billing history' },
  ];

  links.forEach(({ page, label }) => {
    const link = document.createElement('button');
    link.className = 'aos-nav-item';
    link.textContent = label;
    link.addEventListener('click', () => store.setPage(page));
    detailSection.appendChild(link);
  });
}

function renderInternalOverview(kpiStrip, detailSection, state) {
  const port = state.netsoPortfolio;

  renderKpiStrip(kpiStrip, [
    { label: 'Customers', value: port?.total_customers ?? '—', icon: '🏢', accent: true },
    { label: 'Capacity', value: port ? `${port.total_capacity_kw?.toLocaleString()} kW` : '—', icon: '⚡' },
    { label: 'Monthly Revenue', value: port ? `৳${port.financial_summary?.monthly_revenue_bdt?.toLocaleString()}` : '—', icon: '💰' },
    { label: 'Monthly Gen', value: port ? `${port.generation_summary?.current_month_kwh?.toLocaleString()} kWh` : '—', icon: '☀️' },
    { label: 'DSCR Breaches', value: port?.alerts?.dscr_breaches ?? 0, icon: port?.alerts?.dscr_breaches > 0 ? '🚨' : '✅' },
  ]);

  detailSection.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'aos-section-title';
  title.textContent = 'Portfolio Status';
  detailSection.appendChild(title);

  if (port?.customers) {
    const table = document.createElement('table');
    table.className = 'aos-table';
    table.innerHTML = `
      <thead><tr><th>Customer</th><th>Capacity</th><th>Status</th><th>Monthly Gen</th><th>Health</th></tr></thead>
      <tbody>${port.customers.map((c) => `
        <tr>
          <td>${c.customer_name}</td>
          <td>${c.capacity_kw} kW</td>
          <td>${c.status}</td>
          <td>${c.monthly_generation_kwh?.toLocaleString()} kWh</td>
          <td>${(c.health_score * 100).toFixed(0)}%</td>
        </tr>
      `).join('')}</tbody>
    `;
    detailSection.appendChild(table);
  }
}
```

- [ ] **Step 2: Register in index.js**

Add import and page entry:

```javascript
import * as netsoOverviewPage from './pages/netso/netso-overview.js';
```

Add to PAGES:

```javascript
  'netso-overview': netsoOverviewPage,
```

- [ ] **Step 3: Commit**

```bash
git add odysseus/dashboard/pages/netso/netso-overview.js odysseus/dashboard/index.js
git commit -m "feat: add Netso overview page — role-based landing for customers and internal"
```

---

### Task 9: Customer Pages — Generation, Savings, Billing

**Files:**
- Create: `odysseus/dashboard/pages/netso/customer-generation.js`
- Create: `odysseus/dashboard/pages/netso/customer-savings.js`
- Create: `odysseus/dashboard/pages/netso/customer-billing.js`
- Modify: `odysseus/dashboard/index.js` (register all 3)

- [ ] **Step 1: Create customer-generation.js**

Follow the same `render(container)` / `store.subscribe()` / `textContent` pattern from existing pages. Display: KPI strip (capacity, generation, capacity factor, availability, self-consumption), trend indicators (↑/↓ % month-over-month), YTD summary. Use `loadNetsoGeneration()`.

- [ ] **Step 2: Create customer-savings.js**

Display: KPI strip (grid rate, PPA rate, current savings, YTD savings), `savings-tile.js` widget for current month savings with trend, escalation info, lifetime projection. Use `loadNetsoSavings()`.

- [ ] **Step 3: Create customer-billing.js**

Display: current invoice card (amount, status, due date), outstanding summary, payment history table (last 12 invoices). Use `loadNetsoBilling()`.

- [ ] **Step 4: Register all 3 in index.js**

Add imports and PAGES entries for `netso-generation`, `netso-savings`, `netso-billing`.

- [ ] **Step 5: Commit**

```bash
git add odysseus/dashboard/pages/netso/customer-*.js odysseus/dashboard/index.js
git commit -m "feat: add Netso customer pages — generation, savings, billing"
```

---

### Task 10: Internal Pages — Portfolio, Financials

**Files:**
- Create: `odysseus/dashboard/pages/netso/internal-portfolio.js`
- Create: `odysseus/dashboard/pages/netso/internal-financials.js`
- Modify: `odysseus/dashboard/index.js` (register both)

- [ ] **Step 1: Create internal-portfolio.js**

Display: aggregate KPI strip (customers, capacity, revenue, generation), customer list table, customer selector dropdown (sets `store.setSiteId()`), alert summary. Use `loadNetsoPortfolio()`.

- [ ] **Step 2: Create internal-financials.js**

Display: unit economics card, scenario A vs B side-by-side comparison, debt structure, portfolio financials, approval thresholds. Use `loadNetsoFinancials()`.

- [ ] **Step 3: Register both in index.js**

Add imports and PAGES entries for `netso-portfolio`, `netso-financials`.

- [ ] **Step 4: Commit**

```bash
git add odysseus/dashboard/pages/netso/internal-*.js odysseus/dashboard/index.js
git commit -m "feat: add Netso internal pages — portfolio, financials with DSCR scenarios"
```

---

### Task 11: Integration Test + Final Registration

**Files:**
- Test: `tests/test_netso_customer.py` (final integration test)
- Verify: all pages registered in `index.js`

- [ ] **Step 1: Write integration test**

```python
@pytest.mark.integration
class TestNetsoEndToEnd:
    """Verify all Netso endpoints return valid data for the seed customer."""

    def setup_method(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_all_endpoints_return_200(self):
        endpoints = [
            "/api/netso/customers/CGS-001/generation",
            "/api/netso/customers/CGS-001/savings",
            "/api/netso/customers/CGS-001/billing",
            "/api/netso/portfolio",
            "/api/netso/financials",
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            assert resp.status_code == 200, f"{ep} returned {resp.status_code}"

    def test_generation_savings_consistency(self):
        gen = self.client.get("/api/netso/customers/CGS-001/generation").json()
        sav = self.client.get("/api/netso/customers/CGS-001/savings").json()
        assert gen["current_month"]["generation_kwh"] == sav["current_month"]["generation_kwh"]

    def test_financial_constants_match_ground_truth(self):
        port = self.client.get("/api/netso/portfolio").json()
        fin = self.client.get("/api/netso/financials").json()
        assert port["financial_constants"]["true_variable_rate"] == 12.98
        assert fin["unit_economics"]["true_variable_rate_bdt_per_kwh"] == 12.98
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/test_netso_customer.py -v`
Expected: ALL PASS

- [ ] **Step 3: Verify all pages in index.js**

Read `odysseus/dashboard/index.js` and confirm all 6 Netso pages are registered in PAGES.

- [ ] **Step 4: Commit**

```bash
git add tests/test_netso_customer.py
git commit -m "test: add Netso integration tests — endpoint coverage + data consistency"
```

---

### Task 12: Full Suite + Lint

- [ ] **Step 1: Run full test suite**

Run: `pytest -q`
Expected: ALL PASS (existing + new Netso tests)

- [ ] **Step 2: Run linter**

Run: `ruff check . && ruff format .`
Expected: No errors

- [ ] **Step 3: Final commit if lint fixed anything**

```bash
git add -A
git commit -m "chore: lint + format after Netso dashboard implementation"
```
