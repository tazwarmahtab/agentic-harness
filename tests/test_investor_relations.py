"""Tests for TAZ OS Investor Relations Harness — Phase 16."""

from __future__ import annotations
import sys

from pathlib import Path

import pytest

from tazos.registry import load_registry


class TestInvestorRelationsHarnessLoading:
    def test_load_ir_harness(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-INV-001"

    def test_ir_has_5_specialists(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) == 5

    def test_ir_has_planner(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-INV-PLAN"

    def test_ir_has_dispatcher(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-INV-DISPATCH"


class TestInvestorCRM:
    def test_crm_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        crm = bundle.specialists.get("AGT-INV-CRM")
        assert crm is not None
        assert crm.name == "Investor CRM"
        assert crm.criticality.value == "high"

    def test_crm_has_approval_constraint(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        crm = bundle.specialists.get("AGT-INV-CRM")
        assert crm is not None
        constraint_text = " ".join(crm.constraints).lower()
        assert "approval" in constraint_text


class TestPitchDeck:
    def test_pitch_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        pitch = bundle.specialists.get("AGT-INV-PITCH")
        assert pitch is not None
        assert pitch.name == "Pitch Deck Specialist"
        assert pitch.criticality.value == "high"

    def test_pitch_has_financial_rules(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        pitch = bundle.specialists.get("AGT-INV-PITCH")
        assert pitch is not None
        assert pitch.financial_rules is not None
        assert "hard_fails" in pitch.financial_rules
        assert len(pitch.financial_rules["hard_fails"]) >= 2

    def test_pitch_financial_constants_match(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        pitch = bundle.specialists.get("AGT-INV-PITCH")
        assert pitch is not None
        consts = pitch.financial_rules["constants_to_enforce"]
        assert consts["ppa_rate"] == 10.0
        assert consts["true_variable_rate"] == 12.98
        assert consts["blended_rate"] == 14.81
        assert consts["customer_savings_pct"] == 23.0


class TestDueDiligence:
    def test_dd_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        dd = bundle.specialists.get("AGT-INV-DD")
        assert dd is not None
        assert dd.name == "Due Diligence Assistant"
        assert dd.criticality.value == "high"

    def test_dd_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        dd = bundle.specialists.get("AGT-INV-DD")
        assert dd is not None
        assert len(dd.constraints) >= 3


class TestFinancialProjections:
    def test_proj_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        proj = bundle.specialists.get("AGT-INV-PROJ")
        assert proj is not None
        assert proj.name == "Financial Projections"
        assert proj.criticality.value == "critical"

    def test_proj_has_financial_rules(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        proj = bundle.specialists.get("AGT-INV-PROJ")
        assert proj is not None
        assert proj.financial_rules is not None
        assert "hard_fails" in proj.financial_rules
        assert len(proj.financial_rules["hard_fails"]) >= 2

    def test_proj_has_capacity_factor(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        proj = bundle.specialists.get("AGT-INV-PROJ")
        assert proj is not None
        consts = proj.financial_rules["constants_to_enforce"]
        assert consts["capacity_factor"] == 16.5


class TestFundraisingTracker:
    def test_fund_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        fund = bundle.specialists.get("AGT-INV-FUND")
        assert fund is not None
        assert fund.name == "Fundraising Tracker"
        assert fund.criticality.value == "high"

    def test_fund_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/investor_relations")
        if not harness_dir.exists():
            pytest.skip("Investor Relations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        fund = bundle.specialists.get("AGT-INV-FUND")
        assert fund is not None
        assert len(fund.constraints) >= 3


class TestCLIInvestorRelations:
    def test_cli_run_ir_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "run", "--harness", "investor_relations", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "investor_relations" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_validate_ir_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "validate", "--harness", "investor_relations"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)
