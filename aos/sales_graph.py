"""Sales Harness — LangGraph implementation.

Implements the 5-phase sales cycle:
  1. QUALIFY  — Lead Qualifier scores incoming leads
  2. OUTREACH — Outreach Specialist contacts qualified leads
  3. PROPOSE  — Proposal Writer generates commercial proposals
  4. NEGOTIATE — All specialists handle objections
  5. CLOSE    — Finalize deal and dispatch to Legal

Follows the same patterns as the Executive Harness (graph.py)
but with sales-specific nodes and routing.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, END

from aos.llm import LLMClient, create_llm_client
from aos.memory import MemoryStore
from aos.registry import HarnessBundle
from aos.tools import ToolGateway
from aos.usage import UsageTracker


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class SalesCycleState:
    """Mutable state flowing through the sales graph."""
    # Identity
    cycle_id: str = ""
    harness_id: str = "HAR-SAL-001"
    venture_id: str = "VEN-NETSO-001"

    # Phase tracking
    current_phase: str = "qualify"
    phase_results: dict[str, Any] = field(default_factory=dict)

    # Lead data
    lead_id: str = ""
    lead_name: str = ""
    lead_score: float = 0.0
    icp_match: bool = False

    # Outreach
    outreach_channel: str = ""
    outreach_sent: bool = False
    response_received: bool = False

    # Proposal
    proposal_value_bdt: float = 0.0
    proposal_approved: bool = False
    requires_founder_approval: bool = False

    # Negotiation
    objections: list[str] = field(default_factory=list)
    terms_adjusted: bool = False

    # Close
    deal_closed: bool = False
    deal_outcome: str = ""  # "won" | "lost"

    # Pipeline
    pipeline_actions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    # Execution
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 3

    # LLM output (raw)
    raw_outputs: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Node: QUALIFY
# ---------------------------------------------------------------------------

async def qualify_node(state: SalesCycleState, config: Any = None) -> SalesCycleState:
    """Phase 1: Qualify incoming lead.

    Reads CRM pipeline, applies ICP matching (Bangladesh RMG, >500kW load),
    scores the lead, and decides whether to pass to outreach or disqualify.
    """
    llm = config.get("llm")
    bundle = config.get("bundle")

    # Get the lead qualifier agent
    qualifier = bundle.specialists.get("AGT-SAL-LEAD") if bundle else None

    prompt = f"""You are the Lead Qualifier for Netso Energy (HAR-SAL-001).

TASK: Qualify the following lead and provide a score.

LEAD INFORMATION:
- Name: {state.lead_name or 'Unknown lead'}
- ID: {state.lead_id or 'Pending'}

ICP CRITERIA (Bangladesh RMG Rooftop Solar):
1. Industry: Bangladesh RMG/garment manufacturing
2. Load: >500 kW electricity consumption
3. Model fit: BOO/OPEX (no upfront CAPEX from customer)
4. Decision-maker access: Yes/No
5. Timeline: Within 6 months

RESPONSE FORMAT (JSON):
{{
    "lead_id": "string",
    "lead_name": "string",
    "score": 0.0-1.0,
    "icp_match": true/false,
    "qualification_notes": "string",
    "route_to": "outreach" or "disqualify",
    "disqualify_reason": "string or null"
}}"""

    if llm and hasattr(llm, "generate"):
        try:
            response = await llm.generate(prompt, temperature=0.1)
            result = json.loads(response)
            state.lead_score = result.get("score", 0.0)
            state.icp_match = result.get("icp_match", False)
            state.lead_name = result.get("lead_name", state.lead_name)
            state.lead_id = result.get("lead_id", state.lead_id)
            state.raw_outputs["qualify"] = response
            state.phase_results["qualify"] = result
        except Exception as e:
            state.errors.append(f"Qualify error: {str(e)}")
    else:
        # Dry run: default qualification
        state.lead_score = 0.85
        state.icp_match = True
        state.phase_results["qualify"] = {
            "score": 0.85,
            "icp_match": True,
            "route_to": "outreach",
        }

    # Route decision
    if state.icp_match and state.lead_score >= 0.5:
        state.current_phase = "outreach"
    else:
        state.current_phase = "disqualified"
        state.deal_outcome = "lost"

    state.pipeline_actions.append({
        "phase": "qualify",
        "action": "lead_scored",
        "score": state.lead_score,
        "icp_match": state.icp_match,
        "timestamp": time.time(),
    })

    return state


# ---------------------------------------------------------------------------
# Node: OUTREACH
# ---------------------------------------------------------------------------

async def outreach_node(state: SalesCycleState, config: Any = None) -> SalesCycleState:
    """Phase 2: Execute outreach to qualified lead.

    Composes personalized message, sends via preferred channel,
    tracks engagement, and manages follow-up sequence.
    """
    llm = config.get("llm")
    bundle = config.get("bundle")

    outreach_agent = bundle.specialists.get("AGT-SAL-OUT") if bundle else None

    prompt = f"""You are the Outreach Specialist for Netso Energy (HAR-SAL-001).

TASK: Compose and execute outreach for a qualified lead.

LEAD:
- Name: {state.lead_name}
- Score: {state.lead_score}
- ICP Match: {state.icp_match}

CHANNELS: email, LinkedIn, WhatsApp
FOLLOW-UP SEQUENCE: Day 1, 3, 7, 14

RESPONSE FORMAT (JSON):
{{
    "channel": "email|linkedin|whatsapp",
    "message": "personalized outreach message",
    "subject": "email subject if email",
    "follow_up_day": 1,
    "sent": true/false,
    "notes": "string"
}}"""

    if llm and hasattr(llm, "generate"):
        try:
            response = await llm.generate(prompt, temperature=0.3)
            result = json.loads(response)
            state.outreach_channel = result.get("channel", "email")
            state.outreach_sent = result.get("sent", True)
            state.raw_outputs["outreach"] = response
            state.phase_results["outreach"] = result
        except Exception as e:
            state.errors.append(f"Outreach error: {str(e)}")
    else:
        state.outreach_channel = "email"
        state.outreach_sent = True
        state.phase_results["outreach"] = {
            "channel": "email",
            "sent": True,
        }

    state.current_phase = "propose"
    state.pipeline_actions.append({
        "phase": "outreach",
        "action": "outreach_sent",
        "channel": state.outreach_channel,
        "timestamp": time.time(),
    })

    return state


# ---------------------------------------------------------------------------
# Node: PROPOSE
# ---------------------------------------------------------------------------

async def propose_node(state: SalesCycleState, config: Any = None) -> SalesCycleState:
    """Phase 3: Generate commercial proposal.

    Uses ground truth constants for all financial calculations:
    - CAPEX: BDT 55,000/kW (Scenario A)
    - True Variable Rate: BDT 12.98/kWh
    - PPA Rate: BDT 10.00/kWh
    - Customer Savings: 23.0%
    - Escalation: 3% annually
    """
    llm = config.get("llm")
    bundle = config.get("bundle")

    proposal_agent = bundle.specialists.get("AGT-SAL-PROP") if bundle else None

    prompt = f"""You are the Proposal Writer for Netso Energy (HAR-SAL-001).

TASK: Generate a commercial proposal for a qualified lead.

LEAD: {state.lead_name}
SCORE: {state.lead_score}

GROUND TRUTH CONSTANTS (MUST USE THESE EXACT VALUES):
- CAPEX per kW: BDT 55,000 (Scenario A)
- True Variable Rate: BDT 12.98/kWh (NOT blended rate)
- Blended Rate: BDT 14.81/kWh (DO NOT use for savings calculations)
- PPA Rate: BDT 10.00/kWh
- Customer Savings: 23.0% (calculated from True Variable Rate)
- Escalation: 3% annually
- Project lifetime: 25 years

APPROVAL GATE: If proposal value > BDT 5,000,000 → requires founder approval

RESPONSE FORMAT (JSON):
{{
    "proposal_value_bdt": 0,
    "ppa_rate": 10.0,
    "savings_pct": 23.0,
    "capex_per_kw": 55000,
    "escalation_pct": 3.0,
    "requires_approval": true/false,
    "executive_summary": "string",
    "compliance_check": {{
        "uses_true_variable_rate": true,
        "savings_calculation_correct": true,
        "ppa_rate_correct": true
    }}
}}"""

    if llm and hasattr(llm, "generate"):
        try:
            response = await llm.generate(prompt, temperature=0.1)
            result = json.loads(response)
            state.proposal_value_bdt = result.get("proposal_value_bdt", 0)
            state.requires_founder_approval = result.get("requires_approval", False)
            state.raw_outputs["propose"] = response
            state.phase_results["propose"] = result
        except Exception as e:
            state.errors.append(f"Proposal error: {str(e)}")
    else:
        state.proposal_value_bdt = 3000000  # BDT 3M default
        state.requires_founder_approval = False
        state.phase_results["propose"] = {
            "proposal_value_bdt": 3000000,
            "requires_approval": False,
        }

    # Check approval gate
    if state.requires_founder_approval:
        state.current_phase = "approval_pending"
        state.warnings.append(f"Proposal value BDT {state.proposal_value_bdt:,.0f} exceeds BDT 5M threshold — requires founder approval")
    else:
        state.current_phase = "negotiate"

    state.pipeline_actions.append({
        "phase": "propose",
        "action": "proposal_generated",
        "value_bdt": state.proposal_value_bdt,
        "requires_approval": state.requires_founder_approval,
        "timestamp": time.time(),
    })

    return state


# ---------------------------------------------------------------------------
# Node: NEGOTIATE
# ---------------------------------------------------------------------------

async def negotiate_node(state: SalesCycleState, config: Any = None) -> SalesCycleState:
    """Phase 4: Handle objections and negotiate terms.

    Manages customer objections using objection_handlers,
    adjusts terms within approval thresholds, and tracks status.
    """
    llm = config.get("llm")
    bundle = config.get("bundle")

    qualifier = bundle.specialists.get("AGT-SAL-LEAD") if bundle else None

    prompt = f"""You are handling negotiation for Netso Energy (HAR-SAL-001).

LEAD: {state.lead_name}
PROPOSAL VALUE: BDT {state.proposal_value_bdt:,.0f}
PPA RATE: BDT 10.00/kWh
SAVINGS: 23.0%

TASK: Handle objections and negotiate terms.

OBJECTION HANDLING RULES:
- Price objection: Reiterate 23% savings vs grid rate
- Risk objection: Highlight 25-year track record and O&M included
- Timing objection: Emphasize rising grid rates and early-mover advantage
- Technical objection: Offer site assessment and reference visits

PRICING BOUNDS (without approval):
- Minimum PPA: BDT 9.50/kWh
- Maximum discount: 5% from standard terms

RESPONSE FORMAT (JSON):
{{
    "objections_handled": ["list of objections addressed"],
    "terms_adjusted": true/false,
    "adjusted_terms": {{
        "ppa_rate": 10.0,
        "notes": "string"
    }},
    "negotiation_status": "in_progress|won|lost",
    "next_action": "string"
}}"""

    if llm and hasattr(llm, "generate"):
        try:
            response = await llm.generate(prompt, temperature=0.2)
            result = json.loads(response)
            state.objections = result.get("objections_handled", [])
            state.terms_adjusted = result.get("terms_adjusted", False)
            state.raw_outputs["negotiate"] = response
            state.phase_results["negotiate"] = result

            status = result.get("negotiation_status", "in_progress")
            if status == "won":
                state.current_phase = "close"
            elif status == "lost":
                state.current_phase = "closed"
                state.deal_outcome = "lost"
            else:
                state.current_phase = "negotiate"  # Continue
        except Exception as e:
            state.errors.append(f"Negotiation error: {str(e)}")
    else:
        state.current_phase = "close"
        state.phase_results["negotiate"] = {
            "negotiation_status": "won",
        }

    state.pipeline_actions.append({
        "phase": "negotiate",
        "action": "negotiation_complete",
        "objections": state.objections,
        "terms_adjusted": state.terms_adjusted,
        "timestamp": time.time(),
    })

    return state


# ---------------------------------------------------------------------------
# Node: CLOSE
# ---------------------------------------------------------------------------

async def close_node(state: SalesCycleState, config: Any = None) -> SalesCycleState:
    """Phase 5: Close the deal.

    Confirms final terms, dispatches to Legal harness for NDA/LOI/PPA,
    updates CRM, and logs win/loss analysis.
    """
    state.deal_closed = True
    state.deal_outcome = "won"
    state.current_phase = "closed"

    state.pipeline_actions.append({
        "phase": "close",
        "action": "deal_closed",
        "outcome": state.deal_outcome,
        "value_bdt": state.proposal_value_bdt,
        "timestamp": time.time(),
    })

    state.artifacts.append({
        "type": "closed_deal",
        "lead_id": state.lead_id,
        "lead_name": state.lead_name,
        "value_bdt": state.proposal_value_bdt,
        "outcome": state.deal_outcome,
        "pipeline_actions": state.pipeline_actions,
    })

    return state


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_sales_graph(
    bundle: HarnessBundle,
    llm: LLMClient | None = None,
    tool_gateway: ToolGateway | None = None,
    memory_store: MemoryStore | None = None,
) -> any:
    """Build and compile the Sales Harness LangGraph StateGraph.

    Graph topology::

        qualify ─→ outreach ─→ propose ─→ negotiate ─→ close → END
                                  │
                                  └─(approval needed)→ END (waits for approval)
    """
    from functools import partial

    graph = StateGraph(SalesCycleState)
    config = {"bundle": bundle, "llm": llm}

    # Nodes — bind config so LangGraph only needs to pass state
    graph.add_node("qualify", partial(qualify_node, config=config))
    graph.add_node("outreach", partial(outreach_node, config=config))
    graph.add_node("propose", partial(propose_node, config=config))
    graph.add_node("negotiate", partial(negotiate_node, config=config))
    graph.add_node("close", partial(close_node, config=config))

    # Entry
    graph.set_entry_point("qualify")

    # Linear flow
    graph.add_edge("qualify", "outreach")
    graph.add_edge("outreach", "propose")

    # Conditional: propose → negotiate OR END (approval pending)
    def after_propose(state: SalesCycleState) -> str:
        if state.requires_founder_approval:
            return "END"
        if state.current_phase == "disqualified":
            return "END"
        return "negotiate"

    graph.add_conditional_edges(
        "propose",
        after_propose,
        {
            "negotiate": "negotiate",
            "END": END,
        },
    )

    # Conditional: negotiate → close OR END
    def after_negotiate(state: SalesCycleState) -> str:
        if state.deal_outcome == "lost":
            return "END"
        return "close"

    graph.add_conditional_edges(
        "negotiate",
        after_negotiate,
        {
            "close": "close",
            "END": END,
        },
    )

    # close → END
    graph.add_edge("close", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Convenience: run sales cycle via graph
# ---------------------------------------------------------------------------

async def run_sales_cycle(
    bundle: HarnessBundle,
    lead_name: str = "",
    lead_id: str = "",
    venture_id: str = "VEN-NETSO-001",
    llm: LLMClient | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> SalesCycleState:
    """Execute a full sales cycle via the LangGraph pipeline.

    Args:
        bundle: Loaded harness bundle with manifests.
        lead_name: Name of the lead to process.
        lead_id: CRM ID of the lead.
        venture_id: Venture ID.
        llm: LLM client (created if None).
        dry_run: If True, use default values without LLM calls.
        verbose: Print execution details.

    Returns:
        Final SalesCycleState with all phase results.
    """
    if llm is None:
        llm = create_llm_client(dry_run=dry_run, verbose=verbose)

    graph = build_sales_graph(bundle=bundle, llm=llm)

    initial = SalesCycleState(
        cycle_id=f"{date.today().isoformat()}-sales",
        venture_id=venture_id,
        lead_name=lead_name,
        lead_id=lead_id,
    )

    # Run graph — ainvoke returns a dict, reconstruct the state object
    raw = await graph.ainvoke(initial)
    if isinstance(raw, dict):
        result = SalesCycleState(**raw)
    else:
        result = raw

    if verbose:
        print(f"\n{'='*60}")
        print(f"SALES CYCLE COMPLETE: {result.cycle_id}")
        print(f"Lead: {result.lead_name} (Score: {result.lead_score})")
        print(f"Outcome: {result.deal_outcome}")
        print(f"Phases: {list(result.phase_results.keys())}")
        print(f"Errors: {result.errors}")
        print(f"{'='*60}\n")

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AOS Sales Harness")
    parser.add_argument("--lead-name", default="", help="Lead name")
    parser.add_argument("--lead-id", default="", help="Lead CRM ID")
    parser.add_argument("--dry-run", action="store_true", help="Run without LLM")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    from aos.registry import load_registry
    from pathlib import Path

    harness_dir = Path(__file__).parent / "harnesses" / "sales"
    registry = load_registry(harness_dir=harness_dir)

    bundle = next(iter(registry.harnesses.values()))

    import asyncio
    result = asyncio.run(run_sales_cycle(
        bundle=bundle,
        lead_name=args.lead_name,
        lead_id=args.lead_id,
        dry_run=args.dry_run,
        verbose=args.verbose,
    ))

    # Output summary
    summary = {
        "cycle_id": result.cycle_id,
        "lead_name": result.lead_name,
        "lead_score": result.lead_score,
        "deal_outcome": result.deal_outcome,
        "phases_completed": list(result.phase_results.keys()),
        "pipeline_actions": len(result.pipeline_actions),
        "errors": result.errors,
    }
    print(json.dumps(summary, indent=2))
