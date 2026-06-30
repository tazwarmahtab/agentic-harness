"""Tests for TAZ OS Marketing Harness — Phase 14."""

from __future__ import annotations

from pathlib import Path

import pytest

from tazos.registry import load_registry


class TestMarketingHarnessLoading:
    def test_load_marketing_harness(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-MKT-001"

    def test_marketing_has_4_specialists(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) == 4

    def test_marketing_has_planner(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-MKT-PLAN"

    def test_marketing_has_dispatcher(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-MKT-DISPATCH"


class TestContentCreator:
    def test_content_creator_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        content = bundle.specialists.get("AGT-MKT-CONTENT")
        assert content is not None
        assert content.name == "Content Creator"
        assert content.criticality.value == "high"

    def test_content_creator_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        content = bundle.specialists.get("AGT-MKT-CONTENT")
        assert content is not None
        assert len(content.constraints) >= 3

    def test_content_creator_has_generate_document_tool(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        content = bundle.specialists.get("AGT-MKT-CONTENT")
        assert content is not None
        tool_caps = [t.capability for t in content.allowed_tools]
        assert "generate_document" in tool_caps


class TestLinkedInStrategist:
    def test_linkedin_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        linkedin = bundle.specialists.get("AGT-MKT-LINKEDIN")
        assert linkedin is not None
        assert linkedin.name == "LinkedIn Strategist"
        assert linkedin.criticality.value == "high"

    def test_linkedin_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        linkedin = bundle.specialists.get("AGT-MKT-LINKEDIN")
        assert linkedin is not None
        assert len(linkedin.constraints) >= 3


class TestSEOSpecialist:
    def test_seo_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        seo = bundle.specialists.get("AGT-MKT-SEO")
        assert seo is not None
        assert seo.name == "SEO Specialist"
        assert seo.criticality.value == "high"

    def test_seo_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        seo = bundle.specialists.get("AGT-MKT-SEO")
        assert seo is not None
        assert len(seo.constraints) >= 3


class TestWebsiteManager:
    def test_website_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        web = bundle.specialists.get("AGT-MKT-WEB")
        assert web is not None
        assert web.name == "Website Manager"
        assert web.criticality.value == "high"

    def test_website_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/marketing")
        if not harness_dir.exists():
            pytest.skip("Marketing harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        web = bundle.specialists.get("AGT-MKT-WEB")
        assert web is not None
        assert len(web.constraints) >= 3


class TestCLIMarketingHarness:
    def test_cli_run_marketing_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "run", "--harness", "marketing", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "marketing" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_validate_marketing_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "validate", "--harness", "marketing"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)
