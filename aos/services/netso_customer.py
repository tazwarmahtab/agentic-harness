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
    capacity_factor = (
        (latest.get("generation_kwh", 0) / (site["system_capacity_kw"] * 730)) * 100
        if site["system_capacity_kw"] > 0 and latest
        else 0
    )
    self_consumption = (
        (
            (latest.get("generation_kwh", 0) - latest.get("grid_export_kwh", 0))
            / latest.get("generation_kwh", 1)
        )
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
            "interval_years": customer.get("escalation_interval_years", 3),
            "next_escalation_date": customer.get("next_escalation_date", ""),
            "projected_ppa_after_escalation": round(projected_ppa, 2),
        },
        trend=[
            {
                "month": t["month"],
                "savings_bdt": round(
                    t["generation_kwh"] * (TRUE_VARIABLE_RATE - ppa_rate), 2
                ),
            }
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
    total_ytd_revenue = 0
    total_ytd_savings = 0
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

        # YTD: sum actual monthly revenue/savings from all months in generation data
        for m in monthly:
            gen_kwh = m.get("generation_kwh", 0)
            total_ytd_revenue += gen_kwh * ppa_rate
            total_ytd_savings += gen_kwh * (TRUE_VARIABLE_RATE - ppa_rate)

        customer_summaries.append(
            {
                "customer_id": cid,
                "customer_name": c["customer_name"],
                "capacity_kw": c.get("system_capacity_kw", 0),
                "status": c.get("status", "unknown"),
                "monthly_generation_kwh": gen_month,
                "monthly_savings_bdt": round(sav_month, 2),
                "health_score": c.get("health_score", 0),
            }
        )

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
            "ytd_revenue_bdt": round(total_ytd_revenue, 2),
            "ytd_savings_delivered_bdt": round(total_ytd_savings, 2),
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
