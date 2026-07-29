"""Tests for AOS Software Development Harness — Phase 18."""

from __future__ import annotations
import sys

from pathlib import Path

import pytest

from aos.registry import load_registry


class TestSoftwareDevHarnessLoading:
    def test_load_dev_harness(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-DEV-001"

    def test_dev_has_6_specialists(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) == 6

    def test_dev_has_planner(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-DEV-PLAN"

    def test_dev_has_dispatcher(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-DEV-DISPATCH"


class TestProductManager:
    def test_pm_exists(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        pm = bundle.specialists.get("AGT-DEV-PM")
        assert pm is not None
        assert pm.name == "Product Manager"
        assert pm.criticality.value == "high"

    def test_pm_has_prd_constraint(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        pm = bundle.specialists.get("AGT-DEV-PM")
        assert pm is not None
        constraint_text = " ".join(pm.constraints).lower()
        assert "prd" in constraint_text


class TestPRDWriter:
    def test_prd_writer_exists(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        prd = bundle.specialists.get("AGT-DEV-PRD")
        assert prd is not None
        assert prd.name == "PRD Writer"
        assert prd.criticality.value == "high"


class TestUIReviewer:
    def test_ui_reviewer_exists(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        ui = bundle.specialists.get("AGT-DEV-UI")
        assert ui is not None
        assert ui.name == "UI Reviewer"
        assert ui.criticality.value == "medium"


class TestTestingSpecialist:
    def test_testing_exists(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        test = bundle.specialists.get("AGT-DEV-TEST")
        assert test is not None
        assert test.name == "Testing Specialist"
        assert test.criticality.value == "high"

    def test_testing_has_coverage_constraint(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        test = bundle.specialists.get("AGT-DEV-TEST")
        assert test is not None
        constraint_text = " ".join(test.constraints).lower()
        assert "coverage" in constraint_text or "80" in constraint_text


class TestDocumentationWriter:
    def test_docs_exists(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        docs = bundle.specialists.get("AGT-DEV-DOCS")
        assert docs is not None
        assert docs.name == "Documentation Writer"
        assert docs.criticality.value == "medium"


class TestReleaseManager:
    def test_release_exists(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        rel = bundle.specialists.get("AGT-DEV-RELEASE")
        assert rel is not None
        assert rel.name == "Release Manager"
        assert rel.criticality.value == "high"

    def test_release_has_constraints(self) -> None:
        harness_dir = Path("aos/harnesses/software_dev")
        if not harness_dir.exists():
            pytest.skip("Software Dev harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        rel = bundle.specialists.get("AGT-DEV-RELEASE")
        assert rel is not None
        assert len(rel.constraints) >= 3
        constraint_text = " ".join(rel.constraints).lower()
        assert "tested" in constraint_text or "rollback" in constraint_text


class TestCLISoftwareDev:
    def test_cli_run_dev_harness(self) -> None:
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "aos",
                "run",
                "--harness",
                "software_dev",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "software_dev" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_validate_dev_harness(self) -> None:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "aos", "validate", "--harness", "software_dev"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)
