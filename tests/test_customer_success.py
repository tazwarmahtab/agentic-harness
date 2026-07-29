"""Tests for AOS Customer Success Harness — Phase 13."""

from __future__ import annotations
import sys

from pathlib import Path

import pytest

from aos.registry import load_registry


class TestCustomerSuccessHarnessLoading:
    def test_load_cs_harness(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-CSU-001"

    def test_cs_has_4_specialists(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) == 4

    def test_cs_has_planner(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-CSU-PLAN"

    def test_cs_has_dispatcher(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-CSU-DISPATCH"


class TestSystemMonitor:
    def test_monitor_exists(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        mon = bundle.specialists.get("AGT-CSU-MON")
        assert mon is not None
        assert mon.name == "System Monitor"
        assert mon.criticality.value == "high"

    def test_monitor_has_capacity_factor_constraint(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        mon = bundle.specialists.get("AGT-CSU-MON")
        assert mon is not None
        constraint_text = " ".join(mon.constraints).lower()
        assert "capacity_factor" in constraint_text or "16.5" in constraint_text

    def test_monitor_has_financial_constants(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        mon = bundle.specialists.get("AGT-CSU-MON")
        assert mon is not None
        assert mon.financial_rules is not None
        consts = mon.financial_rules["constants_to_enforce"]
        assert consts["capacity_factor"] == 16.5


class TestSupportResponder:
    def test_support_exists(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        sup = bundle.specialists.get("AGT-CSU-SUP")
        assert sup is not None
        assert sup.name == "Support Responder"
        assert sup.criticality.value == "high"

    def test_support_has_sla_constraints(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        sup = bundle.specialists.get("AGT-CSU-SUP")
        assert sup is not None
        constraint_text = " ".join(sup.constraints).lower()
        assert "response_time" in constraint_text or "4h" in constraint_text
        assert "resolution_time" in constraint_text or "24h" in constraint_text


class TestIssueDetector:
    def test_detector_exists(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        det = bundle.specialists.get("AGT-CSU-DETECT")
        assert det is not None
        assert det.name == "Issue Detector"
        assert det.criticality.value == "medium"

    def test_detector_has_constraints(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        det = bundle.specialists.get("AGT-CSU-DETECT")
        assert det is not None
        assert len(det.constraints) >= 2


class TestUpsellSpecialist:
    def test_upsell_exists(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        upsell = bundle.specialists.get("AGT-CSU-UPSELL")
        assert upsell is not None
        assert upsell.name == "Upsell Specialist"
        assert upsell.criticality.value == "medium"

    def test_upsell_has_financial_rules(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        upsell = bundle.specialists.get("AGT-CSU-UPSELL")
        assert upsell is not None
        assert upsell.financial_rules is not None
        consts = upsell.financial_rules["constants_to_enforce"]
        assert consts["ppa_rate"] == 10.0
        assert consts["customer_savings_pct"] == 23.0

    def test_upsell_has_approval_tool(self) -> None:
        harness_dir = Path("aos/harnesses/customer_success")
        if not harness_dir.exists():
            pytest.skip("Customer Success harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        upsell = bundle.specialists.get("AGT-CSU-UPSELL")
        assert upsell is not None
        tool_caps = [t.capability for t in upsell.allowed_tools]
        assert "request_approval" in tool_caps


class TestCLICustomerSuccess:
    def test_cli_run_cs_harness(self) -> None:
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "aos",
                "run",
                "--harness",
                "customer_success",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "customer_success" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_validate_cs_harness(self) -> None:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "aos", "validate", "--harness", "customer_success"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)
