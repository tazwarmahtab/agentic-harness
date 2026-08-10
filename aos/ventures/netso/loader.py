"""Netso venture seed data loader.

Reads seed files (customers, billing, generation, deals) and assembles
a context dict for the harness runtime. This data is injected into the
initial state so agents have real venture context during execution.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Seed file paths relative to venture directory
SEED_FILES = {
    "customers": "seed/customers.json",
    "billing": "seed/billing.json",
    "generation": "seed/generation.json",
    "deals": "deals.json",
}


def load_seed_data(venture_dir: Path) -> dict[str, Any]:
    """Load all seed data files from the venture directory.

    Parameters
    ----------
    venture_dir:
        Path to the venture directory (e.g., aos/ventures/netso/).

    Returns
    -------
    dict with keys: customers, billing, generation, deals, summary
    """
    data: dict[str, Any] = {}

    for key, filename in SEED_FILES.items():
        filepath = venture_dir / filename
        if filepath.exists():
            try:
                with open(filepath) as f:
                    data[key] = json.load(f)
                logger.info("Loaded seed data: %s (%s)", key, filepath)
            except Exception as e:
                logger.warning("Failed to load %s: %s", filepath, e)
                data[key] = None
        else:
            logger.debug("Seed file not found: %s", filepath)
            data[key] = None

    # Build summary for agent context
    data["summary"] = _build_summary(data)

    return data


def _build_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Build a human-readable summary from raw seed data."""
    summary: dict[str, Any] = {
        "total_customers": 0,
        "active_customers": 0,
        "total_capacity_kw": 0,
        "pipeline_deals": 0,
        "outstanding_invoices": 0,
        "outstanding_amount_bdt": 0,
        "recent_generation_kwh": 0,
    }

    # Customers
    customers = data.get("customers", {})
    if isinstance(customers, dict) and "customers" in customers:
        cust_list = customers["customers"]
        summary["total_customers"] = len(cust_list)
        summary["active_customers"] = sum(
            1 for c in cust_list if c.get("status") == "active"
        )
        summary["total_capacity_kw"] = sum(
            c.get("system_capacity_kw", 0) for c in cust_list
        )

    # Billing
    billing = data.get("billing", {})
    if isinstance(billing, dict):
        for cust_id, inv_data in billing.items():
            invoices = inv_data.get("invoices", [])
            for inv in invoices:
                if inv.get("status") == "pending":
                    summary["outstanding_invoices"] += 1
                    summary["outstanding_amount_bdt"] += inv.get("amount_bdt", 0)

    # Generation
    generation = data.get("generation", {})
    if isinstance(generation, dict):
        for cust_id, gen_data in generation.items():
            monthly = gen_data.get("monthly", [])
            if monthly:
                latest = monthly[-1]
                summary["recent_generation_kwh"] += latest.get("generation_kwh", 0)

    # Deals
    deals = data.get("deals", {})
    if isinstance(deals, dict) and "deals" in deals:
        summary["pipeline_deals"] = len(deals["deals"])

    return summary


def format_seed_context(seed_data: dict[str, Any]) -> str:
    """Format seed data as a context string for agent prompts.

    Returns a markdown-formatted string suitable for injection into
    system prompts or agent context windows.
    """
    lines = ["## Netso Energy — Live Data\n"]

    summary = seed_data.get("summary", {})

    # Pipeline
    deals = seed_data.get("deals", {})
    if deals and "deals" in deals:
        lines.append("### Pipeline")
        for deal in deals["deals"]:
            lines.append(
                f"- {deal['id']}: {deal['customer']} ({deal['stage']}) "
                f"— {deal.get('capacity_kw', 'TBD')} kW"
            )
        lines.append("")

    # Customers
    customers = seed_data.get("customers", {})
    if customers and "customers" in customers:
        lines.append("### Customers")
        for cust in customers["customers"]:
            lines.append(
                f"- {cust['customer_id']}: {cust['customer_name']} "
                f"({cust['system_capacity_kw']} kW, {cust['status']})"
            )
        lines.append("")

    # Generation
    generation = seed_data.get("generation", {})
    if generation:
        lines.append("### Recent Generation")
        for cust_id, gen_data in generation.items():
            monthly = gen_data.get("monthly", [])
            if monthly:
                latest = monthly[-1]
                lines.append(
                    f"- {cust_id}: {latest['generation_kwh']:,} kWh "
                    f"(availability: {latest['availability_pct']}%)"
                )
        lines.append("")

    # Billing
    billing = seed_data.get("billing", {})
    if billing:
        lines.append("### Billing Status")
        for cust_id, inv_data in billing.items():
            for inv in inv_data.get("invoices", []):
                status_icon = "✅" if inv["status"] == "paid" else "⏳"
                lines.append(
                    f"- {status_icon} {inv['invoice_id']}: "
                    f"BDT {inv['amount_bdt']:,.2f} ({inv['status']})"
                )
        lines.append("")

    # Summary stats
    lines.append("### Summary")
    lines.append(f"- Active customers: {summary.get('active_customers', 0)}")
    lines.append(f"- Total capacity: {summary.get('total_capacity_kw', 0):,} kW")
    lines.append(
        f"- Outstanding invoices: {summary.get('outstanding_invoices', 0)} "
        f"(BDT {summary.get('outstanding_amount_bdt', 0):,.2f})"
    )
    lines.append(
        f"- Pipeline deals: {summary.get('pipeline_deals', 0)}"
    )

    return "\n".join(lines)
