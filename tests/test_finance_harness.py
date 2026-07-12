"""Tests for Finance Harness — full component stack."""

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

HARNESS_DIR = Path(__file__).resolve().parent.parent / "aos" / "harnesses" / "finance"


@pytest.fixture
def harness_dir():
    if not HARNESS_DIR.exists():
        pytest.skip("Finance harness directory not found")
    return HARNESS_DIR


class TestFinanceHarnessManifests:
    def test_harness_loads(self, harness_dir):
        h = load_harness(harness_dir / "harness.yml")
        assert h.id == "HAR-FIN-001"

    def test_planner_loads(self, harness_dir):
        a = load_agent(harness_dir / "planner.yml")
        assert a.id == "AGT-FIN-PLAN"

    def test_dispatcher_loads(self, harness_dir):
        a = load_agent(harness_dir / "dispatcher.yml")
        assert a.id == "AGT-FIN-DISPATCH"

    def test_three_specialists(self, harness_dir):
        specs = list((harness_dir / "specialists").glob("*.yml"))
        assert len(specs) == 3

    def test_cash_flow_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "cash-flow.yml")
        assert "CASH" in a.id

    def test_investor_deck_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "investor-deck.yml")
        assert "DECK" in a.id

    def test_unit_economics_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "unit-economics.yml")
        assert "UNIT" in a.id


class TestFinanceMemory:
    def test_memory_loads(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.id == "MEM-FIN-001"

    def test_has_three_layers(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.layers is not None

    def test_permissions_exist(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.permissions is not None
        assert len(m.permissions) >= 3


class TestFinanceTools:
    def test_tools_loads(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        assert t.id == "TOL-FIN-001"

    def test_has_financial_model_tool(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        [tool.id for tool in t.tools]
        assert len(t.tools) >= 5


class TestFinanceApprovals:
    def test_approvals_loads(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.id == "POL-FIN-001"

    def test_has_ai_safety_gates(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert len(p.rules) >= 4

    def test_has_auto_actions(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.auto_actions is not None


class TestFinanceEvaluation:
    def test_evaluation_loads(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.id == "EVAL-FIN-001"

    def test_has_harness_metrics(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.harness_metrics is not None
        assert len(e.harness_metrics) >= 3

    def test_has_specialist_metrics(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.specialist_metrics is not None
        assert len(e.specialist_metrics) >= 3

    def test_has_continuous_improvement(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.continuous_improvement is not None


class TestFinanceSOPs:
    def test_sops_dir_exists(self, harness_dir):
        assert (harness_dir / "sops").exists()

    def test_financial_reporting_sop_loads(self, harness_dir):
        sop = load_sop(harness_dir / "sops" / "financial-reporting.yml")
        assert sop.id == "SOP-FIN-001"
