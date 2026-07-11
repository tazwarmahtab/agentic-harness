"""Tests for Marketing Harness — full component stack."""

from pathlib import Path

import pytest

from aos.loader import (
    load_harness, load_agent, load_memory, load_tool_registry,
    load_evaluation, load_policy_collection, load_sop,
)

HARNESS_DIR = Path(__file__).resolve().parent.parent / "aos" / "harnesses" / "marketing"

@pytest.fixture
def harness_dir():
    if not HARNESS_DIR.exists():
        pytest.skip("Marketing harness directory not found")
    return HARNESS_DIR

class TestMarketingManifests:
    def test_harness_loads(self, harness_dir):
        h = load_harness(harness_dir / "harness.yml")
        assert h.id == "HAR-MKT-001"

    def test_four_specialists(self, harness_dir):
        specs = list((harness_dir / "specialists").glob("*.yml"))
        assert len(specs) == 4

    def test_content_creator_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "content-creator.yml")
        assert "CONTENT" in a.id

    def test_linkedin_strategist_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "linkedin-strategist.yml")
        assert "LINKEDIN" in a.id

    def test_seo_specialist_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "seo-specialist.yml")
        assert "SEO" in a.id

    def test_website_manager_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "website-manager.yml")
        assert "WEB" in a.id

class TestMarketingComponents:
    def test_memory_loads(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.id == "MEM-MKT-001"

    def test_tools_loads(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        assert t.id == "TOL-MKT-001"

    def test_approvals_loads(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.id == "POL-MKT-001"

    def test_evaluation_loads(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.id == "EVAL-MKT-001"

    def test_sop_loads(self, harness_dir):
        sop = load_sop(harness_dir / "sops" / "content-pipeline.yml")
        assert sop.id == "SOP-MKT-001"
