"""Tests for TAZ OS multi-harness dispatch — Phase 9."""

from __future__ import annotations

from pathlib import Path

import pytest

from tazos.registry import load_registry, Registry


class TestMultiHarnessLoading:
    def test_load_finance_harness(self) -> None:
        harness_dir = Path("tazos/harnesses/finance")
        if not harness_dir.exists():
            pytest.skip("Finance harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-FIN-001"

    def test_load_sales_harness(self) -> None:
        harness_dir = Path("tazos/harnesses/sales")
        if not harness_dir.exists():
            pytest.skip("Sales harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-SAL-001"

    def test_load_operations_harness(self) -> None:
        harness_dir = Path("tazos/harnesses/operations")
        if not harness_dir.exists():
            pytest.skip("Operations harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-OPS-001"


class TestFinanceSpecialists:
    def test_finance_has_specialists(self) -> None:
        harness_dir = Path("tazos/harnesses/finance")
        if not harness_dir.exists():
            pytest.skip("Finance harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) >= 3  # unit-economics, investor-deck, cash-flow

    def test_finance_has_planner(self) -> None:
        harness_dir = Path("tazos/harnesses/finance")
        if not harness_dir.exists():
            pytest.skip("Finance harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-FIN-PLAN"

    def test_finance_has_dispatcher(self) -> None:
        harness_dir = Path("tazos/harnesses/finance")
        if not harness_dir.exists():
            pytest.skip("Finance harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-FIN-DISPATCH"

    def test_finance_unit_economics_has_financial_rules(self) -> None:
        harness_dir = Path("tazos/harnesses/finance")
        if not harness_dir.exists():
            pytest.skip("Finance harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        unit = bundle.specialists.get("AGT-FIN-UNIT")
        assert unit is not None
        assert unit.financial_rules is not None
        assert "hard_fails" in unit.financial_rules


class TestSalesSpecialists:
    def test_sales_has_specialists(self) -> None:
        harness_dir = Path("tazos/harnesses/sales")
        if not harness_dir.exists():
            pytest.skip("Sales harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) >= 3  # lead-qualifier, proposal-writer, outreach

    def test_proposal_writer_has_financial_rules(self) -> None:
        harness_dir = Path("tazos/harnesses/sales")
        if not harness_dir.exists():
            pytest.skip("Sales harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        prop = bundle.specialists.get("AGT-SAL-PROP")
        assert prop is not None
        assert prop.financial_rules is not None
        assert "hard_fails" in prop.financial_rules


class TestOperationsSpecialists:
    def test_operations_has_specialists(self) -> None:
        harness_dir = Path("tazos/harnesses/operations")
        if not harness_dir.exists():
            pytest.skip("Operations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) >= 3  # site-assessor, procurement, installation-tracker

    def test_procurement_has_approval_gates(self) -> None:
        harness_dir = Path("tazos/harnesses/operations")
        if not harness_dir.exists():
            pytest.skip("Operations harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        proc = bundle.specialists.get("AGT-OPS-PROC")
        assert proc is not None
        # Procurement should have request_approval in allowed_tools
        tool_caps = [t.capability for t in proc.allowed_tools]
        assert "request_approval" in tool_caps


class TestCLICrossHarness:
    def test_cli_run_finance_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "run", "--harness", "finance", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        # Harness loads and runs (may exit non-zero if specialists incomplete)
        assert "finance" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_run_sales_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "run", "--harness", "sales", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "sales" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_run_operations_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "run", "--harness", "operations", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "operations" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_run_unknown_harness_fails(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "run", "--harness", "nonexistent", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()
