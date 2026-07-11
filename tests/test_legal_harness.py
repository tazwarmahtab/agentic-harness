"""Tests for TAZ OS Legal Harness — Phase 12."""

from __future__ import annotations
import sys

from pathlib import Path

import pytest

from aos.registry import load_registry


class TestLegalHarnessLoading:
    def test_load_legal_harness(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-LEG-001"

    def test_legal_has_5_specialists(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) == 5

    def test_legal_has_planner(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-LEG-PLAN"

    def test_legal_has_dispatcher(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-LEG-DISPATCH"


class TestNDASpecialist:
    def test_nda_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        nda = bundle.specialists.get("AGT-LEG-NDA")
        assert nda is not None
        assert nda.name == "NDA Specialist"
        assert nda.criticality.value == "high"

    def test_nda_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        nda = bundle.specialists.get("AGT-LEG-NDA")
        assert nda is not None
        assert len(nda.constraints) >= 3
        constraint_text = " ".join(nda.constraints).lower()
        assert "approval" in constraint_text

    def test_nda_has_approval_tool(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        nda = bundle.specialists.get("AGT-LEG-NDA")
        assert nda is not None
        tool_caps = [t.capability for t in nda.allowed_tools]
        assert "request_approval" in tool_caps


class TestLOISpecialist:
    def test_loi_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        loi = bundle.specialists.get("AGT-LEG-LOI")
        assert loi is not None
        assert loi.name == "LOI Specialist"

    def test_loi_has_financial_rules(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        loi = bundle.specialists.get("AGT-LEG-LOI")
        assert loi is not None
        assert loi.financial_rules is not None
        assert "hard_fails" in loi.financial_rules
        assert len(loi.financial_rules["hard_fails"]) >= 2

    def test_loi_financial_constants_match_ground_truth(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        loi = bundle.specialists.get("AGT-LEG-LOI")
        assert loi is not None
        consts = loi.financial_rules["constants_to_enforce"]
        assert consts["ppa_rate"] == 10.0
        assert consts["true_variable_rate"] == 12.98
        assert consts["blended_rate"] == 14.81
        assert consts["customer_savings_pct"] == 23.0


class TestPPASpecialist:
    def test_ppa_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        ppa = bundle.specialists.get("AGT-LEG-PPA")
        assert ppa is not None
        assert ppa.name == "PPA Specialist"
        assert ppa.criticality.value == "critical"

    def test_ppa_has_financial_rules(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        ppa = bundle.specialists.get("AGT-LEG-PPA")
        assert ppa is not None
        assert ppa.financial_rules is not None
        assert "hard_fails" in ppa.financial_rules
        assert len(ppa.financial_rules["hard_fails"]) >= 3

    def test_ppa_constants_include_escalation(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        ppa = bundle.specialists.get("AGT-LEG-PPA")
        assert ppa is not None
        consts = ppa.financial_rules["constants_to_enforce"]
        assert consts["ppa_rate"] == 10.0
        assert consts["escalation_pct"] == 3.0
        assert consts["nem_export_rate"] == 6.4523


class TestComplianceSpecialist:
    def test_compliance_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        comp = bundle.specialists.get("AGT-LEG-COMP")
        assert comp is not None
        assert comp.name == "Compliance Specialist"

    def test_compliance_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        comp = bundle.specialists.get("AGT-LEG-COMP")
        assert comp is not None
        assert len(comp.constraints) >= 3
        constraint_text = " ".join(comp.constraints).lower()
        assert "deadline" in constraint_text


class TestContractReviewer:
    def test_reviewer_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        rev = bundle.specialists.get("AGT-LEG-REV")
        assert rev is not None
        assert rev.name == "Contract Reviewer"

    def test_reviewer_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/legal")
        if not harness_dir.exists():
            pytest.skip("Legal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        rev = bundle.specialists.get("AGT-LEG-REV")
        assert rev is not None
        constraint_text = " ".join(rev.constraints).lower()
        assert "approval" in constraint_text
        assert "liability" in constraint_text


class TestCLILegalHarness:
    def test_cli_run_legal_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "run", "--harness", "legal", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "legal" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_validate_legal_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "validate", "--harness", "legal"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        # Should not crash
        assert result.returncode in (0, 1)
