"""Tests for Investor Relations Harness — full component stack."""

from pathlib import Path
import pytest
from aos.loader import (
    load_harness, load_agent, load_memory, load_tool_registry,
    load_evaluation, load_policy_collection, load_sop,
)

HARNESS_DIR = Path(__file__).resolve().parent.parent / "aos" / "harnesses" / "investor_relations"

@pytest.fixture
def harness_dir():
    if not HARNESS_DIR.exists():
        pytest.skip("Investor Relations harness directory not found")
    return HARNESS_DIR

class TestIRManifests:
    def test_harness_loads(self, harness_dir):
        h = load_harness(harness_dir / "harness.yml")
        assert h.id == "HAR-INV-001"

    def test_five_specialists(self, harness_dir):
        specs = list((harness_dir / "specialists").glob("*.yml"))
        assert len(specs) == 5

class TestIRComponents:
    def test_memory_loads(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.id == "MEM-INV-001"

    def test_tools_loads(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        assert t.id == "TOL-INV-001"

    def test_approvals_loads(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.id == "POL-INV-001"

    def test_evaluation_loads(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.id == "EVAL-INV-001"

    def test_sop_loads(self, harness_dir):
        sop = load_sop(harness_dir / "sops" / "investor-update-cycle.yml")
        assert sop.id == "SOP-INV-001"
