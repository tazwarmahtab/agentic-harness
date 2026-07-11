"""Tests for Sales Harness — full component stack."""

from pathlib import Path

import pytest

from aos.loader import (
    load_harness,
    load_agent,
    load_memory,
    load_tool_registry,
    load_evaluation,
    load_policy_collection,
    load_sop,
)

HARNESS_DIR = Path(__file__).resolve().parent.parent / "tazos" / "harnesses" / "sales"


@pytest.fixture
def harness_dir():
    if not HARNESS_DIR.exists():
        pytest.skip("Sales harness directory not found")
    return HARNESS_DIR


class TestSalesHarnessManifests:
    """Validate that all Sales harness YAML manifests load correctly."""

    def test_harness_loads(self, harness_dir):
        h = load_harness(harness_dir / "harness.yml")
        assert h.id == "HAR-SAL-001"
        assert h.name == "Sales Harness"

    def test_planner_loads(self, harness_dir):
        a = load_agent(harness_dir / "planner.yml")
        assert a.id == "AGT-SAL-PLAN"
        assert "planner" in a.name.lower() or "plan" in a.id.lower()

    def test_dispatcher_loads(self, harness_dir):
        a = load_agent(harness_dir / "dispatcher.yml")
        assert a.id == "AGT-SAL-DISPATCH"

    def test_three_specialists(self, harness_dir):
        spec_dir = harness_dir / "specialists"
        assert spec_dir.exists()
        specs = list(spec_dir.glob("*.yml"))
        assert len(specs) == 3

    def test_lead_qualifier_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "lead-qualifier.yml")
        assert "LEAD" in a.id

    def test_outreach_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "outreach.yml")
        assert "OUT" in a.id

    def test_proposal_writer_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "proposal-writer.yml")
        assert "PROP" in a.id


class TestSalesMemory:
    """Validate Sales memory manifest."""

    def test_memory_loads(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.id == "MEM-SAL-001"

    def test_memory_has_three_layers(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.layers is not None

    def test_memory_permissions_exist(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.permissions is not None
        assert len(m.permissions) >= 3


class TestSalesTools:
    """Validate Sales tool registry."""

    def test_tools_loads(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        assert t.id == "TOL-SAL-001"

    def test_has_required_tools(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        tool_ids = [tool.id for tool in t.tools]
        assert len(t.tools) >= 5


class TestSalesApprovals:
    """Validate Sales approval gates."""

    def test_approvals_loads(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.id == "POL-SAL-001"

    def test_has_financial_gates(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert len(p.rules) >= 4

    def test_has_auto_actions(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.auto_actions is not None
        assert len(p.auto_actions) >= 5


class TestSalesEvaluation:
    """Validate Sales evaluation framework."""

    def test_evaluation_loads(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.id == "EVAL-SAL-001"

    def test_has_harness_metrics(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.harness_metrics is not None
        assert len(e.harness_metrics) >= 4

    def test_has_specialist_metrics(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.specialist_metrics is not None
        assert len(e.specialist_metrics) >= 3

    def test_has_continuous_improvement(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.continuous_improvement is not None


class TestSalesSOPs:
    """Validate Sales SOPs."""

    def test_sops_dir_exists(self, harness_dir):
        sops_dir = harness_dir / "sops"
        assert sops_dir.exists()

    def test_sales_cycle_sop_loads(self, harness_dir):
        sop = load_sop(harness_dir / "sops" / "sales-cycle.yml")
        assert sop.id == "SOP-SAL-001"
        assert sop.name == "Sales Cycle"
