"""Tests for Operations Harness — full component stack."""

from pathlib import Path

import pytest

from aos.loader import (
    load_harness, load_agent, load_memory, load_tool_registry,
    load_evaluation, load_policy_collection, load_sop,
)

HARNESS_DIR = Path(__file__).resolve().parent.parent / "tazos" / "harnesses" / "operations"

@pytest.fixture
def harness_dir():
    if not HARNESS_DIR.exists():
        pytest.skip("Operations harness directory not found")
    return HARNESS_DIR

class TestOperationsManifests:
    def test_harness_loads(self, harness_dir):
        h = load_harness(harness_dir / "harness.yml")
        assert h.id == "HAR-OPS-001"

    def test_three_specialists(self, harness_dir):
        specs = list((harness_dir / "specialists").glob("*.yml"))
        assert len(specs) == 3

    def test_site_assessor_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "site-assessor.yml")
        assert "SITE" in a.id

    def test_procurement_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "procurement.yml")
        assert "PROC" in a.id

    def test_installation_tracker_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "installation-tracker.yml")
        assert "INST" in a.id

class TestOperationsComponents:
    def test_memory_loads(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.id == "MEM-OPS-001"

    def test_tools_loads(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        assert t.id == "TOL-OPS-001"

    def test_approvals_loads(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.id == "POL-OPS-001"

    def test_evaluation_loads(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.id == "EVAL-OPS-001"

    def test_sop_loads(self, harness_dir):
        sop = load_sop(harness_dir / "sops" / "installation-lifecycle.yml")
        assert sop.id == "SOP-OPS-001"
