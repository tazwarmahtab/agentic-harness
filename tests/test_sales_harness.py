"""Tests for the Sales Harness — Phase 7 implementation."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from aos.sales_graph import (
    SalesCycleState,
    qualify_node,
    outreach_node,
    propose_node,
    negotiate_node,
    close_node,
    build_sales_graph,
    run_sales_cycle,
)
from aos.registry import load_registry, HarnessBundle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sales_bundle() -> HarnessBundle:
    """Load the Sales Harness bundle from manifests."""
    harness_dir = Path(__file__).parent.parent / "aos" / "harnesses" / "sales"
    registry = load_registry(harness_dir=harness_dir)
    return next(iter(registry.harnesses.values()))


@pytest.fixture
def mock_llm():
    """Mock LLM that returns valid JSON for each phase."""
    llm = AsyncMock()

    qualify_response = json.dumps(
        {
            "lead_id": "LEAD-001",
            "lead_name": "Test RMG Factory",
            "score": 0.85,
            "icp_match": True,
            "qualification_notes": "Bangladesh RMG, 800kW load, OPEX fit",
            "route_to": "outreach",
            "disqualify_reason": None,
        }
    )

    outreach_response = json.dumps(
        {
            "channel": "email",
            "message": "Dear Test Factory, we'd like to discuss solar solutions...",
            "subject": "Netso Energy — Solar for Your Factory",
            "follow_up_day": 1,
            "sent": True,
            "notes": "Initial outreach sent",
        }
    )

    propose_response = json.dumps(
        {
            "proposal_value_bdt": 44000000,
            "ppa_rate": 10.0,
            "savings_pct": 23.0,
            "capex_per_kw": 55000,
            "escalation_pct": 3.0,
            "requires_approval": True,
            "executive_summary": "800kW rooftop solar system for Test RMG Factory",
            "compliance_check": {
                "uses_true_variable_rate": True,
                "savings_calculation_correct": True,
                "ppa_rate_correct": True,
            },
        }
    )

    negotiate_response = json.dumps(
        {
            "objections_handled": ["price_concern", "timeline"],
            "terms_adjusted": False,
            "adjusted_terms": {"ppa_rate": 10.0, "notes": "Standard terms accepted"},
            "negotiation_status": "won",
            "next_action": "dispatch to legal",
        }
    )

    async def generate(prompt, temperature=0.3):
        lower = prompt.lower()
        # Order matters: earlier prompts contain keywords from later phases
        if "negotiat" in lower:
            return negotiate_response
        elif "proposal" in lower or "commercial proposal" in lower:
            return propose_response
        elif "task: qualify" in lower or "lead qualifier" in lower:
            return qualify_response
        elif "outreach" in lower:
            return outreach_response
        return qualify_response

    llm.generate = generate
    return llm


@pytest.fixture
def dry_config(sales_bundle):
    """Config for dry-run tests (no LLM)."""
    return {"bundle": sales_bundle, "llm": None}


@pytest.fixture
def llm_config(sales_bundle, mock_llm):
    """Config with mock LLM for full tests."""
    return {"bundle": sales_bundle, "llm": mock_llm}


# ---------------------------------------------------------------------------
# Unit tests — individual nodes
# ---------------------------------------------------------------------------


class TestQualifyNode:
    @pytest.mark.asyncio
    async def test_qualify_dry_run(self, dry_config):
        state = SalesCycleState(lead_name="Test Factory", lead_id="LEAD-001")
        result = await qualify_node(state, dry_config)

        assert result.lead_score == 0.85
        assert result.icp_match is True
        assert result.current_phase == "outreach"
        assert len(result.pipeline_actions) == 1

    @pytest.mark.asyncio
    async def test_qualify_with_llm(self, llm_config):
        state = SalesCycleState(lead_name="Test Factory", lead_id="LEAD-001")
        result = await qualify_node(state, llm_config)

        assert result.lead_score == 0.85
        assert result.icp_match is True
        assert result.current_phase == "outreach"
        assert "qualify" in result.raw_outputs

    @pytest.mark.asyncio
    async def test_qualify_disqualifies_low_score(self, llm_config):
        async def low_score_generate(prompt, temperature=0.3):
            return json.dumps(
                {
                    "lead_id": "LEAD-002",
                    "lead_name": "Bad Lead",
                    "score": 0.2,
                    "icp_match": False,
                    "route_to": "disqualify",
                }
            )

        llm_config["llm"].generate = low_score_generate
        state = SalesCycleState(lead_name="Bad Lead")
        result = await qualify_node(state, llm_config)

        assert result.lead_score == 0.2
        assert result.icp_match is False
        assert result.current_phase == "disqualified"


class TestOutreachNode:
    @pytest.mark.asyncio
    async def test_outreach_dry_run(self, dry_config):
        state = SalesCycleState(lead_name="Test Factory", lead_score=0.85)
        result = await outreach_node(state, dry_config)

        assert result.outreach_channel == "email"
        assert result.outreach_sent is True
        assert result.current_phase == "propose"

    @pytest.mark.asyncio
    async def test_outreach_with_llm(self, llm_config):
        state = SalesCycleState(lead_name="Test Factory", lead_score=0.85)
        result = await outreach_node(state, llm_config)

        assert result.outreach_sent is True
        assert "outreach" in result.raw_outputs


class TestProposeNode:
    @pytest.mark.asyncio
    async def test_propose_dry_run(self, dry_config):
        state = SalesCycleState(lead_name="Test Factory")
        result = await propose_node(state, dry_config)

        assert result.proposal_value_bdt == 3000000
        assert result.requires_founder_approval is False
        assert result.current_phase == "negotiate"

    @pytest.mark.asyncio
    async def test_propose_with_llm(self, llm_config):
        state = SalesCycleState(lead_name="Test Factory")
        result = await propose_node(state, llm_config)

        assert result.proposal_value_bdt == 44000000
        assert result.requires_founder_approval is True
        assert result.current_phase == "approval_pending"
        assert any("approval" in w.lower() for w in result.warnings)


class TestNegotiateNode:
    @pytest.mark.asyncio
    async def test_negotiate_dry_run(self, dry_config):
        state = SalesCycleState(lead_name="Test Factory")
        result = await negotiate_node(state, dry_config)

        assert result.current_phase == "close"

    @pytest.mark.asyncio
    async def test_negotiate_with_llm(self, llm_config):
        state = SalesCycleState(lead_name="Test Factory")
        result = await negotiate_node(state, llm_config)

        assert result.current_phase == "close"
        assert result.objections == ["price_concern", "timeline"]


class TestCloseNode:
    @pytest.mark.asyncio
    async def test_close(self, dry_config):
        state = SalesCycleState(lead_name="Test Factory", proposal_value_bdt=44000000)
        result = await close_node(state, dry_config)

        assert result.deal_closed is True
        assert result.deal_outcome == "won"
        assert result.current_phase == "closed"
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "closed_deal"


# ---------------------------------------------------------------------------
# Integration tests — full graph
# ---------------------------------------------------------------------------


class TestSalesGraph:
    def test_build_graph(self, sales_bundle):
        graph = build_sales_graph(bundle=sales_bundle)
        assert graph is not None

    @pytest.mark.asyncio
    async def test_run_cycle_dry_run(self, sales_bundle):
        result = await run_sales_cycle(
            bundle=sales_bundle,
            lead_name="Test RMG Factory",
            lead_id="LEAD-001",
            dry_run=True,
            verbose=False,
        )

        assert result.cycle_id.startswith("2026-")
        assert result.lead_name == "Test RMG Factory"
        assert result.lead_score == 0.85
        assert result.deal_outcome == "won"
        assert len(result.pipeline_actions) >= 4
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_run_cycle_with_llm(self, sales_bundle, mock_llm):
        result = await run_sales_cycle(
            bundle=sales_bundle,
            lead_name="Test RMG Factory",
            lead_id="LEAD-001",
            llm=mock_llm,
            verbose=False,
        )

        assert result.lead_score == 0.85
        # BDT 44M proposal triggers approval gate — cycle halts at propose
        assert result.requires_founder_approval is True
        assert result.current_phase == "approval_pending"
        assert "qualify" in result.raw_outputs
        assert "outreach" in result.raw_outputs
        assert "propose" in result.raw_outputs

    @pytest.mark.asyncio
    async def test_run_cycle_requires_approval(self, sales_bundle):
        """Large proposal should require founder approval."""
        result = await run_sales_cycle(
            bundle=sales_bundle,
            lead_name="Large Factory",
            lead_id="LEAD-002",
            dry_run=True,
            verbose=False,
        )

        # Dry run default is BDT 3M which doesn't require approval
        assert result.requires_founder_approval is False


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


class TestSalesManifests:
    def test_harness_manifest_exists(self, sales_bundle):
        assert sales_bundle.harness is not None
        assert sales_bundle.harness.id == "HAR-SAL-001"

    def test_specialists_loaded(self, sales_bundle):
        assert "AGT-SAL-LEAD" in sales_bundle.specialists
        assert "AGT-SAL-OUT" in sales_bundle.specialists
        assert "AGT-SAL-PROP" in sales_bundle.specialists

    def test_tools_loaded(self, sales_bundle):
        assert sales_bundle.tools is not None

    def test_approvals_loaded(self, sales_bundle):
        assert sales_bundle.approvals is not None

    def test_sops_loaded(self, sales_bundle):
        assert len(sales_bundle.sops) > 0

    def test_evaluation_loaded(self, sales_bundle):
        assert sales_bundle.evaluation is not None
